"""
TRANSMISSION MODULE

RESPONSIBILITY: Exchange messages with the Monitoring System and survive communication loss.
SECRET: The message format the Monitoring System expects, the shared key, and the local queue.
ANTICIPATED CHANGE: The protocol or message format changes. Only this file changes.
EXPORTED OPERATIONS: sendMessage, receiveMessage, receiveCommand, checkConnection,
                     synchronizePendingMessages, getPendingCount, takeSentMessages
USES: the network link (MonitoringSystem), Storage, Clock.

EXTERNAL INTERFACE with the Monitoring System:
  PROVIDES: every logged event, sent hourly. Malfunctions, maintenance requests and resolved
            malfunctions, sent as soon as they happen. There is no reply to any of these.
  REQUIRES: authorized orders, and FREEZE or SHUTDOWN commands.
  LINK DOWN: the ADC keeps working. Messages wait in the saved queue and are sent when the
             link returns (FR-COM-01). The safety functions never depend on the link.
"""
import json


class Transmission:
    """STATE INVARIANT: a message stays in the saved queue until it has been sent."""

    __SHARED_KEY = "adc-monitoring-key"     # stands in for the authenticated connection (NFR-COM-02)
    __CABINET_ID = "ADC-78"
    __SOFTWARE_VERSION = "1.0"
    __COMMANDS = ["FREEZE", "SHUTDOWN"]
    __ACCESS_EVENTS = ["LOGIN_SUCCESS", "LOGIN_FAILED", "LOGOUT", "SESSION_EXPIRED", "UNAUTHORIZED_REQUEST",
                       "SECURITY_BREACH_FLAG", "ACCOUNT_UNLOCKED", "OVERRIDE_APPROVED", "OVERRIDE_REJECTED"]

    def __init__(self, monitoring, clock, storage):
        self.__monitoring = monitoring
        self.__clock = clock
        self.__storage = storage
        self.__pending = []     # the queue of messages not sent yet
        self.__sentText = []    # what was sent since main.py last asked, as text to show
        self.__nextID = 1
        saved = self.__storage.load("outbox")
        if saved != None and saved != "corrupted":
            self.__pending = saved["pending"]       # unsent messages survive a restart
            self.__nextID = saved["nextID"]

    def __del__(self):
        # Destructor: report what is being kept for the next start.
        print("[Transmission] shut down,", len(self.__pending), "unsent messages kept")

    # ================ PUBLIC INTERFACE ================

    def sendMessage(self, messageType, content):
        """
        PRE:  messageType is "EVENT", "FAULT_ALARM", "MAINTENANCE_REQUEST" or "FAULT_RESOLVED".
        POST: "sent"     - handed to the Monitoring System. No reply is expected.
              "queued"   - the link is down. Saved, and sent when it returns.
              "rejected" - the message is invalid. Nothing changes.
        """
        if messageType == "" or content == None:
            return "rejected"
        self.__queueMessage(self.__toMonitoringFormat(messageType, content))     # saved first, so a crash cannot lose it
        if self.checkConnection() == "disconnected":
            return "queued"
        self.synchronizePendingMessages()
        return "sent"

    def receiveMessage(self):
        """
        PRE:  none.
        POST: the content of a valid order, removed from the link.
              "no_message" - nothing is waiting.
              "rejected"   - the message failed authentication and was discarded.
        """
        message = self.__monitoring.getNextOrder()
        if message == None:
            return "no_message"
        if message["key"] != self.__SHARED_KEY:
            return "rejected"
        return message["content"]

    def receiveCommand(self):
        """
        PRE:  none.
        POST: "FREEZE" or "SHUTDOWN" if the Monitoring System sent one.
              "no_message" - nothing is waiting.
              "rejected"   - the command failed authentication or is not recognized, and was discarded.
        """
        message = self.__monitoring.getNextCommand()
        if message == None:
            return "no_message"
        if message["key"] != self.__SHARED_KEY or message["content"] not in self.__COMMANDS:
            return "rejected"
        return message["content"]

    def checkConnection(self):
        """
        PRE:  none.
        POST: "connected" or "disconnected". Nothing changes.
        """
        if self.__monitoring.isOnline() == True:
            return "connected"
        return "disconnected"

    def synchronizePendingMessages(self):
        """
        PRE:  none.
        POST: "sent"               - every waiting message was handed over and removed from the queue.
              "pending"            - the link is down. Nothing changes.
              "no_action_required" - nothing was waiting.
        """
        if len(self.__pending) == 0:
            return "no_action_required"
        if self.checkConnection() == "disconnected":
            return "pending"
        for message in self.__pending:
            self.__monitoring.send(message)
            self.__sentText.append(json.dumps(message, indent=4))
        self.__pending = []
        self.__save()
        return "sent"

    def getPendingCount(self):
        """
        PRE:  none.
        POST: how many messages are waiting to be sent. Nothing changes.
        """
        return len(self.__pending)

    def takeSentMessages(self):
        """
        PRE:  none.
        POST: the text of every message sent since the last call, so it can be shown. The list is then emptied.
        """
        sentText = self.__sentText
        self.__sentText = []
        return sentText

    # ================ PRIVATE (the secret: the format the Monitoring System expects) ================

    def __toMonitoringFormat(self, messageType, content):
        # The format agreed with the Monitoring System. Every field is always present.
        message = {
            "event_id": None, "unit": self.__CABINET_ID, "event_type": None, "time": None, "user": None,
            "operating_status": None, "availability_status": None, "software_version": None,
            "slot": None, "medication": None, "lot_number": None, "quantity": None, "expiry_date": None,
            "malfunction_type": None, "severity": None, "access_action": None,
        }
        if messageType == "EVENT":
            self.__fillFromEvent(message, content)
        else:
            self.__fillFromFault(message, messageType, content)
        return message

    def __fillFromEvent(self, message, event):
        message["event_id"] = "E" + str(self.__nextID)
        self.__nextID = self.__nextID + 1
        message["event_type"] = event["type"].lower()
        message["time"] = self.__clock.toText(event["time"])
        message["user"] = event["user"]
        if event["type"] in self.__ACCESS_EVENTS:
            message["access_action"] = event["type"].lower()

        extra = event["extra"]
        if "mode" in extra:
            message["operating_status"] = extra["mode"].lower()
            message["software_version"] = self.__SOFTWARE_VERSION
            message["availability_status"] = "unavailable"
            if extra["mode"] == "NORMAL":
                message["availability_status"] = "available"
        if "drawer" in extra:
            message["slot"] = extra["drawer"]
        if "drug" in extra:
            message["medication"] = extra["drug"]
        if "batch" in extra:
            message["lot_number"] = extra["batch"]
        if "amount" in extra:
            message["quantity"] = extra["amount"]
        if "expiry" in extra:
            message["expiry_date"] = extra["expiry"]

    def __fillFromFault(self, message, messageType, fault):
        # The event ID names the original fault, so a later message can be matched to it (FR-COM-02).
        message["malfunction_type"] = fault["category"]
        message["severity"] = fault["severity"].lower()
        message["slot"] = fault["drawer"]
        message["user"] = "SYSTEM"
        message["time"] = self.__clock.toText(fault["detectedAt"])
        if messageType == "FAULT_ALARM":
            message["event_id"] = fault["id"]
            message["event_type"] = "malfunction"
        elif messageType == "MAINTENANCE_REQUEST":
            message["event_id"] = fault["id"] + "-M"
            message["event_type"] = "maintenance_request"
        else:
            message["event_id"] = fault["id"] + "-R"
            message["event_type"] = "malfunction_resolved"
            message["user"] = fault["resolvedBy"]
            message["time"] = self.__clock.toText(fault["verifiedAt"])

    def __queueMessage(self, message):
        self.__pending.append(message)
        self.__save()

    def __save(self):
        self.__storage.save("outbox", {"pending": self.__pending, "nextID": self.__nextID})
