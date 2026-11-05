"""
OVERRIDE MODULE

RESPONSIBILITY: Decide whether authorized staff may bypass the order check in an emergency.
SECRET: The override rules and what counts as an emergency.
ANTICIPATED CHANGE: The override policy or the approved reasons. Only this file changes.
EXPORTED OPERATIONS: requestOverride
USES: Authenticator, Dispensing, EventLogger. It never touches hardware: Dispensing opens the drawer.
"""


class Override:
    """STATE INVARIANT: holds no override state, so approval only lasts as long as the session."""

    __APPROVED_REASONS = ["CODE_BLUE", "RAPID_RESPONSE", "ADC_MALFUNCTION"]

    def __init__(self, auth, dispensing, logger):
        self.__auth = auth
        self.__dispensing = dispensing
        self.__logger = logger

    # ================ PUBLIC INTERFACE ================

    def requestOverride(self, sessionId, drugID, reason):
        """
        PRE:  none.
        POST: {"verdict": "approved", "requestID": id, "drawer": id} - that drawer is unlocked.
              {"verdict": "rejected", "reason": text} - nothing changes (US-AUT-02).
              Every attempt is logged with the person, reason and verdict (NFR-SEC-01).
        """
        identity = self.__auth.getUserIdentity(sessionId)
        personnelID = "NO_SESSION"
        if identity != "rejected":
            personnelID = identity["id"]

        if self.__verifyAuthorization(sessionId) == False:
            self.__recordOverride(personnelID, reason, "rejected")
            return {"verdict": "rejected", "reason": "You are not authorized to override."}
        if reason not in self.__APPROVED_REASONS:
            self.__recordOverride(personnelID, reason, "rejected")
            return {"verdict": "rejected", "reason": "That is not an approved emergency reason."}

        # Dispensing still refuses expired stock, maintenance mode and faulted drawers.
        result = self.__dispensing.releaseForOverride(sessionId, drugID)
        if result["verdict"] == "rejected":
            self.__recordOverride(personnelID, reason, "rejected")
            return result
        self.__recordOverride(personnelID, reason, "approved")
        return {"verdict": "approved", "requestID": result["requestID"], "drawer": result["drawer"]}

    # ================ PRIVATE (the secret: the override rules) ================

    def __verifyAuthorization(self, sessionId):
        return self.__auth.isAuthorized(sessionId, "OVERRIDE")

    def __recordOverride(self, personnelID, reason, verdict):
        self.__logger.logEvent("OVERRIDE_" + verdict.upper(), personnelID, reason)
