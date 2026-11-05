"""
ACTUATOR MODULE

RESPONSIBILITY: Control the physical locks on the drawers.
SECRET: How lock commands are sent to the hardware and how success is confirmed.
ANTICIPATED CHANGE: The actuator type changes. Only this file changes.
EXPORTED OPERATIONS: unlockActuator, lockActuator, getActuatorStatus
USES: the hardware drivers.
"""


class Actuator:
    """STATE INVARIANT: a lock is only reported as moved after reading it back from the hardware."""

    def __init__(self, hardware):
        self.__hardware = hardware
        self.__actuatorIDs = hardware.listActuators()

    # ================ PUBLIC INTERFACE (called by Drawer only) ================

    def unlockActuator(self, actuatorID):
        """
        PRE:  none.
        POST: "unlocked"         - the lock was commanded open and reads back open.
              "ActuatorNotFound" - no such actuator. Nothing changes.
              "ActuatorFailure"  - the lock did not open.
        """
        if actuatorID not in self.__actuatorIDs:
            return "ActuatorNotFound"
        self.__sendCommand(actuatorID, False)
        if self.getActuatorStatus(actuatorID) == "unlocked":
            return "unlocked"
        return "ActuatorFailure"

    def lockActuator(self, actuatorID):
        """
        PRE:  none.
        POST: "locked"           - the lock was commanded shut and reads back shut.
              "ActuatorNotFound" - no such actuator. Nothing changes.
              "ActuatorFailure"  - the lock did not engage.
        """
        if actuatorID not in self.__actuatorIDs:
            return "ActuatorNotFound"
        self.__sendCommand(actuatorID, True)
        if self.getActuatorStatus(actuatorID) == "locked":
            return "locked"
        return "ActuatorFailure"

    def getActuatorStatus(self, actuatorID):
        """
        PRE:  none.
        POST: "locked" or "unlocked" - what the hardware reports.
              "unknown"              - the actuator did not respond.
              "ActuatorNotFound"     - no such actuator.
              Nothing changes.
        """
        if actuatorID not in self.__actuatorIDs:
            return "ActuatorNotFound"
        state = self.__hardware.readLock(actuatorID)
        if state == None:
            return "unknown"
        if state == True:
            return "locked"
        return "unlocked"

    # ================ PRIVATE (the secret: how we talk to this lock model) ================

    def __sendCommand(self, actuatorID, locked):
        self.__hardware.setLock(actuatorID, locked)
