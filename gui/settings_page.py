import customtkinter as ctk
from tkinter import messagebox
from core.database import (
    get_system_config,
    update_system_config,
    update_all_class_times,
    update_class_times,
    get_class_cutoffs,
    get_all_classes,
    finalize_attendance,
    reset_todays_attendance,
    reset_finalization,
)
from datetime import date
from gui import theme
from gui.widgets import ThemedDropdown


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = ""):
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role
        self._class_map: dict = {}

        self.grid_columnconfigure(0, weight=1)
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=40, pady=8)
        container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            container, text="Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 12))

        # ── Attendance Timing card ─────────────────────────────────────────────
        timing_card = ctk.CTkFrame(container, fg_color=theme.BG_SURFACE, corner_radius=10)
        timing_card.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        timing_card.grid_columnconfigure(0, weight=1)
        timing_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            timing_card, text="Attendance Timing",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 12))

        # ── Left column: global defaults ──────────────────────────────────────
        global_col = ctk.CTkFrame(timing_card, fg_color="transparent")
        global_col.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        global_col.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            global_col, text="Global Defaults",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(
            global_col, text="Late Cutoff",
            font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY,
        ).grid(row=1, column=0, sticky="w", pady=(0, 4))

        self.late_cutoff_entry = ctk.CTkEntry(
            global_col, height=40,
            fg_color=theme.BG_SURFACE_ALT, border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.late_cutoff_entry.insert(0, get_system_config("late_cutoff") or "06:30")
        self.late_cutoff_entry.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            global_col, text="Absent Cutoff",
            font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY,
        ).grid(row=3, column=0, sticky="w", pady=(0, 4))

        self.absent_cutoff_entry = ctk.CTkEntry(
            global_col, height=40,
            fg_color=theme.BG_SURFACE_ALT, border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.absent_cutoff_entry.insert(0, get_system_config("absent_cutoff") or "07:00")
        self.absent_cutoff_entry.grid(row=4, column=0, sticky="ew", pady=(0, 12))

        ctk.CTkButton(
            global_col, text="Apply to All Classes",
            command=self.apply_to_all_classes,
            fg_color=theme.BTN_SUCCESS, hover_color=theme.BTN_SUCCESS_HVR,
            height=36, corner_radius=8,
        ).grid(row=5, column=0, sticky="ew", pady=(0, 6))

        ctk.CTkButton(
            global_col, text="Save Global Timing",
            command=self.save_global_timing,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            height=36, corner_radius=8,
        ).grid(row=6, column=0, sticky="ew")

        # ── Vertical divider ──────────────────────────────────────────────────
        ctk.CTkFrame(timing_card, fg_color=theme.BORDER, width=1).grid(
            row=1, column=0, sticky="nse", padx=(0, 0), pady=(0, 12),
        )

        # ── Right column: per-class override ──────────────────────────────────
        class_col = ctk.CTkFrame(timing_card, fg_color="transparent")
        class_col.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        class_col.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            class_col, text="Per-Class Override",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(
            class_col, text="Select Class",
            font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY,
        ).grid(row=1, column=0, sticky="w", pady=(0, 4))

        self.class_dropdown = ThemedDropdown(
            class_col,
            values=["Select Class"],
            command=self._on_class_selected,
        )
        self.class_dropdown.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            class_col, text="Late Cutoff",
            font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY,
        ).grid(row=3, column=0, sticky="w", pady=(0, 4))

        self.class_late_entry = ctk.CTkEntry(
            class_col, height=40,
            fg_color=theme.BG_SURFACE_ALT, border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text="HH:MM",
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
            state="disabled",
        )
        self.class_late_entry.grid(row=4, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            class_col, text="Absent Cutoff",
            font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY,
        ).grid(row=5, column=0, sticky="w", pady=(0, 4))

        self.class_absent_entry = ctk.CTkEntry(
            class_col, height=40,
            fg_color=theme.BG_SURFACE_ALT, border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text="HH:MM",
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
            state="disabled",
        )
        self.class_absent_entry.grid(row=6, column=0, sticky="ew", pady=(0, 12))

        self.save_class_btn = ctk.CTkButton(
            class_col, text="Save Class Timing",
            command=self.save_class_timing,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            height=36, corner_radius=8,
            state="disabled",
        )
        self.save_class_btn.grid(row=7, column=0, sticky="ew")

        # ── Developer tools — superadmin only ─────────────────────────────────
        self.dev_mode_var = ctk.BooleanVar(value=False)
        self._dev_class_map: dict = {}

        if role == "superadmin":
            self.dev_mode_switch = ctk.CTkSwitch(
                container,
                text="Developer Mode — Testing Only",
                variable=self.dev_mode_var,
                command=self.toggle_dev_mode,
            )
            self.dev_mode_switch.grid(row=2, column=0, sticky="w", padx=12, pady=(4, 8))

            self.dev_card = ctk.CTkFrame(container, fg_color=theme.BG_SURFACE, corner_radius=10)
            self.dev_card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                self.dev_card, text="Developer Tools",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=theme.TEXT_PRIMARY,
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 8))

            ctk.CTkLabel(
                self.dev_card, text="Class",
                text_color=theme.TEXT_SECONDARY,
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(4, 4))

            self.dev_class_selector = ThemedDropdown(self.dev_card, values=["Select Class"])
            self.dev_class_selector.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

            btn_frame = ctk.CTkFrame(self.dev_card, fg_color="transparent")
            btn_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 12))

            ctk.CTkButton(
                btn_frame, text="Reset Today's Attendance",
                fg_color=theme.BTN_DANGER, hover_color=theme.BTN_DANGER_HVR,
                command=self._reset_todays_attendance,
            ).pack(fill="x", pady=(0, 6))

            ctk.CTkButton(
                btn_frame, text="Run Finalization Now",
                fg_color=theme.WARNING, hover_color=theme.WARNING_BG,
                command=self._run_finalization_now,
            ).pack(fill="x")

        # Load classes into both dropdowns
        try:
            self._load_classes()
        except Exception:
            pass

    # ── Class loading ─────────────────────────────────────────────────────────

    def _load_classes(self) -> None:
        try:
            classes = get_all_classes() or []
        except Exception:
            classes = []

        self._class_map = {}
        self._dev_class_map = {}
        options = ["Select Class"]

        for c in classes:
            label = f"{c.get('name')} — {c.get('section')}"
            options.append(label)
            self._class_map[label] = c
            self._dev_class_map[label] = c

        try:
            self.class_dropdown.configure(values=options)
        except Exception:
            pass
        try:
            self.dev_class_selector.configure(values=options)
        except Exception:
            pass

    # ── Per-class dropdown interaction ────────────────────────────────────────

    def _on_class_selected(self, label: str) -> None:
        if not label or label == "Select Class":
            self.class_late_entry.configure(state="disabled")
            self.class_absent_entry.configure(state="disabled")
            self.save_class_btn.configure(state="disabled")
            return

        row = self._class_map.get(label)
        if not row:
            return

        class_id = int(row.get("id"))
        late, absent = get_class_cutoffs(class_id)

        # Enable and populate entries
        for entry, val, fallback in (
            (self.class_late_entry,   late,   "06:30"),
            (self.class_absent_entry, absent, "07:00"),
        ):
            entry.configure(state="normal")
            entry.delete(0, "end")
            # Format timedelta/time objects from MySQL as HH:MM
            if val is not None:
                val_str = str(val)
                if len(val_str) > 5:
                    val_str = val_str[:5]
                entry.insert(0, val_str)
            else:
                entry.insert(0, fallback)

        self.save_class_btn.configure(state="normal")

    # ── Timing actions ────────────────────────────────────────────────────────

    def apply_to_all_classes(self):
        try:
            update_all_class_times(self.late_cutoff_entry.get(), self.absent_cutoff_entry.get())
            self._notify("Applied timings to all classes.", "success")
        except Exception as e:
            self._notify(f"Failed: {e}", "error")

    def save_global_timing(self):
        try:
            update_system_config("late_cutoff", self.late_cutoff_entry.get())
            update_system_config("absent_cutoff", self.absent_cutoff_entry.get())
            self._notify("Global timing saved.", "success")
        except Exception as e:
            self._notify(f"Failed to save: {e}", "error")

    def save_class_timing(self):
        label = self.class_dropdown.get()
        row = self._class_map.get(label)
        if not row:
            self._notify("Select a class first.", "error")
            return
        try:
            update_class_times(
                int(row.get("id")),
                self.class_late_entry.get(),
                self.class_absent_entry.get(),
            )
            self._notify(f"Timing saved for {label}.", "success")
        except Exception as e:
            self._notify(f"Failed to save: {e}", "error")

    # ── Developer tools ───────────────────────────────────────────────────────

    def toggle_dev_mode(self):
        if not hasattr(self, "dev_card"):
            return
        try:
            if self.dev_mode_var.get():
                self.dev_card.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
            else:
                self.dev_card.grid_forget()
        except Exception:
            pass

    def _get_selected_dev_class_id(self) -> int | None:
        sel = self.dev_class_selector.get()
        if not sel or sel == "Select Class":
            return None
        row = self._dev_class_map.get(sel)
        return int(row.get("id")) if row else None

    def _reset_todays_attendance(self) -> None:
        cid = self._get_selected_dev_class_id()
        if cid is None:
            self._notify("Select a class first.", "error")
            return
        try:
            a = reset_todays_attendance(cid, date.today())
            b = reset_finalization(cid, date.today())
            self._notify(f"Deleted {a} attendance rows and {b} finalization rows.", "success")
            self._load_classes()
        except Exception:
            self._notify("Failed to reset attendance.", "error")

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
        messagebox.showinfo("Info", message)
