from __future__ import annotations

import customtkinter as ctk
from gui import theme

from core.database import (
    get_all_classes,
    get_archive,
    hard_delete_student,
    log_action,
    restore_student,
    verify_admin,
)


class ArchivePage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role
        self._classes: list[dict] = []
        self._row_widgets: list[ctk.CTkBaseClass] = []

        # center container using grid and side padding so it stretches responsively
        self.grid_columnconfigure(0, weight=1)
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=60, pady=0)
        container.grid_columnconfigure(0, weight=1)

        # Title row with refresh button aligned right
        title_row = ctk.CTkFrame(container, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 20))
        title_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(title_row, text="Archived Students", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w")
        self.count_label = ctk.CTkLabel(title_row, text="0 archived students", font=ctk.CTkFont(size=13), text_color="#888888")
        self.count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkButton(
            title_row,
            text="Refresh",
            command=self.refresh,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            width=120,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        # Table card immediately below
        body = ctk.CTkFrame(container, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        body.grid_columnconfigure(0, weight=1)
        self._build_table(body)

        self.refresh()

    def _build_toolbar(self, parent) -> None:
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        toolbar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="Archived Students",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, sticky="w")

        self.count_label = ctk.CTkLabel(
            toolbar,
            text="0 archived students",
            font=ctk.CTkFont(size=13),
            text_color="#888888",
        )
        self.count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkButton(
            toolbar,
            text="Refresh Archive",
            command=self.refresh,
            fg_color="#1E88E5",
            hover_color="#1565C0",
            width=140,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_table(self, parent) -> None:
        # table card
        card = ctk.CTkFrame(parent, fg_color=theme.BG_SURFACE, corner_radius=12)
        card.grid(row=0, column=0, sticky="nsew", padx=24, pady=(0, 20))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        # Replace scrollable with a regular frame that fills width
        self.table_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.table_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        headers = ["Student ID", "Name", "Class", "Deleted By", "Deleted Date", "Actions"]
        # equal weights so columns spread evenly across full width
        weights = [1, 1, 1, 1, 1, 1]
        for col, weight in enumerate(weights):
            self.table_frame.grid_columnconfigure(col, weight=weight)
        # allow rows area to expand so empty state can center vertically
        self.table_frame.grid_rowconfigure(1, weight=1)

        for col, header in enumerate(headers):
            ctk.CTkLabel(
                self.table_frame,
                text=header,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=(10, 6), pady=(0, 6))

        self.empty_label = ctk.CTkLabel(
            self.table_frame,
            text="No archived students",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=13),
        )

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, "show_notification"):
            self.master_frame.show_notification(message, kind)
        elif hasattr(self.master_frame, "notifications") and hasattr(self.master_frame.notifications, "show"):
            self.master_frame.notifications.show(message, kind=kind)

    def _class_name_from_id(self, class_id: int | None) -> str:
        if class_id is None:
            return "-"
        for class_row in self._classes:
            if int(class_row.get("id", -1)) == int(class_id):
                return f"{class_row.get('name', '')} {class_row.get('section', '')}".strip()
        return str(class_id)

    def _clear_rows(self) -> None:
        for widget in self._row_widgets:
            widget.destroy()
        self._row_widgets.clear()
        self.empty_label.grid_forget()

    def _display_name(self, row: dict) -> str:
        fn = row.get("first_name")
        if fn:
            parts = [str(fn).strip()]
            mn = row.get("middle_name")
            if mn:
                parts.append(str(mn).strip())
            ln = row.get("last_name")
            if ln:
                parts.append(str(ln).strip())
            return " ".join([p for p in parts if p])
        return str(row.get("name", "-")).strip()

    def _confirmation_dialog(self, title: str, message: str, danger: bool = False) -> bool:
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("430x220")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        result = {"ok": False}

        def confirm() -> None:
            result["ok"] = True
            dialog.destroy()

        card = ctk.CTkFrame(dialog, fg_color=theme.BG_SURFACE, corner_radius=0)
        card.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=18, pady=(16, 8))
        ctk.CTkLabel(card, text=message, justify="left", wraplength=380, text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=18, pady=(0, 16))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(actions, text="Cancel", command=dialog.destroy, corner_radius=6).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Confirm",
            command=confirm,
            fg_color="#C62828" if danger else "#1E88E5",
            hover_color="#A51F1F" if danger else "#1565C0",
            corner_radius=6,
        ).pack(side="right")

        self.wait_window(dialog)
        return bool(result["ok"])

    def _handle_restore(self, student_id: str, student_name: str) -> None:
        confirmed = self._confirmation_dialog(
            "Restore Student",
            f"Restore archived student {student_name} ({student_id}) to active students?",
        )
        if not confirmed:
            return

        try:
            restore_student(student_id)
            log_action(
                self.username or "system",
                "RESTORE_STUDENT",
                f"student_id={student_id}",
            )
        except Exception as error:
            # If restore failed with a specific message, show it; otherwise show generic
            msg = str(error) if str(error) else "Failed to restore student."
            self._notify(msg, "error")
            if hasattr(self.app, "show_action_error"):
                self.master_frame.show_action_error("Archive", "Unable to restore the archived student.", error)
            return

        self.refresh()
        if hasattr(self.master_frame, "refresh_all_views"):
            self.master_frame.refresh_all_views()
        self._notify("Student restored successfully", "success")

    def _handle_permanent_delete(self, student_id: str, student_name: str) -> None:
        if self.role != "superadmin":
            self._notify("Only superadmins can permanently delete archived students.", "error")
            return
        # Open password confirmation dialog
        dlg = ctk.CTkToplevel(self)
        dlg.title("Delete Permanently")
        dlg.geometry("520x260")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        card = ctk.CTkFrame(dlg, fg_color="#1E1E1E", corner_radius=0)
        card.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(card, text=f"Delete {student_name}", font=ctk.CTkFont(size=18, weight="bold"), anchor="w").pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            card,
            text="This will permanently delete the student and all their attendance records. This cannot be undone.",
            justify="left",
            wraplength=480,
            text_color="#D0D0D0",
        ).pack(anchor="w", padx=18, pady=(0, 12))

        pw_label = ctk.CTkLabel(card, text="Enter your password to confirm", text_color="#D0D0D0")
        pw_label.pack(anchor="w", padx=18, pady=(0, 6))

        pw_var = ctk.StringVar()
        pw_entry = ctk.CTkEntry(
            card,
            textvariable=pw_var,
            show="*",
            width=420,
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
            height=42,
        )
        pw_entry.pack(anchor="w", padx=18)

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(16, 12))

        def _do_delete() -> None:
            password = (pw_var.get() or "").strip()
            if not password:
                self._notify("Password is required to confirm deletion.", "error")
                return
            try:
                role = verify_admin(self.username or "", password)
            except Exception:
                role = None
            if not role:
                self._notify("Incorrect password.", "error")
                try:
                    pw_var.set("")
                except Exception:
                    pass
                return

            try:
                attendance_deleted = hard_delete_student(student_id)
                log_action(
                    self.username or "system",
                    "HARD_DELETE_STUDENT",
                    f"student_id={student_id}, attendance_deleted={attendance_deleted}",
                )
            except Exception as error:
                self._notify("Failed to permanently delete student.", "error")
                if hasattr(self.master_frame, "show_action_error"):
                    self.master_frame.show_action_error("Archive", "Unable to permanently delete the archived student.", error)
                return

            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()

            self.refresh()
            if hasattr(self.master_frame, "refresh_all_views"):
                self.master_frame.refresh_all_views()
            self._notify(f"Student permanently deleted. Also removed {attendance_deleted} attendance records.", "success")

        ctk.CTkButton(actions, text="Cancel", command=dlg.destroy, corner_radius=6).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Confirm Delete",
            command=_do_delete,
            fg_color="#C62828",
            hover_color="#A51F1F",
            corner_radius=6,
        ).pack(side="right")

        self.wait_window(dlg)

    def _render_rows(self, rows: list[dict]) -> None:
        self._clear_rows()
        self.count_label.configure(text=f"{len(rows)} archived students")

        if not rows:
            self.empty_label.grid(row=1, column=0, columnspan=6, sticky="nsew", padx=10, pady=14)
            return

        for idx, row in enumerate(rows, start=1):
            bg = theme.BG_ROW_ODD if idx % 2 else theme.BG_ROW_EVEN
            values = [
                str(row.get("student_id", "-")),
                self._display_name(row),
                self._class_name_from_id(row.get("class_id")),
                str(row.get("deleted_by", "-")),
                str(row.get("deleted_date", "-"))[:19],
            ]

            for col, value in enumerate(values):
                label = ctk.CTkLabel(
                    self.table_frame,
                    text=value,
                    font=ctk.CTkFont(size=13),
                    text_color=theme.TEXT_PRIMARY,
                    fg_color=bg,
                    anchor="w",
                    corner_radius=4,
                )
                label.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                self._row_widgets.append(label)

            actions = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            actions.grid(row=idx, column=5, sticky="e", padx=(6, 10), pady=2)
            self._row_widgets.append(actions)

            student_id = str(row.get("student_id", ""))
            student_name = self._display_name(row)

            restore_button = ctk.CTkButton(
                actions,
                text="Restore",
                command=lambda sid=student_id, name=student_name: self._handle_restore(sid, name),
                fg_color=theme.ACCENT,
                hover_color=theme.ACCENT_HOVER,
                width=90,
                height=30,
                corner_radius=6,
            )
            restore_button.pack(side="left", padx=(0, 8))
            self._row_widgets.append(restore_button)

            if self.role == "superadmin":
                delete_button = ctk.CTkButton(
                    actions,
                    text="Delete Permanently",
                    command=lambda sid=student_id, name=student_name: self._handle_permanent_delete(sid, name),
                    fg_color=theme.BTN_DANGER,
                    hover_color=theme.BTN_DANGER_HVR,
                    width=150,
                    height=30,
                    corner_radius=6,
                )
                delete_button.pack(side="left")
                self._row_widgets.append(delete_button)

    def refresh(self) -> None:
        try:
            self._classes = get_all_classes()
            rows = get_archive()
        except Exception as error:
            self._notify("Failed to load archive.", "error")
            if hasattr(self.app, "show_action_error"):
                self.app.show_action_error("Archive", "Unable to load archived students.", error)
            return

        self._render_rows(rows)

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role
        self.refresh()
