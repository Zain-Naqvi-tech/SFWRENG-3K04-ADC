"""
INVENTORY MANAGER MODULE

RESPONSIBILITY: Keep accurate quantities, batches, expiry dates and drawer locations; run restocking.
SECRET: The inventory data structure, and how batches are tracked and chosen. No other module ever
        sees the structure: callers only get flat rows or a verdict.
ANTICIPATED CHANGE: The pharmacist changes the inventory structure. Only this file changes.
EXPORTED OPERATIONS: getInventory, checkDispensable, removeMedication, startReplenish, finishReplenish
USES: Authenticator, Operational Mode, Drawer, Fault Monitor, EventLogger, Storage, Clock.
"""


class InventoryManager:
    """STATE INVARIANT: __items is valid saved data with no negative quantities, or None if it could
    not be restored, in which case no stock is ever reported and the cabinet is in the safe state."""

    # What pharmacy loaded when the cabinet was installed. Batch 1050 is the expired one from US-INV-02.
    __STARTING_STOCK = [
        {"drugID": "LORA", "name": "Lorazepam", "drawer": "D1", "batch": "1010", "quantity": 20, "expiry": "2099-01-01"},
        {"drugID": "ACET", "name": "Acetaminophen", "drawer": "D2", "batch": "1020", "quantity": 30, "expiry": "2099-01-01"},
        {"drugID": "AMOX", "name": "Amoxicillin", "drawer": "D3", "batch": "1030", "quantity": 15, "expiry": "2099-01-01"},
        {"drugID": "MORP", "name": "Morphine", "drawer": "D4", "batch": "1050", "quantity": 5, "expiry": "2020-01-01"},
    ]

    def __init__(self, auth, mode, drawer, faults, logger, storage, clock):
        self.__auth = auth
        self.__mode = mode
        self.__drawer = drawer
        self.__faults = faults
        self.__logger = logger
        self.__storage = storage
        self.__clock = clock
        self.__items = None         # the secret: drug ID -> {"name", "drawer", "batches": [...]}
        self.__restock = None       # the restock in progress, if any
        self.__restoreInventory()   # the constructor establishes the invariant

    def __del__(self):
        print("[InventoryManager] shut down")

    # ================ PUBLIC INTERFACE ================

    def getInventory(self, sessionId):
        """
        PRE:  none.
        POST: a list of rows, one per batch (FR-INV-01):
              {"drugID", "name", "drawer", "batch", "quantity", "expiry", "status"}.
              "denied" - the user may not view inventory.
              "error"  - inventory information is unavailable.
        """
        if self.__auth.isAuthorized(sessionId, "VIEW_INVENTORY") == False:
            return "denied"
        if self.__items == None:
            return "error"
        rows = []
        for drugID in self.__items:
            medication = self.__items[drugID]
            for batch in medication["batches"]:
                rows.append({"drugID": drugID, "name": medication["name"], "drawer": medication["drawer"],
                             "batch": batch["batch"], "quantity": batch["quantity"], "expiry": batch["expiry"],
                             "status": self.__checkExpiry(batch)})
        return rows

    def checkDispensable(self, drugID):
        """
        PRE:  none.
        POST: {"verdict": "available", "drawer": id}                  - a valid unit can be dispensed.
              {"verdict": "expired", "batch": id, "expiry": date}     - only expired stock remains (FR-DSP-02).
              {"verdict": ...} "out_of_stock", "MedicationNotFound", "location_unconfirmed" or "error".
              Nothing changes.
        """
        if self.__items == None:
            return {"verdict": "error"}     # never dispense using unverified inventory
        if drugID not in self.__items:
            return {"verdict": "MedicationNotFound"}
        batch = self.__getNextBatch(drugID)
        if batch == None:
            return {"verdict": "out_of_stock"}
        if self.__checkExpiry(batch) == "expired":
            return {"verdict": "expired", "batch": batch["batch"], "expiry": batch["expiry"]}
        if self.__items[drugID]["drawer"] == "":
            return {"verdict": "location_unconfirmed"}
        return {"verdict": "available", "drawer": self.__items[drugID]["drawer"]}

    def removeMedication(self, drugID, amount):
        """
        PRE:  the removal was physically confirmed by the caller.
        POST: "allowed"  - the quantity is reduced, saved and logged.
              "rejected" - unknown drug, invalid amount, or not enough stock. Nothing changes.
        """
        if self.__items == None or drugID not in self.__items:
            return "rejected"
        if amount <= 0 or amount > self.__getQuantity(drugID):
            return "rejected"
        removed = 0
        while removed < amount:
            batch = self.__getNextBatch(drugID)
            batch["quantity"] = batch["quantity"] - 1
            removed = removed + 1
        self.__saveChange(drugID, "removed " + str(amount))
        return "allowed"

    def startReplenish(self, sessionId, drugID, batchID, amount, expiryDate):
        """
        PRE:  none.
        POST: {"verdict": "allowed", "drawer": id}     - authorized and valid. The drawer is unlocked.
              {"verdict": "rejected", "reason": text}  - otherwise. The drawer stays locked (NFR-AUT-01).
        """
        if self.__auth.isAuthorized(sessionId, "REPLENISH") == False:
            return {"verdict": "rejected", "reason": "Access denied: you may not restock."}
        if self.__mode.checkOperationAllowed("REPLENISH") == False:
            return {"verdict": "rejected", "reason": "Restocking is not permitted in the current mode."}
        problem = self.__checkRestock(drugID, batchID, amount, expiryDate)
        if problem != "":
            return {"verdict": "rejected", "reason": problem}

        drawerID = self.__items[drugID]["drawer"]
        startCount = self.__drawer.getDrawerContents(drawerID)
        result = self.__drawer.unlockDrawer(drawerID, True)
        if result != "unlocked":
            self.__faults.reportFault("LOCK_FAILURE", drawerID, result)
            return {"verdict": "rejected", "reason": "Drawer could not be opened."}
        self.__restock = {"session": sessionId, "drugID": drugID, "batchID": batchID, "amount": amount,
                          "expiry": expiryDate, "drawer": drawerID, "startCount": startCount}
        return {"verdict": "allowed", "drawer": drawerID}

    def finishReplenish(self, sessionId):
        """
        PRE:  startReplenish returned "allowed" for this session.
        POST: "success"  - the drawer locked and the sensor confirmed the amount. Inventory is saved and logged.
              "failed"   - the drawer did not lock, or the sensor disagrees. Inventory is unchanged.
              "rejected" - no restock is open for this session. Nothing changes.
        """
        if self.__restock == None or self.__restock["session"] != sessionId:
            return "rejected"
        job = self.__restock
        self.__restock = None
        locked = self.__drawer.lockDrawer(job["drawer"])
        if locked != "locked":
            self.__faults.reportFault("DRAWER_NOT_SECURED", job["drawer"], locked)
            return "failed"
        count = self.__drawer.getDrawerContents(job["drawer"])
        if count != job["startCount"] + job["amount"]:
            return "failed"
        self.__addMedication(job["drugID"], job["batchID"], job["amount"], job["expiry"])
        return "success"

    # ================ PRIVATE (the secret: the data structure and how batches are chosen) ================

    def __restoreInventory(self):
        # Runs once, from the constructor (NFR-FD-03, US-FD-03).
        saved = self.__storage.load("inventory")
        if saved == "corrupted":
            # __items stays None, so dispensing cannot use unverified inventory.
            self.__logger.logEvent("INVENTORY_RECOVERY_FAILED", "SYSTEM", "")
            self.__faults.reportFault("INVENTORY_CORRUPT", "INVENTORY", "saved inventory could not be read")
        elif saved != None:
            self.__items = saved
        else:
            self.__items = {}
            for row in self.__STARTING_STOCK:
                if row["drugID"] not in self.__items:
                    self.__items[row["drugID"]] = {"name": row["name"], "drawer": row["drawer"], "batches": []}
                self.__items[row["drugID"]]["batches"].append(
                    {"batch": row["batch"], "quantity": row["quantity"], "expiry": row["expiry"]})
            self.__storage.save("inventory", self.__items)

    def __checkRestock(self, drugID, batchID, amount, expiryDate):
        # Returns what is wrong with this restock, or "" if nothing is.
        if self.__items == None:
            return "Inventory information is unavailable."
        if drugID not in self.__items or batchID == "":
            return "Unknown medication or batch."
        existing = self.__findBatch(batchID)
        if existing != None and existing not in self.__items[drugID]["batches"]:
            return "Unknown medication or batch."       # that batch belongs to another drug
        if amount == None or amount <= 0:
            return "Amount must be a positive whole number."
        if len(expiryDate) != 10 or expiryDate[4] != "-" or expiryDate[7] != "-":
            return "Expiry date must be YYYY-MM-DD."
        return ""

    def __addMedication(self, drugID, batchID, amount, expiryDate):
        # Private, so stock can only be added after authorization and sensor confirmation.
        batch = self.__findBatch(batchID)
        if batch == None:
            self.__items[drugID]["batches"].append({"batch": batchID, "quantity": amount, "expiry": expiryDate})
        else:
            batch["quantity"] = batch["quantity"] + amount
        self.__saveChange(drugID, "added " + str(amount))

    def __getQuantity(self, drugID):
        total = 0
        for batch in self.__items[drugID]["batches"]:
            total = total + batch["quantity"]
        return total

    def __getNextBatch(self, drugID):
        # The unexpired batch that expires first. If only expired stock is left, an expired batch.
        best = None
        expired = None
        for batch in self.__items[drugID]["batches"]:
            if batch["quantity"] > 0:
                if self.__checkExpiry(batch) == "expired":
                    expired = batch
                elif best == None or batch["expiry"] < best["expiry"]:
                    best = batch
        if best != None:
            return best
        return expired

    def __checkExpiry(self, batch):
        # Medication may be used up to and including its expiry date.
        if self.__clock.today() <= batch["expiry"]:
            return "not_expired"
        return "expired"

    def __findBatch(self, batchID):
        for drugID in self.__items:
            for batch in self.__items[drugID]["batches"]:
                if batch["batch"] == batchID:
                    return batch
        return None

    def __saveChange(self, drugID, change):
        self.__storage.save("inventory", self.__items)
        self.__logger.logEvent("INVENTORY_CHANGED", "SYSTEM", drugID + " " + change + ", now " + str(self.__getQuantity(drugID)))
