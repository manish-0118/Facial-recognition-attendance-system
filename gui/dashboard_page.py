from __future__ import annotations

import customtkinter as ctk

from core.database import (
    get_all_admins,
    get_all_classes,
    get_all_students,
    get_today_attendance,
    get_todays_birthdays,
)
from gui import theme

_AUTO_REFRESH_MS = 30_000


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, username: str, role: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.username = username
        self.role = role

        self._after_id: str | None = None
        self._birthday_card: ctk.CTkFrame | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_stats_row()

        self._load()
        self._schedule_refresh()

    # ── construction ──────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=f"Welcome back, {self.username}",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Here's an overview of your institution's attendance.",
            font=ctk.CTkFont(size=13),
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self._refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            command=self._load,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            width=100,
            height=34,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
        )
        self._refresh_btn.grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_stats_row(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=24, pady=(18, 0))
        for i in range(4):
            row.grid_columnconfigure(i, weight=1)

        self._stat_labels: list[ctk.CTkLabel] = []
        specs = [
            ("Total Students", theme.STAT_BLUE),
            ("Total Classes",  theme.STAT_TEAL),
            ("Present Today",  theme.STAT_GREEN),
            ("Total Admins",   theme.STAT_PURPLE),
        ]
        for col, (title, accent) in enumerate(specs):
            card = ctk.CTkFrame(row, fg_color=theme.BG_SURFACE, corner_radius=10)
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0))
            card.grid_columnconfigure(0, weight=1)

            bar = ctk.CTkFrame(card, fg_color=accent, height=4, corner_radius=0)
            bar.grid(row=0, column=0, sticky="ew")

            value_lbl = ctk.CTkLabel(
                card,
                text="—",
                font=ctk.CTkFont(size=34, weight="bold"),
                text_color=theme.TEXT_PRIMARY,
            )
            value_lbl.grid(row=1, column=0, sticky="w", padx=18, pady=(12, 4))
            self._stat_labels.append(value_lbl)

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=12),
                text_color=theme.TEXT_SECONDARY,
            ).grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))

    # ── data loading ──────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            students = get_all_students()
            classes  = get_all_classes()
            today    = get_today_attendance()
            admins   = get_all_admins()
        except Exception:
            return

        present_count = sum(1 for r in today if r.get("status") == "present")
        self._stat_labels[0].configure(text=str(len(students)))
        self._stat_labels[1].configure(text=str(len(classes)))
        self._stat_labels[2].configure(text=str(present_count))
        self._stat_labels[3].configure(text=str(len(admins)))

        try:
            birthdays = get_todays_birthdays()
        except Exception:
            birthdays = []
        self._update_birthday_card(birthdays)

    def _update_birthday_card(self, birthdays: list[dict]) -> None:
        if self._birthday_card is not None:
            try:
                self._birthday_card.destroy()
            except Exception:
                pass
            self._birthday_card = None

        if not birthdays:
            return

        card = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=10)
        card.grid(row=2, column=0, sticky="ew", padx=24, pady=(12, 0))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="🎂",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=22),
        ).grid(row=0, column=0, rowspan=2, padx=(16, 10), pady=14)

        ctk.CTkLabel(
            card,
            text="Birthdays Today",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=1, sticky="w", pady=(14, 2))

        names = "  •  ".join(self._format_birthday_name(b) for b in birthdays)
        ctk.CTkLabel(
            card,
            text=names,
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
            wraplength=700,
            justify="left",
        ).grid(row=1, column=1, sticky="w", pady=(0, 14))

        self._birthday_card = card

    def _format_birthday_name(self, b: dict) -> str:
        parts = [b.get('first_name', ''), b.get('middle_name', ''), b.get('last_name', '')]
        name = ' '.join(p for p in parts if p).strip()
        return name or str(b.get('name') or b.get('student_id') or '?')

    # ── auto-refresh ──────────────────────────────────────────────────────

    def _schedule_refresh(self) -> None:
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        self._after_id = self.after(_AUTO_REFRESH_MS, self._auto_refresh)

    def _auto_refresh(self) -> None:
        self._load()
        self._schedule_refresh()

    def refresh(self) -> None:
        self._load()

