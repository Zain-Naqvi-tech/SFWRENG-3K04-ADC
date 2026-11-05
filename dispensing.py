"""
DISPENSING MODULE

RESPONSIBILITY: Check dispense requests against authorized orders and coordinate the correct drawer.
SECRET: The dispensing rules, and how orders and open requests are tracked.
ANTICIPATED CHANGE: A dispensing rule changes (e.g. a dose tolerance). Only __validateRequest changes.
EXPORTED OPERATIONS: requestDispense, completeDispense, cancelDispense, releaseForOverride, getUserOrders
USES: Authenticator, Inventory Manager, Drawer, Operational Mode, Fault Monitor, EventLogger,
      Transmission, Storage, Clock.

ASSUMPTION: drawers hold pre-packaged doses, so one dispense removes exactly one unit.
"""


class Dispensing:
    """STATE INVARIANT: an order is dispensed at most once and never after it expires, and a drawer
    is only unlocked for an open request."""

    def __init__(self, auth, inventory, drawer, mode, faults, logger, transmission, storage, clock):
        self.__auth = auth
        self.__inventory = inventory
        self.__drawer = drawer
        self.__mode = mode
        self.__faults = faults
        self.__logger = logger
        self.__transmission = transmission
        self.__storage = storage
        self.__clock = clock
        self.__requests = {}        # request ID -> open or closed request
        self.__requestHistory = []  # every dispense request since the last restart, allowed or refused
        self.__nextID = 1
        self.__orders = []          # authorized orders (m_dispenseAuthorization)
        saved = self.__storage.load("orders")
        if saved != None and saved != "corrupted":
            self.__orders = saved   # saved, so a restart cannot repeat a dose
        self.__receiveNewOrders()

    # ================ PUBLIC INTERFACE ================

    def requestDispense(self, sessionId, patientID, drugID, dose):
        """
        This is authorizingDispense() from our precise specification.
        PRE:  none. Everything is checked here (FR-DSP-01, FR-DSP-02, NFR-AUT-01).
        POST: {"verdict": "allowed", "requestID": id, "drawer": id} - only that drawer is unlocked.
              {"verdict": "rejected", "reason": text} - every drawer stays locked, and the attempt is logged.
        """
        self.__receiveNewOrders()
        user = self.__userOf(sessionId)
        result = self.__checkAndOpen(sessionId, user, patientID, drugID, dose)
        reason = ""
        if result["verdict"] == "rejected":
            reason = result["reason"]
        self.__requestHistory.append({"user": user, "patientID": patientID, "drugID": drugID, "dose": dose,
                                      "verdict": result["verdict"], "reason": reason})
        return result

    def getUserOrders(self, sessionId):
        """
        PRE:  none.
        POST: {"orders": [...], "requests": [...]} for a user who may dispense. Nothing is dispensed.
              Each order is {"orderID", "patientID", "drugID", "dose", "expiry", "validity"}, where
              validity is "valid" or why it cannot be dispensed.
              Each request is one this user made since the last restart, valid or not:
              {"patientID", "drugID", "dose", "verdict", "reason"}.
              "denied" - the user may not dispense.
        """
        self.__receiveNewOrders()
        if self.__auth.isAuthorized(sessionId, "DISPENSE") == False:
            return "denied"
        user = self.__userOf(sessionId)
        orders = []
        for order in self.__orders:
            orders.append({"orderID": order["orderID"], "patientID": order["patientID"], "drugID": order["drugID"],
                           "dose": order["dose"], "expiry": order["expiry"], "validity": self.__orderValidity(order)})
        requests = []
        for request in self.__requestHistory:
            if request["user"] == user:
                requests.append({"patientID": request["patientID"], "drugID": request["drugID"], "dose": request["dose"],
                                 "verdict": request["verdict"], "reason": request["reason"]})
        return {"orders": orders, "requests": requests}

    def completeDispense(self, requestID):
        """
        PRE:  requestDispense or releaseForOverride returned this request ID.
        POST: "completed" - the sensor confirmed one unit left and the drawer locked. Inventory is updated.
              "failed"    - anything else. Never reported as a success, and a fault is raised if unsafe.
              "rejected"  - there is no open request with this ID. Nothing changes.
        """
        if requestID not in self.__requests or self.__requests[requestID]["status"] != "OPEN":
            return "rejected"
        request = self.__requests[requestID]
        request["status"] = "CLOSED"
        drawerID = request["drawer"]

        # Step 1: how many were really taken? Keep the inventory accurate either way.
        count = self.__drawer.getDrawerContents(drawerID)
        taken = None
        if count != "SensorFailure":
            taken = request["startCount"] - count
            if taken > 0:
                self.__inventory.removeMedication(request["drugID"], taken)
            if request["order"] != None:
                if taken > 0:
                    self.__setOrderStatus(request["order"], "DISPENSED")    # no second dose
                else:
                    self.__setOrderStatus(request["order"], "ACTIVE")

        # Step 2: lock it. A failed lock stops all further dispensing (NFR-FD-02).
        locked = self.__drawer.lockDrawer(drawerID)
        if locked == "DrawerAlreadyOpen":
            self.__faults.reportFault("DRAWER_NOT_SECURED", drawerID, "drawer not closed after dispensing")
        elif locked != "locked":
            self.__faults.reportFault("LOCK_FAILURE", drawerID, "drawer did not lock after dispensing")

        # Step 3: only report success if it really happened.
        if locked != "locked" or taken != 1:
            self.__logger.logEvent("DISPENSE_FAILED", request["user"], request["drugID"])
            return "failed"
        self.__logger.logEvent("DISPENSE_COMPLETED", request["user"], requestID + " " + request["drugID"],
                               {"drawer": drawerID, "drug": request["drugID"], "amount": 1})
        return "completed"

    def cancelDispense(self, requestID):
        """
        PRE:  none.
        POST: "cancelled" - the drawer is locked and the order is available again.
              "rejected"  - no open request with this ID, or something was already taken.
        """
        if requestID not in self.__requests or self.__requests[requestID]["status"] != "OPEN":
            return "rejected"
        request = self.__requests[requestID]
        if self.__drawer.getDrawerContents(request["drawer"]) != request["startCount"]:
            return "rejected"
        request["status"] = "CLOSED"
        if request["order"] != None:
            self.__setOrderStatus(request["order"], "ACTIVE")
        if self.__drawer.lockDrawer(request["drawer"]) != "locked":
            self.__faults.reportFault("DRAWER_NOT_SECURED", request["drawer"], "drawer not secured after cancel")
        self.__logger.logEvent("DISPENSE_CANCELLED", request["user"], requestID)
        return "cancelled"

    def releaseForOverride(self, sessionId, drugID):
        """
        PRE:  only Override calls this, after its own checks.
        POST: same result as requestDispense. Authorization, mode, expiry and drawer faults are still
              checked here (D1 decisions 3 and 4). A repeat returns the same open request, so a
              duplicate override gives no second permission.
        """
        user = self.__userOf(sessionId)
        if self.__auth.isAuthorized(sessionId, "OVERRIDE") == False:
            return self.__reject(user, drugID, "Access denied: you may not override.")
        if self.__mode.checkOperationAllowed("OVERRIDE") == False:
            return self.__reject(user, drugID, "Override is not permitted in the current mode.")
        for requestID in self.__requests:
            request = self.__requests[requestID]
            if request["status"] == "OPEN" and request["session"] == sessionId and request["drugID"] == drugID:
                return {"verdict": "allowed", "requestID": requestID, "drawer": request["drawer"]}
        problem = self.__stockProblem(drugID)
        if problem != "":
            return self.__reject(user, drugID, problem)
        drawerID = self.__inventory.checkDispensable(drugID)["drawer"]
        for fault in self.__faults.getActiveFaults():
            if fault["component"] == drawerID:
                return self.__reject(user, drugID, "Drawer " + drawerID + " has an active fault.")
        return self.__openDrawer(sessionId, user, drugID, None)

    # ================ PRIVATE (the secret: the dispensing rules) ================

    def __checkAndOpen(self, sessionId, user, patientID, drugID, dose):
        # Check 1: is this person allowed? (D1 decision 4: two checks before a drawer opens)
        if self.__auth.isAuthorized(sessionId, "DISPENSE") == False:
            return self.__reject(user, drugID, "Access denied: you may not dispense medication.")
        if self.__mode.checkOperationAllowed("DISPENSE") == False:
            return self.__reject(user, drugID, "Dispensing is not permitted in the current mode.")
        # Check 2: is this request allowed?
        result = self.__validateRequest(patientID, drugID, dose)
        if result["verdict"] == "invalid":
            return self.__reject(user, drugID, result["reason"])
        return self.__openDrawer(sessionId, user, drugID, result["order"])

    def __validateRequest(self, patientID, drugID, dose):
        # Private, so a request can never be validated without the authorization and mode checks.
        # Returns {"verdict": "valid", "order": order} or {"verdict": "invalid", "reason": text}.
        problem = self.__stockProblem(drugID)
        if problem != "":
            return {"verdict": "invalid", "reason": problem}
        if dose == None or dose <= 0:
            return {"verdict": "invalid", "reason": "Requested dose is invalid."}

        foundOrder = False
        expiredOrder = None
        for order in self.__orders:
            if order["patientID"] == patientID and order["drugID"] == drugID:
                foundOrder = True
                if order["status"] == "ACTIVE":
                    if self.__orderExpired(order):
                        expiredOrder = order
                    elif order["dose"] == dose:
                        return {"verdict": "valid", "order": order}
                    else:
                        return {"verdict": "invalid", "reason": "ERROR: Dose Mismatch. Requested " + str(dose)
                                + " mg does not match the authorized " + str(order["dose"]) + " mg. Access Denied."}
        if expiredOrder != None:
            return {"verdict": "invalid", "reason": "This order expired on " + expiredOrder["expiry"] + ". Access Denied."}
        if foundOrder:
            return {"verdict": "invalid", "reason": "This order has already been dispensed."}
        return {"verdict": "invalid", "reason": "Access Denied: no authorized order for this patient and medication."}

    def __orderExpired(self, order):
        # An order may be used up to and including its expiry date.
        return order["expiry"] < self.__clock.today()

    def __orderValidity(self, order):
        # Returns "valid", or why this order cannot be dispensed right now.
        if order["status"] == "DISPENSED":
            return "already dispensed"
        if order["status"] == "IN_PROGRESS":
            return "in progress"
        if self.__orderExpired(order):
            return "order expired"
        verdict = self.__inventory.checkDispensable(order["drugID"])["verdict"]
        if verdict == "available":
            return "valid"
        if verdict == "expired":
            return "medication expired"
        if verdict == "out_of_stock":
            return "out of stock"
        if verdict == "MedicationNotFound":
            return "medication not in cabinet"
        if verdict == "location_unconfirmed":
            return "compartment unconfirmed"
        return "inventory unavailable"

    def __stockProblem(self, drugID):
        # Returns what stops this medication being dispensed, or "" if nothing does.
        result = self.__inventory.checkDispensable(drugID)
        verdict = result["verdict"]
        if verdict == "available":
            return ""
        if verdict == "expired":
            return "Dispense Failed: batch " + result["batch"] + " is expired. It expired " + result["expiry"] + ". Please restock with a valid batch."
        if verdict == "out_of_stock":
            return "Insufficient quantity of " + drugID + "."
        if verdict == "MedicationNotFound":
            return "Medication " + drugID + " is not in this cabinet."
        if verdict == "location_unconfirmed":
            return "Compartment for " + drugID + " is unconfirmed."
        return "Inventory information is unavailable."

    def __openDrawer(self, sessionId, user, drugID, order):
        drawerID = self.__inventory.checkDispensable(drugID)["drawer"]
        startCount = self.__drawer.getDrawerContents(drawerID)      # remembered, to confirm removal later
        result = self.__drawer.unlockDrawer(drawerID, True)
        if result != "unlocked":
            self.__faults.reportFault("LOCK_FAILURE", drawerID, result)
            return self.__reject(user, drugID, "Drawer " + drawerID + " could not be opened.")
        requestID = "R-" + str(self.__nextID)
        self.__nextID = self.__nextID + 1
        self.__requests[requestID] = {"session": sessionId, "user": user, "drugID": drugID, "order": order,
                                      "drawer": drawerID, "startCount": startCount, "status": "OPEN"}
        if order != None:
            self.__setOrderStatus(order, "IN_PROGRESS")
        self.__logger.logEvent("DRAWER_UNLOCKED", user, requestID + " " + drugID + " " + drawerID)
        return {"verdict": "allowed", "requestID": requestID, "drawer": drawerID}

    def __receiveNewOrders(self):
        # Authorized orders come from the Monitoring System, through Transmission.
        message = self.__transmission.receiveMessage()
        while message != "no_message":
            if message == "rejected":
                self.__logger.logEvent("MESSAGE_REJECTED", "SYSTEM", "invalid key")
            elif self.__hasOrder(message["orderID"]) == False:      # ignore duplicates
                self.__orders.append({"orderID": message["orderID"], "patientID": message["patientID"],
                                      "drugID": message["drugID"], "dose": message["dose"],
                                      "expiry": message["expiry"], "status": "ACTIVE"})
                self.__storage.save("orders", self.__orders)
                self.__logger.logEvent("ORDER_RECEIVED", "SYSTEM", message["orderID"])
            message = self.__transmission.receiveMessage()

    def __hasOrder(self, orderID):
        for order in self.__orders:
            if order["orderID"] == orderID:
                return True
        return False

    def __setOrderStatus(self, order, status):
        order["status"] = status
        self.__storage.save("orders", self.__orders)

    def __userOf(self, sessionId):
        identity = self.__auth.getUserIdentity(sessionId)
        if identity == "rejected":
            return "NO_SESSION"
        return identity["id"]

    def __reject(self, user, drugID, reason):
        self.__logger.logEvent("DISPENSE_REJECTED", user, drugID + ": " + reason)
        return {"verdict": "rejected", "reason": reason}
