"""
DISPLAY / GUI MODULE (terminal version)

To use it, change the import in main.py to: from display_terminal import Display
It has the same interface as display.py, so nothing else changes. That is the anticipated change.

RESPONSIBILITY: Show ADC information and collect user input.
SECRET: How information is laid out and how input is collected. Other modules do not know it is a terminal.
ANTICIPATED CHANGE: The screen is replaced or the wording changes. Only this file changes.
EXPORTED OPERATIONS: showStatus, showMenu, showMessage, showAlert, showInventory, showEvents, showOrders,
                     getInput, getNumber, getChoice, promptCredentials
USES: nothing. main.py passes it the information to show, so it can never change another module's data.
"""
import time


class Display:
    """STATE INVARIANT: holds no ADC data, only its own wording."""

    # US-STAT-01: never say "Operational" unless the mode really is NORMAL.
    __STATUS_TEXT = {
        "NORMAL": "Operational",
        "MAINTENANCE": "Under Maintenance",
        "SAFE": "SAFE STATE - not functioning normally",
        "UNKNOWN": "Status Unknown",
        "FROZEN": "FROZEN by the Monitoring System",
    }

    # ================ PUBLIC INTERFACE (called by main.py) ================

    def showStatus(self, mode, connection, pending, user, drawers, faults):
        """Shows the mode, connection, user, each drawer's status and every active fault."""
        print()
        print("===== ADC:", self.__STATUS_TEXT[mode], "=====")
        print("Monitoring:", connection, "|", pending, "messages waiting | User:", user)
        for drawerID in drawers:
            print("  Drawer", drawerID, "-", drawers[drawerID])
        if len(faults) == 0:
            print("  No active faults")
        for fault in faults:
            print("  FAULT", fault["id"], fault["severity"], fault["faultType"], "on", fault["component"], "-", fault["description"])

    def showMenu(self):
        """Shows what the user can do, and what we can make happen for the demo."""
        print()
        print("[1 - Log in] FR-AUTH-01               [2 - Log out] FR-AUTH-01")
        print("[3 - Dispense] FR-DSP-01, FR-DSP-02   [4 - Restock] US-INV-01, NFR-AUT-01")
        print("[5 - Emergency override] NFR-SEC-01   [6 - View inventory] FR-INV-01")
        print("[7 - Resolve fault] FR-COM-02         [8 - Resume normal] US-FD-02")
        print("[9 - Maintenance on/off] US-STAT-01   [10 - View logs] FR-LOG-01")
        print("[11 - Verify logs] NFR-AUT-03         [12 - Unlock account] US-AUT-01")
        print("[13 - My orders] FR-DSP-01")
        print(" ")
        print("--- Make something happen (for the demo) ---")
        print(" ")
        print("[20 - Network down/up] FR-COM-01      [21 - Monitoring: Freeze] FR-COM-03")
        print("[22 - New order] FR-DSP-01            [23 - Monitoring: Shutdown] FR-COM-04")
        print("[24 - Skip 5 minutes] FR-LOG-01       [25 - Break a lock] FR-ALM-02")
        print("[26 - Break a sensor] FR-ALM-02       [27 - Power failure] FR-ALM-02, US-FD-01")
        print("[28 - Repair all] US-FD-02            [29 - Skip 3 minutes] NFR-AUT-02")
        print("[30 - Restart software] NFR-FD-03     [31 - Corrupt inventory] US-FD-03")
        print("[32 - Tamper log] US-LOG-02           [33 - Close a drawer] FR-ALM-02")
        print("[0 - Exit]")

    def showMessage(self, text):
        """Shows a normal message (NFR-FD-04: acknowledges an operation)."""
        print(text)

    def showAlert(self, text):
        """Shows an alert. Text plus a beep, so it does not rely on one sense (accessibility)."""
        print("\a!!!", text, "!!!")

    def showInventory(self, rows):
        """Shows medication names, drawers, quantities and expiry dates (FR-INV-01)."""
        for row in rows:
            print(" ", row["drugID"], row["name"], "| drawer", row["drawer"], "| batch", row["batch"],
                  "| qty", row["quantity"], "| expires", row["expiry"], "|", row["status"])

    def showEvents(self, events):
        """Shows log events with their time."""
        for event in events:
            print(" ", event["seq"], self.__formatTime(event["time"]), event["type"], event["user"], event["details"])

    def showOrders(self, orders, requests):
        """Shows every order with whether it is valid, then what this user has requested, valid or not."""
        print("Orders:")
        for order in orders:
            print(" ", order["orderID"], order["patientID"], order["drugID"], order["dose"], "| expires", order["expiry"], "|", order["validity"])
        print("Your requests:")
        if len(requests) == 0:
            print("  No requests yet.")
        for request in requests:
            print(" ", request["patientID"], request["drugID"], request["dose"], "|", request["verdict"], request["reason"])

    def getInput(self, prompt):
        """Returns what the user typed, without extra spaces."""
        return input(prompt).strip()

    def getNumber(self, prompt):
        """Returns a whole number, or None if the input was not one (InvalidInput)."""
        text = self.getInput(prompt)
        if text.isdigit():
            return int(text)
        return None

    def getChoice(self, prompt, options):
        """Shows the options ({key: label}) and returns what the user typed."""
        print(prompt)
        for key in options:
            print("  [" + key + "]", options[key])
        return self.getInput("> ")

    def promptCredentials(self):
        """Shows the login prompt and returns the credentials for Authenticator."""
        badge = self.getInput("Badge: ")
        pin = self.getInput("PIN: ")
        return {"badge": badge, "pin": pin}

    # ================ PRIVATE ================

    def __formatTime(self, seconds):
        return time.strftime("%H:%M:%S", time.localtime(seconds))
