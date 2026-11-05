# ADC demo (Sub-team 78)

Software implementation of an ADC (Automated Dispensing Cabinet) for use in hospital environments.

## Start it

Open a terminal in this folder and run the command below. Do this before the TAs arrive, and leave the window open.

```bash
python main.py
```

Every start resets the cabinet, so the demo always begins the same way.

## How to use the window

- **Blue buttons** are what a person does at the cabinet.
- **Grey buttons** make something happen for the demo, like breaking a lock. They need no login.
- **Every button shows its requirement IDs.** "New requirement" means it has no ID in D1 yet.
- **The bottom bar** is where you answer questions: type and press Enter, or click a purple button.
- **The numbered buttons don't respond** while the bottom bar is waiting for an answer. Answer it first.
- **Logging in** automatically logs out whoever was logged in before.
- **A critical fault logs everyone out.** Log in again as the technician to fix it, or as the charge nurse for an override.

## Logins

| Role | Badge | PIN |
|---|---|---|
| Nurse | `N001` | `1111` |
| Charge nurse | `C001` | `2222` |
| Pharmacist | `P001` | `3333` |
| Technician | `T001` | `4444` |
| Admin | `A001` | `5555` |

## Who can do what

| Action | Nurse | Charge nurse | Pharmacist | Technician | Admin |
|---|---|---|---|---|---|
| 3 - Dispense | Yes | Yes | No | No | No |
| 4 - Restock | No | No | Yes | No | No |
| 5 - Emergency override | No | Yes | No | No | No |
| 6 - View inventory | Yes | Yes | Yes | Yes | No |
| 7 - Resolve fault | No | No | No | Yes | No |
| 8 - Resume normal | No | No | No | Yes | No |
| 9 - Maintenance on/off | No | No | No | Yes | No |
| 10 - View logs | No | No | No | No | Yes |
| 11 - Verify logs | No | No | No | No | Yes |
| 12 - Unlock account | No | No | No | No | Yes |
| 13 - My orders | Yes | Yes | No | No | No |

A denied attempt is refused and flagged in the log.

## What each mode allows

The top bar shows the mode. Even with the right role, the mode can refuse an action.

| Mode | Dispense | Restock | Emergency override |
|---|---|---|---|
| Operational (green) | Yes | Yes | Yes |
| Under Maintenance (amber) | No | Yes | No |
| SAFE STATE (red) | No | No | Yes, except on a drawer with a fault |
| Status Unknown (grey) | No | No | No |
| FROZEN (dark blue) | No | No | No |

## What's in the cabinet

| Patient | Drug | Dose (mg) | Drawer | Stock | Note |
|---|---|---|---|---|---|
| `P-1001` | `LORA` Lorazepam | `2` | D1 | 20 | |
| `P-1001` | `ACET` Acetaminophen | `1000` | D2 | 30 | |
| `P-1002` | `AMOX` Amoxicillin | `500` | D3 | 15 | |
| `P-1002` | `MORP` Morphine | `10` | D4 | 5 | The medication is always expired (batch 1050) |
| `P-1003` | `ACET` Acetaminophen | `1000` | D2 | Shares the 30 above | The order itself is always expired |

Each order can only be dispensed once. Re-run the program to get them all back.

Click **13 - My orders** at any time to see which orders are valid and why, plus everything the logged-in user has requested, allowed or refused.

## How we talk to the Monitoring System

| What | When | Reply from them? |
|---|---|---|
| Every logged event, including all attempts | Every hour | None |
| Malfunction and maintenance request | As soon as the fault is found | None |
| Malfunction resolved | As soon as it's verified | None |
| Authorized orders, from them to us | When they send one | None |
| FREEZE command, from them to us | When they send one | We freeze |
| SHUTDOWN command, from them to us | When they send one | We shut down |

Everything we send is shown in the Activity panel in their format, followed by `SENT`. If the network is down, it waits and goes out when the network returns.

## The demo

Run these in order from a fresh start, and the fault numbers will match. If you jump around, use the fault number shown on screen.

**Short on time?** Do demos 1, 3 and 4. They cover authenticate, dispense and log, plus a hardware fault and a dropped connection.

### Demo 1: Normal dispense (Nurse)

Handout scenario 1. FR-AUTH-01, FR-DSP-01, FR-LOG-01.

| Do this | You should see |
|---|---|
| **1 - Log in**: `N001`, `1111` | User: Nina Patel (NURSE) |
| **3 - Dispense**: `P-1001`, `LORA`, `2` | "drawer D1 is unlocked", and purple buttons appear |
| **Take dose and close** | "Dispense complete", and D1 is LOCKED |
| **6 - View inventory** | LORA quantity went from 20 to 19 |
| **24 - Skip 1 hour** | "Hourly log", then each event in their format with `SENT`, including `dispense_completed`. The session also ends, since an hour passed |

### Demo 2: Requests that get refused (Nurse)

FR-DSP-01, FR-DSP-02, NFR-AUT-01, NFR-AUT-04. Every drawer stays locked.

| Do this | You should see |
|---|---|
| **1 - Log in**: `N001`, `1111` | User: Nina Patel (NURSE) |
| **3 - Dispense**: `P-1001`, `ACET`, `5` | "Dose Mismatch" |
| **3 - Dispense**: `P-1002`, `MORP`, `10` | "batch 1050 is expired" |
| **3 - Dispense**: `P-1001`, `LORA`, `2` | "already been dispensed" |
| **3 - Dispense**: `P-1001`, `AMOX`, `500` | "no authorized order" |
| **3 - Dispense**: `P-1003`, `ACET`, `1000` | "This order expired on 2020-01-01" |
| **13 - My orders** | Each order with valid or why not, and "Your requests" lists your dispense from Demo 1 as allowed, plus all five of these attempts with the reason each was refused |
| **5 - Emergency override**: `ACET`, `CODE_BLUE` | "You are not authorized to override" |
| **4 - Restock**: `LORA`, `2000`, `2099-01-01`, `10` | "you may not restock" |

### Demo 3: Hardware fault, drawer left open (Nurse, then Technician)

Handout scenario 3. FR-ALM-01, FR-ALM-02, FR-COM-02, NFR-FD-01, NFR-FD-02, US-FD-02.

| Do this | You should see |
|---|---|
| **3 - Dispense**: `P-1002`, `AMOX`, `500` | D3 is unlocked |
| **Take dose, leave drawer open** | Top bar turns red, SAFE STATE, D3 is OPEN, F-1 is listed, "Dispense NOT confirmed", and the nurse is logged out. Activity shows `malfunction` and `maintenance_request`, each with `SENT` |
| **1 - Log in**: `N001`, `1111`, then **3 - Dispense**: `P-1001`, `ACET`, `1000` | "not permitted in the current mode" |
| **1 - Log in**: `T001`, `4444` | User: Tom Reid (TECHNICIAN) |
| **7 - Resolve fault**: `F-1` | "Resolve: rejected", because it isn't fixed yet |
| **28 - Repair all** | D3 is LOCKED, still SAFE STATE |
| **8 - Resume normal** | "Resume: rejected", because F-1 is still open |
| **7 - Resolve fault**: `F-1` | "Resolve: resolved", and `malfunction_resolved` with `SENT` |
| **8 - Resume normal** | "Resume: normal_mode", and the top bar is green |

### Demo 4: Connection lost, restock still works (Pharmacist)

Handout scenarios 2 and 4. FR-COM-01, NFR-FD-03, US-INV-01.

| Do this | You should see |
|---|---|
| **20 - Network down/up** | Monitoring: disconnected |
| **1 - Log in**: `P001`, `3333` | User: Priya Shah (PHARMACIST) |
| **4 - Restock**: `LORA`, `2000`, `2099-01-01`, `10` | "count increased by 10", "Saved locally" |
| **6 - View inventory** | LORA now also has batch 2000 with quantity 10 |
| **24 - Skip 1 hour** | "Hourly log", but nothing says `SENT`. Messages waiting goes above 0 |
| **20 - Network down/up** | Monitoring: connected, 0 messages waiting, and the waiting events appear with `SENT`, including `restock` |

### Demo 5: Emergency override (Charge nurse)

US-AUT-02, NFR-SEC-01.

| Do this | You should see |
|---|---|
| **1 - Log in**: `C001`, `2222` | User: Carlos Diaz (CHARGE_NURSE) |
| **5 - Emergency override**: `ACET`, `convenience` | "not an approved emergency reason" |
| **5 - Emergency override**: `MORP`, `CODE_BLUE` | "batch 1050 is expired", because an override can't release expired stock |
| **5 - Emergency override**: `ACET`, `CODE_BLUE` | "OVERRIDE approved and logged", D2 unlocks |
| **Take dose and close** | "Dispense complete" |

### Demo 6: Logs (Nurse is refused, then Admin)

FR-LOG-01, NFR-AUT-03, US-LOG-02.

| Do this | You should see |
|---|---|
| **1 - Log in**: `N001`, `1111` | User: Nina Patel (NURSE) |
| **10 - View logs** | "Access denied" |
| **1 - Log in**: `A001`, `5555` | User: Alex Kim (ADMIN) |
| **10 - View logs**: leave it blank and press Enter | The full history, with times and users |
| **10 - View logs**: `C001` | Only the charge nurse's events, including OVERRIDE_APPROVED |
| **11 - Verify logs** | "Log integrity: valid" |
| **32 - Tamper log** | "Log file edited directly" |
| **11 - Verify logs** | "Log integrity: invalid" |

### Demo 7: Maintenance (Technician, then Nurse)

US-STAT-01.

| Do this | You should see |
|---|---|
| **1 - Log in**: `T001`, `4444` | User: Tom Reid (TECHNICIAN) |
| **9 - Maintenance on/off** | Top bar turns amber, Under Maintenance |
| **1 - Log in**: `N001`, `1111` | User: Nina Patel (NURSE) |
| **3 - Dispense**: `P-1001`, `ACET`, `1000` | "not permitted in the current mode" |
| **1 - Log in**: `T001`, `4444` | User: Tom Reid (TECHNICIAN) |
| **9 - Maintenance on/off** | Top bar is green, Operational |

### Demo 8: Other hardware faults (Technician)

FR-ALM-02, NFR-FD-01, NFR-FD-02. Each critical fault logs you out, so you log in again to fix it.

| Do this | You should see |
|---|---|
| **25 - Break a lock**: `D2` | SAFE STATE, D2 is UNKNOWN, F-2 is listed, not logged in |
| **1 - Log in**: `T001`, `4444`, then **28 - Repair all**, then **7 - Resolve fault**: `F-2`, then **8 - Resume normal** | Back to Operational |
| **26 - Break a sensor**: `D3` | SAFE STATE, D3 is UNKNOWN, F-3 is listed, not logged in |
| **1 - Log in**: `T001`, `4444`, then **28 - Repair all**, then **7 - Resolve fault**: `F-3`, then **8 - Resume normal** | Back to Operational |
| **27 - Power failure** | F-4 MAJOR is listed, but it stays Operational and you stay logged in. Activity shows `"malfunction_type": "electrical"` with `SENT` |
| **28 - Repair all**, then **7 - Resolve fault**: `F-4` | F-4 is gone |
| **1 - Log in**: `N001`, `1111`, then **3 - Dispense**: `P-1001`, `ACET`, `1000` | D2 is unlocked |
| **Take dose and close, but the lock jams** | SAFE STATE, D2 is UNLOCKED, F-5 LOCK_FAILURE is listed, not logged in |
| **1 - Log in**: `T001`, `4444`, then **28 - Repair all**, then **7 - Resolve fault**: `F-5`, then **8 - Resume normal** | Back to Operational |

If the jammed lock stays unfixed for more than 30 seconds, a second fault (F-6) appears by itself. Resolve it too before resuming.

### Demo 9: Session timeout and lockout (Nurse, then Admin)

NFR-AUT-02, US-AUT-01, US-AUT-04.

| Do this | You should see |
|---|---|
| **1 - Log in**: `N001`, `1111` | User: Nina Patel (NURSE) |
| **29 - Skip 3 minutes** | "Session ended", not logged in |
| **1 - Log in**: `N001`, `0000`, three times | "Invalid credentials" each time |
| **1 - Log in**: `N001`, `0000`, a fourth time | "Account Temporarily Locked" |
| **1 - Log in**: `N001`, `1111` | Still locked, even with the right PIN. This 5th attempt also flags a breach in the log |
| **1 - Log in**: `A001`, `5555`, then **12 - Unlock account**: `N001` | "Unlock: success" |
| **1 - Log in**: `N001`, `1111` | "Welcome" |

### Demo 10: New order from the Monitoring System (Nurse)

FR-DSP-01.

| Do this | You should see |
|---|---|
| **22 - New order**: `O9`, `P-2000`, `AMOX`, `500`, `2099-12-31` | Nothing yet. It's picked up at the next dispense or **13 - My orders** |
| **3 - Dispense**: `P-2000`, `AMOX`, `500`, then **Take dose and close** | "Dispense complete", so the new order worked |

### Demo 11: Freeze command from the Monitoring System

New requirement.

| Do this | You should see |
|---|---|
| **21 - Monitoring: Freeze** | Top bar turns dark blue, FROZEN, "FREEZE command received" |
| **3 - Dispense**: `P-1001`, `LORA`, `2` | "not permitted in the current mode" |
| **1 - Log in**: `C001`, `2222`, then **5 - Emergency override**: `ACET`, `CODE_BLUE` | "not permitted in the current mode", so even an override is refused |
| **1 - Log in**: `T001`, `4444`, then **8 - Resume normal** | "Resume: rejected" |
| **30 - Restart software** | Back to Operational. A restart is the only way out of a freeze |

### Demo 12: Restart and corrupted inventory

NFR-FD-03, US-FD-03.

| Do this | You should see |
|---|---|
| **1 - Log in**: `N001`, `1111`, then **6 - View inventory** | The quantities from earlier are still there after the restart |
| **31 - Corrupt inventory** | SAFE STATE, INVENTORY_CORRUPT is listed |
| **1 - Log in**: `N001`, `1111`, then **6 - View inventory** | "Inventory information is unavailable" |
| **3 - Dispense**: `P-1001`, `LORA`, `2` | "not permitted in the current mode" |

A corrupted inventory can't be fixed from the menu. Click **0 - Exit** and run `python main.py` again.

### Demo 13: Shutdown command from the Monitoring System (after re-running)

New requirement.

| Do this | You should see |
|---|---|
| **23 - Monitoring: Shutdown** | "SHUTDOWN command received", and a **Close** button |
| **Close** | The window closes. The shutdown messages appear in the terminal, including "drawers locked" |

## If something looks wrong

| What happened | Why, and what to do |
|---|---|
| Numbered buttons don't respond | The bottom bar is waiting for an answer. Answer it first |
| "already been dispensed" | Each order works once. Re-run the program |
| "Access denied" or "you may not" | Wrong role for that action. Check the "Who can do what" table |
| "not permitted in the current mode" | The mode is refusing it. Check the top bar |
| "Resume: rejected" | Log in as the technician, click **28 - Repair all**, resolve every listed fault, then resume |
| Suddenly logged out | 3 minutes of inactivity, or a critical fault. Log in again |
| FROZEN won't go away | Only **30 - Restart software** clears it |

## Say these before a TA finds them

- The Monitoring System is a fake inside this program. Integration with Part B isn't done.
- The cabinet hardware is simulated, in `simulation.py`.
- A shared key stands in for the authenticated, encrypted connection, so there's no real encryption (NFR-COM-02).
- PINs are stored as plain text.
- The hourly log and fault checks run on a timer only in the window. The terminal version waits for you to press Enter.

## Using the terminal instead

If the window has a problem, change this line in `main.py` and run it again. Nothing else needs to change:

```python
from display_terminal import Display
```

## More detail

[DESIGN_NOTES.md](DESIGN_NOTES.md) has the module interfaces, USES hierarchy, change drill and the list of D2 doc updates.
