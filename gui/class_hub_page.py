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
    update_student,
)
from core.database import soft_delete_student, log_action
from core.face_engine import get_model_status
from gui import theme
from gui.widgets import ThemedRangePicker, SingleDatePicker, center_dialog

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
        top_card = ctk.CTkFrame(root, fg_color=theme.BG_SURFACE, corner_radius=8)
        top_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(13, 6))
        top_card.grid_columnconfigure(0, weight=1)
        top_card.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(top_card, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(12,0), pady=12)
        title = ctk.CTkLabel(left, text="Classes", font=ctk.CTkFont(size=28, weight='bold'), text_color=theme.TEXT_PRIMARY)
        title.grid(row=0, column=0, sticky='w')
        self.class_count_label = ctk.CTkLabel(left, text="0 classes", font=ctk.CTkFont(size=13), text_color=theme.TEXT_SECONDARY)
        self.class_count_label.grid(row=1, column=0, sticky='w', pady=(2,0))

        add_btn = ctk.CTkButton(top_card, text="Add Class", fg_color=theme.BTN_SUCCESS,
                                hover_color=theme.BTN_ADD_HVR, font=ctk.CTkFont(size=13, weight="bold"),
                                command=self._toggle_add_panel)
        add_btn.grid(row=0, column=1, sticky='e', padx=(0,12), pady=12)

        # overlay state — built lazily in _open_add_overlay()
        self._add_win: ctk.CTkToplevel | None = None
        self._add_entries: dict = {}
        self._add_status_var = ctk.StringVar(value="")

        # Bottom card: list of class cards (scrollable)
        bottom_card = ctk.CTkFrame(root, fg_color=theme.BG_SURFACE, corner_radius=8)
        bottom_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 13))
        bottom_card.grid_rowconfigure(0, weight=1)
        bottom_card.grid_columnconfigure(0, weight=1)

        self.cards_frame = ctk.CTkScrollableFrame(bottom_card, fg_color='transparent')
        self.cards_frame.grid(row=0, column=0, sticky='nsew')
        try:
            self.cards_frame.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

    # ── shared popup wiring ───────────────────────────────────────────────────
    def _wire_popup(self, win: ctk.CTkToplevel, on_close=None) -> None:
        """
        Attach two behaviors to any CTkToplevel:
          1. Hide/restore when the main window is minimized/restored.
          2. Destroy when the user clicks anywhere outside the popup.
        on_close: callable to invoke instead of win.destroy() (optional).
        """
        root = self.winfo_toplevel()
        _bids: list[tuple[str, str]] = []

        def _close():
            if on_close:
                on_close()
            else:
                try:
                    if win.winfo_exists():
                        win.destroy()
                except Exception:
                    pass

        def _on_unmap(e):
            if e.widget is root:
                try: win.withdraw()
                except Exception: pass

        def _on_map(e):
            if e.widget is root:
                try:
                    if win.winfo_exists(): win.deiconify(); win.lift()
                except Exception: pass

        _bids.append(("<Unmap>", root.bind("<Unmap>", _on_unmap, add="+")))
        _bids.append(("<Map>",   root.bind("<Map>",   _on_map,   add="+")))

        # Add the click-outside handler with a short delay so the click that
        # opened the popup is fully processed first and doesn't immediately
        # close it.
        def _add_outside():
            def _outside(event):
                try:
                    if not win.winfo_exists(): return
                    wx, wy = win.winfo_rootx(), win.winfo_rooty()
                    ww, wh = win.winfo_width(),  win.winfo_height()
                    if not (wx <= event.x_root <= wx + ww and
                            wy <= event.y_root <= wy + wh):
                        _close()
                except Exception: pass
            _bids.append(("<ButtonPress-1>",
                          root.bind("<ButtonPress-1>", _outside, add="+")))

        win.after(150, _add_outside)

        def _cleanup(_e):
            for ev, bid in _bids:
                try: root.unbind(ev, bid)
                except Exception: pass

        win.bind("<Destroy>", _cleanup, add="+")

    def _toggle_add_panel(self) -> None:
        win = self._add_win
        if win is not None:
            try:
                if win.winfo_exists():
                    try:
                        win.grab_release()
                    except Exception:
                        pass
                    win.destroy()
            except Exception:
                pass
            self._add_win = None
            return
        self._open_add_overlay()

    def _open_add_overlay(self) -> None:
        W, H = 520, 460
        root = self.winfo_toplevel()

        win = ctk.CTkToplevel(root, fg_color=theme.BG_ELEVATED)
        win.overrideredirect(True)
        win.transient(root)
        win.withdraw()
        self._add_win = win
        self._add_status_var.set("")
        win.bind("<Destroy>", lambda _e: setattr(self, "_add_win", None))
        self._wire_popup(win, on_close=self._toggle_add_panel)

        outer = ctk.CTkFrame(win, fg_color=theme.BG_ELEVATED, corner_radius=16)
        outer.pack(fill="both", expand=True)
        outer.grid_columnconfigure(0, weight=1)

        # title row
        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Add Class",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="✕", width=28, height=28, corner_radius=6,
                      fg_color="transparent", hover_color=theme.BG_HOVER,
                      text_color=theme.TEXT_MUTED,
                      command=self._toggle_add_panel).grid(row=0, column=1, sticky="e")

        # field helpers
        def _lbl(parent, text):
            ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=theme.TEXT_PRIMARY, anchor="w",
                         ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        def _ent(parent, default="", placeholder=""):
            e = ctk.CTkEntry(parent, height=36, fg_color=theme.INPUT_BG,
                             border_width=1, border_color=theme.INPUT_BORDER,
                             text_color=theme.TEXT_PRIMARY,
                             placeholder_text_color=theme.TEXT_MUTED,
                             placeholder_text=placeholder, corner_radius=6)
            e.grid(row=1, column=0, sticky="ew")
            if default:
                e.insert(0, default)
            return e

        def _pair(parent, row, la, lb, da="", db="", pa="", pb=""):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 10))
            r.grid_columnconfigure(0, weight=1)
            r.grid_columnconfigure(1, weight=1)
            fa = ctk.CTkFrame(r, fg_color="transparent")
            fa.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            fa.grid_columnconfigure(0, weight=1)
            _lbl(fa, la); ea = _ent(fa, da, pa)
            fb = ctk.CTkFrame(r, fg_color="transparent")
            fb.grid(row=0, column=1, sticky="ew")
            fb.grid_columnconfigure(0, weight=1)
            _lbl(fb, lb); eb = _ent(fb, db, pb)
            return ea, eb

        # Faculty (full width)
        r1 = ctk.CTkFrame(outer, fg_color="transparent")
        r1.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        r1.grid_columnconfigure(0, weight=1)
        _lbl(r1, "Faculty")
        e_name = _ent(r1, placeholder="e.g. BSc CSIT")

        e_sect, e_max   = _pair(outer, 2, "Semester", "Max Students", db="30", pa="e.g. 1st Semester")
        e_late, e_abs   = _pair(outer, 3, "Late Cutoff (HH:MM)", "Absent Cutoff (HH:MM)", da="06:30", db="07:00")
        e_start, e_end  = _pair(outer, 4, "Class Start (HH:MM)", "Class End (HH:MM)", da="06:00", db="10:00")

        self._add_entries = {
            "name": e_name, "section": e_sect, "max_students": e_max,
            "late_cutoff": e_late, "absent_cutoff": e_abs,
            "start_time": e_start, "end_time": e_end,
        }

        # status label
        ctk.CTkLabel(outer, textvariable=self._add_status_var,
                     font=ctk.CTkFont(size=12), anchor="w",
                     text_color=theme.DANGER,
                     ).grid(row=5, column=0, sticky="w", padx=20, pady=(0, 2))

        # action buttons
        act = ctk.CTkFrame(outer, fg_color="transparent")
        act.grid(row=6, column=0, sticky="ew", padx=20, pady=(4, 18))
        ctk.CTkButton(act, text="Clear", command=self._clear_add_form,
                      fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
                      text_color=theme.TEXT_SECONDARY, corner_radius=6, height=36,
                      ).pack(side="left")
        ctk.CTkButton(act, text="Add Class", command=self._handle_add_class,
                      fg_color=theme.BTN_SUCCESS, hover_color=theme.BTN_ADD_HVR,
                      text_color=theme.TEXT_PRIMARY, corner_radius=6, height=36, width=120,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      ).pack(side="right")

        # position and reveal after CTkToplevel finishes its own init
        def _show():
            px = self.winfo_rootx() + (self.winfo_width() - W) // 2
            py = self.winfo_rooty() + (self.winfo_height() - H) // 2
            win.geometry(f"{W}x{H}+{px}+{py}")
            win.deiconify()
            win.lift()
            win.focus_force()
            win.grab_set()

            def _close_if_outside(event):
                try:
                    if not win.winfo_exists():
                        return
                    wx, wy = win.winfo_rootx(), win.winfo_rooty()
                    ww, wh = win.winfo_width(), win.winfo_height()
                    if not (wx <= event.x_root <= wx + ww and
                            wy <= event.y_root <= wy + wh):
                        self._toggle_add_panel()
                except Exception:
                    pass

            win.bind("<ButtonPress-1>", _close_if_outside, add="+")

        win.after(50, _show)

    def _clear_add_form(self) -> None:
        _defaults = {
            "name": "",
            "section": "",
            "max_students": "30",
            "late_cutoff": "06:30",
            "absent_cutoff": "07:00",
            "start_time": "06:00",
            "end_time": "10:00",
        }
        for key, entry in self._add_entries.items():
            try:
                entry.delete(0, "end")
                val = _defaults.get(key, "")
                if val:
                    entry.insert(0, val)
            except Exception:
                pass
        self._add_status_var.set("")

    def _handle_add_class(self) -> None:
        try:
            name     = self._add_entries["name"].get().strip()
            section  = self._add_entries["section"].get().strip()
            max_s    = int(self._add_entries["max_students"].get() or 30)
            late     = self._add_entries["late_cutoff"].get().strip() or None
            absent   = self._add_entries["absent_cutoff"].get().strip() or None
            start    = self._add_entries["start_time"].get().strip() or None
            end      = self._add_entries["end_time"].get().strip() or None
            if not name or not section:
                self._add_status_var.set("Name and section are required.")
                return
            add_class(name, section, self.username or "system",
                      max_students=max_s, late_cutoff=late, absent_cutoff=absent,
                      class_start_time=start, class_end_time=end)
            self._notify("Class added.", "success")
            self._toggle_add_panel()
            self._load_classes()
        except Exception as e:
            self._add_status_var.set(f"Error: {e}")

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
            card = ctk.CTkFrame(self.cards_frame, fg_color=theme.BG_SURFACE_ALT, corner_radius=10)
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
            name_lbl = ctk.CTkLabel(card, text=c.get("name", ""), font=ctk.CTkFont(size=15, weight="bold"), text_color=theme.TEXT_PRIMARY)
            name_lbl.grid(row=0, column=0, sticky="w", padx=(16,0), pady=0)

            # section
            sect_lbl = ctk.CTkLabel(card, text=c.get("section", ""), text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12))
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
            ctr_lbl = ctk.CTkLabel(card, text=f"{present} / {total} Present", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12))
            ctr_lbl.grid(row=0, column=2, sticky="ew")

            # attendance percentage label (colored)
            pct = (present / max(1, total)) * 100 if total > 0 else 0
            pct_color = "#57C46D" if pct > 75 else ("#F4C542" if pct >= 50 else "#FF6B6B")
            pct_text = f"{int(pct)}%"
            pct_lbl = ctk.CTkLabel(card, text=pct_text, font=ctk.CTkFont(size=13, weight="bold"), text_color=pct_color)
            pct_lbl.grid(row=0, column=3, sticky="ew")

            # three-dots menu button instead of Delete
            dots_btn = ctk.CTkButton(card, text="⋮", width=32, height=32, fg_color="transparent", hover_color=theme.BG_SURFACE_ALT, font=ctk.CTkFont(size=18))
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
            lbl = ctk.CTkLabel(self.cards_frame, text="No classes added yet. Click Add Class to get started.", text_color=theme.TEXT_SECONDARY)
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
        top_card = ctk.CTkFrame(root, fg_color=theme.BG_SURFACE, corner_radius=8)
        top_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(13, 6))
        top_card.grid_columnconfigure(0, weight=0)
        top_card.grid_columnconfigure(1, weight=1)
        top_card.grid_columnconfigure(2, weight=0)

        back = ctk.CTkButton(top_card, text="◀ Back", command=self._back_to_level0, fg_color=theme.BG_SURFACE_ALT)
        back.grid(row=0, column=0, sticky="w", padx=(12,8), pady=12)

        self.level1_title = ctk.CTkLabel(top_card, text="", font=ctk.CTkFont(size=24, weight="bold"), text_color=theme.TEXT_PRIMARY)
        self.level1_title.grid(row=0, column=1, sticky="w", padx=(0,0), pady=12)

        nav_frame = ctk.CTkFrame(top_card, fg_color="transparent")
        nav_frame.grid(row=0, column=2, sticky="e", padx=(8,12), pady=12)
        self.prev_btn = ctk.CTkButton(nav_frame, text="◀", width=40, command=lambda: self._change_date(-1))
        self.prev_btn.grid(row=0, column=0)
        self.level1_date_label = ctk.CTkLabel(nav_frame, text=self._format_date(self._selected_date), text_color=theme.TEXT_PRIMARY)
        self.level1_date_label.grid(row=0, column=1, padx=8)
        self.next_btn = ctk.CTkButton(nav_frame, text="▶", width=40, command=lambda: self._change_date(1))
        self.next_btn.grid(row=0, column=2)

        # Bottom card: same colour as Level 0 — no inner nesting
        bottom_card = ctk.CTkFrame(root, fg_color=theme.BG_SURFACE, corner_radius=8)
        bottom_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 13))
        bottom_card.grid_rowconfigure(0, weight=0)
        bottom_card.grid_rowconfigure(1, weight=1)
        bottom_card.grid_columnconfigure(0, weight=1)

        # Toggle buttons: Attendance / Students — placed directly in bottom_card
        self._level1_view_mode = "attendance"
        toggle_frame = ctk.CTkFrame(bottom_card, fg_color="transparent")
        toggle_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        toggle_frame.grid_columnconfigure(0, weight=1)
        toggle_frame.grid_columnconfigure(1, weight=1)
        self._attendance_btn = ctk.CTkButton(toggle_frame, text="Attendance", fg_color=theme.ACCENT, hover_color=theme.ACCENT, command=lambda: self._set_level1_view("attendance"))
        self._attendance_btn.grid(row=0, column=0, sticky="w", padx=(0, 4))
        self._students_btn = ctk.CTkButton(toggle_frame, text="Students", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER, command=lambda: self._set_level1_view("students"))
        self._students_btn.grid(row=0, column=1, sticky="e", padx=(4, 0))

        self._level1_scroll = ctk.CTkScrollableFrame(bottom_card, fg_color="transparent")
        self._level1_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 0))
        try:
            self._level1_scroll.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

        # Stats bar — sits directly in bottom_card with a subtle alt background
        try:
            self._level1_stats_bar = ctk.CTkFrame(bottom_card, fg_color=theme.BG_SURFACE_ALT, height=50)
            self._level1_stats_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))
            self._level1_stats_bar.grid_propagate(False)
            try:
                self._level1_stats_bar.grid_rowconfigure(0, weight=1)
            except Exception:
                pass
            # labels: Present, Late, Absent, Percentage
            self._stats_present_lbl = ctk.CTkLabel(self._level1_stats_bar, text="🟢 Present: 0", text_color=_STATUS_COLORS['present'])
            self._stats_late_lbl = ctk.CTkLabel(self._level1_stats_bar, text="🟡 Late: 0", text_color=_STATUS_COLORS['late'])
            self._stats_absent_lbl = ctk.CTkLabel(self._level1_stats_bar, text="🔴 Absent: 0", text_color=_STATUS_COLORS['absent'])
            self._stats_pct_lbl = ctk.CTkLabel(self._level1_stats_bar, text="📊 0%", text_color=theme.TEXT_PRIMARY)
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
            att = mode == "attendance"
            self._attendance_btn.configure(fg_color=theme.ACCENT if att else theme.BG_SURFACE_ALT, hover_color=theme.ACCENT if att else theme.BG_HOVER)
            self._students_btn.configure(fg_color=theme.ACCENT if not att else theme.BG_SURFACE_ALT, hover_color=theme.ACCENT if not att else theme.BG_HOVER)
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
                ctk.CTkLabel(header_container, text=h, text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12, weight="bold"), anchor="center").grid(row=0, column=i, sticky="ew", padx=6, pady=0)
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
                rnum = idx + 1
                # row container
                row_frame = ctk.CTkFrame(self._level1_scroll, fg_color=theme.BG_ROW_EVEN, corner_radius=6, height=44)
                row_frame.grid(row=rnum, column=0, sticky="ew", padx=8, pady=(0, 5))
                row_frame.grid_propagate(False)
                row_frame.grid_columnconfigure(0, minsize=100, weight=0)
                row_frame.grid_columnconfigure(1, weight=1)
                row_frame.grid_columnconfigure(2, minsize=180, weight=0)
                row_frame.grid_rowconfigure(0, weight=1)
                lbl_id = ctk.CTkLabel(row_frame, text=sid, text_color=theme.TEXT_PRIMARY, fg_color="transparent", anchor="center")
                lbl_name = ctk.CTkLabel(row_frame, text=name, text_color=theme.TEXT_PRIMARY, fg_color="transparent", font=ctk.CTkFont(size=12), anchor="center")
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
            header_container.grid_columnconfigure(2, minsize=160, weight=0)
            header_container.grid_columnconfigure(3, minsize=80, weight=0)
            for i, h in enumerate(["Student ID", "Name", "Registered Date", "Actions"]):
                ctk.CTkLabel(header_container, text=h, text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12, weight="bold"), anchor="center").grid(row=0, column=i, sticky="ew", padx=6, pady=0)
            def _sid_key(x):
                try:
                    return int(str(x.get('student_id', 0)).strip() or 0)
                except Exception:
                    return 0
            for idx, s in enumerate(sorted(students, key=_sid_key)):
                sid = str(s.get("student_id") or s.get("id") or "-")
                name = self._format_profile_name(s)
                reg = s.get("registered_date") or s.get("created_at") or s.get("created") or s.get("registered") or "-"
                rnum = idx + 1
                row_frame = ctk.CTkFrame(self._level1_scroll, fg_color=theme.BG_ROW_EVEN, corner_radius=6, height=44)
                row_frame.grid(row=rnum, column=0, sticky="ew", padx=8, pady=(0, 5))
                row_frame.grid_propagate(False)
                row_frame.grid_columnconfigure(0, minsize=100, weight=0)
                row_frame.grid_columnconfigure(1, weight=1)
                row_frame.grid_columnconfigure(2, minsize=160, weight=0)
                row_frame.grid_columnconfigure(3, minsize=80, weight=0)
                row_frame.grid_rowconfigure(0, weight=1)
                lbl_id = ctk.CTkLabel(row_frame, text=sid, text_color=theme.TEXT_PRIMARY, fg_color="transparent", anchor="center")
                name_lbl = ctk.CTkLabel(row_frame, text=name, text_color=theme.TEXT_PRIMARY, fg_color="transparent", font=ctk.CTkFont(size=12), anchor="center")
                lbl_reg = ctk.CTkLabel(row_frame, text=str(reg), text_color=theme.TEXT_SECONDARY, fg_color="transparent", anchor="center")
                lbl_id.grid(row=0, column=0, sticky="ew", padx=6, pady=0)
                name_lbl.grid(row=0, column=1, sticky="ew", padx=6, pady=0)
                lbl_reg.grid(row=0, column=2, sticky="ew", padx=6, pady=0)
                try:
                    name_lbl.bind("<Button-1>", lambda e, sid=str(s.get("student_id", "")): self._open_student_detail(sid))
                    name_lbl.configure(cursor="hand2")
                except Exception:
                    pass
                try:
                    del_btn = ctk.CTkButton(
                        row_frame,
                        text="Delete",
                        width=70,
                        height=28,
                        fg_color=theme.BTN_DANGER,
                        hover_color=theme.BTN_DANGER_HVR,
                        font=ctk.CTkFont(size=12),
                        command=lambda sid=sid, n=name: self._confirm_soft_delete(sid, n),
                    )
                    del_btn.grid(row=0, column=3, sticky="e", padx=(4, 8))
                except Exception:
                    pass
            # update chart with empty or computed values
            self._update_level1_chart([])

    # ---------- Helper methods referenced during init ----------
    def _apply_period(self, key: str, student_id: str | None = None) -> None:
        # Close the custom calendar popup if it's open
        try:
            if getattr(self, '_cal_panel', None) and self._cal_panel._popup is not None:
                self._cal_panel.close_calendar()
        except Exception:
            pass
        for k, btn in getattr(self, "_filter_buttons", {}).items():
            try:
                active = (k == key)
                btn.configure(
                    fg_color=theme.ACCENT if active else theme.BG_SURFACE_ALT,
                    hover_color=theme.ACCENT if active else theme.BG_HOVER,
                )
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
        self._cal_panel.open_popup_anchored_to(self._filter_buttons["custom"])

    def _on_custom_range_selected(self, from_date: date, to_date: date) -> None:
        sid = getattr(self, "_last_student_id", None)
        if not sid:
            self._notify("No student selected.", "error")
            return
        # Highlight the Custom button as active
        try:
            for k, btn in self._filter_buttons.items():
                active = (k == "custom")
                btn.configure(
                    fg_color=theme.ACCENT if active else theme.BG_SURFACE_ALT,
                    hover_color=theme.ACCENT if active else theme.BG_HOVER,
                )
        except Exception:
            pass
        self._load_student_history(sid, from_date, to_date)

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
        menu.transient(self.winfo_toplevel())
        menu.lift()
        frame = ctk.CTkFrame(menu, fg_color=theme.BG_SURFACE, corner_radius=6)
        frame.pack(padx=6, pady=6)

        def do_delete():
            try:
                menu.destroy()
            except Exception:
                pass
            self._active_popup = None
            # reuse existing delete confirmation flow
            self._confirm_and_delete(class_id, self._class_map.get(class_id, {}).get("name", ""))

        del_btn = ctk.CTkButton(frame, text="Delete Class", fg_color=theme.BTN_DANGER, hover_color=theme.BTN_DANGER_HVR, command=do_delete)
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
        menu.bind('<Destroy>', lambda e: setattr(self, '_active_popup', None))
        self._wire_popup(menu)

    def _confirm_soft_delete(self, student_id: str, student_name: str) -> None:
        """Show a confirmation dialog then soft-delete the student."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Delete Student")
        try:
            dlg.transient(self.winfo_toplevel())
        except Exception:
            pass
        try:
            dlg.grab_set()
        except Exception:
            pass
        center_dialog(dlg, 420, 180)

        # click outside = cancel (grab redirects all clicks to dlg)
        def _close_if_outside(event):
            try:
                dx, dy = dlg.winfo_rootx(), dlg.winfo_rooty()
                dw, dh = dlg.winfo_width(),  dlg.winfo_height()
                if not (dx <= event.x_root <= dx + dw and
                        dy <= event.y_root <= dy + dh):
                    try: dlg.grab_release()
                    except Exception: pass
                    dlg.destroy()
            except Exception:
                pass
        dlg.bind("<ButtonPress-1>", _close_if_outside, add="+")
        # hide when main window minimizes (transient already set above)
        self._wire_popup(dlg)

        card = ctk.CTkFrame(dlg, fg_color=theme.BG_SURFACE, corner_radius=0)
        card.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            card,
            text=f"Delete {student_name}?",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            card,
            text="This will move the student to the Archive. A superadmin can restore or permanently delete them from there.",
            justify="left",
            wraplength=370,
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=18, pady=(0, 14))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 14))

        def _do_delete():
            try:
                soft_delete_student(student_id, self.username or "system")
                log_action(
                    self.username or "system",
                    "SOFT_DELETE_STUDENT",
                    f"student_id={student_id}",
                )
                try:
                    dlg.grab_release()
                except Exception:
                    pass
                dlg.destroy()
                self._notify(f"{student_name} moved to archive.", "success")
                # If we're in level 2, go back to level 1 and refresh
                try:
                    if self.level2.winfo_ismapped():
                        self._back_to_level1()
                except Exception:
                    pass
                self._render_level1()
            except Exception as err:
                self._notify(f"Failed to delete student: {err}", "error")

        ctk.CTkButton(actions, text="Cancel", command=dlg.destroy, fg_color=theme.BG_SURFACE_ALT).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Move to Archive",
            command=_do_delete,
            fg_color=theme.BTN_DANGER,
            hover_color=theme.BTN_DANGER_HVR,
        ).pack(side="right")

    # ---------------- Level 2: Student Detail ----------------
    def _build_level2(self) -> None:
        root = self.level2
        # ensure root expands content
        try:
            root.grid_columnconfigure(0, weight=1)
            root.grid_rowconfigure(1, weight=1)
        except Exception:
            pass

        # Top bar (back button + title)
        top = ctk.CTkFrame(root, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 6))
        top.grid_columnconfigure(1, weight=1)
        back = ctk.CTkButton(top, text="◀ Back", command=self._back_to_level1, fg_color=theme.BG_SURFACE_ALT)
        back.grid(row=0, column=0, sticky="w")
        self.level2_title = ctk.CTkLabel(top, text="", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.TEXT_PRIMARY)
        self.level2_title.grid(row=0, column=1, sticky="w", padx=(12, 0))

        # Content area with two columns
        content = ctk.CTkFrame(root, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(8, 12))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        # LEFT COLUMN
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)

        # Filter bar
        filter_frame = ctk.CTkFrame(left, fg_color=theme.BG_SURFACE, corner_radius=8)
        filter_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        for i in range(4):
            try:
                filter_frame.grid_columnconfigure(i, weight=1)
            except Exception:
                pass
        self._filter_buttons = {}
        periods = [("7d", "7 Days"), ("15d", "15 Days"), ("30d", "1 Month"), ("custom", "Custom")]
        # ensure default period
        if not hasattr(self, "_filter_period"):
            self._filter_period = "30d"
        for i, (key, label) in enumerate(periods):
            cmd = (self._show_custom_filter if key == "custom" else (lambda k=key: self._apply_period(k)))
            is_active = (key == self._filter_period)
            btn = ctk.CTkButton(
                filter_frame, text=label, height=36, corner_radius=6, command=cmd,
                fg_color=theme.ACCENT if is_active else theme.BG_SURFACE_ALT,
                hover_color=theme.ACCENT if is_active else theme.BG_HOVER,
            )
            btn.grid(row=0, column=i, sticky="ew", padx=6, pady=6)
            self._filter_buttons[key] = btn

        # Range picker — not placed in layout; popup opens anchored to Custom button
        self._cal_panel = ThemedRangePicker(
            left,
            on_change=self._on_custom_range_selected,
        )

        # Table card with header + scroll area
        table_card = ctk.CTkFrame(left, fg_color=theme.BG_SURFACE, corner_radius=8)
        table_card.grid(row=1, column=0, sticky="nsew")
        self._table_card = table_card
        left.grid_rowconfigure(1, weight=1)
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(0, weight=0)
        table_card.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(table_card, fg_color=theme.BG_SURFACE_ALT, corner_radius=6)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        header.grid_columnconfigure(0, weight=2)
        header.grid_columnconfigure(1, weight=1)
        header.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(header, text="Date", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_SECONDARY, anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=10)
        ctk.CTkLabel(header, text="Time", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_SECONDARY, anchor="w").grid(row=0, column=1, sticky="w", padx=16, pady=10)
        ctk.CTkLabel(header, text="Status", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_SECONDARY, anchor="w").grid(row=0, column=2, sticky="w", padx=16, pady=10)

        self._student_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self._student_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._student_scroll.grid_columnconfigure(0, weight=2)
        self._student_scroll.grid_columnconfigure(1, weight=1)
        self._student_scroll.grid_columnconfigure(2, weight=1)

        # Summary row
        summary = ctk.CTkFrame(left, fg_color=theme.BG_SURFACE, corner_radius=8)
        summary.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        for i in range(4):
            try:
                summary.grid_columnconfigure(i, weight=1)
            except Exception:
                pass

        # Present
        p_frame = ctk.CTkFrame(summary, fg_color="transparent")
        p_frame.grid(row=0, column=0, sticky="nsew")
        self._present_count_lbl = ctk.CTkLabel(p_frame, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color=_STATUS_COLORS["present"])
        self._present_count_lbl.pack(anchor="center", pady=(6, 0))
        self._present_label = ctk.CTkLabel(p_frame, text="Present", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY)
        self._present_label.pack(anchor="center", pady=(2, 8))

        # Late
        l_frame = ctk.CTkFrame(summary, fg_color="transparent")
        l_frame.grid(row=0, column=1, sticky="nsew")
        self._late_count_lbl = ctk.CTkLabel(l_frame, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color=_STATUS_COLORS["late"])
        self._late_count_lbl.pack(anchor="center", pady=(6, 0))
        self._late_label = ctk.CTkLabel(l_frame, text="Late", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY)
        self._late_label.pack(anchor="center", pady=(2, 8))

        # Absent
        a_frame = ctk.CTkFrame(summary, fg_color="transparent")
        a_frame.grid(row=0, column=2, sticky="nsew")
        self._absent_count_lbl = ctk.CTkLabel(a_frame, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color=_STATUS_COLORS["absent"])
        self._absent_count_lbl.pack(anchor="center", pady=(6, 0))
        self._absent_label = ctk.CTkLabel(a_frame, text="Absent", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY)
        self._absent_label.pack(anchor="center", pady=(2, 8))

        # Attendance %
        pct_frame = ctk.CTkFrame(summary, fg_color="transparent")
        pct_frame.grid(row=0, column=3, sticky="nsew")
        # create two names for compatibility
        self._pct_count_lbl = ctk.CTkLabel(pct_frame, text="0%", font=ctk.CTkFont(size=22, weight="bold"), text_color=theme.TEXT_PRIMARY)
        self._pct_count_lbl.pack(anchor="center", pady=(6, 0))
        self._pct_lbl = self._pct_count_lbl
        self._pct_label = ctk.CTkLabel(pct_frame, text="Attendance", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY)
        self._pct_label.pack(anchor="center", pady=(2, 8))

        # ── RIGHT COLUMN ──────────────────────────────────────────────────────────
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        # Resume-style profile card
        profile_card = ctk.CTkFrame(right, fg_color=theme.BG_SURFACE, corner_radius=12)
        profile_card.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 10))
        profile_card.grid_columnconfigure(0, weight=1)
        self._profile_card = profile_card

        # Photo — centered circle
        self._profile_photo_frame = ctk.CTkFrame(
            profile_card,
            fg_color=theme.BG_SURFACE_ALT,
            corner_radius=60,
            width=120, height=120,
        )
        self._profile_photo_frame.grid(row=0, column=0, pady=(20, 10))
        self._profile_photo_frame.grid_propagate(False)
        self._profile_photo_frame.grid_rowconfigure(0, weight=1)
        self._profile_photo_frame.grid_columnconfigure(0, weight=1)

        # Full name (centered)
        self._profile_name_lbl = ctk.CTkLabel(
            profile_card, text="",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self._profile_name_lbl.grid(row=1, column=0, pady=(0, 2))

        # Student ID (centered, muted)
        self._profile_id_lbl = ctk.CTkLabel(
            profile_card, text="",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        self._profile_id_lbl.grid(row=2, column=0, pady=(0, 14))

        # Divider
        ctk.CTkFrame(profile_card, fg_color=theme.BORDER, height=1).grid(
            row=3, column=0, sticky="ew", padx=16, pady=(0, 10),
        )

        # Detail rows
        det = ctk.CTkFrame(profile_card, fg_color="transparent")
        det.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        det.grid_columnconfigure(0, weight=0, minsize=105)
        det.grid_columnconfigure(1, weight=1)

        _detail_fields = [
            ("First Name",    "_det_first"),
            ("Middle Name",   "_det_middle"),
            ("Last Name",     "_det_last"),
            ("Class",         "_det_class"),
            ("Date of Birth", "_det_dob"),
            ("Age",           "_det_age"),
            ("Address",       "_det_address"),
            ("Registered By", "_det_reg_by"),
            ("Registered On", "_det_reg_date"),
        ]
        for _r, (_lbl, _attr) in enumerate(_detail_fields):
            ctk.CTkLabel(
                det, text=_lbl,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            ).grid(row=_r, column=0, sticky="w", pady=4)
            _val = ctk.CTkLabel(
                det, text="—",
                font=ctk.CTkFont(size=12),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
                wraplength=0,
            )
            _val.grid(row=_r, column=1, sticky="ew", padx=(8, 0), pady=4)
            setattr(self, _attr, _val)

        # ── Action buttons (replaces the old ⋮ overflow menu) ──────────────────
        actions = ctk.CTkFrame(profile_card, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 18))
        actions.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            actions, text="✏  Edit Student",
            height=36, corner_radius=8,
            fg_color=theme.BTN_SECONDARY, hover_color=theme.BTN_SECONDARY_HVR,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=13),
            command=self._edit_current_student,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self._export_btn = ctk.CTkButton(
            actions, text="⬇  Export",
            height=36, corner_radius=8,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13),
            command=lambda: self._open_export_menu(self._export_btn),
        )
        self._export_btn.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkButton(
            actions, text="Delete Student",
            height=36, corner_radius=8,
            fg_color=theme.BTN_DANGER, hover_color=theme.BTN_DANGER_HVR,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13),
            command=self._delete_current_student,
        ).grid(row=2, column=0, sticky="ew")

        # Chart frame (row 1 now — exp_frame removed; actions moved into profile card)
        right.grid_rowconfigure(1, weight=1)
        self._student_chart_frame = ctk.CTkFrame(right, fg_color=theme.BG_SURFACE)
        self._student_chart_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(8, 0))

    # ── Export dropdown for student detail ───────────────────────────────────

    def _open_export_menu(self, anchor_widget) -> None:
        # Clear any stale reference; toggle-close only if the popup is genuinely alive.
        existing = getattr(self, "_active_popup", None)
        if existing is not None:
            alive = False
            try:
                alive = existing.winfo_exists()
            except Exception:
                pass
            try:
                existing.destroy()
            except Exception:
                pass
            self._active_popup = None
            if alive:
                return  # genuine toggle: was open → now closed

        _BTN_W = 180
        # Known content: 2 items
        mw = _BTN_W + 16
        mh = 2 * 36 + 8

        # CTkToplevel is the correct CTk primitive for floating popups;
        # CTkFrame + lift() does not work reliably because CTk renders through
        # internal Canvas widgets, breaking normal tkinter z-ordering.
        menu = ctk.CTkToplevel(self)
        menu.overrideredirect(True)
        menu.withdraw()           # hide until positioned

        outer = ctk.CTkFrame(menu, fg_color=theme.BG_SURFACE, corner_radius=8,
                              border_width=1, border_color=theme.BORDER)
        outer.pack(fill="both", expand=True)

        def _close():
            try:
                menu.destroy()
            except Exception:
                pass
            self._active_popup = None

        def _item(text, cmd):
            b = ctk.CTkButton(
                outer, text=text, anchor="w",
                width=_BTN_W, height=34, corner_radius=0,
                fg_color="transparent",
                hover_color=theme.BG_HOVER,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=13),
                command=cmd,
            )
            b.pack(fill="x", padx=4, pady=(2, 0))
            return b

        def _close_then(fn):
            _close()
            fn()

        _item("⬇  Export as PDF",   lambda: _close_then(self._export_pdf))
        _item("⬇  Export as Excel", lambda: _close_then(self._export_excel))

        # Anchor the dropdown to the bottom-left of the Export button.
        self.update_idletasks()
        sw = menu.winfo_screenwidth()
        sh = menu.winfo_screenheight()

        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4

        if y + mh > sh - 10:
            y = anchor_widget.winfo_rooty() - mh - 4

        x = max(4, min(x, sw - mw - 4))

        menu.geometry(f"{mw}x{mh}+{x}+{y}")
        menu.deiconify()
        menu.lift()
        self._active_popup = menu
        menu.bind("<Destroy>", lambda _e: setattr(self, "_active_popup", None))
        self._wire_popup(menu)

    # ── Edit student dialog ───────────────────────────────────────────────────

    def _edit_current_student(self) -> None:
        sid = getattr(self, "_selected_student_id", None)
        if not sid:
            return
        try:
            profile = get_student_profile(sid) or {}
        except Exception:
            self._notify("Could not load student profile.", "error")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Edit Student")
        try:
            dlg.transient(self.winfo_toplevel())
        except Exception:
            pass
        try:
            dlg.grab_set()
        except Exception:
            pass
        center_dialog(dlg, 480, 500)

        card = ctk.CTkFrame(dlg, fg_color=theme.BG_SURFACE, corner_radius=0)
        card.pack(fill="both", expand=True, padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card, text="Edit Student",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            card, text=f"ID: {sid}",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 12))
        ctk.CTkFrame(card, fg_color=theme.BORDER, height=1).grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 14))

        _LBL_W = 110
        _fields: list[tuple[str, int, str]] = [
            ("First Name",   3, "first_name"),
            ("Middle Name",  4, "middle_name"),
            ("Last Name",    5, "last_name"),
        ]
        entries: dict[str, ctk.CTkEntry] = {}
        for label, row, key in _fields:
            ctk.CTkLabel(
                card, text=label, anchor="w",
                width=_LBL_W,
                text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(size=12),
            ).grid(row=row, column=0, sticky="w", padx=(18, 8), pady=6)
            ent = ctk.CTkEntry(
                card,
                fg_color=theme.BG_SURFACE_ALT,
                border_color=theme.BG_SURFACE_ALT,
                text_color=theme.TEXT_PRIMARY,
                corner_radius=6,
            )
            ent.grid(row=row, column=1, sticky="ew", padx=(0, 18), pady=6)
            val = profile.get(key) or ""
            if val and val != "—":
                ent.insert(0, str(val))
            entries[key] = ent

        # Date of Birth — inline date picker
        ctk.CTkLabel(
            card, text="Date of Birth", anchor="w",
            width=_LBL_W,
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=12),
        ).grid(row=6, column=0, sticky="w", padx=(18, 8), pady=6)
        dob_raw = profile.get("date_of_birth")
        dob_initial = None
        if dob_raw:
            try:
                if hasattr(dob_raw, "year"):
                    dob_initial = dob_raw
                else:
                    from datetime import datetime as _dt2
                    dob_initial = _dt2.strptime(str(dob_raw)[:10], "%Y-%m-%d").date()
            except Exception:
                dob_initial = None
        dob_picker = SingleDatePicker(card, initial_date=dob_initial, placeholder="Date of birth")
        dob_picker.grid(row=6, column=1, sticky="ew", padx=(0, 18), pady=6)

        # Address — multiline
        ctk.CTkLabel(
            card, text="Address", anchor="w",
            width=_LBL_W,
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=12),
        ).grid(row=7, column=0, sticky="nw", padx=(18, 8), pady=(6, 0))
        addr_box = ctk.CTkTextbox(
            card, height=60,
            fg_color=theme.BG_SURFACE_ALT,
            border_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=6,
        )
        addr_box.grid(row=7, column=1, sticky="ew", padx=(0, 18), pady=6)
        addr_val = profile.get("address") or ""
        if addr_val and addr_val != "—":
            addr_box.insert("1.0", str(addr_val))

        # Status label
        status_lbl = ctk.CTkLabel(card, text="", text_color=theme.DANGER, font=ctk.CTkFont(size=12))
        status_lbl.grid(row=8, column=0, columnspan=2, padx=18, pady=(4, 0))

        def _save():
            fn = entries["first_name"].get().strip()
            mn = entries["middle_name"].get().strip() or None
            ln = entries["last_name"].get().strip()
            if not fn or not ln:
                status_lbl.configure(text="First name and last name are required.")
                return
            dob_date = dob_picker.get_date()
            dob_str = dob_date.strftime("%Y-%m-%d") if dob_date else None
            addr_str = addr_box.get("1.0", "end").strip() or None
            try:
                update_student(sid, fn, mn, ln, date_of_birth=dob_str, address=addr_str)
                log_action(
                    self.username or "system",
                    "EDIT_STUDENT",
                    f"student_id={sid}",
                )
            except Exception:
                status_lbl.configure(text="Failed to save changes. Please try again.")
                return
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()
            self._notify("Student details updated.", "success")
            self._load_student_detail(sid)
            try:
                profile2 = get_student_profile(sid) or {}
                name2 = self._format_profile_name(profile2) or sid
                self.level2_title.configure(text=name2)
            except Exception:
                pass

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=9, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))
        ctk.CTkButton(
            actions, text="Cancel", command=dlg.destroy,
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY, corner_radius=6, height=34,
        ).pack(side="left")
        ctk.CTkButton(
            actions, text="Save Changes", command=_save,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            corner_radius=6, height=34,
        ).pack(side="right")

    def _back_to_level1(self) -> None:
        self.level2.grid_remove()
        self.level1.grid()

    def _delete_current_student(self) -> None:
        sid = getattr(self, "_selected_student_id", None)
        if not sid:
            return
        profile = {}
        try:
            profile = get_student_profile(sid) or {}
        except Exception:
            profile = {}
        name = self._format_profile_name(profile) or str(sid)
        self._confirm_soft_delete(sid, name)

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
        # render (rows)
        for w in list(self._student_scroll.children.values()):
            try:
                w.destroy()
            except Exception:
                pass

        present = late = absent = 0
        dates = []
        status_map = {}

        # ensure column weights on scroll
        try:
            self._student_scroll.grid_columnconfigure(0, weight=2)
            self._student_scroll.grid_columnconfigure(1, weight=1)
            self._student_scroll.grid_columnconfigure(2, weight=1)
        except Exception:
            pass

        for idx, r in enumerate(sorted(filtered, key=lambda x: x.get("date") or "")):
            d = r.get("date")
            # normalize date object
            try:
                if isinstance(d, str):
                    d_obj = datetime.fromisoformat(d).date()
                else:
                    d_obj = d
            except Exception:
                d_obj = d

            date_text = d_obj.strftime("%d %b %Y") if hasattr(d_obj, "strftime") else str(d_obj)
            t_raw = str(r.get("time", ""))
            time_text = t_raw[:5]

            st = str(r.get("status", "")).lower()
            if st == "present":
                present += 1
            elif st == "late":
                late += 1
            else:
                absent += 1

            # Date cell
            ctk.CTkLabel(
                self._student_scroll,
                text=date_text,
                font=ctk.CTkFont(size=12),
                text_color=theme.TEXT_PRIMARY,
                fg_color=theme.BG_ROW_EVEN,
                corner_radius=6,
            ).grid(row=idx, column=0, sticky="ew", padx=8, pady=(0, 5))

            # Time cell
            ctk.CTkLabel(
                self._student_scroll,
                text=time_text,
                font=ctk.CTkFont(size=12),
                text_color=theme.TEXT_MUTED,
                fg_color=theme.BG_ROW_EVEN,
                corner_radius=6,
            ).grid(row=idx, column=1, sticky="ew", padx=8, pady=(0, 5))

            # Status badge
            badge_text = st.capitalize() if st else "-"
            if st == "present":
                badge_bg = "#1A3D2B"
                badge_fg = "#57C46D"
            elif st == "late":
                badge_bg = "#3D3010"
                badge_fg = "#F4C542"
            else:
                badge_bg = "#3D1A1A"
                badge_fg = "#FF6B6B"

            lbl = ctk.CTkLabel(
                self._student_scroll,
                text=badge_text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=badge_fg,
                fg_color=badge_bg,
                corner_radius=4,
            )
            lbl.grid(row=idx, column=2, sticky="ew", padx=10, pady=(0, 5), ipadx=6, ipady=3)

            try:
                if hasattr(d_obj, "date"):
                    dates.append(d_obj)
                    status_map[d_obj] = st
                else:
                    dates.append(d_obj)
                    status_map[d_obj] = st
            except Exception:
                pass

        total = present + late + absent
        pct = int((present / total) * 100) if total > 0 else 0
        pct_color = "#57C46D" if pct > 75 else ("#F4C542" if pct >= 60 else "#FF6B6B")

        # update summary (big numbers)
        try:
            self._present_count_lbl.configure(text=str(present))
            self._late_count_lbl.configure(text=str(late))
            self._absent_count_lbl.configure(text=str(absent))
            self._pct_count_lbl.configure(text=f"{pct}%", text_color=pct_color)
        except Exception:
            pass

        # keep backward-compatible small labels
        try:
            self._present_label.configure(text=f"Present: {present}")
            self._late_label.configure(text=f"Late: {late}")
            self._absent_label.configure(text=f"Absent: {absent}")
            self._pct_label.configure(text=f"Attendance: {pct}%", text_color=pct_color)
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
        # remember last student for history/filters
        try:
            self._last_student_id = student_id
        except Exception:
            pass
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
        # update level2 title with student name from DB
        try:
            profile = get_student_profile(student_id) or {}
            name = self._format_profile_name(profile) or str(profile.get('name') or student_id)
            self.level2_title.configure(text=name)
        except Exception:
            try:
                self.level2_title.configure(text=str(student_id))
            except Exception:
                pass

    def _load_student_detail(self, student_id: str) -> None:
        """Fetch student profile and populate Level 2 widgets (name, photo, history)."""
        try:
            profile = get_student_profile(student_id) or {}
        except Exception:
            profile = {}

        # Name
        try:
            name = self._format_profile_name(profile) or str(profile.get('name') or student_id)
        except Exception:
            name = str(profile.get('name') or student_id)

        # Header labels (name + ID centered above divider)
        try:
            self._profile_name_lbl.configure(text=name)
            self._profile_id_lbl.configure(text=f"Student ID: {student_id}")
        except Exception:
            pass

        # Detail fields
        try:
            first_name  = str(profile.get('first_name')  or '—')
            middle_name = str(profile.get('middle_name') or '—')
            last_name   = str(profile.get('last_name')   or '—')
            reg_by      = str(profile.get('registered_by') or '—')
            reg_raw     = profile.get('registered_date')
            reg_date    = str(reg_raw)[:10] if reg_raw else '—'
            cls_id      = profile.get('class_id')
            cls_data    = self._class_map.get(cls_id) or {}
            if cls_data:
                class_label = f"{cls_data.get('name', '')} - {cls_data.get('section', '')}".strip(' -')
            else:
                class_label = str(cls_id or '—')
            dob_raw = profile.get('date_of_birth')
            if dob_raw:
                if hasattr(dob_raw, 'strftime'):
                    dob_d = dob_raw
                    dob_str = dob_raw.strftime("%d %B %Y")
                else:
                    from datetime import datetime as _dt
                    try:
                        dob_d = _dt.strptime(str(dob_raw)[:10], "%Y-%m-%d").date()
                        dob_str = dob_d.strftime("%d %B %Y")
                    except Exception:
                        dob_d = None
                        dob_str = str(dob_raw)
                if dob_d:
                    today = date.today()
                    age = today.year - dob_d.year - ((today.month, today.day) < (dob_d.month, dob_d.day))
                    age_str = f"{age} years"
                else:
                    age_str = '—'
            else:
                dob_str = '—'
                age_str = '—'
            address_val = str(profile.get('address') or '—')

            self._det_first.configure(text=first_name)
            self._det_middle.configure(text=middle_name)
            self._det_last.configure(text=last_name)
            self._det_class.configure(text=class_label)
            self._det_reg_by.configure(text=reg_by)
            self._det_reg_date.configure(text=reg_date)
            self._det_dob.configure(text=dob_str)
            self._det_age.configure(text=age_str)
            self._det_address.configure(text=address_val)
        except Exception:
            pass

        # Profile photo — circular 120×120 or initials fallback
        _PHOTO_SIZE = 120
        img_obj = None
        try:
            from PIL import Image as _PILImg, ImageDraw as _PILDraw
            raw = profile.get('profile_photo') or profile.get('photo')
            img_source = None
            if isinstance(raw, (bytes, bytearray)):
                img_source = io.BytesIO(raw)
            elif isinstance(raw, str) and raw:
                img_source = raw
            if img_source:
                base = _PILImg.open(img_source).convert('RGBA')
                w_, h_ = base.size
                side = min(w_, h_)
                base = base.crop(
                    ((w_ - side) // 2, (h_ - side) // 2,
                     (w_ + side) // 2, (h_ + side) // 2)
                )
                base = base.resize((_PHOTO_SIZE, _PHOTO_SIZE), _PILImg.LANCZOS)
                mask = _PILImg.new('L', (_PHOTO_SIZE, _PHOTO_SIZE), 0)
                _PILDraw.Draw(mask).ellipse((0, 0, _PHOTO_SIZE, _PHOTO_SIZE), fill=255)
                circle = _PILImg.new('RGBA', (_PHOTO_SIZE, _PHOTO_SIZE), (0, 0, 0, 0))
                circle.paste(base, mask=mask)
                img_obj = ctk.CTkImage(
                    light_image=circle, dark_image=circle,
                    size=(_PHOTO_SIZE, _PHOTO_SIZE),
                )
        except Exception:
            img_obj = None

        try:
            for w in list(self._profile_photo_frame.children.values()):
                try:
                    w.destroy()
                except Exception:
                    pass
            if img_obj:
                self._profile_photo_image = img_obj
                lbl = ctk.CTkLabel(self._profile_photo_frame, image=img_obj, text="", fg_color="transparent")
                lbl.grid(row=0, column=0)
                self._profile_photo_label = lbl
            else:
                initials = ''.join(p[0].upper() for p in name.split() if p)[:2] or '?'
                lbl = ctk.CTkLabel(
                    self._profile_photo_frame, text=initials,
                    font=ctk.CTkFont(size=36, weight="bold"),
                    text_color=theme.TEXT_SECONDARY,
                )
                lbl.grid(row=0, column=0)
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
 