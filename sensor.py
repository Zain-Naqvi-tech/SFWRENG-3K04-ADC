"""
SENSOR MODULE

RESPONSIBILITY: Read the physical sensors and give other modules checked readings.
SECRET: How readings are collected and what values are valid for each kind of sensor.
ANTICIPATED CHANGE: A sensor type changes (e.g. weight replaced by RFID). Only this file changes.
EXPORTED OPERATIONS: readSensor
USES: the hardware drivers.

4-VARIABLE MODEL: this is the IN relation. The software never sees the real door (m_drawerClosed),
only the reading this module returns.
"""


class Sensor:
    """STATE INVARIANT: readSensor never returns an unchecked value."""

    # The secret: what counts as a valid reading for each kind of sensor.
    __LIMITS = {
        "door": {"low": 0, "high": 1},          # 0 = open, 1 = closed
        "count": {"low": 0, "high": 500},       # items in the drawer
        "power": {"low": 0, "high": 1},         # 0 = failed, 1 = on
    }

    def __init__(self, hardware):
        self.__hardware = hardware
        self.__sensorKinds = hardware.listSensors()     # sensor ID -> kind

    # ================ PUBLIC INTERFACE (called by Drawer and Fault Monitor) ================

    def readSensor(self, sensorID):
        """
        PRE:  none.
        POST: the reading, if it is valid.
              "SensorNotFound"       - no such sensor.
              "SensorFailure"        - the sensor did not respond.
              "InvalidSensorReading" - the value is outside its valid range.
              Nothing changes.
        """
        if sensorID not in self.__sensorKinds:
            return "SensorNotFound"
        value = self.__hardware.readSensor(sensorID)
        if value == None:
            return "SensorFailure"
        if self.__isValid(sensorID, value) == False:
            return "InvalidSensorReading"
        return value

    # ================ PRIVATE ================

    def __isValid(self, sensorID, value):
        limits = self.__LIMITS[self.__sensorKinds[sensorID]]
        return value >= limits["low"] and value <= limits["high"]
