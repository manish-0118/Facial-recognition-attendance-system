import customtkinter as ctk
from tkinter import filedialog, messagebox
from gui.widgets import ThemedDropdown
from core.database import (
    get_system_config,
    update_system_config,
    update_all_class_times,
    get_all_classes,
    finalize_attendance,
    reset_todays_attendance,
    reset_finalization,
)
from datetime import date
from gui import theme


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = ""):
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role

        self.grid_columnconfigure(0, weight=1)
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=40, pady=8)
        container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(container, text="Settings", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 12))

        cards_row = ctk.CTkFrame(container, fg_color="transparent")
        cards_row.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 12))
        cards_row.grid_columnconfigure(0, weight=1)
        cards_row.grid_columnconfigure(1, weight=1)

        # Left card
        left_card = ctk.CTkFrame(cards_row, fg_color=theme.BG_SURFACE, corner_radius=10)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        left_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left_card, text="Attendance Timing", font=ctk.CTkFont(size=16, weight="bold"), text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(left_card, text="Late Cutoff", font=ctk.CTkFont(size=13), text_color=theme.TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=12, pady=(6, 4))
        self.late_cutoff_entry = ctk.CTkEntry(
            left_card,
            height=42,
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.late_cutoff_entry.insert(0, get_system_config("late_cutoff") or "06:30")
        self.late_cutoff_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(left_card, text="Absent Cutoff", font=ctk.CTkFont(size=13), text_color=theme.TEXT_SECONDARY).grid(row=3, column=0, sticky="w", padx=12, pady=(6, 4))
        self.absent_cutoff_entry = ctk.CTkEntry(
            left_card,
            height=42,
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.absent_cutoff_entry.insert(0, get_system_config("absent_cutoff") or "07:00")
        self.absent_cutoff_entry.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.apply_all_button = ctk.CTkButton(left_card, text="Apply to All Classes", command=self.apply_to_all_classes, fg_color=theme.BTN_SUCCESS, hover_color=theme.BTN_SUCCESS_HVR, height=36, corner_radius=8)
        self.apply_all_button.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

        # Right card
        right_card = ctk.CTkFrame(cards_row, fg_color=theme.BG_SURFACE, corner_radius=10)
        right_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)
        right_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_card, text="System Configuration", font=ctk.CTkFont(size=16, weight="bold"), text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(right_card, text="Max Classes", font=ctk.CTkFont(size=13), text_color=theme.TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=12, pady=(6, 4))
        self.max_classes_entry = ctk.CTkEntry(
            right_card,
            height=42,
            state="normal" if role == "superadmin" else "disabled",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.max_classes_entry.insert(0, get_system_config("max_classes") or "10")
        self.max_classes_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        ctk.CTkLabel(right_card, text="Camera Source", font=ctk.CTkFont(size=13), text_color=theme.TEXT_SECONDARY).grid(row=3, column=0, sticky="w", padx=12, pady=(6, 4))
        self.camera_source_var = ctk.StringVar(value=get_system_config("camera_source") or "0")
        self.camera_source_dropdown = ThemedDropdown(
            right_card,
            values=["0", "1", "RTSP"],
            variable=self.camera_source_var,
        )
        self.camera_source_dropdown.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.rtsp_url_label = ctk.CTkLabel(right_card, text="RTSP URL", font=ctk.CTkFont(size=13), text_color=theme.TEXT_SECONDARY)
        self.rtsp_url_entry = ctk.CTkEntry(
            right_card,
            height=42,
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.rtsp_url_entry.insert(0, get_system_config("rtsp_url") or "")
        self.rtsp_url_label.grid(row=5, column=0, sticky="w", padx=12, pady=(4, 4))
        self.rtsp_url_entry.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 12))
        if self.camera_source_var.get() != "RTSP":
            self.rtsp_url_label.grid_forget()
            self.rtsp_url_entry.grid_forget()
        self.camera_source_var.trace("w", self.toggle_rtsp_url)

        # Backup card
        backup_card = ctk.CTkFrame(container, fg_color=theme.BG_SURFACE, corner_radius=10)
        backup_card.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        backup_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(backup_card, text="Backup & Restore", font=ctk.CTkFont(size=15, weight="bold"), text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        actions = ctk.CTkFrame(backup_card, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))
        ctk.CTkButton(actions, text="Manual Backup", command=self.manual_backup, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, height=36).grid(row=0, column=0, padx=(0, 8))
        if role == "superadmin":
            ctk.CTkButton(actions, text="Restore Backup", command=self.restore_backup, fg_color=theme.BTN_DANGER, hover_color=theme.BTN_DANGER_HVR, height=36).grid(row=0, column=1)

        # Developer tools — superadmin only
        self.dev_mode_var = ctk.BooleanVar(value=False)
        self._dev_class_map = {}

        if role == "superadmin":
            self.dev_mode_switch = ctk.CTkSwitch(
                container,
                text="Developer Mode — Testing Only",
                variable=self.dev_mode_var,
                command=self.toggle_dev_mode,
            )
            self.dev_mode_switch.grid(row=3, column=0, sticky="w", padx=12, pady=(4, 8))

            self.dev_card = ctk.CTkFrame(container, fg_color=theme.BG_SURFACE, corner_radius=10)
            self.dev_card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(self.dev_card, text="Developer Tools", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 8))
            ctk.CTkLabel(self.dev_card, text="Class", text_color=theme.TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=12, pady=(4, 4))
            self.dev_class_selector = ThemedDropdown(self.dev_card, values=["Select Class"])
            self.dev_class_selector.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
            btn_frame = ctk.CTkFrame(self.dev_card, fg_color="transparent")
            btn_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 12))
            ctk.CTkButton(btn_frame, text="Reset Today's Attendance", fg_color=theme.BTN_DANGER, hover_color=theme.BTN_DANGER_HVR, command=self._reset_todays_attendance).pack(fill="x", pady=(0, 6))
            ctk.CTkButton(btn_frame, text="Run Finalization Now", fg_color=theme.WARNING, hover_color=theme.WARNING_BG, command=self._run_finalization_now).pack(fill="x")

        # Backup frequency + Save
        self.backup_frequency_var = ctk.StringVar(value=get_system_config("backup_frequency") or "Daily")
        ctk.CTkLabel(right_card, text="Backup Frequency", font=ctk.CTkFont(size=13), text_color=theme.TEXT_SECONDARY).grid(row=7, column=0, sticky="w", padx=12, pady=(6, 4))
        self.backup_frequency_dropdown = ThemedDropdown(
            right_card,
            values=["Daily", "Weekly", "Manual"],
            variable=self.backup_frequency_var,
        )
        self.backup_frequency_dropdown.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 12))

        # Centered Save button with fixed width
        save_frame = ctk.CTkFrame(container, fg_color="transparent")
        save_frame.grid(row=5, column=0, pady=(0, 12))
        save_frame.grid_columnconfigure(0, weight=1)
        self.save_button = ctk.CTkButton(save_frame, text="Save Settings", command=self.save_settings, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, height=40, width=200)
        # left-align the button inside its wrapper with fixed width
        try:
            self.save_button.pack(anchor="w", padx=12)
        except Exception:
            self.save_button.grid(row=0, column=0, sticky="w", padx=12)

        if role == "superadmin":
            try:
                self._load_dev_classes()
            except Exception:
                pass

    # ----- actions & helpers -----
    def toggle_rtsp_url(self, *args):
        if self.camera_source_var.get() == "RTSP":
            try:
                self.rtsp_url_label.grid(row=5, column=0, sticky="w", padx=12, pady=(4, 4))
                self.rtsp_url_entry.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 12))
            except Exception:
                pass
        else:
            try:
                self.rtsp_url_label.grid_forget()
                self.rtsp_url_entry.grid_forget()
            except Exception:
                pass

    def apply_to_all_classes(self):
        try:
            update_all_class_times(self.late_cutoff_entry.get(), self.absent_cutoff_entry.get())
            self._notify("Applied timings to all classes.", "success")
        except Exception as e:
            self._notify(f"Failed to apply to all classes: {e}", "error")

    def manual_backup(self):
        # placeholder: real implementation depends on backup system
        self._notify("Manual backup triggered.", "success")

    def restore_backup(self):
        # placeholder
        self._notify("Restore requested.", "success")

    def save_settings(self):
        try:
            update_system_config("late_cutoff", self.late_cutoff_entry.get())
            update_system_config("absent_cutoff", self.absent_cutoff_entry.get())
            update_system_config("max_classes", self.max_classes_entry.get())
            update_system_config("camera_source", self.camera_source_var.get())
            update_system_config("rtsp_url", self.rtsp_url_entry.get())
            update_system_config("backup_frequency", self.backup_frequency_var.get())
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Settings saved successfully.", "success")
            else:
                messagebox.showinfo("Success", "Settings saved successfully.")
        except Exception as e:
            self._notify(f"Failed to save settings: {e}", "error")

    def toggle_dev_mode(self):
        if not hasattr(self, "dev_card"):
            return
        try:
            if self.dev_mode_var.get():
                self.dev_card.grid(row=4, column=0, sticky="w", padx=12, pady=(0, 12))
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
            label = f"{c.get('name')} — {c.get('section')}"
            options.append(label)
            self._dev_class_map[label] = c
        try:
            self.dev_class_selector.configure(values=options)
        except Exception:
            pass

    def _get_selected_dev_class_id(self) -> int | None:
        sel = self.dev_class_selector.get()
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
            a = reset_todays_attendance(cid, date.today())
            b = reset_finalization(cid, date.today())
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification(f"Deleted {a} attendance rows and {b} finalization rows.", "success")
            else:
                messagebox.showinfo("Success", f"Deleted {a} attendance rows and {b} finalization rows.")
            self._load_dev_classes()
        except Exception:
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Failed to reset attendance.", "error")
            else:
                messagebox.showerror("Error", "Failed to reset attendance.")

    def _run_finalization_now(self):
        try:
            finalize_attendance()
            self._notify("Finalization run.", "success")
        except Exception as e:
            self._notify(f"Finalization failed: {e}", "error")

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, "show_notification"):
            try:
                self.master_frame.show_notification(message, kind)
                return
            except Exception:
                pass
        if hasattr(self.master_frame, "notifications") and hasattr(self.master_frame.notifications, "show"):
            try:
                self.master_frame.notifications.show(message, kind=kind)
            except Exception:
                pass
