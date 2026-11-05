"""
STORAGE (helper file)

Saves data to files so it survives a restart (NFR-FD-03).
Secret: how and where data is stored. Modules only say save("inventory", data).
Anticipated change: moving from files to a database would only change this file.
"""
import json


class Storage:
    def __init__(self):
        self.__files = {
            "inventory": "data_inventory.json",
            "orders": "data_orders.json",
            "log": "data_log.json",
            "outbox": "data_outbox.json",
            "faults": "data_faults.json",
        }

    def save(self, name, data):
        file = open(self.__files[name], "w")
        file.write(json.dumps(data, indent=1))
        file.close()

    def load(self, name):
        # Returns the saved data, None if nothing is saved, or "corrupted" if it cannot be read.
        try:
            file = open(self.__files[name], "r")
        except FileNotFoundError:
            return None
        text = file.read()
        file.close()
        try:
            return json.loads(text)
        except ValueError:
            return "corrupted"

    def reset(self):
        # Start the demo from a clean state.
        for name in self.__files:
            self.save(name, None)

    # ----- Demo only: damage a file from outside, the way a real fault or attacker would. -----

    def simulateCorruption(self, name):
        file = open(self.__files[name], "w")
        file.write("{ corrupted")
        file.close()

    def simulateTampering(self, name):
        # Someone edits the file directly, bypassing the module that owns it.
        file = open(self.__files[name], "r")
        text = file.read()
        file.close()
        file = open(self.__files[name], "w")
        file.write(text.replace("SYSTEM", "HACKER", 1))
        file.close()
