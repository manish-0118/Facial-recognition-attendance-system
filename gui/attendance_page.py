from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import customtkinter as ctk
from core.database import get_all_classes, get_today_attendance
from datetime import date
from gui import theme
from gui.widgets import ThemedDropdown


class AttendancePage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.class_list: list[dict] = []
        self.selected_class_id: int | None = None
        self.base_dir = Path(__file__).resolve().parent.parent
        self.stop_signal_path = self.base_dir / "stop_signal.txt"
        self.attendance_process: subprocess.Popen | None = None
        self.process_check_after_id: str | None = None
        self._present_after_id: str | None = None
        self.status_var = ctk.StringVar(value="Launch attendance in a separate camera window.")
        self.start_button:  ctk.CTkButton | None = None
        self.stop_button:   ctk.CTkButton | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(
            header, text="Take Attendance", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY
        ).pack(side="left", padx=20, pady=15)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Centered main card containing all attendance controls
        wrapper = ctk.CTkFrame(body, fg_color="transparent")
        wrapper.grid(row=0, column=0, sticky="nsew")
        # three-column wrapper so center column stays centered
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_columnconfigure(1, weight=0)
        wrapper.grid_columnconfigure(2, weight=1)

        info_card = ctk.CTkFrame(wrapper, fg_color=theme.BG_SURFACE, corner_radius=12, width=560, height=420)
        # place in center column; give breathing room and increased top/bottom padding
        info_card.grid(row=0, column=1, sticky="n", padx=0, pady=(30, 20))
        info_card.grid_propagate(False)
        info_card.grid_columnconfigure(0, weight=1)

        # Class selector (full width of card)
        ctk.CTkLabel(
            info_card,
            text="Class",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        self.class_selector = ThemedDropdown(
            info_card,
            values=["Select Class"],
            command=self._on_class_selected,
        )
        self.class_selector.grid(row=1, column=0, sticky="ew", padx=16)

        # Buttons frame (left aligned)
        btn_frame = ctk.CTkFrame(info_card, fg_color=info_card.cget("fg_color"))
        btn_frame.grid(row=2, column=0, sticky="w", padx=16, pady=(12, 6))

        self.start_button = ctk.CTkButton(
            btn_frame,
            text="Start Attendance",
            command=self.start_attendance,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            width=160,
            height=40,
        )
        self.start_button.pack(side="left", padx=(0, 8))

        self.stop_button = ctk.CTkButton(
            btn_frame,
            text="Stop Attendance",
            command=self.stop_attendance,
            fg_color=theme.BTN_DANGER,
            hover_color=theme.BTN_DANGER_HVR,
            width=160,
            height=40,
            state="disabled",
        )
        self.stop_button.pack(side="left")

        # Present counter
        self.present_count_var = ctk.StringVar(value="Present Today: 0 students")
        self.present_label = ctk.CTkLabel(info_card, textvariable=self.present_count_var, text_color=theme.TEXT_PRIMARY)
        self.present_label.grid(row=3, column=0, sticky="w", padx=16, pady=(10, 12))

        # Process/status area (keeps existing process status messages)
        self._process_status_label = ctk.CTkLabel(
            info_card,
            textvariable=self.status_var,
            text_color=theme.TEXT_PRIMARY,
            justify="left",
            wraplength=700,
        )
        self._process_status_label.grid(row=4, column=0, sticky="w", padx=16, pady=(0, 16))

        # populate classes into selector
        try:
            self._load_classes()
        except Exception:
            pass

    def on_page_shown(self) -> None:
        self._sync_button_state()
        if self.attendance_process is not None:
            self._schedule_process_check()
        try:
            self._refresh_present_count()
        except Exception:
            pass

    def on_page_hidden(self) -> None:
        # cancel present counter schedule when hidden
        try:
            if self._present_after_id:
                self.after_cancel(self._present_after_id)
                self._present_after_id = None
        except Exception:
            pass
        return

    def start_attendance(self) -> None:
        if self.attendance_process is not None and self.attendance_process.poll() is None:
            self._sync_button_state()
            return

        # validate class selection
        if self.selected_class_id is None:
            # no class chosen
            if hasattr(self.master_frame, "show_notification"):
                self.master_frame.show_notification("Please select a class before starting attendance.", "error")
            elif hasattr(self.master_frame, "notifications") and hasattr(self.master_frame.notifications, "show"):
                self.master_frame.notifications.show("Please select a class before starting attendance.", kind="error")
            self.status_var.set("Please select a class first.")
            return
        selected_class_id = int(self.selected_class_id)

        try:
            if self.stop_signal_path.exists():
                self.stop_signal_path.unlink()
            self.attendance_process = subprocess.Popen(
                [sys.executable, "take_attendance.py", str(selected_class_id)],
                cwd=str(self.base_dir),
            )
        except Exception as error:
            self.attendance_process = None
            if hasattr(self.master_frame, "show_action_error"):
                self.master_frame.show_action_error("Take Attendance", "Unable to launch the standalone attendance session.", error)
            self.status_var.set("Unable to start the attendance session.")
            self._sync_button_state()
            return

        self.status_var.set("Attendance session running... Press Q in the camera window to stop.")
        self._sync_button_state()
        self._schedule_process_check()

    def stop_attendance(self) -> None:
        is_running = self.attendance_process is not None and self.attendance_process.poll() is None
        if not is_running:
            self._sync_button_state()
            return

        try:
            self.stop_signal_path.open("w").close()
            self.status_var.set("Stop signal sent. Waiting for the attendance window to close.")
        except Exception as error:
            if hasattr(self.master_frame, "show_action_error"):
                self.master_frame.show_action_error("Take Attendance", "Unable to send the stop signal to the attendance session.", error)
            return

        self._sync_button_state()

    def _sync_button_state(self) -> None:
        if self.start_button is None or self.stop_button is None:
            return
        is_running = self.attendance_process is not None and self.attendance_process.poll() is None
        self.start_button.configure(state="disabled" if is_running else "normal")
        self.stop_button.configure(state="normal" if is_running else "disabled")
        if not is_running and self.status_var.get() in {
            "Attendance session running... Press Q in the camera window to stop.",
            "Stop signal sent. Waiting for the attendance window to close.",
        }:
            self.status_var.set("Launch attendance in a separate camera window.")

    def _schedule_process_check(self) -> None:
        if self.process_check_after_id is not None:
            try:
                self.after_cancel(self.process_check_after_id)
            except ValueError:
                pass
            self.process_check_after_id = None
        self.process_check_after_id = self.after(500, self._check_process_status)

    def _check_process_status(self) -> None:
        self.process_check_after_id = None
        if self.attendance_process is None:
            self._sync_button_state()
            return

        if self.attendance_process.poll() is None:
            self._sync_button_state()
            self._schedule_process_check()
            return

        self.attendance_process = None
        if self.stop_signal_path.exists():
            self.stop_signal_path.unlink()
        self.status_var.set("Launch attendance in a separate camera window.")
        self._sync_button_state()
        if hasattr(self.master_frame, "refresh_dashboard"):
            self.master_frame.refresh_dashboard()
        if hasattr(self.master_frame, "refresh_records_view"):
            self.master_frame.refresh_records_view()
        # Attendance finalization is handled by the background scheduler

    # ------------------------------------------------------------------
    # Present counter helper
    # ------------------------------------------------------------------
    def _refresh_present_count(self) -> None:
        try:
            class_id = int(self.selected_class_id) if self.selected_class_id is not None else None
            rows = get_today_attendance(class_id)
            count = len(rows)
            self.present_count_var.set(f"Present Today: {count} students")
        except Exception:
            self.present_count_var.set("Present Today: 0 students")
        # schedule next refresh
        try:
            if getattr(self, "_present_after_id", None):
                try:
                    self.after_cancel(self._present_after_id)
                except Exception:
                    pass
            self._present_after_id = self.after(10_000, self._refresh_present_count)
        except Exception:
            pass

    def _load_classes(self) -> None:
        try:
            classes = get_all_classes()
        except Exception:
            classes = []
        # store minimal class list of dicts with id and name
        self.class_list = []
        options = ["Select Class"]
        for class_row in classes:
            cid = int(class_row.get("id"))
            name = f"{class_row.get('name', '')} - {class_row.get('section', '')}".strip()
            self.class_list.append({"id": cid, "name": name})
            options.append(name)
        try:
            self.class_selector.configure(values=options)
            self.class_selector.set("Select Class")
        except Exception:
            pass

    def _on_class_selected(self, selected: str) -> None:
        # update selected_class_id from self.class_list
        if not selected or selected == "Select Class":
            self.selected_class_id = None
            try:
                self._refresh_present_count()
            except Exception:
                pass
            return
        for item in self.class_list:
            if item.get("name") == selected:
                self.selected_class_id = int(item.get("id"))
                try:
                    self._refresh_present_count()
                except Exception:
                    pass
                return
        self.selected_class_id = None
        try:
            self._refresh_present_count()
        except Exception:
            pass
