<<<<<<< HEAD
# ADC demo (Sub-team 78)

Run from inside `adc_simple`:

```bash
python main.py
```

This opens the ADC window. To use the terminal version instead, change the import in `main.py` to `from display_terminal import Display`. Nothing else changes.

| Badge / PIN | Role | Can do |
|---|---|---|
| N001 / 1111 | Nurse | dispense, view inventory |
| C001 / 2222 | Charge nurse | also override |
| P001 / 3333 | Pharmacist | restock |
| T001 / 4444 | Technician | maintenance, resolve faults, resume |
| A001 / 5555 | Admin | logs, unlock accounts |

Orders: `P-1001` LORA 2, ACET 1000. `P-1002` AMOX 500, MORP 10 (batch 1050 is expired).

## Try these

The numbers are the numbered buttons. Anything else is typed into the box at the bottom. After a dispense or override, the numbered `1` to `5` below are the purple buttons, in order.

| Scenario | Keys |
|---|---|
| Dispense | `1` N001 1111, `3` P-1001 LORA 2, `1` |
| Wrong dose | `3` P-1001 ACET 5 |
| Expired | `3` P-1002 MORP 10 |
| Nurse tries override | `5` ACET CODE_BLUE |
| Drawer left open (alarm, safe state) | `3` P-1002 AMOX 500, `2` |
| Show the alarm reached Monitoring | `24` |
| Fix it | `1` T001 4444, `7` F-1 (rejected), `28`, `7` F-1 (resolved), `8` |
| Network loss, then back | `20`, do anything, `20` |
| Restock | `1` P001 3333, `4` LORA 2000 2099-01-01 10 |
| Override | `1` C001 2222, `5` ACET CODE_BLUE, `1` |
| Tampered log | `1` A001 5555, `32`, `11` |
| Broken lock or sensor | `25` D2, or `26` D2 |
| Power failure (keeps running) | `27` |
| Maintenance | `1` T001 4444, `9` |
| Session timeout | log in, `29` |
| Lockout | `1` with a wrong PIN, 4 times |
| Restart keeps data | `30` |
| Corrupt inventory (do this last, then re-run the program) | `31` |
| New or forged order | `22`, or `23` then any dispense then `24` |

## How the code follows Weeks 5 and 6

| Course rule | In the code |
|---|---|
| One module = one file, named for the module | Each file below has one class, and starts with its responsibility, secret and anticipated change |
| "The exported operations are the module's public methods. Everything else is private." | Each file has a PUBLIC INTERFACE section and a PRIVATE section |
| "A public field is a leaked secret." | Every field in every class is `self.__name` |
| A secret is "private fields and constants" | PINs, permissions, fault types, time limits and tables are `__private` class constants |
| Public methods have pre/post in the doc comment | Every public method has a PRE and POST |
| State invariant: set by the constructor, kept by every public method | Stated at the top of each class |
| USES: references the class holds, injected, acyclic | `startSystem` in `main.py` |
| Hardware modules have a simulated implementation behind the same interface | `Hardware` in `simulation.py`, reached only by Actuator and Sensor |
| Invalid state change means "no change plus a log entry" | `OperationalMode.__changeMode` |
| Partner protocol is a secret inside one comms module | Message format and key are inside Transmission |

## Module interfaces

| Module (file) | Secret | Public operation: called by | Private |
|---|---|---|---|
| Authenticator (`authenticator.py`) | How credentials are verified, the users, sessions | `authenticate`, `logout`, `unlockAccount`: main. `getUserIdentity`: Dispensing, Fault Monitor, Override, main. `isAuthorized`: Dispensing, Inventory, Fault Monitor, Mode, Override, main | `__checkCredentials`, `__validateSession`, `__recordActivity` |
| Dispensing (`dispensing.py`) | Dispensing rules, orders, open requests | `requestDispense`, `completeDispense`, `cancelDispense`: main. `releaseForOverride`: Override | `__validateRequest`, `__stockProblem`, `__openDrawer`, `__receiveNewOrders`, `__hasOrder`, `__setOrderStatus`, `__userOf`, `__reject` |
| Inventory Manager (`inventory_manager.py`) | Data structure, how batches are chosen | `getInventory`, `startReplenish`, `finishReplenish`: main. `checkDispensable`, `removeMedication`: Dispensing | `__restoreInventory`, `__checkRestock`, `__addMedication`, `__getQuantity`, `__getNextBatch`, `__checkExpiry`, `__findBatch`, `__saveChange` |
| EventLogger (`event_logger.py`) | Log format, checksum | `logEvent`: most modules. `getEventHistory`, `getUserEvents`, `verifyLogIntegrity`: main | `__restoreLogs`, `__readRecords`, `__toEvent`, `__checksum` |
| Fault Monitor (`fault_monitor.py`) | Fault types, priorities, thresholds, detection | `checkHardwareStatus`, `resolveFault`: main. `reportFault`: Dispensing, Inventory. `getActiveFaults`: Dispensing, main | `__detectFault`, `__hasFaultOn`, `__hasCriticalFault`, `__lockAllDrawers`, `__save` |
| Operational Mode (`operational_mode.py`) | Modes, transitions, what each permits | `getCurrentMode`, `setMode`, `resumeNormalOperation`, `completeStartup`: main. `enterSafeState`: Fault Monitor. `checkOperationAllowed`: Dispensing, Inventory | `__changeMode` |
| Transmission (`transmission.py`) | Message format, key, acks, retries, queue | `sendMessage`: EventLogger, Fault Monitor. `receiveMessage`: Dispensing. `checkConnection`, `synchronizePendingMessages`, `getPendingCount`: main | `__queueMessage`, `__acknowledgeMessage`, `__save` |
| Actuator (`actuator.py`) | How locks are commanded and confirmed | `unlockActuator`, `lockActuator`, `getActuatorStatus`: Drawer | `__sendCommand` |
| Sensor (`sensor.py`) | How readings are collected, valid ranges | `readSensor`: Drawer, Fault Monitor | `__isValid` |
| Drawer (`drawer.py`) | Which lock and sensors belong to each drawer | `listDrawers`, `getDrawerStatus`: Fault Monitor, main. `getDrawerContents`, `unlockDrawer`: Dispensing, Inventory. `lockDrawer`: Dispensing, Inventory, Fault Monitor | fields only |
| Override (`override.py`) | Override rules, approved reasons | `requestOverride`: main | `__verifyAuthorization`, `__recordOverride` |
| Display (`display.py`, or `display_terminal.py`) | Layout, wording, how input is collected | All 10 operations: main | How the window is built and how input is collected |

Helper files, not modules: `main.py` (connects everything and runs the loop), `simulation.py` (fake clock, cabinet and Monitoring System), `storage.py` (saves to files).

## USES (no cycles)

```
main      -> Display, and the modules below (Actuator and Sensor are not reachable from the loop)
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
| "Add a temperature fault" | `sensor.py` `__LIMITS`, `fault_monitor.py` `__FAULT_TYPES` and `__detectFault` (cross-cutting) | No |
| "Move logs to a database" | `storage.py` only | No |
| "Use a different screen" | `display.py` only, or one import line to switch to `display_terminal.py` | No |
| "New message format" | `transmission.py` only, agreed with the Monitoring team | External interface only |

After any change, update that requirement's row in the traceability table and re-run its scenario above.

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
| | "Requester unauthorized: access_denied" | the caller checks VIEW_LOGS |
| Fault Monitor | exports detectFault | private |
| | reportFault(fault), resolveFault(faultID) | `reportFault(faultType, component, description)`, `resolveFault(sessionId, faultID)` |
| | checkHardwareStatus "normal" | also requires no open critical fault |
| Operational Mode | setMode(newMode), resumeNormalOperation() | `setMode(sessionId, newMode)`, NORMAL and MAINTENANCE only; `resumeNormalOperation(sessionId, hardwareStatus)` |
| | | adds `completeStartup(hardwareStatus)` |
| Transmission | exports queueMessage, acknowledgeMessage | private; adds `getPendingCount()` |
| | sendMessage(message) | `sendMessage(messageType, content)` |
| Sensor | no operations listed; status and health rows | `readSensor(sensorID)` only; delete those rows |
| Drawer | no operations listed; contents return MedicationList | list the 5 above; contents return an item count |
| Actuator | also lists ActuatorUnresponsive, InvalidCommand, HardwareConnectionFailure | verdicts are ActuatorNotFound, ActuatorFailure, and `unknown` for no response |
| Override | requestOverride(personnelID, reason), verifyAuthorization, recordOverride | `requestOverride(sessionId, drugID, reason)`; the other two are private |
| Display | refers to an ADC Controller, uses most modules | no controller: `main.py` runs the loop and Display uses nothing; list the 10 operations (including `getChoice`) |
| Precise spec table | FR-AUT-01 | D1's ID is FR-AUTH-01 |

## Known limits (say these before a TA finds them)

- The Monitoring System is a fake in the same program. Part B integration is not done.
- NFR-COM-02: a shared key stands in for the authenticated, encrypted connection. There is no real encryption.
- PINs are plain text, and the log checksum is a simple one.
- Fault checks run each time the screen refreshes, not on a timer.
- Modes are plain strings in a transition table. Week 6 suggests an enum, which we skipped to keep it simple.
- Python's `__private` blocks normal access, but `obj._Class__name` could still get in. No module does this.
- The destructors print to the terminal that started the program, not to the window, so keep it visible if you want to show them on a restart.
=======
# SFWRENG-3K04-ADC
Software implementation of and ADC (Automated Dispensing Cabinet) for use in hospital environments.
>>>>>>> 9d4985100b75cddab2ff34cdae427ad56c073900
