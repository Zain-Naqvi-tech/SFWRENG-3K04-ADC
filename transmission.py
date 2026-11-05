"""
TRANSMISSION MODULE

RESPONSIBILITY: Exchange messages with the Monitoring System and survive communication loss.
SECRET: Message format, the shared key, acknowledgements, retry logic and the local queue.
ANTICIPATED CHANGE: The protocol or message format changes. Only this file changes.
EXPORTED OPERATIONS: sendMessage, receiveMessage, checkConnection, synchronizePendingMessages, getPendingCount
USES: the network link (MonitoringSystem), Storage, Clock.

EXTERNAL INTERFACE with the Monitoring System:
  PROVIDES: EVENT, FAULT_ALARM, MAINTENANCE_REQUEST, FAULT_RESOLVED.
  REQUIRES: an acknowledgement for each message, and new authorized orders.
  LINK DOWN: the ADC keeps working. Messages wait in the saved queue and are sent when the
             link returns (FR-COM-01). The safety functions never depend on the link.
"""


class Transmission:
    """STATE INVARIANT: a message stays in the saved queue until it is acknowledged."""

    __SHARED_KEY = "adc-monitoring-key"     # stands in for the authenticated connection (NFR-COM-02)
    __CABINET_ID = "ADC-78"

    def __init__(self, monitoring, clock, storage):
        self.__monitoring = monitoring
        self.__clock = clock
        self.__storage = storage
        self.__pending = []     # the queue of unacknowledged messages
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
        PRE:  none.
        POST: "sent"     - delivered and acknowledged.
              "queued"   - the link is down. Saved, and sent when it returns.
              "failed"   - no acknowledgement. Saved, and retried.
              "rejected" - the message is invalid. Nothing changes.
        """
        if messageType == "" or content == None:
            return "rejected"
        message = {"id": self.__nextID, "cabinet": self.__CABINET_ID, "time": self.__clock.now(),
                   "type": messageType, "content": content}
        self.__nextID = self.__nextID + 1
        self.__queueMessage(message)        # saved first, so a crash cannot lose it
        if self.checkConnection() == "disconnected":
            return "queued"
        self.synchronizePendingMessages()
        if message in self.__pending:
            return "failed"
        return "sent"

    def receiveMessage(self):
        """
        PRE:  none.
        POST: the content of a valid message, removed from the link.
              "no_message" - nothing is waiting.
              "rejected"   - the message failed authentication and was discarded.
        """
        message = self.__monitoring.getNextOrder()
        if message == None:
            return "no_message"
        if message["key"] != self.__SHARED_KEY:
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
        POST: "sent"               - every waiting message was acknowledged and removed.
              "pending"            - the link is down. Nothing changes.
              "partial_success"    - some were not acknowledged. They stay queued for a retry.
              "no_action_required" - nothing was waiting.
        """
        if len(self.__pending) == 0:
            return "no_action_required"
        if self.checkConnection() == "disconnected":
            return "pending"
        acknowledged = []
        for message in self.__pending:
            if self.__monitoring.send(message) == True:
                acknowledged.append(message["id"])
        for messageID in acknowledged:
            self.__acknowledgeMessage(messageID)
        if len(self.__pending) > 0:
            return "partial_success"
        return "sent"

    def getPendingCount(self):
        """
        PRE:  none.
        POST: how many messages are waiting to be acknowledged. Nothing changes.
        """
        return len(self.__pending)

    # ================ PRIVATE (the secret: how the queue and acknowledgements work) ================

    def __queueMessage(self, message):
        self.__pending.append(message)
        self.__save()

    def __acknowledgeMessage(self, messageID):
        # A message is only removed once it is acknowledged.
        for message in self.__pending:
            if message["id"] == messageID:
                self.__pending.remove(message)
                self.__save()
                return

    def __save(self):
        self.__storage.save("outbox", {"pending": self.__pending, "nextID": self.__nextID})
