"""
DRAWER MODULE

RESPONSIBILITY: Manage each drawer: its status, its lock, and how many items it holds.
SECRET: Which actuator and sensors belong to each drawer. Other modules only say "D1".
ANTICIPATED CHANGE: The number of drawers changes. Only the number passed to the constructor changes.
EXPORTED OPERATIONS: listDrawers, getDrawerStatus, getDrawerContents, unlockDrawer, lockDrawer
USES: Actuator, Sensor.
"""


class Drawer:
    """STATE INVARIANT: every drawer is commanded locked from construction until an authorized unlock."""

    def __init__(self, actuator, sensor, drawerCount):
        self.__actuator = actuator
        self.__sensor = sensor
        self.__drawers = {}     # the secret: drawer ID -> its actuator and sensors
        for number in range(1, drawerCount + 1):
            self.__drawers["D" + str(number)] = {
                "actuator": "LOCK" + str(number),
                "door": "DOOR" + str(number),
                "count": "COUNT" + str(number),
            }
        for drawerID in self.__drawers:
            self.lockDrawer(drawerID)       # the constructor establishes the invariant

    def __del__(self):
        # Destructor: never leave a drawer unlocked on shutdown.
        for drawerID in self.__drawers:
            self.lockDrawer(drawerID)
        print("[Drawer] shut down, drawers locked")

    # ================ PUBLIC INTERFACE ================

    def listDrawers(self):
        """
        PRE:  none.
        POST: a new list of every drawer ID. Nothing changes.
        """
        drawerIDs = []
        for drawerID in self.__drawers:
            drawerIDs.append(drawerID)
        return drawerIDs

    def getDrawerStatus(self, drawerID):
        """
        PRE:  none.
        POST: "locked" or "unlocked" - the drawer is closed and this is its lock state.
              "open"                 - the drawer is physically open.
              "unknown"              - a sensor or the lock cannot be trusted.
              "DrawerNotFound"       - no such drawer.
              Nothing changes.
        """
        if drawerID not in self.__drawers:
            return "DrawerNotFound"
        closed = self.__sensor.readSensor(self.__drawers[drawerID]["door"])
        lock = self.__actuator.getActuatorStatus(self.__drawers[drawerID]["actuator"])
        if closed != 0 and closed != 1:
            return "unknown"
        if lock == "unknown":
            return "unknown"
        if self.getDrawerContents(drawerID) == "SensorFailure":
            return "unknown"
        if closed == 0:
            return "open"
        return lock

    def getDrawerContents(self, drawerID):
        """
        PRE:  none.
        POST: the number of items the sensor sees, "DrawerNotFound" or "SensorFailure".
              Nothing changes. (Inventory Manager knows which drug is in which drawer.)
        """
        if drawerID not in self.__drawers:
            return "DrawerNotFound"
        count = self.__sensor.readSensor(self.__drawers[drawerID]["count"])
        if count == "SensorFailure" or count == "InvalidSensorReading":
            return "SensorFailure"
        return count

    def unlockDrawer(self, drawerID, authorized):
        """
        PRE:  the caller has checked the user AND the request (NFR-AUT-01).
        POST: "unlocked" - only this drawer was unlocked.
              Otherwise the drawer stays locked and the result is "DrawerNotFound",
              "UnauthorizedDrawerAccess", "DrawerStatusUnknown" or "ActuatorFailure".
        """
        status = self.getDrawerStatus(drawerID)
        if status == "DrawerNotFound":
            return "DrawerNotFound"
        if authorized == False:
            return "UnauthorizedDrawerAccess"
        if status == "unknown":
            return "DrawerStatusUnknown"
        return self.__actuator.unlockActuator(self.__drawers[drawerID]["actuator"])

    def lockDrawer(self, drawerID):
        """
        PRE:  none.
        POST: "locked" - the lock read back as engaged.
              "DrawerNotFound", "DrawerAlreadyOpen" (cannot lock an open drawer) or "ActuatorFailure".
        """
        if drawerID not in self.__drawers:
            return "DrawerNotFound"
        if self.__sensor.readSensor(self.__drawers[drawerID]["door"]) == 0:
            return "DrawerAlreadyOpen"
        return self.__actuator.lockActuator(self.__drawers[drawerID]["actuator"])
