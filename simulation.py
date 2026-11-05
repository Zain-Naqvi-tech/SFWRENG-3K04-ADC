"""
SIMULATION (helper file, NOT an ADC module)

This file stands in for everything OUTSIDE our software:
  Clock            - the time, with a "skip" so we do not wait 3 minutes in a demo
  Hardware         - the physical cabinet: locks, sensors, and what a person does to them
  MonitoringSystem - the other team's system (Part B)

Week 6: "Hardware-hiding modules get a real implementation and a simulated one
behind the same interface." Swapping this for real drivers would not change any module,
because only Actuator and Sensor ever talk to Hardware.
"""
import time


class Clock:
    def __init__(self):
        self.__skippedSeconds = 0

    def now(self):
        # Current time in seconds.
        return time.time() + self.__skippedSeconds

    def today(self):
        # Today's date as "YYYY-MM-DD".
        return time.strftime("%Y-%m-%d", time.localtime(self.now()))

    def skip(self, seconds):
        # Demo only: pretend this much time has passed.
        self.__skippedSeconds = self.__skippedSeconds + seconds


class Hardware:
    """The physical cabinet. Each drawer has one lock, one door sensor and one item-count sensor."""

    __STARTING_ITEMS = {"D1": 20, "D2": 30, "D3": 15, "D4": 5}

    def __init__(self, drawerCount):
        self.__locks = {}           # actuator ID -> True if locked
        self.__sensors = {}         # sensor ID -> reading
        self.__sensorKinds = {}     # sensor ID -> "door", "count" or "power"
        self.__drawers = {}         # drawer label -> its lock and sensors
        self.__deadLocks = []       # locks that do not respond at all
        self.__jammedLocks = []     # locks that respond but do not move
        self.__deadSensors = []     # sensors that do not respond

        self.__sensors["POWER"] = 1
        self.__sensorKinds["POWER"] = "power"
        for number in range(1, drawerCount + 1):
            drawerID = "D" + str(number)
            lock = "LOCK" + str(number)
            door = "DOOR" + str(number)
            count = "COUNT" + str(number)
            self.__drawers[drawerID] = {"lock": lock, "door": door, "count": count}
            self.__locks[lock] = True
            self.__sensors[door] = 1        # 1 = closed, 0 = open
            self.__sensorKinds[door] = "door"
            self.__sensors[count] = 0
            if drawerID in self.__STARTING_ITEMS:
                self.__sensors[count] = self.__STARTING_ITEMS[drawerID]
            self.__sensorKinds[count] = "count"

    # ----- The driver interface. Only Actuator and Sensor call these. -----

    def listActuators(self):
        actuatorIDs = []
        for actuatorID in self.__locks:
            actuatorIDs.append(actuatorID)
        return actuatorIDs

    def listSensors(self):
        return self.__sensorKinds.copy()

    def setLock(self, actuatorID, locked):
        if actuatorID in self.__deadLocks or actuatorID in self.__jammedLocks:
            return
        if locked == True and self.__doorIsOpen(actuatorID):
            return                  # NAT: a lock cannot engage on an open drawer
        self.__locks[actuatorID] = locked

    def readLock(self, actuatorID):
        if actuatorID in self.__deadLocks:
            return None
        return self.__locks[actuatorID]

    def readSensor(self, sensorID):
        if sensorID in self.__deadSensors:
            return None
        return self.__sensors[sensorID]

    # ----- What a person physically does at the cabinet. Only main.py calls these. -----

    def openDrawer(self, drawerID):
        lock = self.__drawers[drawerID]["lock"]
        if self.__locks[lock] == False:     # a locked drawer cannot be pulled open
            self.__sensors[self.__drawers[drawerID]["door"]] = 0

    def closeDrawer(self, drawerID):
        self.__sensors[self.__drawers[drawerID]["door"]] = 1

    def changeItems(self, drawerID, amount):
        count = self.__drawers[drawerID]["count"]
        self.__sensors[count] = self.__sensors[count] + amount

    # ----- Faults we can inject during the demo. Only main.py calls these. -----

    def breakLock(self, drawerID):
        self.__deadLocks.append(self.__drawers[drawerID]["lock"])

    def jamLock(self, drawerID):
        self.__jammedLocks.append(self.__drawers[drawerID]["lock"])

    def breakSensor(self, drawerID):
        self.__deadSensors.append(self.__drawers[drawerID]["door"])

    def cutPower(self):
        self.__sensors["POWER"] = 0

    def repairAll(self):
        # A technician fixes everything and closes every drawer.
        self.__deadLocks = []
        self.__jammedLocks = []
        self.__deadSensors = []
        self.__sensors["POWER"] = 1
        for drawerID in self.__drawers:
            self.closeDrawer(drawerID)

    def __doorIsOpen(self, actuatorID):
        for drawerID in self.__drawers:
            if self.__drawers[drawerID]["lock"] == actuatorID:
                return self.__sensors[self.__drawers[drawerID]["door"]] == 0
        return False


class MonitoringSystem:
    """A fake of the other team's system. It only knows the agreed messages, not ADC internals."""

    __SHARED_KEY = "adc-monitoring-key"     # agreed by both teams

    def __init__(self):
        self.__online = True
        self.__dropNextAck = False
        self.__received = []                # every message, stored once
        self.__seenIDs = []                 # used to ignore repeats
        self.__ordersToSend = []
        # The pharmacy's authorized orders. These reach the ADC through Transmission.
        self.sendOrder("O1", "P-1001", "LORA", 2)
        self.sendOrder("O2", "P-1001", "ACET", 1000)
        self.sendOrder("O3", "P-1002", "AMOX", 500)
        self.sendOrder("O4", "P-1002", "MORP", 10)

    # ----- Called by Transmission, across the system boundary. -----

    def isOnline(self):
        return self.__online

    def send(self, message):
        # Receives a message from the ADC. Returns True if the ADC gets an acknowledgement.
        if self.__online == False:
            return False
        if message["id"] not in self.__seenIDs:     # a repeat is ignored, so no duplicate records
            self.__seenIDs.append(message["id"])
            self.__received.append(message)
        if self.__dropNextAck == True:
            self.__dropNextAck = False
            return False
        return True

    def getNextOrder(self):
        if self.__online == False or len(self.__ordersToSend) == 0:
            return None
        return self.__ordersToSend.pop(0)

    # ----- Demo controls. Only main.py calls these. -----

    def toggleLink(self):
        self.__online = not self.__online

    def loseNextAcknowledgement(self):
        self.__dropNextAck = True

    def sendOrder(self, orderID, patientID, drugID, dose):
        order = {"orderID": orderID, "patientID": patientID, "drugID": drugID, "dose": dose}
        self.__ordersToSend.append({"key": self.__SHARED_KEY, "content": order})

    def sendForgedOrder(self):
        # An order that did not really come from us: the key is wrong.
        order = {"orderID": "FORGED", "patientID": "P-1001", "drugID": "MORP", "dose": 10}
        self.__ordersToSend.append({"key": "wrong-key", "content": order})

    def listReceived(self):
        # Returns one line of text per message received, for main.py to show on the screen.
        lines = ["Monitoring System has received " + str(len(self.__received)) + " messages:"]
        for message in self.__received:
            content = message["content"]
            if message["type"] == "EVENT":
                lines.append("  EVENT " + content["type"] + " " + content["user"] + " " + content["details"])
            elif message["type"] == "FAULT_RESOLVED":
                lines.append("  FAULT_RESOLVED " + content["faultID"])
            else:
                lines.append("  " + message["type"] + " " + content["id"] + " " + content["faultType"] + " on " + content["component"])
        return lines
