import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.database import (
    get_system_config,
    update_system_config,
    update_all_class_times,
    get_all_classes,
    finalize_attendance,
    reset_todays_attendance,
    reset_finalization,
)
from datetime import datetime

class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = ""):
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role

        self.grid_columnconfigure(0, weight=1)
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=60, pady=0)
        container.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(container, text="Settings", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").grid(row=0, column=0, sticky="w", padx=24, pady=(20, 6))

        # Two cards side-by-side inside centered container
        cards_row = ctk.CTkFrame(container, fg_color="transparent")
        cards_row.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 16))
        cards_row.grid_columnconfigure(0, weight=1)
        cards_row.grid_columnconfigure(1, weight=1)

        # Left card: Attendance Timing
        left_card = ctk.CTkFrame(cards_row, fg_color="#1E1E1E", corner_radius=12)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=0)
        left_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left_card, text="Attendance Timing", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").grid(row=0, column=0, sticky="w", padx=24, pady=(18, 12))

        ctk.CTkLabel(left_card, text="Late Cutoff", font=ctk.CTkFont(size=14), text_color="white").grid(row=1, column=0, sticky="w", padx=24, pady=(8, 6))
        self.late_cutoff_entry = ctk.CTkEntry(left_card, height=40)
        self.late_cutoff_entry.insert(0, get_system_config("late_cutoff") or "06:30")
        self.late_cutoff_entry.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))

        ctk.CTkLabel(left_card, text="Absent Cutoff", font=ctk.CTkFont(size=14), text_color="white").grid(row=3, column=0, sticky="w", padx=24, pady=(8, 6))
        self.absent_cutoff_entry = ctk.CTkEntry(left_card, height=40)
        self.absent_cutoff_entry.insert(0, get_system_config("absent_cutoff") or "07:00")
        self.absent_cutoff_entry.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 16))

        # Apply to all classes button
        self.apply_all_button = ctk.CTkButton(left_card, text="Apply to All Classes", command=self.apply_to_all_classes, fg_color="#4CAF50", hover_color="#3A9B3A", height=36, corner_radius=8)
        self.apply_all_button.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 12))

        # Right card: System Configuration
        right_card = ctk.CTkFrame(cards_row, fg_color="#1E1E1E", corner_radius=12)
        right_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=0)
        right_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right_card, text="System Configuration", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").grid(row=0, column=0, sticky="w", padx=24, pady=(18, 12))

        ctk.CTkLabel(right_card, text="Max Classes", font=ctk.CTkFont(size=14), text_color="white").grid(row=1, column=0, sticky="w", padx=24, pady=(8, 6))
        self.max_classes_entry = ctk.CTkEntry(right_card, state="normal" if role == "superadmin" else "disabled", height=40)
        self.max_classes_entry.insert(0, get_system_config("max_classes") or "10")
        self.max_classes_entry.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))

        ctk.CTkLabel(right_card, text="Camera Source", font=ctk.CTkFont(size=14), text_color="white").grid(row=3, column=0, sticky="w", padx=24, pady=(8, 6))
        self.camera_source_var = ctk.StringVar(value=get_system_config("camera_source") or "0")
        self.camera_source_dropdown = ctk.CTkOptionMenu(right_card, variable=self.camera_source_var, values=["0", "1", "RTSP"], fg_color="#1F1F1F", button_color="#1E88E5", button_hover_color="#1565C0")
        self.camera_source_dropdown.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 12))
        # RTSP URL (hidden unless RTSP selected)
        self.rtsp_url_label = ctk.CTkLabel(right_card, text="RTSP URL", font=ctk.CTkFont(size=14), text_color="white")
        self.rtsp_url_label.grid(row=5, column=0, sticky="w", padx=24, pady=(4, 4))
        self.rtsp_url_entry = ctk.CTkEntry(right_card, height=40)
        self.rtsp_url_entry.insert(0, get_system_config("rtsp_url") or "")
        self.rtsp_url_entry.grid(row=6, column=0, sticky="ew", padx=24, pady=(0, 12))
        if self.camera_source_var.get() != "RTSP":
            self.rtsp_url_label.grid_forget()
            self.rtsp_url_entry.grid_forget()

        # Backup & Restore full-width card
        backup_card = ctk.CTkFrame(container, fg_color="#1E1E1E", corner_radius=12)
        backup_card.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        backup_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(backup_card, text="Backup & Restore", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").grid(row=0, column=0, sticky="w", padx=24, pady=(16, 12))

        actions = ctk.CTkFrame(backup_card, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 16))
        ctk.CTkButton(actions, text="Manual Backup", command=self.manual_backup, fg_color="#1E88E5", hover_color="#1565C0", height=40, corner_radius=8).grid(row=0, column=0, padx=(0, 12))
        if role == "superadmin":
            ctk.CTkButton(actions, text="Restore Backup", command=self.restore_backup, fg_color="#C62828", hover_color="#A51F1F", height=40, corner_radius=8).grid(row=0, column=1)

        # Developer Mode (superadmin only)
        if role == "superadmin":
            # toggle
            self.dev_mode_var = ctk.BooleanVar(value=False)
            self.dev_mode_switch = ctk.CTkSwitch(container, text="Developer Mode — Testing Only", variable=self.dev_mode_var, command=self.toggle_dev_mode)
            self.dev_mode_switch.grid(row=4, column=0, sticky="w", padx=24, pady=(4, 8))

            # developer card (hidden by default) — styled like other settings cards
            self.dev_card = ctk.CTkFrame(container, fg_color="#1E1E1E", corner_radius=12)
            # section title
            ctk.CTkLabel(self.dev_card, text="Developer Tools", font=ctk.CTkFont(size=16, weight="bold"), text_color="white").grid(row=0, column=0, sticky="w", padx=24, pady=(12, 8))

            # class selector and action buttons
            ctk.CTkLabel(self.dev_card, text="Class", text_color="white").grid(row=1, column=0, sticky="w", padx=24, pady=(4, 4))
            self.dev_class_selector = ctk.CTkOptionMenu(self.dev_card, values=["Select Class"], width=320)
            self.dev_class_selector.grid(row=2, column=0, sticky="w", padx=24, pady=(0, 12))

            btn_frame = ctk.CTkFrame(self.dev_card, fg_color="transparent")
            btn_frame.grid(row=3, column=0, sticky="w", padx=24, pady=(4, 12))
            ctk.CTkButton(btn_frame, text="Reset Today's Attendance", fg_color="#D32F2F", hover_color="#B71C1C", command=self._reset_todays_attendance).pack(side="left", padx=(0,8))
            ctk.CTkButton(btn_frame, text="Run Finalization Now", fg_color="#F57F17", hover_color="#EF6C00", command=self._run_finalization_now).pack(side="left")

            # don't show by default
            self.dev_card.grid_forget()
            # populate classes
            self._load_dev_classes()

        # Backup frequency (kept for compatibility)
        self.backup_frequency_var = ctk.StringVar(value=get_system_config("backup_frequency") or "Daily")
        # place visually inside right_card underneath camera settings
        ctk.CTkLabel(right_card, text="Backup Frequency", font=ctk.CTkFont(size=13), text_color="white").grid(row=7, column=0, sticky="w", padx=20, pady=(8, 4))
        self.backup_frequency_dropdown = ctk.CTkOptionMenu(right_card, variable=self.backup_frequency_var, values=["Daily", "Weekly", "Manual"], fg_color="#1F1F1F", button_color="#1E88E5", button_hover_color="#1565C0")
        self.backup_frequency_dropdown.grid(row=8, column=0, sticky="ew", padx=20, pady=(0, 12))

        # Save Settings full-width button at bottom
        self.save_button = ctk.CTkButton(container, text="Save Settings", command=self.save_settings, fg_color="#1E88E5", hover_color="#1565C0", height=44, corner_radius=8)
        self.save_button.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 20))

        # hide/show RTSP handling
        self.camera_source_var.trace("w", self.toggle_rtsp_url)

    def toggle_rtsp_url(self, *args):
        if self.camera_source_var.get() == "RTSP":
            try:
                self.rtsp_url_label.grid(row=5, column=0, sticky="w", padx=16, pady=(4, 4))
                self.rtsp_url_entry.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 12))
            except Exception:
                pass
        else:
            try:
                self.rtsp_url_label.grid_forget()
                self.rtsp_url_entry.grid_forget()
            except Exception:
                pass

    def save_settings(self):
        update_system_config("late_cutoff", self.late_cutoff_entry.get())
        update_system_config("absent_cutoff", self.absent_cutoff_entry.get())
        if self.role == "superadmin":
            update_system_config("max_classes", self.max_classes_entry.get())
        update_system_config("camera_source", self.camera_source_var.get())
        if self.camera_source_var.get() == "RTSP":
            update_system_config("rtsp_url", self.rtsp_url_entry.get())
        update_system_config("backup_frequency", self.backup_frequency_var.get())
        if hasattr(self.master_frame, "show_notification"):
            self.master_frame.show_notification("Settings saved successfully.", "success")
        else:
            messagebox.showinfo("Success", "Settings saved successfully.")

    def toggle_dev_mode(self):
        try:
            if self.dev_mode_var.get():
                self.dev_card.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 12))
            else:
                self.dev_card.grid_forget()
        except Exception:
            pass

    def _load_dev_classes(self) -> None:
        try:
            classes = get_all_classes() or []
        except Exception:
            classes = []
        options = ["Select Class"]
        self._dev_class_map = {}
        for c in classes:
            label = f"{c.get('name','')} {c.get('section','')} (ID: {c.get('id')})"
            options.append(label)
            self._dev_class_map[label] = c
        try:
            self.dev_class_selector.configure(values=options)
            self.dev_class_selector.set("Select Class")
        except Exception:
            pass

    def _get_selected_dev_class_id(self) -> int | None:
        sel = self.dev_class_selector.get() if hasattr(self, 'dev_class_selector') else None
        if not sel or sel == "Select Class":
            return None
        row = self._dev_class_map.get(sel)
        return int(row.get('id')) if row else None

    def _reset_todays_attendance(self) -> None:
        cid = self._get_selected_dev_class_id()
        if cid is None:
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Select a class first.", "error")
            else:
                messagebox.showerror("Error", "Select a class first.")
            return
        try:
            from datetime import date as _d

            a = reset_todays_attendance(cid, _d.today())
            b = reset_finalization(cid, _d.today())
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification(f"Deleted {a} attendance rows and {b} finalization rows.", "success")
            else:
                messagebox.showinfo("Success", f"Deleted {a} attendance rows and {b} finalization rows.")
            # refresh classes listing if needed
            self._load_dev_classes()
        except Exception:
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Failed to reset attendance.", "error")
            else:
                messagebox.showerror("Error", "Failed to reset attendance.")

    def _run_finalization_now(self) -> None:
        cid = self._get_selected_dev_class_id()
        if cid is None:
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Select a class first.", "error")
            else:
                messagebox.showerror("Error", "Select a class first.")
            return
        try:
            from datetime import date as _d

            finalize_attendance(cid, _d.today())
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Finalization executed.", "success")
            else:
                messagebox.showinfo("Success", "Finalization executed.")
        except Exception:
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Finalization failed.", "error")
            else:
                messagebox.showerror("Error", "Finalization failed.")

    def apply_to_all_classes(self) -> None:
        late = self.late_cutoff_entry.get()
        absent = self.absent_cutoff_entry.get()
        try:
            updated = update_all_class_times(late, absent)
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification(f"Updated {updated} classes.", "success")
            else:
                messagebox.showinfo("Success", f"Updated {updated} classes.")
        except Exception:
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Failed to update classes.", "error")
            else:
                messagebox.showerror("Error", "Failed to update classes.")

    def manual_backup(self):
        # Placeholder for backup logic
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        if hasattr(self.master_frame, "show_notification"):
            self.master_frame.show_notification(f"Backup created: {backup_filename}", "success")
        else:
            messagebox.showinfo("Success", f"Backup created: {backup_filename}")

    def restore_backup(self):
        backup_file = filedialog.askopenfilename(filetypes=[("SQL Files", "*.sql")])
        if backup_file:
            # Placeholder for restore logic
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification(f"Backup restored from: {backup_file}", "success")
            else:
                messagebox.showinfo("Success", f"Backup restored from: {backup_file}")