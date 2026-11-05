"""
EVENTLOGGER MODULE

RESPONSIBILITY: Keep a traceable history of ADC activity and make it available to the Monitoring System.
SECRET: The log format, timestamps, and the checksum that exposes tampering.
ANTICIPATED CHANGE: A better logging system or different log fields. Only this file changes.
EXPORTED OPERATIONS: logEvent, getEventHistory, getUserEvents, verifyLogIntegrity
USES: Transmission, Storage, Clock.

There is deliberately NO edit or delete operation (NFR-AUT-03). Records are never removed,
so the seven-day retention always holds (US-LOG-01).

An Event given to callers is: {"seq", "time", "type", "user", "details"}. The checksum is never exposed.
"""


class EventLogger:
    """STATE INVARIANT: each saved record's checksum includes the checksum of the record before it."""

    def __init__(self, transmission, clock, storage):
        self.__transmission = transmission
        self.__clock = clock
        self.__storage = storage
        self.__restoreLogs()

    def __del__(self):
        print("[EventLogger] shut down, log is saved")

    # ================ PUBLIC INTERFACE ================

    def logEvent(self, eventType, user, details):
        """
        PRE:  none.
        POST: "success"  - saved locally, with a timestamp, and handed to Transmission (FR-LOG-01).
              "rejected" - the event has no type. Nothing changes.
        """
        if eventType == "":
            return "rejected"
        records = self.__readRecords()
        previousCheck = 0
        if len(records) > 0:
            previousCheck = records[len(records) - 1]["check"]
        record = {"seq": len(records), "time": self.__clock.now(), "type": eventType,
                  "user": user, "details": details}
        record["check"] = self.__checksum(record, previousCheck)
        records.append(record)
        self.__storage.save("log", records)
        self.__transmission.sendMessage("EVENT", self.__toEvent(record))
        return "success"

    def getEventHistory(self, startTime, endTime):
        """
        PRE:  the caller has checked VIEW_LOGS. (Authenticator uses this module, so this
              module cannot use Authenticator without creating a cycle.)
        POST: a list of Events in the time range, or "rejected" if startTime > endTime.
        """
        if startTime > endTime:
            return "rejected"
        events = []
        for record in self.__readRecords():
            if record["time"] >= startTime and record["time"] <= endTime:
                events.append(self.__toEvent(record))
        return events

    def getUserEvents(self, userID):
        """
        PRE:  the caller has checked VIEW_LOGS.
        POST: a list of that user's Events, or "UserNotFound" if there are none.
        """
        events = []
        for record in self.__readRecords():
            if record["user"] == userID:
                events.append(self.__toEvent(record))
        if len(events) == 0:
            return "UserNotFound"
        return events

    def verifyLogIntegrity(self):
        """
        PRE:  none.
        POST: "valid"   - every record matches its checksum.
              "invalid" - at least one does not. The bad records are flagged in a new
                          event and sent to the Monitoring System (US-LOG-02).
        """
        badRecords = []
        previousCheck = 0
        for record in self.__readRecords():
            if record["check"] != self.__checksum(record, previousCheck):
                badRecords.append(record["seq"])
            previousCheck = record["check"]
        if len(badRecords) > 0:
            self.logEvent("LOG_TAMPERING_DETECTED", "SYSTEM", "records " + str(badRecords))
            return "invalid"
        return "valid"

    # ================ PRIVATE (the secret: the record format and the checksum) ================

    def __restoreLogs(self):
        # Runs once, from the constructor (NFR-FD-03).
        saved = self.__storage.load("log")
        if saved == "corrupted":
            self.__storage.save("log", [])
            self.logEvent("LOG_RECOVERY_FAILED", "SYSTEM", "log could not be read, started a new one")

    def __readRecords(self):
        # Always read from storage, so an edit to the file is seen by verifyLogIntegrity.
        saved = self.__storage.load("log")
        if saved == None or saved == "corrupted":
            return []
        return saved

    def __toEvent(self, record):
        # Callers get a copy without the checksum, so the internal record stays hidden.
        return {"seq": record["seq"], "time": record["time"], "type": record["type"],
                "user": record["user"], "details": record["details"]}

    def __checksum(self, record, previousCheck):
        # Each checksum includes the one before it, so the records are chained together.
        text = str(record["seq"]) + record["type"] + record["user"] + record["details"]
        total = previousCheck
        for letter in text:
            total = (total * 31 + ord(letter)) % 1000000007
        return total
