"""
AUTHENTICATOR MODULE

RESPONSIBILITY: Verify who a user is and what they may do, within a valid session.
SECRET: How credentials are verified, who the users are, and how sessions are tracked.
ANTICIPATED CHANGE: PIN replaced by biometrics or access cards. Only __checkCredentials changes.
EXPORTED OPERATIONS: authenticate, getUserIdentity, logout, isAuthorized, unlockAccount, endAllSessions
USES: EventLogger, Clock.

REQ from our 4-variable model: c_accessGranted = valid session AND m_requestedOperation is in
m_userPermission. Otherwise the request is flagged (c_unauthorizedFlag). See isAuthorized.
"""


class Authenticator:
    """STATE INVARIANT: a session exists only for a verified user and is removed once it expires."""

    # Private constants: part of the secret, so no other module can see or depend on them.
    __TIMEOUT_SECONDS = 180     # NFR-AUT-02
    __LOCK_AFTER = 4            # US-AUT-01: account temporarily locked
    __FLAG_AFTER = 5            # US-AUT-04: potential security breach
    __USERS = {
        "N001": {"name": "Nina Patel", "role": "NURSE", "pin": "1111"},
        "C001": {"name": "Carlos Diaz", "role": "CHARGE_NURSE", "pin": "2222"},
        "P001": {"name": "Priya Shah", "role": "PHARMACIST", "pin": "3333"},
        "T001": {"name": "Tom Reid", "role": "TECHNICIAN", "pin": "4444"},
        "A001": {"name": "Alex Kim", "role": "ADMIN", "pin": "5555"},
    }
    __PERMISSIONS = {
        "NURSE": ["DISPENSE", "VIEW_INVENTORY"],
        "CHARGE_NURSE": ["DISPENSE", "OVERRIDE", "VIEW_INVENTORY"],
        "PHARMACIST": ["REPLENISH", "VIEW_INVENTORY"],
        "TECHNICIAN": ["MAINTENANCE", "RESOLVE_FAULT", "VIEW_INVENTORY"],
        "ADMIN": ["VIEW_LOGS", "UNLOCK_ACCOUNT"],
    }

    def __init__(self, logger, clock):
        self.__logger = logger
        self.__clock = clock
        self.__sessions = {}            # session ID -> {"badge", "lastActivity"}
        self.__failedAttempts = {}      # badge -> consecutive failed attempts
        self.__nextSession = 1

    def __del__(self):
        # Destructor: sessions do not survive a shutdown.
        print("[Authenticator] shut down,", len(self.__sessions), "sessions ended")

    # ================ PUBLIC INTERFACE ================

    def authenticate(self, credentials):
        """
        PRE:  credentials came from the login prompt.
        POST: {"verdict": "authenticated", "sessionId": id} - a new session exists.
              {"verdict": "rejected", "sessionId": None}    - invalid credentials.
              {"verdict": "locked", "sessionId": None}      - locked after 4 failures (US-AUT-01).
              Every failure is logged. The 5th in a row is flagged as a breach (US-AUT-04).
        """
        badge = credentials["badge"]
        if badge not in self.__failedAttempts:
            self.__failedAttempts[badge] = 0

        if self.__failedAttempts[badge] < self.__LOCK_AFTER and self.__checkCredentials(credentials):
            self.__failedAttempts[badge] = 0
            sessionId = "S" + str(self.__nextSession)
            self.__nextSession = self.__nextSession + 1
            self.__sessions[sessionId] = {"badge": badge, "lastActivity": self.__clock.now()}
            self.__logger.logEvent("LOGIN_SUCCESS", badge, "")
            return {"verdict": "authenticated", "sessionId": sessionId}

        self.__failedAttempts[badge] = self.__failedAttempts[badge] + 1
        attempts = self.__failedAttempts[badge]
        self.__logger.logEvent("LOGIN_FAILED", badge, "attempt " + str(attempts))
        if attempts == self.__FLAG_AFTER:
            self.__logger.logEvent("SECURITY_BREACH_FLAG", badge, "repeated invalid credentials")
        if attempts >= self.__LOCK_AFTER:
            return {"verdict": "locked", "sessionId": None}
        return {"verdict": "rejected", "sessionId": None}

    def getUserIdentity(self, sessionId):
        """
        PRE:  none.
        POST: {"id", "name", "role"} if the session is valid.
              "rejected" if the session is invalid or expired.
        """
        if self.__validateSession(sessionId) != "valid":
            return "rejected"
        user = self.__USERS[self.__sessions[sessionId]["badge"]]
        return {"id": self.__sessions[sessionId]["badge"], "name": user["name"], "role": user["role"]}

    def logout(self, sessionId):
        """
        PRE:  none.
        POST: "success" - the session is ended and logged.
              "failure" - the session is invalid or already expired. Nothing changes.
        """
        if self.__validateSession(sessionId) != "valid":
            return "failure"
        self.__logger.logEvent("LOGOUT", self.__sessions[sessionId]["badge"], "")
        del self.__sessions[sessionId]
        return "success"

    def isAuthorized(self, sessionId, action):
        """
        This is requestAccess() from our precise specification.
        PRE:  none.
        POST: True  - the session is valid and the role permits the action. The inactivity timer resets.
              False - otherwise, and the request is logged and flagged (NFR-AUT-04).
        """
        if self.__validateSession(sessionId) != "valid":
            self.__logger.logEvent("UNAUTHORIZED_REQUEST", "NO_SESSION", action)
            return False
        badge = self.__sessions[sessionId]["badge"]
        role = self.__USERS[badge]["role"]
        if action not in self.__PERMISSIONS[role]:
            self.__logger.logEvent("UNAUTHORIZED_REQUEST", badge, action)
            return False
        self.__recordActivity(sessionId)
        return True

    def unlockAccount(self, sessionId, badge):
        """
        PRE:  none.
        POST: "success" - the failed attempts for that badge are cleared and logged (US-AUT-01).
              "failure" - the user is not an admin, or the badge is unknown. Nothing changes.
        """
        if self.isAuthorized(sessionId, "UNLOCK_ACCOUNT") == False:
            return "failure"
        if badge not in self.__USERS:
            return "failure"
        self.__failedAttempts[badge] = 0
        self.__logger.logEvent("ACCOUNT_UNLOCKED", self.__sessions[sessionId]["badge"], badge)
        return "success"

    def endAllSessions(self):
        """
        PRE:  Fault Monitor found a critical fault.
        POST: every session is ended and logged (handleFault: c_sessionActive = False,
              o_sessionControl = Terminate). Staff can log in again for recovery or an override.
        """
        for sessionId in self.__sessions:
            self.__logger.logEvent("SESSION_TERMINATED", self.__sessions[sessionId]["badge"], "critical fault")
        self.__sessions = {}

    # ================ PRIVATE (the secret: how we verify people and track sessions) ================

    def __checkCredentials(self, credentials):
        # To switch from PINs to biometrics or access cards, this is the method to change.
        badge = credentials["badge"]
        if badge not in self.__USERS:
            return False
        return self.__USERS[badge]["pin"] == credentials["pin"]

    def __validateSession(self, sessionId):
        # Returns "valid", "invalid" or "expired". Private, so no caller can skip the expiry check.
        if sessionId not in self.__sessions:
            return "invalid"
        session = self.__sessions[sessionId]
        if self.__clock.now() - session["lastActivity"] >= self.__TIMEOUT_SECONDS:
            self.__logger.logEvent("SESSION_EXPIRED", session["badge"], "")
            del self.__sessions[sessionId]
            return "expired"
        return "valid"

    def __recordActivity(self, sessionId):
        self.__sessions[sessionId]["lastActivity"] = self.__clock.now()
