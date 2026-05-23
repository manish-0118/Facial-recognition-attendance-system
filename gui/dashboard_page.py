from __future__ import annotations

import customtkinter as ctk

from core.database import (
    get_all_admins,
    get_all_classes,
    get_all_students,
    get_today_attendance,
)

_AUTO_REFRESH_MS = 30_000

_STATUS_COLORS = {
    "present": "#4CAF50",
    "late": "#FFC107",
    "absent": "#F44336",
}

_COL_HEADERS = ["Name", "Student ID", "Class", "Time", "Status"]
_COL_WEIGHTS = [3, 2, 2, 2, 2]


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, username: str, role: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.username = username
        self.role = role

        self._after_id: str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_stats_row()
        self._build_table_section()

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
            text_color="white",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Here's a snapshot of today's attendance activity.",
            font=ctk.CTkFont(size=13),
            text_color="white",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self._refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            command=self._load,
            fg_color="#1E88E5",
            hover_color="#1565C0",
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
            ("Total Students", "#2C5EFF"),
            ("Total Classes", "#00897B"),
            ("Present Today", "#2E7D32"),
            ("Total Admins", "#6A1B9A"),
        ]
        for col, (title, accent) in enumerate(specs):
            card = ctk.CTkFrame(row, fg_color="#1A1A1A", corner_radius=10)
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0))
            card.grid_columnconfigure(0, weight=1)

            bar = ctk.CTkFrame(card, fg_color=accent, height=4, corner_radius=0)
            bar.grid(row=0, column=0, sticky="ew")

            value_lbl = ctk.CTkLabel(
                card,
                text="—",
                font=ctk.CTkFont(size=34, weight="bold"),
                text_color="#F5F5F5",
            )
            value_lbl.grid(row=1, column=0, sticky="w", padx=18, pady=(12, 4))
            self._stat_labels.append(value_lbl)

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=12),
                text_color="white",
            ).grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))

    def _build_table_section(self) -> None:
        section = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=10)
        section.grid(row=2, column=0, sticky="nsew", padx=24, pady=(18, 18))
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            section,
            text="Today's Attendance",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 10))

        scroll = ctk.CTkScrollableFrame(section, fg_color="transparent", corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        scroll.grid_columnconfigure(tuple(range(len(_COL_HEADERS))), weight=1)
        for i, w in enumerate(_COL_WEIGHTS):
            scroll.grid_columnconfigure(i, weight=w)
        self._table_scroll = scroll

        # fixed header row
        for col, heading in enumerate(_COL_HEADERS):
            ctk.CTkLabel(
                scroll,
                text=heading,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="white",
                anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=(12, 4), pady=(0, 6))

        self._table_row_widgets: list[list[ctk.CTkLabel]] = []

        self._empty_label = ctk.CTkLabel(
            scroll,
            text="No attendance records for today.",
            font=ctk.CTkFont(size=13),
            text_color="white",
        )

    # ── data loading ──────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            students = get_all_students()
            classes = get_all_classes()
            today = get_today_attendance()
            admins = get_all_admins()
        except Exception:
            return

        # update stat cards
        present_count = sum(1 for r in today if r.get("status") == "present")
        self._stat_labels[0].configure(text=str(len(students)))
        self._stat_labels[1].configure(text=str(len(classes)))
        self._stat_labels[2].configure(text=str(present_count))
        self._stat_labels[3].configure(text=str(len(admins)))

        # build class id → display name map
        class_map: dict[int, str] = {
            c["id"]: f"{c['name']} {c['section']}" for c in classes
        }

        self._refresh_table(today, class_map)

    def _refresh_table(self, rows: list[dict], class_map: dict[int, str]) -> None:
        scroll = self._table_scroll

        # destroy old data rows (keep header at row 0)
        for widget_row in self._table_row_widgets:
            for w in widget_row:
                w.destroy()
        self._table_row_widgets.clear()
        self._empty_label.grid_forget()

        if not rows:
            self._empty_label.grid(
                row=1, column=0, columnspan=len(_COL_HEADERS),
                padx=12, pady=20, sticky="w"
            )
            return

        for data_idx, record in enumerate(rows):
            grid_row = data_idx + 1  # row 0 is the header
            bg = "#1A1A1A" if data_idx % 2 == 0 else "#1F1F1F"
            status = str(record.get("status", "")).lower()
            status_color = _STATUS_COLORS.get(status, "white")
            class_display = class_map.get(record.get("class_id"), str(record.get("class_id", "—")))

            time_val = record.get("time")
            if time_val is not None:
                time_str = str(time_val)[:5]  # HH:MM from timedelta or time object
            else:
                time_str = "—"

            # Display full split name if available, otherwise fallback to name
            if record.get("first_name"):
                parts = [str(record.get("first_name"))]
                if record.get("middle_name"):
                    parts.append(str(record.get("middle_name")))
                if record.get("last_name"):
                    parts.append(str(record.get("last_name")))
                display_name = " ".join([p for p in parts if p])
            else:
                display_name = record.get("name", "—")

            cell_values = [
                display_name,
                record.get("student_id", "—"),
                class_display,
                time_str,
                status.capitalize() if status else "—",
            ]

            widget_row: list[ctk.CTkLabel] = []
            for col, (value, _) in enumerate(zip(cell_values, _COL_HEADERS)):
                text_color = status_color if col == 4 else "white"
                lbl = ctk.CTkLabel(
                    scroll,
                    text=value,
                    font=ctk.CTkFont(size=12),
                    text_color=text_color,
                    anchor="w",
                    fg_color=bg,
                )
                lbl.grid(row=grid_row, column=col, sticky="ew", padx=(12, 4), pady=2)
                widget_row.append(lbl)

            self._table_row_widgets.append(widget_row)

    # ── auto-refresh ──────────────────────────────────────────────────────

    def _schedule_refresh(self) -> None:
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        self._after_id = self.after(_AUTO_REFRESH_MS, self._auto_refresh)

    def _auto_refresh(self) -> None:
        self._load()
        self._schedule_refresh()

    # ── called by app.py ──────────────────────────────────────────────────

    def refresh(self) -> None:
        self._load()

    def update_user(self, username: str, role: str) -> None:
        """Called by app.py after login to update the displayed name."""
        self.username = username
        self.role = role
