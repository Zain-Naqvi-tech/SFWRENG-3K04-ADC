# Defining all the constants we need for this project.

CABINET_ID = "ADC-78-01"
SESSION_TIMEOUT_S = 180 #this is the time in seconds before the session times out
LOCKOUT_ATTEMPTS = 4 #maximum failed login attempts before the user is locked out
FAULT_REPORT_LIMIT_S = 2 #maximum seconds between detecting a fault and the alarm reaching the monitoring system
DRAWER_OPEN_LIMIT_S = 30 #maximum seconds a drawer can stay open before it is flagged as a fault
DATA_DIR = "data" #where all the data is stored
ACK_LIMIT_S = 2 #maximum seconds between receiving an alarm and the user acknowledging it