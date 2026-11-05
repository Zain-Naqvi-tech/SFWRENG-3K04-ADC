# Design notes

For writing the D2 document and answering TA questions. To run the demo, use the [README](README.md).

## How the code follows Weeks 5 and 6

| Course rule | In the code |
|---|---|
| One module = one file, named for the module | Each file below has one class, and starts with its responsibility, secret and anticipated change |
| "The exported operations are the module's public methods. Everything else is private." | Each file has a PUBLIC INTERFACE section and a PRIVATE section |
| "A public field is a leaked secret." | Every field in every class is `self.__name` |
| A secret is "private fields and constants" | PINs, permissions, fault types, time limits and tables are `__private` class constants |
| Public methods have pre/post in the doc comment | Every public method in the ADC modules has a PRE and POST, except Display, which has a one-line description |
| State invariant: set by the constructor, kept by every public method | Stated at the top of each class |
| USES: references the class holds, injected, acyclic | `startSystem` in `main.py` |
| Hardware modules have a simulated implementation behind the same interface | `Hardware` in `simulation.py`, reached only by Actuator and Sensor |
| Invalid state change means "no change plus a log entry" | `OperationalMode.__changeMode` |
| Partner protocol is a secret inside one comms module | Message format and key are inside Transmission |

## Module interfaces

| Module (file) | Secret | Public operation: called by | Private |
|---|---|---|---|
| Authenticator (`authenticator.py`) | How credentials are verified, the users, sessions | `authenticate`, `logout`, `unlockAccount`: main. `getUserIdentity`: Dispensing, Fault Monitor, Override, main. `isAuthorized`: Dispensing, Inventory, Fault Monitor, Mode, Override, main. `endAllSessions`: Fault Monitor | `__checkCredentials`, `__validateSession`, `__recordActivity` |
| Dispensing (`dispensing.py`) | Dispensing rules, orders, open requests | `requestDispense`, `completeDispense`, `cancelDispense`, `getUserOrders`: main. `releaseForOverride`: Override | `__checkAndOpen`, `__validateRequest`, `__orderExpired`, `__orderValidity`, `__stockProblem`, `__openDrawer`, `__receiveNewOrders`, `__hasOrder`, `__setOrderStatus`, `__userOf`, `__reject` |
| Inventory Manager (`inventory_manager.py`) | Data structure, how batches are chosen | `getInventory`, `startReplenish`, `finishReplenish`: main. `checkDispensable`, `removeMedication`: Dispensing | `__restoreInventory`, `__checkRestock`, `__addMedication`, `__getQuantity`, `__getNextBatch`, `__checkExpiry`, `__findBatch`, `__saveChange` |
| EventLogger (`event_logger.py`) | Log format, checksum | `logEvent`: most modules. `getEventHistory`, `getUserEvents`, `verifyLogIntegrity`, `sendHourlyLog`: main | `__restoreLogs`, `__readRecords`, `__toEvent`, `__checksum` |
| Fault Monitor (`fault_monitor.py`) | Fault types, priorities, thresholds, detection | `checkHardwareStatus`, `resolveFault`: main. `reportFault`: Dispensing, Inventory. `getActiveFaults`: Dispensing, main | `__detectFault`, `__hasFaultOn`, `__hasCriticalFault`, `__lockAllDrawers`, `__save` |
| Operational Mode (`operational_mode.py`) | Modes, transitions, what each permits | `getCurrentMode`, `setMode`, `resumeNormalOperation`, `completeStartup`, `freeze`: main. `enterSafeState`: Fault Monitor. `checkOperationAllowed`: Dispensing, Inventory | `__changeMode` |
| Transmission (`transmission.py`) | The format the Monitoring System expects, the key, the queue | `sendMessage`: EventLogger, Fault Monitor. `receiveMessage`: Dispensing. `receiveCommand`, `checkConnection`, `synchronizePendingMessages`, `getPendingCount`, `takeSentMessages`: main | `__toMonitoringFormat`, `__fillFromEvent`, `__fillFromFault`, `__queueMessage`, `__save` |
| Actuator (`actuator.py`) | How locks are commanded and confirmed | `unlockActuator`, `lockActuator`, `getActuatorStatus`: Drawer | `__sendCommand` |
| Sensor (`sensor.py`) | How readings are collected, valid ranges | `readSensor`: Drawer, Fault Monitor | `__isValid` |
| Drawer (`drawer.py`) | Which lock and sensors belong to each drawer | `listDrawers`, `getDrawerStatus`: Fault Monitor, main. `getDrawerContents`, `unlockDrawer`: Dispensing, Inventory. `lockDrawer`: Dispensing, Inventory, Fault Monitor | fields only |
| Override (`override.py`) | Override rules, approved reasons | `requestOverride`: main | `__verifyAuthorization`, `__recordOverride` |
| Display (`display.py`, or `display_terminal.py`) | Layout, wording, how input is collected | All 11 operations: main | How the window is built and how input is collected |

Helper files, not modules: `main.py` (connects everything and runs the loop), `simulation.py` (fake clock, cabinet and Monitoring System), `storage.py` (saves to files).

## External interface with the Monitoring System

**What the simulation covers:** `MonitoringSystem` in `simulation.py` only does what the ADC touches at the boundary: being online or offline, accepting our messages, and giving us orders and commands. How they store, show or act on our messages belongs to them.

| Direction | Message | When |
|---|---|---|
| ADC to Monitoring | Every logged event | Every hour, no reply |
| ADC to Monitoring | `malfunction` and `maintenance_request` | As soon as a fault is found, no reply |
| ADC to Monitoring | `malfunction_resolved` | As soon as the fix is verified, no reply |
| Monitoring to ADC | Authorized order, with an expiry date | When they send one |
| Monitoring to ADC | FREEZE | The cabinet freezes and locks its drawers. Only a restart clears it |
| Monitoring to ADC | SHUTDOWN | The cabinet shuts down and locks its drawers |

**When the link is down:** the cabinet keeps working. Outgoing messages wait in the saved queue and go out when it returns. Orders and commands can't arrive until then.

**Faults, by malfunction type:**

| Fault | `malfunction_type` | `severity` | Result |
|---|---|---|---|
| POWER_FAILURE | `electrical` | `major` | Cabinet keeps running |
| HARDWARE_UNRESPONSIVE (a lock or sensor stops responding) | `electrical` | `critical` | Safe state |
| LOCK_FAILURE | `mechanical` | `critical` | Safe state |
| DRAWER_NOT_SECURED | `mechanical` | `critical` | Safe state |
| INVENTORY_CORRUPT | `software` | `critical` | Safe state |

## Precise specification to code

Use this for the implementation notes and the traceability table.

| Spec function | In the code | Where |
|---|---|---|
| `requestAccess()` | `isAuthorized(sessionId, action)` | `authenticator.py` |
| `authorizingDispense()` | `requestDispense(sessionId, patientID, drugID, dose)` | `dispensing.py` |
| `handleFault()` | `reportFault(faultType, component, description)` | `fault_monitor.py` |
| `updateInventory(m, q, DISPENSE)` | `removeMedication(drugID, amount)` | `inventory_manager.py` |
| `updateInventory(m, q, RESTOCK)` | `finishReplenish(sessionId)`, then private `__addMedication` | `inventory_manager.py` |
| `systemMode = Fault` | The `SAFE` mode | `operational_mode.py` |
| `o_lockCommand[d]` | `setLock(actuatorID, locked)`: True locks, False unlocks | `actuator.py`, `simulation.py` |
| `i_doorSensor[d]` | The door sensor reading: 1 closed, 0 open | `sensor.py`, `drawer.py` |
| `m_dispenseAuthorization` | Orders received from the Monitoring System | `dispensing.py` |

| Document assumption | How the code holds it |
|---|---|
| Quantity in a slot is never negative | `removeMedication` rejects more than is held |
| A dispense can't remove more than is in the slot or lot | Stock is removed one unit at a time, only from a batch with stock |
| A lot's expiry date never changes | A restock with a different expiry for an existing lot is rejected |
| The current date only moves forward | `Clock.skip` only ever adds time |
| Each slot holds one medication | Each drug has one drawer, and restocking only adds to that drug's own drawer |

## USES (no cycles)

```
main         -> Display, and the modules below (Actuator and Sensor are not reachable from the loop)
Override     -> Dispensing, Authenticator, EventLogger
Dispensing   -> Inventory, Drawer, Mode, Fault Monitor, Authenticator, EventLogger, Transmission
Inventory    -> Fault Monitor, Drawer, Mode, Authenticator, EventLogger
Fault Monitor-> Mode, Drawer, Sensor, Authenticator, EventLogger, Transmission
Mode         -> Authenticator, EventLogger
Authenticator-> EventLogger
EventLogger  -> Transmission
Drawer       -> Actuator, Sensor
```

Three calls in the doc would create cycles, so they go the other way:

- Drawer does not report to Fault Monitor. Fault Monitor checks Drawer.
- Operational Mode does not ask Fault Monitor. The hardware verdict is passed in as a parameter.
- Dispensing does not ask Override. Override calls Dispensing, which re-checks authorization itself.

## Change drill (Week 6: "which module changes, and what does not?")

| TA says | What changes | Interface change? |
|---|---|---|
| "Switch to a different sensor" | `sensor.py` only | No |
| "Different lock model" | `actuator.py` only | No |
| "Fingerprint instead of PIN" | `authenticator.py` `__checkCredentials`, and the prompt in `display.py` | No |
| "Session timeout is 2 minutes" | `authenticator.py` `__TIMEOUT_SECONDS` | No |
| "Dispensing allowed in maintenance" | `operational_mode.py` `__PERMITTED` | No |
| "Allow a 10% dose tolerance" | `dispensing.py` `__validateRequest` | No |
| "Six drawers" | `NUMBER_OF_DRAWERS` in `main.py`, and stock in `inventory_manager.py` | No |
| "Add a temperature fault" | `sensor.py` `__LIMITS`, `fault_monitor.py` `__FAULT_TYPES` and `__detectFault`, plus the fake sensor in `simulation.py` (cross-cutting) | No |
| "Move logs to a database" | `storage.py` only | No |
| "Use a different screen" | `display.py` only, or one import line to switch to `display_terminal.py` | No |
| "New message format" | `transmission.py` only, agreed with the Monitoring team | External interface only |

After any change, update that requirement's row in the traceability table and re-run its scenario.

## Update the D2 doc to match

| Module | Doc says | Code does |
|---|---|---|
| Authenticator | exports validateSession, recordActivity | private |
| | exports isAuthenticated(userID, sessionID) | replaced by `isAuthorized(sessionId, action)` |
| | | adds `unlockAccount(sessionId, badge)` |
| Dispensing | exports validateRequest | private |
| | | adds `releaseForOverride(sessionId, drugID)` |
| | "Change:" is blank | a dispensing rule changes, e.g. a dose tolerance |
| Inventory | exports getMedication, getQuantity, checkExpiry, addMedication, restoreInventory | removed or private; callers use `checkDispensable(drugID)` and `getInventory(sessionId)` |
| | | adds `startReplenish`, `finishReplenish` |
| EventLogger | exports restoreLogs | private |
| | | `logEvent` also takes optional details for the Monitoring format |
| | "Requester unauthorized: access_denied" | the caller checks VIEW_LOGS |
| Fault Monitor | exports detectFault | private |
| | reportFault(fault), resolveFault(faultID) | `reportFault(faultType, component, description)`, `resolveFault(sessionId, faultID)` |
| | checkHardwareStatus "normal" | also requires no open critical fault |
| Operational Mode | setMode(newMode), resumeNormalOperation() | `setMode(sessionId, newMode)`, NORMAL and MAINTENANCE only; `resumeNormalOperation(sessionId, hardwareStatus)` |
| | | adds `completeStartup(hardwareStatus)` |
| Transmission | exports queueMessage | private |
| | exports acknowledgeMessage, plus the "acknowledged" rows and the Effects line about acknowledgements | removed: the Monitoring System sends no reply |
| | "failed", "partial_success" and "Synchronization failures are logged and retried" | removed, for the same reason |
| | | adds `receiveCommand()`, `getPendingCount()`, `takeSentMessages()` |
| | sendMessage(message) | `sendMessage(messageType, content)` |
| EventLogger (hourly) | not in the doc | adds `sendHourlyLog()` |
| Operational Mode (freeze) | not in the doc | adds `freeze()` and the FROZEN mode |
| New requirements | not in D1 | add IDs for the FREEZE and SHUTDOWN commands, then put them on the buttons |
| US-LOG-01 | uploads weekly | now hourly |
| Dispensing (orders) | no order expiry, and no list of orders | adds `getUserOrders(sessionId)`. Orders now carry an expiry date, and an expired order is rejected. This is a new decision with no D1 ID, so add it |
| US-COM-01 | monitoring confirms receipt | no reply now, so reword it |
| Sensor | no operations listed; status and health rows | `readSensor(sensorID)` only; delete those rows |
| Drawer | no operations listed; contents return MedicationList | list the 5 above; contents return an item count |
| Actuator | also lists ActuatorUnresponsive, InvalidCommand, HardwareConnectionFailure | verdicts are ActuatorNotFound, ActuatorFailure, and `unknown` for no response |
| Override | requestOverride(personnelID, reason), verifyAuthorization, recordOverride | `requestOverride(sessionId, drugID, reason)`; the other two are private |
| Display | refers to an ADC Controller, uses most modules | no controller: `main.py` runs the loop and Display uses nothing; list the 11 operations (including `getChoice` and `showOrders`) |
| Precise spec table | FR-AUT-01 | D1's ID is FR-AUTH-01 |

## Fix in the precise specification

| Where | Problem | Change it to |
|---|---|---|
| Dispense invariant | It's reversed: `dispensing = False ⇒ ... ∧ fault = True` | `dispensing = True ⇒ ... ∧ fault = False` |
| `handleFault` post | The first line is garbled, and has no closing bracket | `criticalFaultDetected = True ⇒ systemMode = Fault ∧ ...` |
| `handleFault`, and `D` in dispensing | They say any fault, but a power failure keeps running (D1 assumption 3) | Say critical fault |
| `handleFault` invariant | `¬c_sessionActive ∧ ¬c_accessGranted` always would block the technician's recovery and the charge nurse's override | Sessions open when the fault happens are terminated, and new ones are only useful for recovery or an override. Normal dispensing stays disabled |
| `handleFault` post | Uses `o_unlockCommand`, which isn't in the variable table | `o_lockCommand[d] = True` |
| Variable table | `faultDetected`, `systemMode`, `i_authenticationResult` and others are used but not listed, and some Type/Domain cells are blank | Add them and fill them in |
| 4-variable model | There's no `OUT` relation, and no NAT relation for the drawers | Add `c_drawerLocked[d] = o_lockCommand[d]`, and that a lock can't engage on an open drawer |
| `IN` | Says `m_presentedCredentials`; the table says `m_credentialPresented` | Use one name |

## Other limits

- Modes are plain strings in a transition table. Week 6 suggests an enum, which we skipped to keep it simple.
- Python's `__private` blocks normal access, but `obj._Class__name` could still get in. No module does this.
- The destructors print to the terminal that started the program, not to the window.
- The log checksum is a simple one.
- The message format comes from the Monitoring team. Their example only shows `restock`, so the other `event_type`, `operating_status`, `availability_status`, `access_action` and `severity` values, and the `unit` of `ADC-78`, are the values we chose within that format.
- The key check on incoming orders and commands stays, because the doc requires it, but no button triggers a failure any more.
