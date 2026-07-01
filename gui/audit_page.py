from __future__ import annotations

import threading

import customtkinter as ctk

from core.database import get_audit_log, get_exports_log
from gui import theme

# ── Module-level prefetch ─────────────────────────────────────────────────────
# Started right after login so data is ready before the user ever clicks the page.
_prefetched: tuple[list[dict], list[dict]] | None = None   # (audit_rows, export_rows)


def prefetch_audit_data(role: str) -> None:
    """Kick off a background fetch immediately after login. Safe to call from main thread."""
    global _prefetched
    _prefetched = None
    if role != "superadmin":
        return

    def _fetch() -> None:
        global _prefetched
        try:
            audit = get_audit_log()
        except Exception:
            audit = []
        try:
            export = get_exports_log()
        except Exception:
            export = []
        _prefetched = (audit, export)   # atomic write — GIL-safe

    threading.Thread(target=_fetch, daemon=True).start()


def clear_audit_prefetch() -> None:
    """Reset the prefetch cache on logout."""
    global _prefetched
    _prefetched = None


# ─────────────────────────────────────────────────────────────────────────────

class AuditPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role

        self._audit_row_widgets: list[ctk.CTkBaseClass] = []
        self._export_row_widgets: list[ctk.CTkBaseClass] = []

        # Cache: None = not yet fetched, list = cached result
        self._cached_audit:  list[dict] | None = None
        self._cached_export: list[dict] | None = None
        self._fetching = False

        self._view = "center"  # "audit" | "center" | "export"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        header.grid_columnconfigure(2, weight=1)
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="Audit & Export Logs",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=15)

        # 3-segment pill toggle
        pill = ctk.CTkFrame(header, fg_color=theme.BG_SURFACE_ALT, corner_radius=8)
        pill.grid(row=0, column=1, pady=12)

        self._toggle_btns: dict[str, ctk.CTkButton] = {}
        for name, label, width in [
            ("audit",  "Audit Log",      130),
            ("center", "◆",               36),
            ("export", "Export History", 150),
        ]:
            btn = ctk.CTkButton(
                pill, text=label, width=width, height=34, corner_radius=6,
                fg_color="transparent", hover_color=theme.BG_HOVER,
                text_color=theme.TEXT_MUTED,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda n=name: self._set_view(n),
            )
            btn.pack(side="left", padx=2, pady=2)
            self._toggle_btns[name] = btn

        # ── Body ──────────────────────────────────────────────────────────
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_rowconfigure(1, weight=1)

        self.audit_card  = self._build_log_card(self.body, 0, "Audit Log",
                                                ["Admin", "Action", "Details", "Timestamp"],
                                                self._refresh_audit_clicked)
        self.export_card = self._build_log_card(self.body, 1, "Export History",
                                                ["Admin", "Export Type", "Filename", "Timestamp"],
                                                self._refresh_export_clicked)

        self._apply_view()
        # Use prefetched data if already ready; otherwise start our own background fetch
        if _prefetched is not None:
            self._on_fetch_done(_prefetched[0], _prefetched[1])
        else:
            self._start_fetch()

    # ── Toggle ────────────────────────────────────────────────────────────

    def _set_view(self, view: str) -> None:
        self._view = view
        self._apply_view()

    def _apply_view(self) -> None:
        v = self._view
        for name, btn in self._toggle_btns.items():
            if name == v:
                btn.configure(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                              text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", hover_color=theme.BG_HOVER,
                              text_color=theme.TEXT_MUTED)

        if v == "audit":
            self.audit_card["card"].grid()
            self.export_card["card"].grid_remove()
            self.body.grid_rowconfigure(0, weight=1)
            self.body.grid_rowconfigure(1, weight=0)
        elif v == "export":
            self.audit_card["card"].grid_remove()
            self.export_card["card"].grid()
            self.body.grid_rowconfigure(0, weight=0)
            self.body.grid_rowconfigure(1, weight=1)
        else:
            self.audit_card["card"].grid()
            self.export_card["card"].grid()
            self.body.grid_rowconfigure(0, weight=1)
            self.body.grid_rowconfigure(1, weight=1)

    # ── Card builder ──────────────────────────────────────────────────────

    def _build_log_card(self, parent, row: int, title: str,
                        headers: list[str], refresh_cmd) -> dict:
        card = ctk.CTkFrame(parent, fg_color=theme.BG_SURFACE, corner_radius=14)
        card.grid(row=row, column=0, sticky="nsew", padx=20, pady=(10, 10))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(card, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        toolbar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(toolbar, text=title,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(toolbar, text="Refresh", command=refresh_cmd,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      width=90, height=30, corner_radius=6,
                      font=ctk.CTkFont(size=12)).grid(row=0, column=1, sticky="e")

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        weights = [1, 1, 3, 2]
        for col, weight in enumerate(weights):
            scroll.grid_columnconfigure(col, weight=weight)
        for col, header in enumerate(headers):
            ctk.CTkLabel(scroll, text=header,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=theme.TEXT_SECONDARY, anchor="w",
                         ).grid(row=0, column=col, sticky="ew", padx=(10, 6), pady=(0, 6))

        status_lbl = ctk.CTkLabel(scroll, text="",
                                  text_color=theme.TEXT_MUTED,
                                  font=ctk.CTkFont(size=13))

        return {"card": card, "scroll": scroll, "status": status_lbl}

    # ── Background fetch ──────────────────────────────────────────────────

    def _start_fetch(self) -> None:
        if self._fetching:
            return
        self._fetching = True
        self._set_status("audit",  "Loading...", theme.TEXT_MUTED)
        self._set_status("export", "Loading...", theme.TEXT_MUTED)
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _do_fetch(self) -> None:
        audit_rows:  list[dict] = []
        export_rows: list[dict] = []

        if self._is_superadmin():
            try:
                audit_rows = get_audit_log()
            except Exception:
                audit_rows = []
            try:
                export_rows = get_exports_log()
            except Exception:
                export_rows = []

        try:
            self.after(0, lambda a=audit_rows, e=export_rows: self._on_fetch_done(a, e))
        except Exception:
            pass

    def _on_fetch_done(self, audit_rows: list[dict], export_rows: list[dict]) -> None:
        self._fetching = False
        self._cached_audit  = audit_rows
        self._cached_export = export_rows
        self._render_audit(audit_rows)
        self._render_export(export_rows)

    # ── Render helpers ────────────────────────────────────────────────────

    def _set_status(self, card_key: str, text: str, color: str) -> None:
        card = self.audit_card if card_key == "audit" else self.export_card
        lbl = card["status"]
        lbl.configure(text=text, text_color=color)
        lbl.grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=12)

    def _hide_status(self, card_key: str) -> None:
        card = self.audit_card if card_key == "audit" else self.export_card
        card["status"].grid_forget()

    def _clear_rows(self, widgets: list, card_key: str) -> None:
        for w in widgets:
            try:
                w.destroy()
            except Exception:
                pass
        widgets.clear()
        self._hide_status(card_key)

    def _render_audit(self, rows: list[dict]) -> None:
        self._clear_rows(self._audit_row_widgets, "audit")

        if not self._is_superadmin():
            self._set_status("audit", "Superadmin access required.", theme.DANGER)
            return

        if not rows:
            self._set_status("audit", "No audit records found.", theme.TEXT_MUTED)
            return

        scroll = self.audit_card["scroll"]
        for idx, row in enumerate(rows, start=1):
            bg = theme.BG_ROW_ODD if idx % 2 else theme.BG_ROW_EVEN
            for col, val in enumerate([
                str(row.get("admin_username", "-")),
                str(row.get("action", "-")),
                str(row.get("details", "-")),
                str(row.get("timestamp", "-"))[:19],
            ]):
                lbl = ctk.CTkLabel(scroll, text=val, font=ctk.CTkFont(size=12),
                                   text_color=theme.TEXT_PRIMARY, fg_color=bg,
                                   anchor="w", corner_radius=4)
                lbl.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                self._audit_row_widgets.append(lbl)

    def _render_export(self, rows: list[dict]) -> None:
        self._clear_rows(self._export_row_widgets, "export")

        if not self._is_superadmin():
            self._set_status("export", "Superadmin access required.", theme.DANGER)
            return

        if not rows:
            self._set_status("export", "No export records found.", theme.TEXT_MUTED)
            return

        scroll = self.export_card["scroll"]
        for idx, row in enumerate(rows, start=1):
            bg = theme.BG_ROW_ODD if idx % 2 else theme.BG_ROW_EVEN
            for col, val in enumerate([
                str(row.get("admin_username", "-")),
                str(row.get("export_type", "-")),
                str(row.get("filename", "-")),
                str(row.get("timestamp", "-"))[:19],
            ]):
                lbl = ctk.CTkLabel(scroll, text=val, font=ctk.CTkFont(size=12),
                                   text_color=theme.TEXT_PRIMARY, fg_color=bg,
                                   anchor="w", corner_radius=4)
                lbl.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                self._export_row_widgets.append(lbl)

    # ── Refresh button handlers ───────────────────────────────────────────

    def _refresh_audit_clicked(self) -> None:
        self._cached_audit = None
        self._start_fetch()

    def _refresh_export_clicked(self) -> None:
        self._cached_export = None
        self._start_fetch()

    # ── Public API ────────────────────────────────────────────────────────

    def _is_superadmin(self) -> bool:
        return self.role == "superadmin"

    def refresh(self) -> None:
        # Called on initial load — use cache if available, else fetch
        if self._cached_audit is not None and self._cached_export is not None:
            self._render_audit(self._cached_audit)
            self._render_export(self._cached_export)
        else:
            self._start_fetch()

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role
        self._cached_audit  = None
        self._cached_export = None
        self._start_fetch()

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, "show_notification"):
            self.master_frame.show_notification(message, kind)
