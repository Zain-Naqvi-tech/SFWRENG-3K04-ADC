"""
MAIN (helper file, NOT an ADC module)

Run the demo with: python main.py

This file does two things:
  1. startSystem() creates every module and connects them.
  2. main() runs the while loop that uses them.

It only ever calls public operations. It holds no secrets: PINs, drawer wiring, fault types and
data formats all live inside the module that owns them.
"""
from actuator import Actuator
from authenticator import Authenticator
from dispensing import Dispensing
from display import Display
from drawer import Drawer
from event_logger import EventLogger
from fault_monitor import FaultMonitor
from inventory_manager import InventoryManager
from operational_mode import OperationalMode
from override import Override
from sensor import Sensor
from simulation import Clock, Hardware, MonitoringSystem
from storage import Storage
from transmission import Transmission

NUMBER_OF_DRAWERS = 4


def startSystem(hardware, monitoring, clock, storage):
    # This is the USES hierarchy. Each module only receives modules created before it,
    # so nothing can depend on itself in a circle.
    actuator = Actuator(hardware)
    sensor = Sensor(hardware)
    drawer = Drawer(actuator, sensor, NUMBER_OF_DRAWERS)
    transmission = Transmission(monitoring, clock, storage)
    logger = EventLogger(transmission, clock, storage)
    auth = Authenticator(logger, clock)
    mode = OperationalMode(auth, logger)
    faults = FaultMonitor(auth, drawer, sensor, mode, logger, transmission, storage, clock)
    inventory = InventoryManager(auth, mode, drawer, faults, logger, storage, clock)
    dispensing = Dispensing(auth, inventory, drawer, mode, faults, logger, transmission, storage)
    override = Override(auth, dispensing, logger)
    logger.verifyLogIntegrity()

    # The while loop only gets the modules it needs. Actuator and Sensor are not in here:
    # the loop cannot reach them, only Drawer and Fault Monitor can.
    adc = {
        "drawer": drawer,
        "transmission": transmission,
        "logger": logger,
        "auth": auth,
        "mode": mode,
        "faults": faults,
        "inventory": inventory,
        "dispensing": dispensing,
        "override": override,
    }
    return adc


def collectDose(adc, hardware, screen, request):
    # The drawer is unlocked. What does the person physically do?
    drawerID = request["drawer"]
    options = {
        "1": "Take dose and close",
        "2": "Take dose, leave drawer open",
        "3": "Cancel",
        "4": "Close without taking",
        "5": "Take dose and close, but the lock jams",
    }
    action = screen.getChoice("Drawer " + drawerID + " is unlocked:", options)
    if action == "3":
        screen.showMessage("Cancel: " + adc["dispensing"].cancelDispense(request["requestID"]))
        return
    if action == "1" or action == "2" or action == "5":
        hardware.openDrawer(drawerID)
        hardware.changeItems(drawerID, -1)
    if action != "2":
        hardware.closeDrawer(drawerID)
    if action == "5":
        hardware.jamLock(drawerID)

    if adc["dispensing"].completeDispense(request["requestID"]) == "completed":
        screen.showMessage("Dispense complete. Drawer locked and inventory updated.")
    else:
        screen.showAlert("Dispense NOT confirmed.")


def main():
    clock = Clock()
    storage = Storage()
    storage.reset()                 # every demo starts from the same state
    hardware = Hardware(NUMBER_OF_DRAWERS)
    monitoring = MonitoringSystem()
    screen = Display()
    adc = startSystem(hardware, monitoring, clock, storage)
    session = None
    running = True

    while running:
        # ---------- The monitoring cycle: check the hardware, retry unsent messages ----------
        # FR-ALM-01, NFR-COM-01: a fault is found here and its alarm is sent right away.
        adc["mode"].completeStartup(adc["faults"].checkHardwareStatus())
        if adc["transmission"].synchronizePendingMessages() == "partial_success":
            adc["logger"].logEvent("SYNC_FAILED", "SYSTEM", "will retry")

        # ---------- Show the current state (US-STAT-01) ----------
        identity = adc["auth"].getUserIdentity(session)
        user = "not logged in"
        if identity != "rejected":
            user = identity["name"] + " (" + identity["role"] + ")"
        elif session != None:
            screen.showAlert("Session ended after 3 minutes of inactivity.")    # NFR-AUT-02
            session = None
        drawers = {}
        for drawerID in adc["drawer"].listDrawers():
            drawers[drawerID] = adc["drawer"].getDrawerStatus(drawerID)
        screen.showStatus(adc["mode"].getCurrentMode(), adc["transmission"].checkConnection(),
                          adc["transmission"].getPendingCount(), user, drawers, adc["faults"].getActiveFaults())
        screen.showMenu()
        choice = screen.getInput("> ")

        if choice == "0":
            running = False

        # ---------- What a user does at the cabinet ----------

        elif choice == "1":         # Log in (FR-AUTH-01)
            adc["auth"].logout(session)
            result = adc["auth"].authenticate(screen.promptCredentials())
            session = result["sessionId"]
            if result["verdict"] == "authenticated":
                screen.showMessage("Welcome.")
            elif result["verdict"] == "locked":
                screen.showAlert("Account Temporarily Locked - Invalid Credentials. An administrator can unlock it.")
            else:
                screen.showAlert("Invalid credentials.")

        elif choice == "2":         # Log out
            adc["auth"].logout(session)
            session = None

        elif choice == "3":         # Dispense (Scenario 1: FR-DSP-01, FR-DSP-02)
            patientID = screen.getInput("Patient ID: ")
            drugID = screen.getInput("Drug ID: ")
            dose = screen.getNumber("Dose (mg): ")
            result = adc["dispensing"].requestDispense(session, patientID, drugID, dose)
            if result["verdict"] == "rejected":
                screen.showAlert(result["reason"])
            else:
                screen.showMessage("Dispensing " + drugID + " for " + patientID + ": drawer " + result["drawer"] + " is unlocked.")
                collectDose(adc, hardware, screen, result)

        elif choice == "4":         # Restock (Scenario 2: US-INV-01)
            drugID = screen.getInput("Drug ID: ")
            batchID = screen.getInput("Batch ID: ")
            expiry = screen.getInput("Expiry (YYYY-MM-DD): ")
            amount = screen.getNumber("Amount: ")
            result = adc["inventory"].startReplenish(session, drugID, batchID, amount, expiry)
            if result["verdict"] == "rejected":
                screen.showAlert(result["reason"])
            else:
                screen.showMessage("Drawer " + result["drawer"] + " is unlocked. Loading stock and closing.")
                hardware.openDrawer(result["drawer"])
                hardware.changeItems(result["drawer"], amount)
                hardware.closeDrawer(result["drawer"])
                if adc["inventory"].finishReplenish(session) == "success":
                    screen.showMessage("Inventory successfully updated: " + drugID + " count increased by " + str(amount))
                    if adc["transmission"].checkConnection() == "disconnected":
                        screen.showAlert("Saved locally. Monitoring will be updated when the connection returns.")
                else:
                    screen.showAlert("Restock NOT confirmed.")

        elif choice == "5":         # Emergency override (US-AUT-02, NFR-SEC-01)
            drugID = screen.getInput("Drug ID: ")
            reason = screen.getInput("Reason (CODE_BLUE, RAPID_RESPONSE, ADC_MALFUNCTION): ")
            result = adc["override"].requestOverride(session, drugID, reason)
            if result["verdict"] == "rejected":
                screen.showAlert("Override rejected: " + result["reason"])
            else:
                screen.showMessage("OVERRIDE approved and logged: drawer " + result["drawer"] + " is unlocked.")
                collectDose(adc, hardware, screen, result)

        elif choice == "6":         # View inventory (FR-INV-01)
            rows = adc["inventory"].getInventory(session)
            if rows == "denied":
                screen.showAlert("Access denied.")
            elif rows == "error":
                screen.showAlert("Inventory information is unavailable.")
            else:
                screen.showInventory(rows)

        elif choice == "7":         # Resolve a fault (FR-COM-02)
            faultID = screen.getInput("Fault ID: ")
            screen.showMessage("Resolve: " + adc["faults"].resolveFault(session, faultID))

        elif choice == "8":         # Resume normal operation (US-FD-02)
            hardwareStatus = adc["faults"].checkHardwareStatus()
            screen.showMessage("Resume: " + adc["mode"].resumeNormalOperation(session, hardwareStatus))

        elif choice == "9":         # Maintenance on or off
            if adc["mode"].getCurrentMode() == "MAINTENANCE":
                screen.showMessage("End maintenance: " + adc["mode"].setMode(session, "NORMAL"))
            else:
                screen.showMessage("Start maintenance: " + adc["mode"].setMode(session, "MAINTENANCE"))

        elif choice == "10":        # View logs (FR-LOG-01)
            if adc["auth"].isAuthorized(session, "VIEW_LOGS"):
                badge = screen.getInput("Badge to filter by (blank for all): ")
                if badge == "":
                    screen.showEvents(adc["logger"].getEventHistory(0, clock.now()))
                else:
                    events = adc["logger"].getUserEvents(badge)
                    if events == "UserNotFound":
                        screen.showAlert("No records for that user.")
                    else:
                        screen.showEvents(events)
            else:
                screen.showAlert("Access denied.")

        elif choice == "11":        # Verify the log has not been tampered with (NFR-AUT-03)
            if adc["auth"].isAuthorized(session, "VIEW_LOGS"):
                screen.showMessage("Log integrity: " + adc["logger"].verifyLogIntegrity())
            else:
                screen.showAlert("Access denied.")

        elif choice == "12":        # Unlock an account (US-AUT-01)
            badge = screen.getInput("Badge to unlock: ")
            screen.showMessage("Unlock: " + adc["auth"].unlockAccount(session, badge))

        # ---------- Things outside the ADC that we make happen for the demo ----------

        elif choice == "20":        # Communication loss (Scenario 4: FR-COM-01)
            monitoring.toggleLink()
            screen.showMessage("Network is now up: " + str(monitoring.isOnline()))

        elif choice == "21":        # The message arrives but its acknowledgement is lost (US-COM-01)
            monitoring.loseNextAcknowledgement()
            screen.showMessage("The next acknowledgement will be lost.")

        elif choice == "22":        # The Monitoring System sends a new authorized order
            orderID = screen.getInput("Order ID: ")
            patientID = screen.getInput("Patient ID: ")
            drugID = screen.getInput("Drug ID: ")
            dose = screen.getNumber("Dose (mg): ")
            monitoring.sendOrder(orderID, patientID, drugID, dose)

        elif choice == "23":        # A forged order with the wrong key (NFR-COM-02)
            monitoring.sendForgedOrder()
            screen.showMessage("Forged order sent. It is checked at the next dispense request.")

        elif choice == "24":        # What the other team's system can see
            for line in monitoring.listReceived():
                screen.showMessage(line)

        elif choice == "25":        # Hardware fault: a lock stops responding (Scenario 3)
            drawerID = screen.getInput("Drawer (D1-D4): ")
            if drawerID in adc["drawer"].listDrawers():
                hardware.breakLock(drawerID)

        elif choice == "26":        # Hardware fault: a door sensor stops responding
            drawerID = screen.getInput("Drawer (D1-D4): ")
            if drawerID in adc["drawer"].listDrawers():
                hardware.breakSensor(drawerID)

        elif choice == "27":        # Power failure (FR-ALM-02)
            hardware.cutPower()

        elif choice == "28":        # A technician repairs the hardware
            hardware.repairAll()
            screen.showMessage("Hardware repaired and all drawers closed.")

        elif choice == "29":        # Session timeout without waiting (NFR-AUT-02)
            clock.skip(181)
            screen.showMessage("3 minutes have passed.")

        elif choice == "30" or choice == "31":      # Restart, optionally with corrupted inventory (NFR-FD-03)
            if choice == "31":
                storage.simulateCorruption("inventory")
            screen.showMessage("--- restarting software ---")
            adc.clear()             # destroys every module, so their destructors run
            adc = startSystem(hardware, monitoring, clock, storage)
            session = None

        elif choice == "32":        # Someone edits the log file directly (US-LOG-02)
            storage.simulateTampering("log")
            screen.showMessage("Log file edited directly. Log in as admin and use 11 to check it.")

        elif choice == "33":        # A person closes a drawer that was left open
            drawerID = screen.getInput("Drawer (D1-D4): ")
            if drawerID in adc["drawer"].listDrawers():
                hardware.closeDrawer(drawerID)

        else:
            screen.showAlert("Invalid choice.")

    adc.clear()                     # destroys every module, so their destructors run
    screen.showMessage("Goodbye.")


main()
