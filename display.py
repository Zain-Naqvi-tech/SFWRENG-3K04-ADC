"""
DISPLAY / GUI MODULE

RESPONSIBILITY: Show ADC information and collect user input.
SECRET: How information is laid out and how input is collected. Other modules do not know it is a window.
ANTICIPATED CHANGE: The screen is replaced or the wording changes. Only this file changes.
                    display_terminal.py has the same interface: change one import in main.py to use it.
EXPORTED OPERATIONS: showStatus, showMenu, showMessage, showAlert, showInventory, showEvents, showOrders,
                     getInput, getNumber, getChoice, promptCredentials
USES: nothing. main.py passes it the information to show, so it can never change another module's data.
"""
import time
import tkinter as tk


class Display:
    """STATE INVARIANT: holds no ADC data, only its own widgets and wording."""

    # US-STAT-01: never say "Operational" unless the mode really is NORMAL.
    __STATUS_TEXT = {
        "NORMAL": "Operational",
        "MAINTENANCE": "Under Maintenance",
        "SAFE": "SAFE STATE - not functioning normally",
        "UNKNOWN": "Status Unknown",
        "FROZEN": "FROZEN by the Monitoring System",
    }

    # Colour always comes with text, so the screen does not rely on colour alone (accessibility).
    __MODE_COLOURS = {"NORMAL": "#1e7d45", "MAINTENANCE": "#b7791f", "SAFE": "#c0392b", "UNKNOWN": "#5b6470",
                      "FROZEN": "#2c4a6e"}
    __DRAWER_COLOURS = {"locked": "#1e7d45", "unlocked": "#b7791f", "open": "#c0392b", "unknown": "#5b6470"}
    __BACKGROUND = "#eef1f4"
    __USER_BUTTON = "#1f5f99"
    __DEMO_BUTTON = "#5b6470"
    __CHOICE_BUTTON = "#7a4fa3"

    # The buttons, with the requirements each one shows. Each key is the choice main.py receives.
    __USER_ACTIONS = {
        "1": "Log in\nFR-AUTH-01", "2": "Log out\nFR-AUTH-01",
        "3": "Dispense\nFR-DSP-01, FR-DSP-02", "4": "Restock\nUS-INV-01, NFR-AUT-01",
        "5": "Emergency override\nNFR-SEC-01, US-AUT-02", "6": "View inventory\nFR-INV-01",
        "7": "Resolve fault\nFR-COM-02", "8": "Resume normal\nUS-FD-02",
        "9": "Maintenance on/off\nUS-STAT-01", "10": "View logs\nFR-LOG-01",
        "11": "Verify logs\nNFR-AUT-03", "12": "Unlock account\nUS-AUT-01",
        "13": "My orders\nFR-DSP-01",
    }
    __DEMO_ACTIONS = {
        "20": "Network down/up\nFR-COM-01", "21": "Monitoring: Freeze\nNew requirement",
        "22": "New order\nFR-DSP-01", "23": "Monitoring: Shutdown\nNew requirement",
        "24": "Skip 1 hour\nFR-LOG-01", "25": "Break a lock\nFR-ALM-02, NFR-FD-01",
        "26": "Break a sensor\nFR-ALM-02, NFR-FD-01", "27": "Power failure\nFR-ALM-02, US-FD-01",
        "28": "Repair all\nUS-FD-02", "29": "Skip 3 minutes\nNFR-AUT-02",
        "30": "Restart software\nNFR-FD-03", "31": "Corrupt inventory\nUS-FD-03",
        "32": "Tamper log\nUS-LOG-02", "33": "Close a drawer\nFR-ALM-02", "0": "Exit",
    }

    def __init__(self):
        self.__menuOpen = False     # True when the next getInput should wait for a menu button
        self.__closed = False       # True once the window has been closed
        self.__menuEnabled = False  # True while the menu buttons can be clicked
        self.__menuButtons = []
        self.__drawerCards = {}     # drawer ID -> its widgets, created the first time we see it

        self.__window = tk.Tk()
        self.__window.title("Automated Dispensing Cabinet")
        self.__window.geometry("1180x720")
        self.__window.minsize(980, 640)
        self.__window.configure(bg=self.__BACKGROUND)
        self.__window.columnconfigure(1, weight=1)
        self.__window.rowconfigure(3, weight=1)
        self.__window.protocol("WM_DELETE_WINDOW", self.__onWindowClosed)
        self.__answer = tk.StringVar()      # the while loop in main.py waits until this is set

        self.__buildBanner()
        self.__buildDrawerRow()
        self.__buildFaultRow()
        self.__buildButtons()
        self.__buildActivity()
        self.__buildInputBar()
        self.showMessage("Cabinet started. Log in to begin.")

    def __del__(self):
        # Destructor: close the window when the program ends.
        self.__window.destroy()

    # ================ PUBLIC INTERFACE (called by main.py) ================

    def showStatus(self, mode, connection, pending, user, drawers, faults):
        """Shows the mode, connection, user, each drawer's status and every active fault."""
        colour = self.__MODE_COLOURS[mode]
        self.__banner.config(bg=colour)
        self.__modeLabel.config(text=self.__STATUS_TEXT[mode], bg=colour)
        self.__modeRequirement.config(bg=colour)
        self.__linkLabel.config(text="Monitoring: " + connection + "  |  " + str(pending) + " messages waiting", bg=colour)
        self.__userLabel.config(text="User: " + user, bg=colour)

        for drawerID in drawers:
            if drawerID not in self.__drawerCards:
                self.__addDrawerCard(drawerID)
            self.__updateDrawerCard(drawerID, drawers[drawerID])

        if len(faults) == 0:
            self.__faultLabel.config(text="No active faults  (FR-ALM-01, FR-ALM-02)", fg=self.__MODE_COLOURS["NORMAL"])
        else:
            text = ""
            for fault in faults:
                text = text + "FAULT " + fault["id"] + "  " + fault["severity"] + "  " + fault["faultType"]
                text = text + " on " + fault["component"] + " - " + fault["description"] + "\n"
            self.__faultLabel.config(text=text.strip(), fg=self.__MODE_COLOURS["SAFE"])

    def showMenu(self):
        """The buttons are always on screen. This makes the next getInput wait for one of them."""
        self.__menuOpen = True

    def showMessage(self, text):
        """Shows a normal message (NFR-FD-04: acknowledges an operation)."""
        self.__write(text + "\n", "normal")

    def showAlert(self, text):
        """Shows an alert. Coloured text plus a beep, so it does not rely on one sense (accessibility)."""
        self.__window.bell()
        self.__write("! " + text + "\n", "alert")

    def showInventory(self, rows):
        """Shows medication names, drawers, quantities and expiry dates (FR-INV-01)."""
        self.__write("\nDRUG   NAME            DRAWER  BATCH  QTY   EXPIRES      STATUS\n", "heading")
        for row in rows:
            line = row["drugID"].ljust(7) + row["name"].ljust(16) + row["drawer"].ljust(8) + row["batch"].ljust(7)
            line = line + str(row["quantity"]).ljust(6) + row["expiry"].ljust(13) + row["status"] + "\n"
            if row["status"] == "expired":
                self.__write(line, "alert")
            else:
                self.__write(line, "normal")
        self.__write("\n", "normal")

    def showEvents(self, events):
        """Shows log events with their time."""
        self.__write("\n#    TIME      EVENT                     USER        DETAILS\n", "heading")
        for event in events:
            line = str(event["seq"]).ljust(5) + self.__formatTime(event["time"]).ljust(10)
            line = line + event["type"].ljust(26) + event["user"].ljust(12) + event["details"] + "\n"
            self.__write(line, "normal")
        self.__write("\n", "normal")

    def showOrders(self, orders, requests):
        """Shows every order with whether it is valid, then what this user has requested, valid or not."""
        self.__write("\nORDER  PATIENT  DRUG  DOSE  EXPIRES     VALID?\n", "heading")
        for order in orders:
            line = order["orderID"].ljust(7) + order["patientID"].ljust(9) + order["drugID"].ljust(6)
            line = line + str(order["dose"]).ljust(6) + order["expiry"].ljust(12) + order["validity"] + "\n"
            if order["validity"] == "valid":
                self.__write(line, "normal")
            else:
                self.__write(line, "alert")
        self.__write("\nYOUR REQUESTS\nPATIENT  DRUG  DOSE  RESULT\n", "heading")
        if len(requests) == 0:
            self.__write("No requests yet.\n", "normal")
        for request in requests:
            line = request["patientID"].ljust(9) + request["drugID"].ljust(6) + str(request["dose"]).ljust(6) + request["verdict"]
            if request["verdict"] == "allowed":
                self.__write(line + "\n", "normal")
            else:
                self.__write(line + " - " + request["reason"] + "\n", "alert")
        self.__write("\n", "normal")

    def getInput(self, prompt):
        """Returns the menu button clicked if showMenu was just called, or "" if a second passes with
        no click, so the loop in main.py keeps running. Otherwise returns what the user typed."""
        if self.__menuOpen == True:
            self.__menuOpen = False
            return self.__waitForMenuButton()
        return self.__askForText(prompt, "")

    def getNumber(self, prompt):
        """Returns a whole number, or None if the input was not one (InvalidInput)."""
        text = self.getInput(prompt)
        if text.isdigit():
            return int(text)
        return None

    def getChoice(self, prompt, options):
        """Shows one button per option ({key: label}) and returns the key of the one clicked."""
        self.__promptLabel.config(text=prompt)
        buttons = []
        for key in options:
            button = self.__makeButton(self.__choiceArea, options[key], key, self.__CHOICE_BUTTON)
            button.pack(side="left", padx=4)
            buttons.append(button)
        answer = self.__waitForAnswer()
        for button in buttons:
            button.destroy()
        return answer

    def promptCredentials(self):
        """Shows the login prompt and returns the credentials for Authenticator. The PIN is hidden."""
        badge = self.__askForText("Badge: ", "")
        pin = self.__askForText("PIN: ", "*")
        return {"badge": badge, "pin": pin}

    # ================ PRIVATE (the secret: how the window is built and how input is collected) ================

    def __buildBanner(self):
        # Row 0, the top bar: its colour shows the mode at a glance (US-STAT-01).
        self.__banner = tk.Frame(self.__window, padx=18, pady=4)
        self.__banner.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.__banner.columnconfigure(0, weight=1)
        self.__modeLabel = tk.Label(self.__banner, fg="white", font=("Segoe UI", 20, "bold"))
        self.__modeLabel.grid(row=0, column=0, rowspan=3, sticky="w")
        self.__linkLabel = tk.Label(self.__banner, fg="white", font=("Segoe UI", 10))
        self.__linkLabel.grid(row=0, column=1, sticky="e")
        self.__userLabel = tk.Label(self.__banner, fg="white", font=("Segoe UI", 10, "bold"))
        self.__userLabel.grid(row=1, column=1, sticky="e")
        self.__modeRequirement = tk.Label(self.__banner, text="US-STAT-01, NFR-FD-01", fg="white", font=("Segoe UI", 8))
        self.__modeRequirement.grid(row=2, column=1, sticky="e")

    def __buildDrawerRow(self):
        # Row 1: one card per drawer. The cards are added by showStatus.
        self.__drawerRow = tk.Frame(self.__window, bg=self.__BACKGROUND, padx=12, pady=4)
        self.__drawerRow.grid(row=1, column=0, columnspan=2, sticky="ew")

    def __addDrawerCard(self, drawerID):
        frame = tk.Frame(self.__drawerRow, padx=10, pady=2)
        frame.pack(side="left", padx=6, expand=True, fill="x")
        name = tk.Label(frame, text="Drawer " + drawerID, fg="white", font=("Segoe UI", 10))
        name.pack()
        status = tk.Label(frame, fg="white", font=("Segoe UI", 13, "bold"))
        status.pack()
        self.__drawerCards[drawerID] = {"frame": frame, "name": name, "status": status}

    def __updateDrawerCard(self, drawerID, status):
        colour = self.__DRAWER_COLOURS[status]
        card = self.__drawerCards[drawerID]
        card["frame"].config(bg=colour)
        card["name"].config(bg=colour)
        card["status"].config(text=status.upper(), bg=colour)

    def __buildFaultRow(self):
        # Row 2: the active faults, or "No active faults".
        self.__faultLabel = tk.Label(self.__window, bg=self.__BACKGROUND, font=("Segoe UI", 10, "bold"),
                                     justify="left", anchor="w")
        self.__faultLabel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20)

    def __buildButtons(self):
        # Row 3, left side: what a user does, then what we make happen for the demo.
        panel = tk.Frame(self.__window, bg=self.__BACKGROUND, padx=12, pady=2)
        panel.grid(row=3, column=0, sticky="ns")
        self.__addButtonGroup(panel, "At the cabinet", self.__USER_ACTIONS, self.__USER_BUTTON)
        self.__addButtonGroup(panel, "Make something happen (for the demo)", self.__DEMO_ACTIONS, self.__DEMO_BUTTON)

    def __addButtonGroup(self, panel, title, actions, colour):
        tk.Label(panel, text=title, bg=self.__BACKGROUND, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6, 2))
        group = tk.Frame(panel, bg=self.__BACKGROUND)
        group.pack(anchor="w")
        position = 0
        for key in actions:
            button = self.__makeButton(group, key + " - " + actions[key], key, colour)
            button.config(width=19, state="disabled")
            button.grid(row=position // 4, column=position % 4, padx=2, pady=2, sticky="nsew")
            self.__menuButtons.append(button)
            position = position + 1

    def __makeButton(self, parent, text, key, colour):
        # Clicking the button gives main.py the same key it would get from typing it.
        def clicked():
            self.__answer.set(key)
        return tk.Button(parent, text=text, command=clicked, bg=colour, fg="white", wraplength=150, relief="flat",
                         activebackground=colour, activeforeground="white", disabledforeground="#c9d1d9",
                         font=("Segoe UI", 9), padx=2, pady=2)

    def __buildActivity(self):
        # Row 3, right side: every message, alert and table appears here.
        panel = tk.Frame(self.__window, bg=self.__BACKGROUND, padx=8, pady=8)
        panel.grid(row=3, column=1, sticky="nsew")
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)
        tk.Label(panel, text="Activity  (FR-LOG-01, NFR-FD-04)", bg=self.__BACKGROUND, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.__activity = tk.Text(panel, width=40, height=8, wrap="word", state="disabled", font=("Consolas", 10), bg="white", relief="flat", padx=8, pady=6)
        self.__activity.grid(row=1, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(panel, command=self.__activity.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.__activity.config(yscrollcommand=scrollbar.set)
        self.__activity.tag_config("normal", foreground="#1c2733")
        self.__activity.tag_config("alert", foreground=self.__MODE_COLOURS["SAFE"], font=("Consolas", 10, "bold"))
        self.__activity.tag_config("heading", foreground=self.__USER_BUTTON, font=("Consolas", 10, "bold"))

    def __buildInputBar(self):
        # Row 4: where the user answers a question, by typing or by clicking a choice.
        bar = tk.Frame(self.__window, bg="white", padx=14, pady=5)
        bar.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.__promptLabel = tk.Label(bar, bg="white", font=("Segoe UI", 11, "bold"))
        self.__promptLabel.pack(side="left", padx=(0, 10))
        self.__choiceArea = tk.Frame(bar, bg="white")
        self.__choiceArea.pack(side="left")
        # The text box and OK button are only put on screen when the user has to type something.
        self.__entry = tk.Entry(bar, width=28, font=("Segoe UI", 11))
        self.__entry.bind("<Return>", self.__submitText)
        self.__okButton = tk.Button(bar, text="OK", command=self.__submitText, bg=self.__USER_BUTTON, fg="white",
                                    activebackground=self.__USER_BUTTON, activeforeground="white", relief="flat", padx=12)

    def __waitForMenuButton(self):
        self.__promptLabel.config(text="Choose an action")
        if self.__menuEnabled == False:
            self.__setMenuButtons("normal")
            self.__menuEnabled = True
        # If nobody clicks within a second, return "" so main.py can run its monitoring cycle again.
        timer = self.__window.after(1000, self.__oneSecondPassed)
        answer = self.__waitForAnswer()
        self.__window.after_cancel(timer)
        if answer != "":
            self.__setMenuButtons("disabled")
            self.__menuEnabled = False
        return answer

    def __oneSecondPassed(self):
        self.__answer.set("")

    def __setMenuButtons(self, state):
        for button in self.__menuButtons:
            button.config(state=state)

    def __askForText(self, prompt, hideWith):
        self.__promptLabel.config(text=prompt)
        self.__entry.config(show=hideWith)
        self.__entry.pack(side="left")
        self.__okButton.pack(side="left", padx=8)
        self.__entry.focus_set()
        answer = self.__waitForAnswer()
        self.__entry.delete(0, "end")
        self.__entry.pack_forget()
        self.__okButton.pack_forget()
        return answer.strip()

    def __submitText(self, event=None):
        self.__answer.set(self.__entry.get())

    def __waitForAnswer(self):
        # The window keeps responding while main.py waits here for a click or for Enter.
        if self.__closed == True:
            return "0"
        self.__window.wait_variable(self.__answer)
        return self.__answer.get()

    def __onWindowClosed(self):
        # Closing the window is the same as pressing Exit, so the destructors still run.
        self.__closed = True
        self.__window.withdraw()
        self.__answer.set("0")

    def __write(self, text, style):
        self.__activity.config(state="normal")
        self.__activity.insert("end", text, style)
        self.__activity.config(state="disabled")
        self.__activity.see("end")

    def __formatTime(self, seconds):
        return time.strftime("%H:%M:%S", time.localtime(seconds))
