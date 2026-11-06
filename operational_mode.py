"""
OPERATIONAL MODE MODULE

RESPONSIBILITY: Hold the cabinet's mode and decide which operations each mode permits.
SECRET: The modes, the allowed changes between them, and what each mode permits.
ANTICIPATED CHANGE: A new mode, or a mode permitting different operations. Only the two tables change.
EXPORTED OPERATIONS: getCurrentMode, setMode, enterSafeState, checkOperationAllowed,
                     resumeNormalOperation, completeStartup, freeze
USES: Authenticator, EventLogger.

This is our D1 state machine at the cabinet level. Every transition is one line in __ALLOWED_CHANGES.
The SAFE mode here is "systemMode = Fault" in handleFault() in our precise specification.
Fault Monitor uses this module, so this module cannot call Fault Monitor. That is why the
hardware verdict is passed in as a parameter.
"""


class OperationalMode:
    """STATE INVARIANT: the mode only ever changes along __ALLOWED_CHANGES, and is never
    NORMAL before self-checks pass (US-STAT-01). Every change produces one log entry."""

    # What each mode permits.
    __PERMITTED = {
        "UNKNOWN": [],
        "NORMAL": ["DISPENSE", "REPLENISH", "OVERRIDE"],
        "MAINTENANCE": ["REPLENISH"],
        "SAFE": ["OVERRIDE"],       # US-AUT-02: emergency access when the cabinet has malfunctioned
        "FROZEN": [],               # the Monitoring System froze the cabinet: nothing is permitted
    }

    # The transition table: which mode may change to which.
    __ALLOWED_CHANGES = {
        "UNKNOWN": ["NORMAL", "SAFE", "FROZEN"],
        "NORMAL": ["MAINTENANCE", "SAFE", "FROZEN"],
        "MAINTENANCE": ["NORMAL", "SAFE", "FROZEN"],
        "SAFE": ["NORMAL", "FROZEN"],
        "FROZEN": [],
    }

    def __init__(self, auth, logger):
        self.__auth = auth
        self.__logger = logger
        self.__mode = "UNKNOWN"     # the constructor establishes the invariant

    # ================ PUBLIC INTERFACE ================

    def getCurrentMode(self):
        """
        PRE:  none.
        POST: "UNKNOWN", "NORMAL", "MAINTENANCE", "SAFE" or "FROZEN". Nothing changes.
        """
        return self.__mode

    def setMode(self, sessionId, newMode):
        """
        PRE:  none.
        POST: "success"  - an authorized change between NORMAL and MAINTENANCE.
              "rejected" - anything else, and the mode is unchanged. The safe state is only
                           entered by a fault and only left through resumeNormalOperation.
        """
        if newMode != "NORMAL" and newMode != "MAINTENANCE":
            return "rejected"
        if self.__mode != "NORMAL" and self.__mode != "MAINTENANCE":
            return "rejected"
        if self.__auth.isAuthorized(sessionId, "MAINTENANCE") == False:
            return "rejected"
        return self.__changeMode(newMode)

    def enterSafeState(self, faultID):
        """
        PRE:  Fault Monitor has recorded this fault.
        POST: "safe_mode" - the mode is SAFE (NFR-FD-01), or stays FROZEN, which already permits nothing.
              "rejected"  - there is no fault ID. The mode is unchanged.
        """
        if faultID == "":
            return "rejected"
        if self.__mode != "SAFE" and self.__mode != "FROZEN":
            self.__changeMode("SAFE")
        return "safe_mode"

    def freeze(self):
        """
        PRE:  the Monitoring System sent an authenticated FREEZE command.
        POST: the mode is FROZEN and nothing is permitted. It stays frozen until the software restarts.
        """
        if self.__mode != "FROZEN":
            self.__changeMode("FROZEN")

    def checkOperationAllowed(self, action):
        """
        PRE:  none.
        POST: True only if the current mode permits the action. Nothing changes.
        """
        return action in self.__PERMITTED[self.__mode]

    def resumeNormalOperation(self, sessionId, hardwareStatus):
        """
        PRE:  hardwareStatus came from FaultMonitor.checkHardwareStatus.
        POST: "normal_mode" - the mode was SAFE, hardwareStatus is "normal" (hardware is fine and no
                              critical fault is open) and recovery is authorized (US-FD-02).
              "rejected"    - otherwise, and the mode is unchanged.
        """
        if self.__mode != "SAFE":
            return "rejected"
        if hardwareStatus != "normal":
            return "rejected"
        if self.__auth.isAuthorized(sessionId, "RESOLVE_FAULT") == False:
            return "rejected"
        if self.__changeMode("NORMAL") != "success":
            return "rejected"
        return "normal_mode"

    def completeStartup(self, hardwareStatus):
        """
        PRE:  hardwareStatus came from FaultMonitor.checkHardwareStatus.
        POST: UNKNOWN becomes NORMAL if hardwareStatus is "normal". Otherwise nothing changes.
        """
        if self.__mode == "UNKNOWN" and hardwareStatus == "normal":
            self.__changeMode("NORMAL")

    # ================ PRIVATE ================

    def __changeMode(self, newMode):
        # The ONE place the mode changes. It asks the table, so an invalid change is impossible.
        # An invalid change means "no change plus a log entry" (Week 6).
        if newMode not in self.__ALLOWED_CHANGES[self.__mode]:
            self.__logger.logEvent("MODE_CHANGE_REJECTED", "SYSTEM", self.__mode + " -> " + newMode)
            return "rejected"
        self.__logger.logEvent("MODE_CHANGED", "SYSTEM", self.__mode + " -> " + newMode, {"mode": newMode})
        self.__mode = newMode
        return "success"
