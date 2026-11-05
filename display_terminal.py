"""
DISPLAY / GUI MODULE (terminal version)

To use it, change the import in main.py to: from display_terminal import Display
It has the same interface as display.py, so nothing else changes. That is the anticipated change.

RESPONSIBILITY: Show ADC information and collect user input.
SECRET: How information is laid out and how input is collected. Other modules do not know it is a terminal.
ANTICIPATED CHANGE: The screen is replaced or the wording changes. Only this file changes.
EXPORTED OPERATIONS: showStatus, showMenu, showMessage, showAlert, showInventory, showEvents,
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
    }

    # ================ PUBLIC INTERFACE (called by main.py) ================

    def showStatus(self, mode, connection, pending, user, drawers, faults):
        """Shows the mode, connection, user, each drawer's status and every active fault."""
        print()
        print("===== ADC:", self.__STATUS_TEXT[mode], "=====")
        print("Monitoring:", connection, "|", pending, "messages waiting | User:", user)
        for drawerID in drawers:
            print("  Drawer", drawerID, "-", drawers[drawerID])
        for fault in faults:
            print("  FAULT", fault["id"], fault["severity"], fault["faultType"], "on", fault["component"], "-", fault["description"])

    def showMenu(self):
        """Shows what the user can do, and what we can make happen for the demo."""
        print()
        print("[1 - Log in]             [2 - Log out]         [3 - Dispense]         [4 - Restock]")
        print("[5 - Emergency override] [6 - View inventory]  [7 - Resolve fault]    [8 - Resume normal]")
        print("[9 - Maintenance on/off] [10 - View logs]      [11 - Verify logs]     [12 - Unlock account]")
        print(" ")
        print("--- Make something happen (for the demo) ---")
        print(" ")
        print("[20 - Network down/up]   [21 - Lose next ack]  [22 - New order]       [23 - Forged order]")
        print("[24 - Show what Monitoring received]       [25 - Break a lock]    [26 - Break a sensor]")
        print("[27 - Power failure]     [28 - Repair all]     [29 - Skip 3 minutes]  [30 - Restart software]")
        print("[31 - Corrupt inventory] [32 - Tamper log]     [33 - Close a drawer]  [0 - Exit]")

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
