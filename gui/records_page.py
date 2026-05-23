from __future__ import annotations

from datetime import date, datetime, timedelta
import io
import traceback

import customtkinter as ctk # pyright: ignore[reportMissingImports]
from tkinter import filedialog

from core.database import (
    get_all_classes,
    get_attendance_by_date,
    get_attendance_by_student,
    get_student_profile,
)

# plotting imports
_HAS_MATPLOTLIB = True
try:
    import matplotlib # pyright: ignore[reportMissingModuleSource]

    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure # pyright: ignore[reportMissingModuleSource]
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg # pyright: ignore[reportMissingModuleSource]
except Exception:
    _HAS_MATPLOTLIB = False

_HAS_PIL = True
try:
    from PIL import Image, ImageTk, ImageDraw # pyright: ignore[reportMissingImports]
except Exception:
    _HAS_PIL = False

_STATUS_COLORS = {
    "present": "#57C46D",
    "late": "#F4C542",
    "absent": "#FF6B6B",
}


class RecordsPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role

        # allow main card to expand full width
        self.grid_columnconfigure(0, weight=1)

        self._classes: list[dict] = []
        self._class_map: dict[str, dict] = {}
        self._selected_class_id: int | None = None
        self._current_date: date = date.today()

        # top-level frames for two-level UI
        self.level1_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.level1_frame.grid(row=0, column=0, sticky="nsew")
        self.level2_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.level2_frame.grid(row=0, column=0, sticky="nsew")
        self.level2_frame.grid_remove()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_level1()

        # initial load
        self._load_classes()

    # ---------- Level 1 (Class View) ----------
    def _build_level1(self) -> None:
        root = self.level1_frame
        # centered card container — full width with equal margins
        card = ctk.CTkFrame(root, fg_color="#1E1E1E", corner_radius=6)
        card.grid(row=0, column=0, sticky="nsew", padx=60, pady=20)
        card.grid_columnconfigure(0, weight=3)
        card.grid_columnconfigure(1, weight=2)

        # left side (60%) - controls + table
        left = ctk.CTkFrame(card, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(18, 12), pady=18)
        left.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(left, text="Class View", font=ctk.CTkFont(size=18, weight="bold"), text_color="white")
        title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        ctrl = ctk.CTkFrame(left, fg_color="transparent")
        ctrl.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ctrl.grid_columnconfigure(0, weight=1)
        ctrl.grid_columnconfigure(1, weight=2)

        ctk.CTkLabel(ctrl, text="Class:", text_color="white").grid(row=0, column=0, sticky="w")
        self.class_dropdown = ctk.CTkOptionMenu(ctrl, values=["Select Class"], width=320)
        self.class_dropdown.grid(row=0, column=1, sticky="w", padx=(8, 8))
        self.class_dropdown.set("Select Class")
        self.class_dropdown.configure(command=lambda _: self._on_class_change())

        # date navigator centered evenly
        nav = ctk.CTkFrame(left, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="ew", pady=(6, 8))
        nav.grid_columnconfigure(0, weight=1)
        nav.grid_columnconfigure(1, weight=1)
        nav.grid_columnconfigure(2, weight=1)

        self.prev_btn = ctk.CTkButton(nav, text="◀", width=40, command=self._prev_day)
        self.prev_btn.grid(row=0, column=0)
        self.date_label = ctk.CTkLabel(nav, text=self._format_date(self._current_date), text_color="white")
        self.date_label.grid(row=0, column=1)
        self.next_btn = ctk.CTkButton(nav, text="▶", width=40, command=self._next_day)
        self.next_btn.grid(row=0, column=2)

        # table area
        table_card = ctk.CTkFrame(left, fg_color="#1E1E1E", corner_radius=0)
        table_card.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        table_card.grid_columnconfigure(0, weight=1)
        # header row
        header_row = ctk.CTkFrame(table_card, fg_color="#1E1E1E")
        header_row.grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 4))
        for i, h in enumerate(["Student ID", "Name", "Status"]):
            ctk.CTkLabel(header_row, text=h, text_color="#888888", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=i, sticky="w", padx=8)

        self.table_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.table_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))

        # right side (40%) - chart
        right = ctk.CTkFrame(card, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 18), pady=18)
        right.grid_columnconfigure(0, weight=1)
        self._chart_frame = ctk.CTkFrame(right, fg_color="#1E1E1E")
        self._chart_frame.grid(row=0, column=0, sticky="nsew")
        self._init_overview_chart()

    def _load_classes(self) -> None:
        try:
            self._classes = get_all_classes() or []
        except Exception as e:
            self._notify(f"Failed to load classes: {e}", "error")
            self._classes = []

        options = ["Select Class"]
        self._class_map.clear()
        for c in self._classes:
            label = f"{c.get('name','')} {c.get('section','')} (ID: {c.get('id')})"
            options.append(label)
            self._class_map[label] = c

        current = self.class_dropdown.get() if hasattr(self, "class_dropdown") else "Select Class"
        self.class_dropdown.configure(values=options)
        self.class_dropdown.set(current if current in options else "Select Class")

    def _on_class_change(self) -> None:
        sel = self.class_dropdown.get()
        if not sel or sel == "Select Class":
            self._selected_class_id = None
            self._clear_table()
            return
        class_row = self._class_map.get(sel)
        self._selected_class_id = int(class_row.get("id")) if class_row else None
        self._fetch_and_render()

    def _prev_day(self) -> None:
        self._current_date -= timedelta(days=1)
        self.date_label.configure(text=self._format_date(self._current_date))
        if self._selected_class_id:
            self._fetch_and_render()

    def _next_day(self) -> None:
        self._current_date += timedelta(days=1)
        self.date_label.configure(text=self._format_date(self._current_date))
        if self._selected_class_id:
            self._fetch_and_render()

    def _format_date(self, d: date) -> str:
        try:
            return d.strftime("%A, %d %B %Y")
        except Exception:
            return str(d)

    def _clear_table(self) -> None:
        for w in list(self.table_scroll.children.values()):
            try:
                w.destroy()
            except Exception:
                pass

    def _fetch_and_render(self) -> None:
        self._clear_table()
        if not self._selected_class_id:
            return
        try:
            rows = get_attendance_by_date(self._current_date, self._selected_class_id) or []
        except Exception as e:
            self._notify(f"Failed to load attendance: {e}", "error")
            rows = []

        present_count = 0
        total = len(rows)

        for idx, r in enumerate(rows):
            sid = str(r.get("student_id", "-"))
            name = self._display_name(r)
            status = str(r.get("status", "")).lower()
            if status == "present":
                present_count += 1

            fg = _STATUS_COLORS.get(status, "white")
            bg = "#1E1E1E" if idx % 2 == 0 else "#252525"

            lbl_id = ctk.CTkLabel(self.table_scroll, text=sid, text_color="white", fg_color=bg, corner_radius=4)
            lbl_name = ctk.CTkLabel(self.table_scroll, text=name, text_color="white", fg_color=bg, corner_radius=4)
            lbl_status = ctk.CTkLabel(self.table_scroll, text=status.capitalize() if status else "-", text_color=fg, fg_color=bg, corner_radius=4)

            row = idx + 1
            lbl_id.grid(row=row, column=0, sticky="w", padx=8, pady=4, ipadx=6, ipady=6)
            lbl_name.grid(row=row, column=1, sticky="w", padx=8, pady=4, ipadx=6, ipady=6)
            lbl_status.grid(row=row, column=2, sticky="w", padx=8, pady=4, ipadx=6, ipady=6)

            # clickable name: underline on hover + pointer
            def on_enter(ev, lbl=lbl_name):
                try:
                    lbl.configure(text_color="#1E88E5")
                    lbl.configure(font=ctk.CTkFont(size=12, underline=True))
                    lbl.configure(cursor="hand2")
                except Exception:
                    pass

            def on_leave(ev, lbl=lbl_name):
                try:
                    lbl.configure(text_color="white")
                    lbl.configure(font=ctk.CTkFont(size=12, underline=False))
                    lbl.configure(cursor="")
                except Exception:
                    pass

            lbl_name.bind("<Enter>", on_enter)
            lbl_name.bind("<Leave>", on_leave)
            lbl_name.bind("<Button-1>", lambda e, sid=sid: self._open_student_view(sid))

        # update chart
        self._update_overview_chart(present_count, total)

    def _init_overview_chart(self) -> None:
        if not _HAS_MATPLOTLIB:
            self._chart_canvas = None
            return
        fig = Figure(figsize=(7, 3), dpi=100)
        # light background for chart area
        fig.patch.set_facecolor('#F5F5F5')
        self._overview_ax = fig.add_subplot(111)
        self._overview_ax.set_facecolor('#FFFFFF')
        self._overview_fig = fig
        self._chart_canvas = FigureCanvasTkAgg(fig, master=self._chart_frame)
        self._chart_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _update_overview_chart(self, present: int, total: int) -> None:
        if not _HAS_MATPLOTLIB or not hasattr(self, "_overview_ax"):
            return
        ax = self._overview_ax
        ax.clear()

        # If no class selected or no data, show empty state text
        if not self._selected_class_id or total == 0:
            ax.text(0.5, 0.5, "Select a class to view attendance", ha='center', va='center', color='black', fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])
            # remove spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            self._chart_canvas.draw()
            return

        labels = ["Present", "Total Students"]
        values = [present, total]
        colors = ["#2196F3", "#90A4AE"]
        bars = ax.bar(labels, values, color=colors)
        ax.set_title(f"Attendance Overview — {self._format_date(self._current_date)}", color='black')
        ax.set_ylim(0, max(1, total))
        # styling
        ax.set_facecolor('#FFFFFF')
        ax.title.set_color('black')
        ax.tick_params(colors='black')
        # remove top/right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        # subtle horizontal gridlines
        ax.yaxis.grid(True, alpha=0.3)
        # value labels
        try:
            ax.bar_label(bars, padding=3, color='black')
        except Exception:
            pass
        self._chart_canvas.draw()

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

    # ---------- Level 2 (Student View) ----------
    def _open_student_view(self, student_id: str) -> None:
        # hide level1
        self.level1_frame.grid_remove()
        self.level2_frame.grid()
        for w in list(self.level2_frame.children.values()):
            try:
                w.destroy()
            except Exception:
                pass

        # top back
        top = ctk.CTkFrame(self.level2_frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        back_btn = ctk.CTkButton(top, text="◀ Back", command=self._close_student_view, fg_color="#2A2A2A")
        back_btn.pack(side="left")

        # fetch profile
        try:
            profile = get_student_profile(student_id) or {}
        except Exception as e:
            self._notify(f"Failed to load student: {e}", "error")
            profile = {}

        # centered card for level2
        card = ctk.CTkFrame(self.level2_frame, fg_color="#1E1E1E", corner_radius=6)
        card.grid(row=1, column=0, sticky="nsew", padx=40, pady=12)
        card.grid_columnconfigure(0, weight=3)
        card.grid_columnconfigure(1, weight=2)

        # left: filters + table
        left = ctk.CTkFrame(card, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(18, 12), pady=18)
        left.grid_columnconfigure(0, weight=1)

        # filters (time buttons)
        filt_frame = ctk.CTkFrame(left, fg_color="transparent")
        filt_frame.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._filter_period = "7d"
        self._filter_buttons = {}
        for i, (key, label) in enumerate([("7d", "7 Days"), ("15d", "15 Days"), ("1m", "1 Month")]):
            btn = ctk.CTkButton(filt_frame, text=label, width=100, corner_radius=20, command=lambda k=key: self._apply_period(k))
            btn.grid(row=0, column=i, padx=6)
            self._filter_buttons[key] = btn
        filter_btn = ctk.CTkButton(filt_frame, text="Filter", width=80, corner_radius=20, command=self._show_custom_filter)
        filter_btn.grid(row=0, column=3, padx=6)

        # history area (table)
        table_card = ctk.CTkFrame(left, fg_color="#1E1E1E")
        table_card.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        table_card.grid_columnconfigure(0, weight=1)
        self._student_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self._student_scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # summary row under table
        summary = ctk.CTkFrame(left, fg_color="transparent")
        summary.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        # placeholders for colored labels
        self._present_label = ctk.CTkLabel(summary, text="Present: 0", text_color=_STATUS_COLORS["present"], font=ctk.CTkFont(size=14, weight="bold"))
        self._late_label = ctk.CTkLabel(summary, text="Late: 0", text_color=_STATUS_COLORS["late"], font=ctk.CTkFont(size=14, weight="bold"))
        self._absent_label = ctk.CTkLabel(summary, text="Absent: 0", text_color=_STATUS_COLORS["absent"], font=ctk.CTkFont(size=14, weight="bold"))
        self._pct_label = ctk.CTkLabel(summary, text="Attendance: 0%", text_color="#FFFFFF", font=ctk.CTkFont(size=14, weight="bold"))
        self._present_label.grid(row=0, column=0, padx=(0, 12))
        self._late_label.grid(row=0, column=1, padx=(0, 12))
        self._absent_label.grid(row=0, column=2, padx=(0, 12))
        self._pct_label.grid(row=0, column=3, padx=(0, 12))

        # right: profile card + chart
        right = ctk.CTkFrame(card, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 18), pady=18)
        right.grid_columnconfigure(0, weight=1)

        # profile card
        profile_card = ctk.CTkFrame(right, fg_color="#1A1A1A", corner_radius=6)
        profile_card.grid(row=0, column=0, sticky="ew", pady=(0, 12), padx=8)
        profile_card.grid_columnconfigure(0, weight=1)

        # photo + details inside profile card
        details = ctk.CTkFrame(profile_card, fg_color="transparent")
        details.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        details.grid_columnconfigure(0, weight=1)
        name = self._format_profile_name(profile)
        ctk.CTkLabel(details, text=name, font=ctk.CTkFont(size=16, weight="bold"), text_color="white").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(details, text=f"Student ID: {student_id}", text_color="#D0D0D0").grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(details, text=f"Class: {self._format_class_display(profile.get('class_id'))}", text_color="#D0D0D0").grid(row=2, column=0, sticky="w")

        photo_frame = ctk.CTkFrame(profile_card, fg_color="transparent")
        photo_frame.grid(row=0, column=1, sticky="e", padx=8, pady=8)
        photo = profile.get("profile_photo")
        if photo and _HAS_PIL:
            try:
                img = Image.open(io.BytesIO(photo)).convert("RGBA")
                img = img.resize((100, 100), Image.LANCZOS)
                mask = Image.new("L", (100, 100), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, 100, 100), fill=255)
                img.putalpha(mask)
                tkimg = ImageTk.PhotoImage(img)
                lbl = ctk.CTkLabel(photo_frame, image=tkimg, text="")
                lbl.image = tkimg
                lbl.grid(row=0, column=0)
            except Exception:
                ctk.CTkLabel(photo_frame, text="", width=100, height=6, fg_color="#444444").grid(row=0, column=0)
        else:
            ctk.CTkLabel(photo_frame, text="", width=100, height=6, fg_color="#444444").grid(row=0, column=0)

        # student chart
        self._student_chart_frame = ctk.CTkFrame(right, fg_color="#1E1E1E")
        self._student_chart_frame.grid(row=1, column=0, sticky="nsew", padx=8)

        # store references
        self._student_scroll = self._student_scroll

        # load default period
        self._apply_period("7d", student_id=student_id)

    def _close_student_view(self) -> None:
        self.level2_frame.grid_remove()
        self.level1_frame.grid()

    def _format_profile_name(self, profile: dict) -> str:
        fn = profile.get("first_name")
        if fn:
            parts = [str(fn).strip()]
            for key in ("middle_name", "last_name"):
                v = profile.get(key)
                if v:
                    parts.append(str(v).strip())
            return " ".join(parts)
        return str(profile.get("name", "-"))

    def _show_custom_filter(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Custom Filter")
        win.geometry("360x120")
        ctk.CTkLabel(win, text="From (YYYY-MM-DD)").pack(padx=8, pady=(8, 2))
        from_entry = ctk.CTkEntry(win, placeholder_text="YYYY-MM-DD")
        from_entry.pack(padx=8, pady=2)
        ctk.CTkLabel(win, text="To (YYYY-MM-DD)").pack(padx=8, pady=(6, 2))
        to_entry = ctk.CTkEntry(win, placeholder_text="YYYY-MM-DD")
        to_entry.pack(padx=8, pady=2)

        def apply_custom():
            frm = from_entry.get().strip()
            to = to_entry.get().strip()
            try:
                dfrom = datetime.fromisoformat(frm).date()
                dto = datetime.fromisoformat(to).date()
            except Exception:
                self._notify("Invalid dates. Use YYYY-MM-DD.", "error")
                return
            # call loader with custom range
            sid = getattr(self, "_last_student_id", None)
            if not sid:
                self._notify("No student selected.", "error")
                return
            self._load_student_history(sid, dfrom, dto)
            win.destroy()

        ctk.CTkButton(win, text="Apply", command=apply_custom).pack(pady=8)

    def _apply_period(self, key: str, student_id: str | None = None) -> None:
        # highlight button styles
        for k, btn in self._filter_buttons.items():
            btn.configure(fg_color="#1E88E5" if k == key else "#2A2A2A")
        self._filter_period = key
        if student_id:
            self._last_student_id = student_id
        sid = getattr(self, "_last_student_id", None)
        if not sid:
            return

        today = date.today()
        if key == "7d":
            start = today - timedelta(days=6)
        elif key == "15d":
            start = today - timedelta(days=14)
        else:
            start = today - timedelta(days=30)
        self._load_student_history(sid, start, today)

    def _load_student_history(self, student_id: str, start_date: date, end_date: date) -> None:
        self._last_student_id = student_id
        try:
            rows = get_attendance_by_student(student_id) or []
        except Exception as e:
            self._notify(f"Failed to load history: {e}", "error")
            rows = []

        # filter by date range
        filtered = []
        for r in rows:
            try:
                d = r.get("date")
                if isinstance(d, str):
                    d = datetime.fromisoformat(d).date()
                if d and start_date <= d <= end_date:
                    filtered.append(r)
            except Exception:
                continue

        # clear and render table
        for w in list(self._student_scroll.children.values()):
            try:
                w.destroy()
            except Exception:
                pass

        headers = ["Date", "Time", "Status"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(self._student_scroll, text=h, text_color="#888888", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=col, sticky="w", padx=8, pady=6)

        present = late = absent = 0
        dates = []
        status_map = {}
        for idx, r in enumerate(sorted(filtered, key=lambda x: x.get("date") or ""), start=1):
            d = r.get("date")
            t = str(r.get("time", ""))[:8]
            st = str(r.get("status", "")).lower()
            if st == "present":
                present += 1
            elif st == "late":
                late += 1
            else:
                absent += 1

            fg = _STATUS_COLORS.get(st, "white")
            bg = "#1E1E1E" if idx % 2 == 1 else "#252525"
            ctk.CTkLabel(self._student_scroll, text=str(d), text_color="white", fg_color=bg, corner_radius=4).grid(row=idx, column=0, sticky="w", padx=8, pady=2, ipadx=6, ipady=6)
            ctk.CTkLabel(self._student_scroll, text=t, text_color="white", fg_color=bg, corner_radius=4).grid(row=idx, column=1, sticky="w", padx=8, pady=2, ipadx=6, ipady=6)
            ctk.CTkLabel(self._student_scroll, text=st.capitalize() if st else "-", text_color=fg, fg_color=bg, corner_radius=4).grid(row=idx, column=2, sticky="w", padx=8, pady=2, ipadx=6, ipady=6)

            # for chart
            try:
                dd = r.get("date")
                if isinstance(dd, str):
                    dd = datetime.fromisoformat(dd).date()
                dates.append(dd)
                status_map[dd] = st
            except Exception:
                pass

        total = present + late + absent
        pct = int((present / total) * 100) if total > 0 else 0
        pct_color = "#57C46D" if pct > 75 else ("#F4C542" if pct >= 60 else "#FF6B6B")
        # update colored summary labels
        try:
            self._present_label.configure(text=f"Present: {present}")
            self._late_label.configure(text=f"Late: {late}")
            self._absent_label.configure(text=f"Absent: {absent}")
            self._pct_label.configure(text=f"Attendance: {pct}%", text_color=pct_color)
        except Exception:
            # fallback for older layout
            if hasattr(self, "_summary_label"):
                self._summary_label.configure(text=f"Present: {present} | Late: {late} | Absent: {absent} | Attendance: {pct}%", text_color=pct_color)

        # student chart
        self._update_student_chart(dates, status_map, start_date, end_date)

    def _update_student_chart(self, dates: list, status_map: dict, start: date, end: date) -> None:
        if not _HAS_MATPLOTLIB:
            return
        # prepare x-axis days
        n = (end - start).days + 1
        days = [start + timedelta(days=i) for i in range(n)]
        # build two-series: student status value (1/0.6/0) and class average percent
        status_vals = []
        status_colors = []
        avg_vals = []
        # compute class average attendance % for the period (present count / total students *100)
        total_days = len(days)
        for d in days:
            st = status_map.get(d, "absent")
            if st == "present":
                status_vals.append(1)
                status_colors.append(_STATUS_COLORS["present"])
            elif st == "late":
                status_vals.append(0.6)
                status_colors.append(_STATUS_COLORS["late"])
            else:
                status_vals.append(0)
                status_colors.append(_STATUS_COLORS["absent"])
            # placeholder for class average: if available in status_map like 'class_avg' use it, else compute from present fraction
            # here we approximate class average as present(1)/1 *100 else 0
            avg_pct = 100 if st == "present" else (60 if st == "late" else 0)
            avg_vals.append(avg_pct)

        fig = Figure(figsize=(7, 3.5), dpi=100)
        fig.patch.set_facecolor('#F5F5F5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#FFFFFF')

        x = [d.strftime("%d %b") for d in days]
        import numpy as _np
        indices = _np.arange(len(x))
        width = 0.35
        bars1 = ax.bar(indices - width/2, status_vals, width, color=status_colors, label='Status')
        bars2 = ax.bar(indices + width/2, avg_vals, width, color='#2196F3', label='Class Avg (%)')

        ax.set_xticks(indices)
        ax.set_xticklabels(x, rotation=45, ha='right')
        ax.set_title("Daily Attendance", color='black')
        ax.set_ylabel("Value", color='black')
        ax.tick_params(colors='black')
        # remove top/right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.yaxis.grid(True, alpha=0.3)
        # value labels
        try:
            ax.bar_label(bars1, padding=2, color='black')
        except Exception:
            pass
        try:
            ax.bar_label(bars2, padding=2, color='black')
        except Exception:
            pass

        # legend below chart
        ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.25), ncol=2)

        canvas = FigureCanvasTkAgg(fig, master=self._student_chart_frame)
        for w in list(self._student_chart_frame.children.values()):
            try:
                w.destroy()
            except Exception:
                pass
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas.draw()

    # ---------- Utilities ----------
    def _format_class_display(self, class_id: int | None) -> str:
        if class_id is None:
            return "-"
        for row in self._classes:
            if int(row.get("id", -1)) == int(class_id):
                return f"{row.get('name', '')} {row.get('section', '')}".strip()
        return str(class_id)

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, "show_notification"):
            self.master_frame.show_notification(message, kind)
        elif hasattr(self.master_frame, "notifications") and hasattr(self.master_frame.notifications, "show"):
            self.master_frame.notifications.show(message, kind=kind)

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role
