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
| EventLogger (`event_logger.py`) | Log format, checksum | `logEvent`: most modules. `getEventHistory`, `getUserEvents`, `verifyLogIntegrity`, `sendPeriodicLog`: main | `__restoreLogs`, `__readRecords`, `__toEvent`, `__checksum` |
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
| ADC to Monitoring | Every logged event | Every 5 minutes, no reply |
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
| "Send logs at a different rate" (this really happened: hourly became 5 minutes at the Monitoring team's request) | `event_logger.py` `__SEND_INTERVAL_SECONDS`. The demo skip button only needs its label and amount changed if it should match | No |
| "Dispensing allowed in maintenance" | `operational_mode.py` `__PERMITTED` | No |
| "Allow a 10% dose tolerance" | `dispensing.py` `__validateRequest` | No |
| "Six drawers" | `NUMBER_OF_DRAWERS` in `main.py`, and stock in `inventory_manager.py` | No |
| "Add a temperature fault" | `sensor.py` `__LIMITS`, `fault_monitor.py` `__FAULT_TYPES` and `__detectFault`, plus the fake sensor in `simulation.py` (cross-cutting) | No |
| "Move logs to a database" | `storage.py` only | No |
| "Use a different screen" | `display.py` only, or one import line to switch to `display_terminal.py` | No |
| "New message format" | `transmission.py` only, agreed with the Monitoring team | External interface only |

After any change, update that requirement's row in the traceability table and re-run its scenario.

## Update the D2 doc to match

Checked against the 42-page draft (`temp_del_2_file.pdf`) on 2026-11-06. Page numbers are from that PDF. Exported operations and their parameters all match the code; these are the things that don't.

### The doc contradicts the code

| Page | Doc says | Change it to |
|---|---|---|
| 3, 41 | FR-AUT-01 | FR-AUTH-01. That's D1's ID, and the code already uses it |
| 20-23 | `sendHourlyLog`, "one hour", "Hourly transmission not due" | `sendPeriodicLog`, 5 minutes (300 seconds), "Periodic transmission not due". Timer also restarts at startup. Add `__SEND_INTERVAL_SECONDS` to the private list, and "how often logs are sent" to the Secret |
| 11, 13 | `___checkCredentials`, `___USERS`, `___PERMISSIONS`, `___sessions`, `___failed_attempts`, `___TIMEOUT_seconds` | `__checkCredentials`, `__USERS`, `__PERMISSIONS`, `__sessions`, `__failedAttempts`, `__TIMEOUT_SECONDS`. Also write `__validateSession` and `__recordActivity` with their underscores |
| 15 | completeDispense, contents unreadable: "SensorFailure" | The verdict is `"failed"`. The order stays IN_PROGRESS, because nobody knows whether a dose left |
| 15-16 | cancelDispense "automatically cancels", verdict "Not cancelled" | The user chooses Cancel. The verdict is `"rejected"` |
| 16 | getUserOrders returns orders "belonging to" the user | Every order, but only that user's requests |
| 17 | `__requests` is "# of currently active" requests | A dictionary of open and closed requests, by request ID |
| 19 | removeMedication "-1 from the inventory" | Subtracts `amount`, which can be more than 1 when more was physically taken |
| 23 | CommunicationManager | Transmission |
| 26 | Override "valid for one session" | Valid for one request, as page 27 already says |
| 28 | "safe or fault mode" (twice) | There is no fault mode. Dispensing is refused in UNKNOWN, MAINTENANCE, SAFE and FROZEN. SAFE still permits OVERRIDE |
| 30 | Secret includes encryption and retry logic | A shared key stands in for the encrypted connection (NFR-COM-02). The retry is `synchronizePendingMessages`, run every cycle |
| 31 | "Message acknowledgements allow the ADC to determine..." | Delete. It contradicts page 30: no replies come back |
| 32 | `takeSentMessage()` | `takeSentMessages()` |
| 34 | Actuator gives status to "Drawer Module and Fault Monitor" | Drawer only |
| 37 | Exception DrawerAlreadyLocked; "Updates the recorded drawer state" | Delete both. The code has no such verdict, and Drawer stores no state: it reads the hardware every time |
| 38-40 | ADC Controller, ControllerUnavailable, DisplayFailure, InputUnavailable, InformationUnavailable, "utilizes dang near every module" | `main.py` runs the loop and Display uses nothing. The only input error is a non-number, where `getNumber` returns None |

### Errors in the precise specification (pages 4-9)

| Where | Problem | Change it to |
|---|---|---|
| Dispense invariant | Reversed: `dispensing = False ⇒ ... ∧ fault = True` | `dispensing = True ⇒ ... ∧ fault = False` |
| Dispense `D` | Leaves out mode, medication expiry (FR-DSP-02), order expiry and already-dispensed, all of which the code checks. "fault" means any fault, but a power failure keeps running | Add them, and say critical fault |
| `handleFault` post | First line is garbled (requires `c_unauthorizedFlag = True`), and has no closing bracket | `criticalFaultDetected = True ⇒ systemMode = Fault ∧ ...` |
| `handleFault` invariant | `¬c_sessionActive ∧ ¬c_accessGranted` always would block the technician's recovery and the charge nurse's override, both of which the code allows | Sessions open at the fault are terminated. Afterwards only recovery and override are permitted, and normal dispensing stays disabled |
| `handleFault` post | `o_unlockCommand` isn't in the variable table | `o_lockCommand[d] = True` |
| `updateInventory` pre | Allows q > stock on DISPENSE, which breaks its own invariant | Add `operation = DISPENSE ⇒ q ≤ stock[m]` |
| Variable table | `i_authenticationResult`, `systemMode`, `faultDetected`, `stock` and others are used but not listed. Many Type/Domain cells are blank, and "Grant or Deny" is on the `o_sessionControl` row instead of `o_accessDecision` | Add them and fill them in |
| Variable table | `m_credentialsValid` and `i_permissionData` come from an "external" authority | They come from the private tables in Authenticator. Say this stands in for the hospital's system |
| 4-variable model | No `OUT` relation, and no NAT relation for the drawers. FROZEN isn't specified | Add `c_drawerLocked[d] = o_lockCommand[d]`, that a lock can't engage on an open drawer, and the FREEZE behaviour |
| `IN` | `m_presentedCredentials`; the table says `m_credentialPresented` | Use one name |

### Missing, and worth marks

| What | Rubric | Where to get it |
|---|---|---|
| External ADC-Monitoring interface: provides, requires, behaviour when the other side is down | Criterion 3 | "External interface" above, and the header of `transmission.py` |
| Any diagram. The handout requires them embedded. Page 10 is only two lecture slides (the DoseChecker example), so delete it | Criteria 1, 3 | Decomposition and USES (above), and the D1 state machine as realized in `operational_mode.py` |
| "How the secret is implemented" for Inventory Manager and Operational Mode. Drawer's is one line and doesn't name `__drawers` | Criterion 3 | "Module interfaces" above |
| Semantics for showMenu and the 9 Display operations after it. Page 40 stops at a bare heading | Criterion 3 | Docstrings in `display.py` |
| Traceability rows for NFR-FD-01, NFR-FD-02, NFR-FD-04 and NFR-AUT-02. Modules Operational Mode, Drawer and Display. `[TBD]` on Actuator and Sensor. "N/A" specs. Classes and functions in the code column | Criterion 5 | "Precise specification to code" above |
| Implementation notes, introduction, assumptions and decisions | Criteria 1, 4, 6 | Not written yet |

### Say in "what changed since D1"

| ID | Change |
|---|---|
| US-LOG-01 | Weekly upload is now every 5 minutes, at the Monitoring team's request |
| US-COM-01 | "Monitoring system shall confirm receipt" is gone: there are no replies |
| NFR-FD-01 | D1 says losing communication enters the safe state, but D1 decision 2 says it doesn't stop the cabinet. The code follows decision 2 |
| US-INV-02, US-STAT-01 | D1 uses each ID for two different stories. Give the second ones new IDs |
| NFR-AUT-01 | D1 says keycard or camera. The code uses badge and PIN, behind `__checkCredentials` |
| FREEZE, SHUTDOWN, order expiry | New, with no D1 ID. Add IDs, then put them on the "New requirement" buttons in both display files |
| FR-ALM-01 | Requires a fault type and brief description. The agreed message only carries the category (`malfunction_type`) and severity: `faultType` and `description` are never sent. Either amend the requirement, or agree new fields with the Monitoring team |

### Clean up before submitting

- Page 2: "(HERE, ill talk...)", "We changed blah blah blah", and the empty "Monitoring System:" heading. Sub-teams submit separately.
- Page 40: the "Functions and Files we need" scratch list.
- Margin comments BL1 (it has a Google Docs link) and BL2.
- Numbering: Override has "6. Effects" and "7. Exceptions", two modules are numbered 7, and Operational Mode, Drawer and Display have no number.
- Cover page: replace "Team Document" with the course, sub-team 78 and names, as in D1.
- Draft introduction: FR-ALM-01 says "immediately"; the 2 seconds is NFR-COM-01. "Locks all drawers until the fault is resolved" needs the override exception (US-AUT-02).

### In the code, not changed

- `config.py` is imported by nothing, and disagrees with the code (`CABINET_ID` is `ADC-78-01`; messages use `ADC-78`). Delete it, or expect a TA to ask.

## Other limits

- Modes are plain strings in a transition table. Week 6 suggests an enum, which we skipped to keep it simple.
- Python's `__private` blocks normal access, but `obj._Class__name` could still get in. No module does this.
- The destructors print to the terminal that started the program, not to the window.
- The log checksum is a simple one.
- The message format comes from the Monitoring team. Their example only shows `restock`, so the other `event_type`, `operating_status`, `availability_status`, `access_action` and `severity` values, and the `unit` of `ADC-78`, are the values we chose within that format.
- The key check on incoming orders and commands stays, because the doc requires it, but no button triggers a failure any more.
