from __future__ import annotations

import customtkinter as ctk

from core.database import get_audit_log, get_exports_log
from gui import theme


class AuditPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role
        self._audit_row_widgets: list[ctk.CTkBaseClass] = []
        self._export_row_widgets: list[ctk.CTkBaseClass] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(header, text="Audit & Export Logs", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left", padx=20, pady=15)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.permission_label = ctk.CTkLabel(
            body,
            text="",
            text_color=theme.DANGER,
            font=ctk.CTkFont(size=13),
            justify="left",
        )
        self.permission_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        self.audit_card = self._build_log_card(
            body,
            row=1,
            title="Audit Log",
            headers=["Admin", "Action", "Details", "Timestamp"],
            refresh_command=self.refresh_audit_log,
            refresh_label="Refresh Audit Log",
        )

        self.export_card = self._build_log_card(
            body,
            row=2,
            title="Export History",
            headers=["Admin", "Export Type", "Filename", "Timestamp"],
            refresh_command=self.refresh_export_log,
            refresh_label="Refresh Export History",
        )

        self.refresh()

    def _build_log_card(self, parent, row: int, title: str, headers: list[str], refresh_command, refresh_label: str):
        card = ctk.CTkFrame(parent, fg_color=theme.BG_SURFACE, corner_radius=14)
        card.grid(row=row, column=0, sticky="nsew", padx=20, pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(card, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            toolbar,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            toolbar,
            text=refresh_label,
            command=refresh_command,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            width=170,
        ).grid(row=0, column=1, sticky="e")

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        weights = [1, 1, 3, 2]
        for col, weight in enumerate(weights):
            scroll.grid_columnconfigure(col, weight=weight)
        for col, header in enumerate(headers):
            ctk.CTkLabel(
                scroll,
                text=header,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=(10, 6), pady=(0, 6))

        empty_label = ctk.CTkLabel(
            scroll,
            text="No records found.",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=13),
        )

        return {"card": card, "scroll": scroll, "empty": empty_label}

    def _is_superadmin(self) -> bool:
        return self.role == "superadmin"

    def _clear_row_widgets(self, widgets: list[ctk.CTkBaseClass], empty_label: ctk.CTkLabel) -> None:
        for widget in widgets:
            widget.destroy()
        widgets.clear()
        empty_label.grid_forget()

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, "show_notification"):
            self.master_frame.show_notification(message, kind)
        elif hasattr(self.master_frame, "notifications") and hasattr(self.master_frame.notifications, "show"):
            self.master_frame.notifications.show(message, kind=kind)

    def refresh_audit_log(self) -> None:
        self._clear_row_widgets(self._audit_row_widgets, self.audit_card["empty"])

        if not self._is_superadmin():
            self.audit_card["empty"].configure(text="Superadmin access required.")
            self.audit_card["empty"].grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=12)
            return

        try:
            rows = get_audit_log()
        except Exception as error:
            self._notify("Failed to load audit log.", "error")
            if hasattr(self.master_frame, "show_action_error"):
                self.master_frame.show_action_error("Audit Log", "Unable to fetch audit records.", error)
            return

        if not rows:
            self.audit_card["empty"].configure(text="No audit records found.")
            self.audit_card["empty"].grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=12)
            return

        for idx, row in enumerate(rows, start=1):
            bg = theme.BG_ROW_ODD if idx % 2 else theme.BG_ROW_EVEN
            values = [
                str(row.get("admin_username", "-")),
                str(row.get("action", "-")),
                str(row.get("details", "-")),
                str(row.get("timestamp", "-"))[:19],
            ]
            for col, value in enumerate(values):
                label = ctk.CTkLabel(
                    self.audit_card["scroll"],
                    text=value,
                    font=ctk.CTkFont(size=12),
                    text_color=theme.TEXT_PRIMARY,
                    fg_color=bg,
                    anchor="w",
                    corner_radius=4,
                )
                label.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                self._audit_row_widgets.append(label)

    def refresh_export_log(self) -> None:
        self._clear_row_widgets(self._export_row_widgets, self.export_card["empty"])

        if not self._is_superadmin():
            self.export_card["empty"].configure(text="Superadmin access required.")
            self.export_card["empty"].grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=12)
            return

        try:
            rows = get_exports_log()
        except Exception as error:
            self._notify("Failed to load export history.", "error")
            if hasattr(self.master_frame, "show_action_error"):
                self.master_frame.show_action_error("Export History", "Unable to fetch export records.", error)
            return

        if not rows:
            self.export_card["empty"].configure(text="No export records found.")
            self.export_card["empty"].grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=12)
            return

        for idx, row in enumerate(rows, start=1):
            bg = theme.BG_ROW_ODD if idx % 2 else theme.BG_ROW_EVEN
            values = [
                str(row.get("admin_username", "-")),
                str(row.get("export_type", "-")),
                str(row.get("filename", "-")),
                str(row.get("timestamp", "-"))[:19],
            ]
            for col, value in enumerate(values):
                label = ctk.CTkLabel(
                    self.export_card["scroll"],
                    text=value,
                    font=ctk.CTkFont(size=12),
                    text_color=theme.TEXT_PRIMARY,
                    fg_color=bg,
                    anchor="w",
                    corner_radius=4,
                )
                label.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                self._export_row_widgets.append(label)

    def refresh(self) -> None:
        if self._is_superadmin():
            self.permission_label.configure(text="", text_color="#888888")
        else:
            self.permission_label.configure(text="Only superadmin can access this page.", text_color="#FF5252")
        self.refresh_audit_log()
        self.refresh_export_log()

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role
        self.refresh()