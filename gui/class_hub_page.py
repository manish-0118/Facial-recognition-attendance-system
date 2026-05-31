from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from typing import List

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.database import (
    get_all_classes,
    get_class_count,
    get_max_classes,
    add_class,
    delete_class,
    get_attendance_by_date,
    get_attendance_by_student,
    get_student_profile,
    get_students_by_class,
)
from core.face_engine import get_model_status

# Optional heavy deps
try:
    import pandas as pd
except Exception:
    pd = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
except Exception:
    SimpleDocTemplate = None

_HAS_MATPLOTLIB = True
try:
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.animation import FuncAnimation
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import numpy as _np
except Exception:
    _HAS_MATPLOTLIB = False

_STATUS_COLORS = {
    "present": "#57C46D",
    "late": "#F4C542",
    "absent": "#FF6B6B",
}


class ClassHubPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.master_frame = master
        self.username = username
        self.role = role

        self._classes: List[dict] = []
        self._class_map = {}
        self._selected_class_id = None
        self._selected_date = date.today()
        self._selected_student_id = None
        self._active_popup = None

        self.level0 = ctk.CTkFrame(self, fg_color="transparent")
        self.level1 = ctk.CTkFrame(self, fg_color="transparent")
        self.level2 = ctk.CTkFrame(self, fg_color="transparent")
        for lvl in (self.level0, self.level1, self.level2):
            lvl.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.level1.grid_remove()
        self.level2.grid_remove()

        self._build_level0()
        self._build_level1()
        self._build_level2()
        self._load_classes()
        
    def _build_level0(self) -> None:
        root = self.level0
        # layout weights
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=1)

        # Top card: title and add control
        top_card = ctk.CTkFrame(root, fg_color="#1E1E1E", corner_radius=8)
        top_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(13, 6))
        top_card.grid_columnconfigure(0, weight=1)
        top_card.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(top_card, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(12,0), pady=12)
        title = ctk.CTkLabel(left, text="Classes", font=ctk.CTkFont(size=28, weight='bold'), text_color='white')
        title.grid(row=0, column=0, sticky='w')
        self.class_count_label = ctk.CTkLabel(left, text="0 classes", font=ctk.CTkFont(size=13), text_color='#B0BEC5')
        self.class_count_label.grid(row=1, column=0, sticky='w', pady=(2,0))

        add_btn = ctk.CTkButton(top_card, text="Add Class", fg_color="#4CAF50", command=self._toggle_add_panel)
        add_btn.grid(row=0, column=1, sticky='e', padx=(0,12), pady=12)

        # Slide-down add panel (hidden by default)
        # placed under top_card visually; styled as card
        self._add_panel = ctk.CTkFrame(top_card, fg_color='#1E1E1E', corner_radius=8)
        self._add_panel.grid(row=1, column=0, columnspan=2, sticky='ew', padx=12, pady=(8,8))
        self._add_panel.grid_columnconfigure(0, weight=1)
        # build form fields
        labels = [
            ("Class Name", "name"),
            ("Section", "section"),
            ("Max Students", "max_students"),
            ("Late Cutoff (mins)", "late_cutoff"),
            ("Absent Cutoff (mins)", "absent_cutoff"),
            ("Class Start (HH:MM)", "start_time"),
            ("Class End (HH:MM)", "end_time"),
        ]
        self._add_entries = {}
        form = ctk.CTkFrame(self._add_panel, fg_color='transparent')
        form.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        for i, (label, key) in enumerate(labels):
            ctk.CTkLabel(form, text=label, text_color='white').grid(row=i, column=0, sticky='w', padx=12, pady=(8,4))
            ent = ctk.CTkEntry(form, height=30)
            ent.grid(row=i, column=1, sticky='ew', padx=12, pady=(8,4))
            self._add_entries[key] = ent
        form.grid_columnconfigure(1, weight=1)
        btn_frame = ctk.CTkFrame(form, fg_color='transparent')
        btn_frame.grid(row=len(labels), column=0, columnspan=2, sticky='e', padx=12, pady=(8,12))
        save_btn = ctk.CTkButton(btn_frame, text="Save", fg_color="#4CAF50", command=self._handle_add_class)
        save_btn.grid(row=0, column=0, padx=(0,8))
        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", fg_color="#2A2A2A", command=self._toggle_add_panel)
        cancel_btn.grid(row=0, column=1)
        # hide initially
        try:
            self._add_panel.grid_remove()
        except Exception:
            pass

        # Bottom card: list of class cards (scrollable)
        bottom_card = ctk.CTkFrame(root, fg_color="#1E1E1E", corner_radius=8)
        bottom_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 13))
        bottom_card.grid_propagate(False)
        bottom_card.grid_rowconfigure(0, weight=1)
        bottom_card.grid_columnconfigure(0, weight=1)

        self.cards_frame = ctk.CTkScrollableFrame(bottom_card, fg_color='transparent')
        self.cards_frame.grid(row=0, column=0, sticky='nsew')
        try:
            self.cards_frame.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

    def _toggle_add_panel(self) -> None:
        if self._add_panel.winfo_ismapped():
            self._add_panel.grid_remove()
        else:
            self._add_panel.grid()

    def _handle_add_class(self) -> None:
        try:
            name = self._add_entries["name"].get().strip()
            section = self._add_entries["section"].get().strip()
            max_students = int(self._add_entries["max_students"].get() or 30)
            late = self._add_entries["late_cutoff"].get().strip() or None
            absent = self._add_entries["absent_cutoff"].get().strip() or None
            start = self._add_entries["start_time"].get().strip() or None
            end = self._add_entries["end_time"].get().strip() or None
            if not name or not section:
                self._notify("Name and section required.", "error")
                return
            add_class(name, section, self.username or "system", max_students=max_students, late_cutoff=late, absent_cutoff=absent, class_start_time=start, class_end_time=end)
            self._notify("Class added.", "success")
            self._add_panel.grid_remove()
            self._load_classes()
        except Exception as e:
            self._notify(f"Failed to add class: {e}", "error")

    def _load_classes(self) -> None:
        try:
            self._classes = get_all_classes() or []
        except Exception:
            self._classes = []
        # clear cards
        for w in list(self.cards_frame.children.values()):
            try:
                w.destroy()
            except Exception:
                pass
        # render full-width compact cards
        self._class_map = {}
        for idx, c in enumerate(self._classes):
            card = ctk.CTkFrame(self.cards_frame, fg_color="#2A2A2A", corner_radius=10)
            # full width, fixed height
            card.grid(row=idx, column=0, sticky="ew", padx=12, pady=6)
            card.configure(height=60)
            card.grid_propagate(False)
            card.grid_rowconfigure(0, weight=1)
            # inner grid: 5 columns with specified weights/minsizes for consistent alignment
            card.grid_columnconfigure(0, weight=0, minsize=200)
            card.grid_columnconfigure(1, weight=1)
            card.grid_columnconfigure(2, weight=1)
            card.grid_columnconfigure(3, weight=1)
            card.grid_columnconfigure(4, weight=0, minsize=50)

            # class name
            name_lbl = ctk.CTkLabel(card, text=c.get("name", ""), font=ctk.CTkFont(size=15, weight="bold"), text_color="white")
            name_lbl.grid(row=0, column=0, sticky="w", padx=(16,0), pady=0)

            # section
            sect_lbl = ctk.CTkLabel(card, text=c.get("section", ""), text_color="#B0BEC5", font=ctk.CTkFont(size=12))
            sect_lbl.grid(row=0, column=1, sticky="ew")

            # present count
            try:
                rows = get_attendance_by_date(date.today(), c.get("id")) or []
                present = sum(1 for r in rows if str(r.get("status", "")).lower() == "present")
            except Exception:
                present = 0
            try:
                students = get_students_by_class(c.get("id")) or []
                total = len(students)
            except Exception:
                # fallback to stored max_students if query fails
                total = int(c.get("max_students") or 0)
            ctr_lbl = ctk.CTkLabel(card, text=f"{present} / {total} Present", text_color="#FFFFFF", font=ctk.CTkFont(size=12))
            ctr_lbl.grid(row=0, column=2, sticky="ew")

            # attendance percentage label (colored)
            pct = (present / max(1, total)) * 100 if total > 0 else 0
            pct_color = "#57C46D" if pct > 75 else ("#F4C542" if pct >= 50 else "#FF6B6B")
            pct_text = f"{int(pct)}%"
            pct_lbl = ctk.CTkLabel(card, text=pct_text, font=ctk.CTkFont(size=13, weight="bold"), text_color=pct_color)
            pct_lbl.grid(row=0, column=3, sticky="ew")

            # three-dots menu button instead of Delete
            dots_btn = ctk.CTkButton(card, text="⋮", width=32, height=32, fg_color="transparent", hover_color="#2A2A2A", font=ctk.CTkFont(size=18))
            dots_btn.grid(row=0, column=4, sticky="e", padx=(0,8))
            dots_btn.configure(command=lambda cid=c.get("id"), w=dots_btn: self._show_card_menu(cid, w))

            # click anywhere on card (but not the delete button) -> go to detail
            def make_open(cid):
                return lambda e=None: self._open_class_detail(cid)

            card.bind("<Button-1>", make_open(c.get("id")))
            for child in card.winfo_children():
                try:
                    if isinstance(child, ctk.CTkButton):
                        continue
                    child.bind("<Button-1>", make_open(c.get("id")))
                except Exception:
                    pass

            self._class_map[c.get("id")] = c

        self.class_count_label.configure(text=f"{len(self._classes)} classes")
        if not self._classes:
            lbl = ctk.CTkLabel(self.cards_frame, text="No classes added yet. Click Add Class to get started.", text_color="white")
            lbl.grid(row=0, column=0, padx=12, pady=12)

    def _confirm_and_delete(self, class_id: int, class_name: str) -> None:
        if not messagebox.askyesno("Delete Class", f"Delete class {class_name}? This will remove students' class association."):
            return
        try:
            delete_class(class_id, self.username or "system")
            self._notify("Class deleted.", "success")
            self._load_classes()
        except Exception as e:
            self._notify(f"Failed to delete class: {e}", "error")

    # ---------------- Level 1: Class Detail ----------------
    def _build_level1(self) -> None:
        root = self.level1
        # Use same top/bottom sizing as Level 0
        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        # Top card: class title and date navigator
        top_card = ctk.CTkFrame(root, fg_color="#1E1E1E", corner_radius=8)
        top_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(13, 6))
        top_card.grid_columnconfigure(0, weight=0)
        top_card.grid_columnconfigure(1, weight=1)
        top_card.grid_columnconfigure(2, weight=0)

        back = ctk.CTkButton(top_card, text="◀ Back", command=self._back_to_level0, fg_color="#2A2A2A")
        back.grid(row=0, column=0, sticky="w", padx=(12,8), pady=12)

        self.level1_title = ctk.CTkLabel(top_card, text="", font=ctk.CTkFont(size=24, weight="bold"), text_color="white")
        self.level1_title.grid(row=0, column=1, sticky="w", padx=(0,0), pady=12)

        nav_frame = ctk.CTkFrame(top_card, fg_color="transparent")
        nav_frame.grid(row=0, column=2, sticky="e", padx=(8,12), pady=12)
        self.prev_btn = ctk.CTkButton(nav_frame, text="◀", width=40, command=lambda: self._change_date(-1))
        self.prev_btn.grid(row=0, column=0)
        self.level1_date_label = ctk.CTkLabel(nav_frame, text=self._format_date(self._selected_date), text_color="white")
        self.level1_date_label.grid(row=0, column=1, padx=8)
        self.next_btn = ctk.CTkButton(nav_frame, text="▶", width=40, command=lambda: self._change_date(1))
        self.next_btn.grid(row=0, column=2)

        # Bottom card: main content area
        bottom_card = ctk.CTkFrame(root, fg_color="#1E1E1E", corner_radius=8)
        bottom_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 13))
        bottom_card.grid_rowconfigure(0, weight=1)
        # single column layout now; left_card takes full width
        bottom_card.grid_columnconfigure(0, weight=1)

        # Left inner card (students list)
        left_card = ctk.CTkFrame(bottom_card, fg_color="#2A2A2A", corner_radius=8)
        # left_card now spans full width
        left_card.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        left_card.grid_rowconfigure(1, weight=1)
        left_card.grid_columnconfigure(0, weight=1)

        # toggle buttons: Attendance / Students
        self._level1_view_mode = "attendance"
        toggle_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        toggle_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(8,6))
        toggle_frame.grid_columnconfigure(0, weight=1)
        toggle_frame.grid_columnconfigure(1, weight=1)
        self._attendance_btn = ctk.CTkButton(toggle_frame, text="Attendance", fg_color="#1E88E5", command=lambda: self._set_level1_view("attendance"))
        self._attendance_btn.grid(row=0, column=0, sticky="w", padx=(8,4))
        self._students_btn = ctk.CTkButton(toggle_frame, text="Students", fg_color="#2A2A2A", command=lambda: self._set_level1_view("students"))
        self._students_btn.grid(row=0, column=1, sticky="e", padx=(4,8))

        # header row labels area (we will populate in render)
    
        self._level1_scroll = ctk.CTkScrollableFrame(left_card, fg_color="transparent")
        # place scroll frame directly below toggles with minimal top gap
        self._level1_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4,0))
        # ensure scroll frame expands horizontally so child row frames stretch full width
        try:
            self._level1_scroll.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

        # Stats bar at bottom of left_card (reserved height) — visible only in Attendance mode
        try:
            self._level1_stats_bar = ctk.CTkFrame(left_card, fg_color="#1A1A1A", height=50)
            self._level1_stats_bar.grid(row=2, column=0, sticky="ew", padx=6, pady=(8,8))
            self._level1_stats_bar.grid_propagate(False)
            # labels: Present, Late, Absent, Percentage
            self._stats_present_lbl = ctk.CTkLabel(self._level1_stats_bar, text="🟢 Present: 0", text_color=_STATUS_COLORS['present'])
            self._stats_late_lbl = ctk.CTkLabel(self._level1_stats_bar, text="🟡 Late: 0", text_color=_STATUS_COLORS['late'])
            self._stats_absent_lbl = ctk.CTkLabel(self._level1_stats_bar, text="🔴 Absent: 0", text_color=_STATUS_COLORS['absent'])
            self._stats_pct_lbl = ctk.CTkLabel(self._level1_stats_bar, text="📊 0%", text_color='white')
            # place labels in a row
            self._stats_present_lbl.grid(row=0, column=0, padx=(12,8))
            self._stats_late_lbl.grid(row=0, column=1, padx=(8,8))
            self._stats_absent_lbl.grid(row=0, column=2, padx=(8,8))
            self._stats_pct_lbl.grid(row=0, column=3, padx=(8,12))
        except Exception:
            self._level1_stats_bar = None
            self._stats_present_lbl = None
            self._stats_late_lbl = None
            self._stats_absent_lbl = None
            self._stats_pct_lbl = None

        # right_card removed — Level 1 uses the left_card full width and a bottom stats bar instead

    def _open_class_detail(self, class_id: int) -> None:
        self._selected_class_id = class_id
        cls = self._class_map.get(class_id) or {}
        self.level1_title.configure(text=f"{cls.get('name','')} {cls.get('section','')}")
        self.level1_date_label.configure(text=self._format_date(self._selected_date))
        self.level0.grid_remove()
        self.level1.grid()
        self._render_level1()

    def _set_level1_view(self, mode: str) -> None:
        if mode not in ("attendance", "students"):
            return
        self._level1_view_mode = mode
        # update button colors
        try:
            self._attendance_btn.configure(fg_color="#1E88E5" if mode == "attendance" else "#2A2A2A")
            self._students_btn.configure(fg_color="#1E88E5" if mode == "students" else "#2A2A2A")
        except Exception:
            pass
        # show/hide stats bar depending on mode
        try:
            if mode == "attendance":
                try:
                    if getattr(self, '_level1_stats_bar', None):
                        self._level1_stats_bar.grid()
                except Exception:
                    pass
            else:
                try:
                    if getattr(self, '_level1_stats_bar', None):
                        self._level1_stats_bar.grid_remove()
                except Exception:
                    pass
        except Exception:
            pass
        self._render_level1()

    def _back_to_level0(self) -> None:
        self.level1.grid_remove()
        self.level0.grid()
        self._load_classes()

    def _change_date(self, delta: int) -> None:
        self._selected_date += timedelta(days=delta)
        self.level1_date_label.configure(text=self._format_date(self._selected_date))
        self._render_level1()

    def _render_level1(self) -> None:
        # clear header and table
        
        for w in list(self._level1_scroll.children.values()):
            try:
                w.destroy()
            except Exception:
                pass
        if not self._selected_class_id:
            return
        mode = getattr(self, "_level1_view_mode", "attendance")
        if mode == "attendance":
            try:
                rows = get_attendance_by_date(self._selected_date, self._selected_class_id) or []
            except Exception:
                rows = []
            # ensure stats bar visible
            try:
                if getattr(self, '_level1_stats_bar', None):
                    self._level1_stats_bar.grid()
            except Exception:
                pass
            # header (inside scroll frame at row=0) — configured column weights for alignment
            header_container = ctk.CTkFrame(self._level1_scroll, fg_color='transparent')
            header_container.grid(row=0, column=0, sticky='ew', padx=8, pady=(4,4))
            header_container.grid_columnconfigure(0, minsize=100, weight=0)
            header_container.grid_columnconfigure(1, weight=1)
            header_container.grid_columnconfigure(2, minsize=180, weight=0)
            for i, h in enumerate(["Student ID", "Name", "Status"]):
                ctk.CTkLabel(header_container, text=h, text_color="#888888", font=ctk.CTkFont(size=12, weight="bold"), anchor="center").grid(row=0, column=i, sticky="ew", padx=6, pady=0)
            # rows
            def _sid_key(x):
                try:
                    return int(str(x.get('student_id', 0)).strip() or 0)
                except Exception:
                    return 0

            for idx, r in enumerate(sorted(rows, key=_sid_key)):
                sid = str(r.get("student_id", "-"))
                name = self._display_name(r)
                status = str(r.get("status", "")).lower()
                fg = _STATUS_COLORS.get(status, "white")
                bg = "#1E1E1E" if idx % 2 == 0 else "#252525"
                rnum = idx + 1
                # row container
                row_frame = ctk.CTkFrame(self._level1_scroll, fg_color=bg, corner_radius=4, height=44)
                row_frame.grid(row=rnum, column=0, sticky="ew", padx=8, pady=(2,2))
                row_frame.grid_propagate(False)
                row_frame.grid_columnconfigure(0, minsize=100, weight=0)
                row_frame.grid_columnconfigure(1, weight=1)
                row_frame.grid_columnconfigure(2, minsize=180, weight=0)
                row_frame.grid_rowconfigure(0, weight=1)
                lbl_id = ctk.CTkLabel(row_frame, text=sid, text_color="white", fg_color="transparent", anchor="center")
                lbl_name = ctk.CTkLabel(row_frame, text=name, text_color="white", fg_color="transparent", font=ctk.CTkFont(size=12), anchor="center")
                lbl_status = ctk.CTkLabel(row_frame, text=status.capitalize() if status else "-", text_color=fg, fg_color="transparent", anchor="center")
                lbl_id.grid(row=0, column=0, sticky="ew", padx=6, pady=0)
                lbl_name.grid(row=0, column=1, sticky="ew", padx=6, pady=0)
                lbl_status.grid(row=0, column=2, sticky="ew", padx=6, pady=0)
                try:
                    lbl_name.bind("<Button-1>", lambda e, sid=sid: self._open_student_detail(sid))
                    lbl_name.configure(cursor="hand2")
                except Exception:
                    pass
            self._update_level1_chart(rows)
        else:
            # students view
            try:
                students = get_students_by_class(self._selected_class_id) or []
            except Exception:
                students = []
            # hide stats bar when viewing students
            try:
                if getattr(self, '_level1_stats_bar', None):
                    self._level1_stats_bar.grid_remove()
            except Exception:
                pass
            # header: Student ID, Name, Registered Date (inside scroll at row=0)
            header_container = ctk.CTkFrame(self._level1_scroll, fg_color='transparent')
            header_container.grid(row=0, column=0, sticky='ew', padx=8, pady=(4,4))
            header_container.grid_columnconfigure(0, minsize=100, weight=0)
            header_container.grid_columnconfigure(1, weight=1)
            header_container.grid_columnconfigure(2, minsize=180, weight=0)
            for i, h in enumerate(["Student ID", "Name", "Registered Date"]):
                ctk.CTkLabel(header_container, text=h, text_color="#888888", font=ctk.CTkFont(size=12, weight="bold"), anchor="center").grid(row=0, column=i, sticky="ew", padx=6, pady=0)
            def _sid_key(x):
                try:
                    return int(str(x.get('student_id', 0)).strip() or 0)
                except Exception:
                    return 0
            for idx, s in enumerate(sorted(students, key=_sid_key)):
                sid = str(s.get("student_id") or s.get("id") or "-")
                name = self._format_profile_name(s)
                reg = s.get("registered_date") or s.get("created_at") or s.get("created") or s.get("registered") or "-"
                bg = "#1E1E1E" if idx % 2 == 0 else "#252525"
                rnum = idx + 1
                row_frame = ctk.CTkFrame(self._level1_scroll, fg_color=bg, corner_radius=4, height=44)
                row_frame.grid(row=rnum, column=0, sticky="ew", padx=8, pady=(2,2))
                row_frame.grid_propagate(False)
                row_frame.grid_columnconfigure(0, minsize=100, weight=0)
                row_frame.grid_columnconfigure(1, weight=1)
                row_frame.grid_columnconfigure(2, minsize=180, weight=0)
                row_frame.grid_rowconfigure(0, weight=1)
                lbl_id = ctk.CTkLabel(row_frame, text=sid, text_color="white", fg_color="transparent", anchor="center")
                name_lbl = ctk.CTkLabel(row_frame, text=name, text_color="white", fg_color="transparent", font=ctk.CTkFont(size=12), anchor="center")
                lbl_reg = ctk.CTkLabel(row_frame, text=str(reg), text_color="#D0D0D0", fg_color="transparent", anchor="center")
                lbl_id.grid(row=0, column=0, sticky="ew", padx=6, pady=0)
                name_lbl.grid(row=0, column=1, sticky="ew", padx=6, pady=0)
                lbl_reg.grid(row=0, column=2, sticky="ew", padx=6, pady=0)
                try:
                    name_lbl.bind("<Button-1>", lambda e, sid=str(s.get("student_id", "")): self._open_student_detail(sid))
                    name_lbl.configure(cursor="hand2")
                except Exception:
                    pass
            # update chart with empty or computed values
            self._update_level1_chart([])

    # ---------- Helper methods referenced during init ----------
    def _apply_period(self, key: str, student_id: str | None = None) -> None:
        for k, btn in getattr(self, "_filter_buttons", {}).items():
            try:
                btn.configure(fg_color="#1E88E5" if k == key else "#2A2A2A")
            except Exception:
                pass
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
            sid = getattr(self, "_last_student_id", None)
            if not sid:
                self._notify("No student selected.", "error")
                return
            self._load_student_history(sid, dfrom, dto)
            win.destroy()

        ctk.CTkButton(win, text="Apply", command=apply_custom).pack(pady=8)

    def _export_excel(self) -> None:
        if pd is None:
            self._notify("Pandas not installed — cannot export Excel.", "error")
            return
        sid = getattr(self, "_selected_student_id", None)
        if not sid:
            self._notify("No student selected.", "error")
            return
        rows = get_attendance_by_student(sid) or []
        if not rows:
            self._notify("No attendance data to export.", "error")
            return
        fname = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel","*.xlsx")])
        if not fname:
            return
        try:
            df = pd.DataFrame(rows)
            df.to_excel(fname, index=False)
            self._notify(f"Exported Excel: {fname}", "success")
        except Exception as e:
            self._notify(f"Failed to export Excel: {e}", "error")

    def _export_pdf(self) -> None:
        if SimpleDocTemplate is None:
            self._notify("reportlab not available — cannot export PDF.", "error")
            return
        sid = getattr(self, "_selected_student_id", None)
        if not sid:
            self._notify("No student selected.", "error")
            return
        rows = get_attendance_by_student(sid) or []
        if not rows:
            self._notify("No attendance data to export.", "error")
            return
        fname = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF","*.pdf")])
        if not fname:
            return
        try:
            doc = SimpleDocTemplate(fname, pagesize=letter)
            styles = getSampleStyleSheet()
            elems = [Paragraph(f"Attendance Report — {sid}", styles["Heading2"]), Spacer(1, 12)]
            data = [["Date", "Time", "Status"]]
            for r in rows:
                data.append([str(r.get("date")), str(r.get("time")), str(r.get("status"))])
            table = Table(data, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ]))
            elems.append(table)
            doc.build(elems)
            self._notify(f"Exported PDF: {fname}", "success")
        except Exception as e:
            self._notify(f"Failed to export PDF: {e}", "error")

    def _update_level1_chart(self, rows: list) -> None:
        # Update the bottom stats bar (Present, Late, Absent, Attendance %)
        try:
            present = sum(1 for r in rows if str(r.get('status', '')).lower() == 'present')
            late = sum(1 for r in rows if str(r.get('status', '')).lower() == 'late')
            absent = sum(1 for r in rows if str(r.get('status', '')).lower() == 'absent')
        except Exception:
            present = late = absent = 0
        try:
            total = len(get_students_by_class(self._selected_class_id) or [])
        except Exception:
            total = present + late + absent

        try:
            pct = int((present / max(1, total)) * 100) if total > 0 else 0
        except Exception:
            pct = 0

        try:
            if getattr(self, '_stats_present_lbl', None):
                self._stats_present_lbl.configure(text=f"🟢 Present: {present}")
            if getattr(self, '_stats_late_lbl', None):
                self._stats_late_lbl.configure(text=f"🟡 Late: {late}")
            if getattr(self, '_stats_absent_lbl', None):
                self._stats_absent_lbl.configure(text=f"🔴 Absent: {absent}")
            if getattr(self, '_stats_pct_lbl', None):
                self._stats_pct_lbl.configure(text=f"📊 {pct}%")
                # color the pct label based on thresholds
                pct_color = '#57C46D' if pct > 75 else ('#F4C542' if pct >= 60 else '#FF6B6B')
                try:
                    self._stats_pct_lbl.configure(text_color=pct_color)
                except Exception:
                    pass
        except Exception:
            pass

    # Level 1 charting removed — charts and animations are no longer used in Level 1

    def _show_card_menu(self, class_id: int, widget) -> None:
        # small popup menu near the widget with Delete and Cancel
        # destroy any existing popup
        try:
            if getattr(self, "_active_popup", None):
                try:
                    self._active_popup.destroy()
                except Exception:
                    pass
                self._active_popup = None
        except Exception:
            pass

        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
        except Exception:
            x = self.winfo_rootx() + 100
            y = self.winfo_rooty() + 100

        menu = ctk.CTkToplevel(self)
        menu.overrideredirect(True)
        menu.lift()
        frame = ctk.CTkFrame(menu, fg_color="#1A1A1A", corner_radius=6)
        frame.pack(padx=6, pady=6)

        def do_delete():
            try:
                menu.destroy()
            except Exception:
                pass
            self._active_popup = None
            # reuse existing delete confirmation flow
            self._confirm_and_delete(class_id, self._class_map.get(class_id, {}).get("name", ""))

        del_btn = ctk.CTkButton(frame, text="Delete Class", fg_color="#C62828", hover_color="#B71C1C", command=do_delete)
        del_btn.pack(fill="x", pady=(4, 6), padx=4)
        cancel_btn = ctk.CTkButton(frame, text="Cancel", fg_color="transparent", command=lambda: menu.destroy())
        cancel_btn.pack(fill="x", pady=(0, 4), padx=4)

        # position and ensure it doesn't go off-screen to the right
        menu.update_idletasks()
        pw = menu.winfo_width()
        ph = menu.winfo_height()
        sw = menu.winfo_screenwidth()
        if x + pw > sw:
            x = max(10, sw - pw - 10)
        menu.geometry(f"+{x}+{y}")
        self._active_popup = menu
        # clear active ref when destroyed
        menu.bind('<Destroy>', lambda e: setattr(self, '_active_popup', None))

    # ---------------- Level 2: Student Detail ----------------
    def _build_level2(self) -> None:
        root = self.level2
        top = ctk.CTkFrame(root, fg_color='transparent')
        top.grid(row=0, column=0, sticky='ew', padx=24, pady=(12,6))
        top.grid_columnconfigure(1, weight=1)
        back = ctk.CTkButton(top, text='◀ Back', command=self._back_to_level1, fg_color='#2A2A2A')
        back.grid(row=0, column=0, sticky='w')
        self.level2_title = ctk.CTkLabel(top, text='', font=ctk.CTkFont(size=18, weight='bold'), text_color='white')
        self.level2_title.grid(row=0, column=1, sticky='w')

        content = ctk.CTkFrame(root, fg_color='transparent')
        content.grid(row=1, column=0, sticky='nsew', padx=24, pady=(8,12))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)

        left = ctk.CTkFrame(content, fg_color='transparent')
        left.grid(row=0, column=0, sticky='nsew', padx=(0,12))
        left.grid_columnconfigure(0, weight=1)

        # table card for student history
        table_card = ctk.CTkFrame(left, fg_color='#1E1E1E')
        table_card.grid(row=0, column=0, sticky='nsew', pady=(0,0))
        table_card.grid_columnconfigure(0, weight=1)
        self._student_scroll = ctk.CTkScrollableFrame(table_card, fg_color='transparent')
        self._student_scroll.grid(row=0, column=0, sticky='nsew', padx=4, pady=4)

        # summary row
        summary = ctk.CTkFrame(left, fg_color='transparent')
        summary.grid(row=1, column=0, sticky='ew', pady=(8,0))
        self._present_label = ctk.CTkLabel(summary, text='Present: 0', text_color=_STATUS_COLORS['present'], font=ctk.CTkFont(size=14, weight='bold'))
        self._late_label = ctk.CTkLabel(summary, text='Late: 0', text_color=_STATUS_COLORS['late'], font=ctk.CTkFont(size=14, weight='bold'))
        self._absent_label = ctk.CTkLabel(summary, text='Absent: 0', text_color=_STATUS_COLORS['absent'], font=ctk.CTkFont(size=14, weight='bold'))
        self._pct_label = ctk.CTkLabel(summary, text='Attendance: 0%', text_color='#FFFFFF', font=ctk.CTkFont(size=14, weight='bold'))
        self._present_label.grid(row=0, column=0, padx=(0,12))
        self._late_label.grid(row=0, column=1, padx=(0,12))
        self._absent_label.grid(row=0, column=2, padx=(0,12))
        self._pct_label.grid(row=0, column=3, padx=(0,12))

        # right: profile + export + chart
        right = ctk.CTkFrame(content, fg_color='transparent')
        right.grid(row=0, column=1, sticky='nsew')
        profile_card = ctk.CTkFrame(right, fg_color='#1A1A1A', corner_radius=6)
        profile_card.grid(row=0, column=0, sticky='ew', pady=(0,12), padx=8)
        profile_card.grid_columnconfigure(0, weight=1)
        self._profile_photo_frame = ctk.CTkFrame(profile_card, fg_color='transparent', width=120, height=120)
        self._profile_photo_frame.grid(row=0, column=1, rowspan=3, padx=(8,0))
        self._profile_photo_frame.grid_propagate(False)
        self._profile_name_lbl = ctk.CTkLabel(profile_card, text='', font=ctk.CTkFont(size=16, weight='bold'), text_color='white')
        self._profile_name_lbl.grid(row=0, column=0, sticky='w')
        self._profile_id_lbl = ctk.CTkLabel(profile_card, text='', text_color='#D0D0D0')
        self._profile_id_lbl.grid(row=1, column=0, sticky='w')
        self._profile_class_lbl = ctk.CTkLabel(profile_card, text='', text_color='#D0D0D0')
        self._profile_class_lbl.grid(row=2, column=0, sticky='w')

        exp_frame = ctk.CTkFrame(right, fg_color='transparent')
        exp_frame.grid(row=1, column=0, sticky='ew', pady=(6,0))
        ctk.CTkButton(exp_frame, text='Export PDF', fg_color='#1E88E5', command=self._export_pdf).grid(row=0, column=0, padx=8)
        ctk.CTkButton(exp_frame, text='Export Excel', fg_color='#2A7F62', command=self._export_excel).grid(row=0, column=1, padx=8)

        # student chart frame
        right.grid_rowconfigure(2, weight=1)
        self._student_chart_frame = ctk.CTkFrame(right, fg_color='#1E1E1E')
        self._student_chart_frame.grid(row=2, column=0, sticky='nsew', padx=8, pady=(8,0))

    def _back_to_level1(self) -> None:
        self.level2.grid_remove()
        self.level1.grid()

    def _load_student_history(self, student_id: str, start_date: date, end_date: date) -> None:
        try:
            rows = get_attendance_by_student(student_id) or []
        except Exception:
            rows = []
        filtered = []
        for r in rows:
            try:
                d = r.get('date')
                if isinstance(d, str):
                    d = datetime.fromisoformat(d).date()
                if d and start_date <= d <= end_date:
                    filtered.append(r)
            except Exception:
                continue
        # render
        for w in list(self._student_scroll.children.values()):
            try:
                w.destroy()
            except Exception:
                pass
        headers = ['Date', 'Time', 'Status']
        for col, h in enumerate(headers):
            ctk.CTkLabel(self._student_scroll, text=h, text_color='#888888', font=ctk.CTkFont(size=12, weight='bold')).grid(row=0, column=col, sticky='w', padx=8, pady=6)
        present = late = absent = 0
        dates = []
        status_map = {}
        for idx, r in enumerate(sorted(filtered, key=lambda x: x.get('date') or ''), start=1):
            d = r.get('date')
            t = str(r.get('time', ''))[:8]
            st = str(r.get('status', '')).lower()
            if st == 'present':
                present += 1
            elif st == 'late':
                late += 1
            else:
                absent += 1
            fg = _STATUS_COLORS.get(st, 'white')
            bg = '#1E1E1E' if idx % 2 == 1 else '#252525'
            ctk.CTkLabel(self._student_scroll, text=str(d), text_color='white', fg_color=bg, corner_radius=4).grid(row=idx, column=0, sticky='w', padx=8, pady=2, ipadx=6, ipady=6)
            ctk.CTkLabel(self._student_scroll, text=t, text_color='white', fg_color=bg, corner_radius=4).grid(row=idx, column=1, sticky='w', padx=8, pady=2, ipadx=6, ipady=6)
            ctk.CTkLabel(self._student_scroll, text=st.capitalize() if st else '-', text_color=fg, fg_color=bg, corner_radius=4).grid(row=idx, column=2, sticky='w', padx=8, pady=2, ipadx=6, ipady=6)
            try:
                dd = r.get('date')
                if isinstance(dd, str):
                    dd = datetime.fromisoformat(dd).date()
                dates.append(dd)
                status_map[dd] = st
            except Exception:
                pass
        total = present + late + absent
        pct = int((present / total) * 100) if total > 0 else 0
        pct_color = '#57C46D' if pct > 75 else ('#F4C542' if pct >= 60 else '#FF6B6B')
        try:
            self._present_label.configure(text=f'Present: {present}')
            self._late_label.configure(text=f'Late: {late}')
            self._absent_label.configure(text=f'Absent: {absent}')
            self._pct_label.configure(text=f'Attendance: {pct}%', text_color=pct_color)
        except Exception:
            pass
        # chart
        self._update_student_chart(dates, status_map, start_date, end_date)

    def _update_student_chart(self, dates: list, status_map: dict, start: date, end: date) -> None:
        if not _HAS_MATPLOTLIB:
            return
        n = (end - start).days + 1
        days = [start + timedelta(days=i) for i in range(n)]
        vals = []
        colors = []
        for d in days:
            st = status_map.get(d, 'absent')
            if st == 'present':
                vals.append(1)
                colors.append(_STATUS_COLORS['present'])
            elif st == 'late':
                vals.append(0.6)
                colors.append(_STATUS_COLORS['late'])
            else:
                vals.append(0)
                colors.append(_STATUS_COLORS['absent'])
        fig = Figure(figsize=(6, 2.5), dpi=100)
        fig.patch.set_facecolor('#1E1E1E')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#252525')
        ax.bar([d.strftime('%d %b') for d in days], vals, color=colors)
        ax.set_title('Daily Attendance')
        ax.title.set_color('white')
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_visible(False)
        canvas = FigureCanvasTkAgg(fig, master=self._student_chart_frame)
        for w in list(self._student_chart_frame.children.values()):
            try:
                w.destroy()
            except Exception:
                pass
        canvas.get_tk_widget().pack(fill='both', expand=True)
        canvas.draw()

    def _show_level(self, level: int) -> None:
        """Show the requested level (0,1,2) and hide others."""
        try:
            if level == 0:
                self.level1.grid_remove()
                self.level2.grid_remove()
                self.level0.grid()
            elif level == 1:
                self.level0.grid_remove()
                self.level2.grid_remove()
                self.level1.grid()
            else:
                self.level0.grid_remove()
                self.level1.grid_remove()
                self.level2.grid()
        except Exception:
            pass

    def _open_student_detail(self, student_id: str) -> None:
        """Open level 2 for a student and load their details."""
        self._selected_student_id = student_id
        # switch to level 2
        try:
            self._show_level(2)
        except Exception:
            # fallback to direct grid manipulation
            try:
                self.level1.grid_remove()
                self.level0.grid_remove()
                self.level2.grid()
            except Exception:
                pass
        # populate details
        self._load_student_detail(student_id)

    def _load_student_detail(self, student_id: str) -> None:
        """Fetch student profile and populate Level 2 widgets (name, photo, history)."""
        try:
            profile = get_student_profile(student_id) or {}
        except Exception:
            profile = {}

        # Name and meta
        try:
            name = self._format_profile_name(profile) or str(profile.get('name') or student_id)
        except Exception:
            name = str(profile.get('name') or student_id)
        try:
            self._profile_name_lbl.configure(text=name)
            self._profile_id_lbl.configure(text=f"Student ID: {student_id}")
            self._profile_class_lbl.configure(text=f"Class: {profile.get('class_id')}")
        except Exception:
            pass

        # Photo: try PIL if available, else show initials
        img_obj = None
        try:
            from PIL import Image, ImageTk
            img_source = None
            if profile.get('photo'):
                raw = profile.get('photo')
                if isinstance(raw, (bytes, bytearray)):
                    img_source = io.BytesIO(raw)
            elif profile.get('photo_path'):
                img_source = profile.get('photo_path')
            if img_source:
                try:
                    img = Image.open(img_source).convert('RGBA')
                    img = img.resize((120, 120))
                    img_obj = ImageTk.PhotoImage(img)
                except Exception:
                    img_obj = None
        except Exception:
            img_obj = None

        try:
            # clear existing photo area
            for w in list(self._profile_photo_frame.children.values()):
                try:
                    w.destroy()
                except Exception:
                    pass
            if img_obj:
                # keep reference
                self._profile_photo_image = img_obj
                lbl = ctk.CTkLabel(self._profile_photo_frame, image=img_obj, text='')
                lbl.grid(row=0, column=0, padx=8, pady=8)
                self._profile_photo_label = lbl
            else:
                initials = ''.join([p[0].upper() for p in name.split() if p])[:2] or '?'
                lbl = ctk.CTkLabel(self._profile_photo_frame, text=initials, font=ctk.CTkFont(size=40, weight='bold'))
                lbl.grid(row=0, column=0, padx=8, pady=8)
                self._profile_photo_label = lbl
        except Exception:
            pass

        # Load recent history (last 30 days)
        try:
            today = date.today()
            start = today - timedelta(days=29)
            self._load_student_history(student_id, start, today)
        except Exception:
            pass

    # ---------------- Utilities ----------------
    def _format_date(self, d: date) -> str:
        try:
            return d.strftime('%A, %d %B %Y')
        except Exception:
            return str(d)

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, 'show_notification'):
            self.master_frame.show_notification(message, kind)
        elif hasattr(self.master_frame, 'notifications') and hasattr(self.master_frame.notifications, 'show'):
            self.master_frame.notifications.show(message, kind=kind)

    def _display_name(self, row: dict) -> str:
        fn = row.get('first_name')
        if fn:
            parts = [str(fn).strip()]
            mn = row.get('middle_name')
            if mn:
                parts.append(str(mn).strip())
            ln = row.get('last_name')
            if ln:
                parts.append(str(ln).strip())
            return ' '.join([p for p in parts if p])
        return str(row.get('name', '-')).strip()

    def _format_profile_name(self, profile: dict) -> str:
        fn = profile.get('first_name')
        if fn:
            parts = [str(fn).strip()]
            for key in ('middle_name', 'last_name'):
                v = profile.get(key)
                if v:
                    parts.append(str(v).strip())
            return ' '.join(parts)
        return str(profile.get('name', '-'))
 