"""
FAULT MONITOR MODULE

RESPONSIBILITY: Detect abnormal hardware and software conditions, raise alarms, trigger the safe state.
SECRET: The fault types, their priorities, the time limit, and how each component is checked.
ANTICIPATED CHANGE: A new fault type or a different priority. Only __FAULT_TYPES and __detectFault change.
EXPORTED OPERATIONS: checkHardwareStatus, reportFault, resolveFault, getActiveFaults
USES: Authenticator, Drawer, Sensor, Operational Mode, EventLogger, Transmission, Storage, Clock.

A Fault given to callers is: {"id", "faultType", "severity", "category", "component", "drawer",
"description", "detectedAt"}. The category is "electrical", "mechanical" or "software" (US-FD-01).
"""


class FaultMonitor:
    """STATE INVARIANT: every active CRITICAL fault means the cabinet is in the safe state,
    including after a restart, so restarting cannot clear it (D1 decision 1)."""

    # The secret: every fault type, its priority and its category. CRITICAL means safe state.
    __FAULT_TYPES = {
        "DRAWER_NOT_SECURED": {"severity": "CRITICAL", "category": "mechanical"},
        "LOCK_FAILURE": {"severity": "CRITICAL", "category": "mechanical"},
        "HARDWARE_UNRESPONSIVE": {"severity": "CRITICAL", "category": "electrical"},
        "INVENTORY_CORRUPT": {"severity": "CRITICAL", "category": "software"},
        "POWER_FAILURE": {"severity": "MAJOR", "category": "electrical"},   # D1 assumption 3: reserves keep it running
    }
    __DRAWER_TIME_LIMIT = 30            # seconds a drawer may stay open or unlocked (FR-ALM-02)
    __POWER_SENSOR = "POWER"

    def __init__(self, auth, drawer, sensor, mode, logger, transmission, storage, clock):
        self.__auth = auth
        self.__drawer = drawer
        self.__sensor = sensor
        self.__mode = mode
        self.__logger = logger
        self.__transmission = transmission
        self.__storage = storage
        self.__clock = clock
        self.__faults = {}              # fault ID -> fault record
        self.__nextID = 1
        self.__unsecuredSince = {}      # drawer ID -> when it was first seen open or unlocked

        # A restart must not clear the safe state.
        saved = self.__storage.load("faults")
        if saved != None and saved != "corrupted":
            self.__faults = saved["faults"]
            self.__nextID = saved["nextID"]
            for faultID in self.__faults:
                if self.__faults[faultID]["severity"] == "CRITICAL":
                    self.__mode.enterSafeState(faultID)

    # ================ PUBLIC INTERFACE ================

    def checkHardwareStatus(self):
        """
        PRE:  none.
        POST: every abnormal component has been reported, then:
              "normal"         - all components are fine and no critical fault is open.
              "fault_detected" - a component is abnormal, or a critical fault is still open.
              "unknown"        - a component's status cannot be determined.
        """
        result = "normal"
        components = self.__drawer.listDrawers()
        components.append(self.__POWER_SENSOR)
        for component in components:
            faultType = self.__detectFault(component)
            if faultType != "no_fault":
                self.reportFault(faultType, component, "detected by hardware check")
                if faultType != "HARDWARE_UNRESPONSIVE":
                    result = "fault_detected"
                elif result == "normal":
                    result = "unknown"      # unknown status is never treated as normal
        if result == "normal" and self.__hasCriticalFault():
            result = "fault_detected"
        return result

    def reportFault(self, faultType, component, description):
        """
        PRE:  faultType is one of DRAWER_NOT_SECURED, LOCK_FAILURE, HARDWARE_UNRESPONSIVE,
              INVENTORY_CORRUPT or POWER_FAILURE.
        POST: "success"  - recorded once and logged, alarm and maintenance request sent
                           (FR-ALM-01, FR-ALM-02). A CRITICAL fault enters the safe state and locks
                           every drawer that can lock (NFR-FD-01).
              "rejected" - unknown fault type. Nothing changes.
        """
        if faultType not in self.__FAULT_TYPES:
            return "rejected"
        for faultID in self.__faults:
            fault = self.__faults[faultID]
            if fault["faultType"] == faultType and fault["component"] == component:
                return "success"        # already known: do not raise the same alarm twice

        faultID = "F-" + str(self.__nextID)
        self.__nextID = self.__nextID + 1
        drawerID = None
        if component in self.__drawer.listDrawers():
            drawerID = component
        fault = {"id": faultID, "faultType": faultType, "severity": self.__FAULT_TYPES[faultType]["severity"],
                 "category": self.__FAULT_TYPES[faultType]["category"], "component": component, "drawer": drawerID,
                 "description": description, "detectedAt": self.__clock.now()}
        self.__faults[faultID] = fault
        self.__save()
        self.__logger.logEvent("FAULT_DETECTED", "SYSTEM", faultID + " " + faultType + " on " + component)
        self.__transmission.sendMessage("FAULT_ALARM", fault)
        self.__transmission.sendMessage("MAINTENANCE_REQUEST", fault)
        if fault["severity"] == "CRITICAL":
            self.__mode.enterSafeState(faultID)
            self.__lockAllDrawers()
        return "success"

    def resolveFault(self, sessionId, faultID):
        """
        PRE:  none.
        POST: "resolved"      - authorized, and the fix was verified on the hardware. The fault is
                                removed and the Monitoring System is told (FR-COM-02).
              "FaultNotFound" - no such fault.
              "rejected"      - not authorized, or not actually fixed. The fault stays active.
        """
        if self.__auth.isAuthorized(sessionId, "RESOLVE_FAULT") == False:
            return "rejected"
        if faultID not in self.__faults:
            return "FaultNotFound"
        component = self.__faults[faultID]["component"]
        if component in self.__drawer.listDrawers():
            if self.__drawer.lockDrawer(component) != "locked":
                return "rejected"
        if self.__detectFault(component) != "no_fault":
            return "rejected"           # a fault cannot be marked resolved without verification

        resolved = self.__faults[faultID]
        del self.__faults[faultID]
        self.__save()
        user = self.__auth.getUserIdentity(sessionId)
        self.__logger.logEvent("FAULT_RESOLVED", user["id"], faultID)
        resolved["resolvedBy"] = user["id"]
        resolved["verifiedAt"] = self.__clock.now()
        self.__transmission.sendMessage("FAULT_RESOLVED", resolved)
        return "resolved"

    def getActiveFaults(self):
        """
        PRE:  none.
        POST: a list of copies of the active Faults. Nothing changes.
        """
        faults = []
        for faultID in self.__faults:
            faults.append(self.__faults[faultID].copy())
        return faults

    # ================ PRIVATE (the secret: how each component is checked) ================

    def __detectFault(self, component):
        # Returns "no_fault", a fault type, or "ComponentNotFound".
        if component == self.__POWER_SENSOR:
            reading = self.__sensor.readSensor(self.__POWER_SENSOR)
            if reading == 1:
                return "no_fault"
            if reading == 0:
                return "POWER_FAILURE"
            return "HARDWARE_UNRESPONSIVE"

        if component not in self.__drawer.listDrawers():
            return "ComponentNotFound"      # software faults cannot be verified on the hardware

        status = self.__drawer.getDrawerStatus(component)
        if status == "unknown":
            return "HARDWARE_UNRESPONSIVE"
        if status == "locked":
            if component in self.__unsecuredSince:
                del self.__unsecuredSince[component]
            return "no_fault"

        # The drawer is open or unlocked. That is fine for a short time, during a dispense.
        if component not in self.__unsecuredSince:
            self.__unsecuredSince[component] = self.__clock.now()
        overLimit = self.__clock.now() - self.__unsecuredSince[component] > self.__DRAWER_TIME_LIMIT
        if status == "unlocked" and (overLimit or self.__hasFaultOn(component)):
            if self.__drawer.lockDrawer(component) == "locked":     # secure it as soon as it is closed
                del self.__unsecuredSince[component]
                return "no_fault"
        if overLimit:
            return "DRAWER_NOT_SECURED"
        return "no_fault"

    def __hasFaultOn(self, component):
        for faultID in self.__faults:
            if self.__faults[faultID]["component"] == component:
                return True
        return False

    def __hasCriticalFault(self):
        for faultID in self.__faults:
            if self.__faults[faultID]["severity"] == "CRITICAL":
                return True
        return False

    def __lockAllDrawers(self):
        for drawerID in self.__drawer.listDrawers():
            self.__drawer.lockDrawer(drawerID)

    def __save(self):
        # A corrupt-inventory fault is not saved: it is detected again at startup if still true.
        toSave = {}
        for faultID in self.__faults:
            if self.__faults[faultID]["component"] != "INVENTORY":
                toSave[faultID] = self.__faults[faultID]
        self.__storage.save("faults", {"faults": toSave, "nextID": self.__nextID})
