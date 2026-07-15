from __future__ import annotations

import calendar as _cal_mod
import os as _os
import tkinter as tk
import weakref
import customtkinter as ctk
from datetime import date

from gui import theme

# ── floating-popup registry ───────────────────────────────────────────────────
# Tracks every widget that currently has a floating popup placed on root.
# close_all_floating_popups() is called by show_page() before navigation so
# stale popups never overlay a different page and block clicks.
_floating_open: weakref.WeakSet = weakref.WeakSet()


def close_all_floating_popups() -> None:
    """Close every open dropdown / date-picker popup.  Called on page navigation."""
    for widget in list(_floating_open):
        try:
            if hasattr(widget, '_collapse'):
                widget._collapse()
            elif hasattr(widget, '_close_popup'):
                widget._close_popup()
            elif hasattr(widget, '_close'):
                widget._close()
        except Exception:
            pass


def _safe_unbind(widget: tk.Misc, sequence: str, funcid: str) -> None:
    """Remove one specific handler without clearing sibling handlers.

    Python < 3.12 widget.unbind(seq, funcid) is broken: it clears ALL handlers
    for that sequence, not just the requested one.  This reimplements the fix
    that landed in CPython 3.12 (bpo-36817).
    """
    try:
        current = widget.tk.call('bind', widget._w, sequence)
        if not current:
            widget.tk.deletecommand(funcid)
            return
        new_lines = [l for l in current.split('\n') if funcid not in l]
        widget.tk.call('bind', widget._w, sequence, '\n'.join(new_lines))
        widget.tk.deletecommand(funcid)
    except Exception:
        pass

_FAVICON = _os.path.abspath(_os.path.join(
    _os.path.dirname(_os.path.dirname(__file__)), "assets", "favicon.ico"
))

try:
    from PIL import Image as _PIL_Image, ImageDraw as _PIL_Draw
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


def center_dialog(dialog, width: int, height: int) -> None:
    """Size and center a CTkToplevel on the root window, themed to BG_SURFACE."""
    try:
        root = dialog.master.winfo_toplevel()
        x = root.winfo_rootx() + (root.winfo_width()  - width)  // 2
        y = root.winfo_rooty() + (root.winfo_height() - height) // 2
    except Exception:
        x = (dialog.winfo_screenwidth()  - width)  // 2
        y = (dialog.winfo_screenheight() - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    try:
        dialog.configure(fg_color=theme.BG_SURFACE)
    except Exception:
        pass
    # CTkToplevel schedules its own icon override at ~200 ms; fire at 250 ms to win.
    if _os.path.isfile(_FAVICON):
        dialog.after(250, lambda: dialog.iconbitmap(_FAVICON))


def make_eye_image(size: int, color: str, slashed: bool = False):
    """Return a PIL RGBA Image of an open or slashed eye at *size*×*size* px."""
    if not _PIL_OK:
        return None
    scale = 4
    s = size * scale
    img = _PIL_Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = _PIL_Draw.Draw(img)
    ri, gi, bi = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    c = (ri, gi, bi, 255)
    lw = max(2, s // 14)
    cx, cy = s // 2, s // 2
    rx, ry = int(s * 0.44), int(s * 0.24)
    bbox = (cx - rx, cy - ry, cx + rx, cy + ry)
    d.arc(bbox, start=180, end=360, fill=c, width=lw)
    d.arc(bbox, start=0,   end=180, fill=c, width=lw)
    pr = max(2, s // 9)
    d.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=c)
    if slashed:
        d.line(
            (cx - rx + lw, cy + ry + ry // 2, cx + rx - lw, cy - ry - ry // 2),
            fill=c, width=lw + 2,
        )
    return img.resize((size, size), _PIL_Image.Resampling.LANCZOS)


class ThemedDropdown(ctk.CTkFrame):
    """
    Dropdown whose trigger is a fixed-height styled box (INPUT_BG + border).
    When opened, a floating popup appears directly below (or above if near the
    window bottom) and overlays whatever is behind it — the page layout is
    never disturbed.

    API: get(), set(value), configure(values=..., state=..., command=...)
    CTkComboBox-only kwargs are silently absorbed.
    """

    _COMBOBOX_ONLY = frozenset({
        "button_color", "button_hover_color",
        "dropdown_fg_color", "dropdown_text_color", "dropdown_hover_color",
        "dropdown_font", "justify",
        "fg_color", "border_width", "border_color",
        "corner_radius", "text_color",
    })
    _MAX_OPTIONS_H = 200  # popup options area scrolls beyond this many px

    def __init__(
        self,
        master,
        values: list[str] | None = None,
        command=None,
        variable=None,
        state: str = "normal",
        height: int = 42,
        **kwargs,
    ) -> None:
        for k in list(kwargs):
            if k in self._COMBOBOX_ONLY:
                kwargs.pop(k)

        # Outer frame IS the trigger — same styling as a form input
        super().__init__(
            master,
            fg_color=theme.INPUT_BG,
            border_width=1,
            border_color=theme.BORDER,
            corner_radius=8,
            height=height,
            **kwargs,
        )
        # Keep fixed height so the page layout is never displaced
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._values: list[str] = list(values or [])
        self._command = command
        self._variable = variable
        self._disabled = False
        self._expanded = False
        self._popup: tk.Frame | None = None
        self._root_bid: str | None = None
        self._row_h = height

        if variable is not None and variable.get() in self._values:
            self._current: str = variable.get()
        elif self._values:
            self._current = self._values[0]
        else:
            self._current = ""

        self._value_lbl = ctk.CTkLabel(
            self,
            text=self._current,
            anchor="w",
            text_color=theme.TEXT_PRIMARY,
            fg_color="transparent",
            font=ctk.CTkFont(size=13),
        )
        self._value_lbl.grid(row=0, column=0, sticky="ew", padx=(14, 0))

        self._arrow_lbl = ctk.CTkLabel(
            self,
            text="▾",
            anchor="center",
            text_color=theme.TEXT_SECONDARY,
            fg_color="transparent",
            font=ctk.CTkFont(size=15),
            width=32,
        )
        self._arrow_lbl.grid(row=0, column=1, padx=(0, 8))

        for w in (self, self._value_lbl, self._arrow_lbl):
            w.bind("<Button-1>", lambda _e: self._toggle())
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

        if state == "disabled":
            self._apply_disabled(True)
        else:
            self._set_cursor("hand2")

        if variable is not None:
            variable.trace_add("write", self._on_var_write)

        self.bind("<Destroy>", lambda _: self._cleanup())

    # ── state ─────────────────────────────────────────────────────────────────

    def _apply_disabled(self, disabled: bool) -> None:
        self._disabled = disabled
        self._set_cursor("" if disabled else "hand2")
        try:
            self._value_lbl.configure(
                text_color=theme.TEXT_MUTED if disabled else theme.TEXT_PRIMARY
            )
            self._arrow_lbl.configure(
                text_color=theme.TEXT_MUTED if disabled else theme.TEXT_SECONDARY
            )
        except Exception:
            pass

    def _set_cursor(self, cursor: str) -> None:
        for w in (self, self._value_lbl, self._arrow_lbl):
            try:
                w.configure(cursor=cursor)
            except Exception:
                pass

    # ── trigger hover ─────────────────────────────────────────────────────────

    def _on_enter(self, _=None) -> None:
        if not self._disabled:
            try:
                self.configure(fg_color=theme.INPUT_HIGHLIGHT)
            except Exception:
                pass

    def _on_leave(self, _=None) -> None:
        try:
            mx = self.winfo_pointerx()
            my = self.winfo_pointery()
            x  = self.winfo_rootx()
            y  = self.winfo_rooty()
            w  = self.winfo_width()
            h  = self.winfo_height()
            if not (x <= mx <= x + w and y <= my <= y + h):
                self.configure(fg_color=theme.INPUT_BG)
        except Exception:
            try:
                self.configure(fg_color=theme.INPUT_BG)
            except Exception:
                pass

    # ── public API ────────────────────────────────────────────────────────────

    def get(self) -> str:
        return self._current

    def set(self, value: str) -> None:
        self._current = value
        try:
            self._value_lbl.configure(text=value)
        except Exception:
            pass
        if self._variable is not None:
            try:
                self._variable.set(value)
            except Exception:
                pass

    def configure(self, **kwargs) -> None:
        for k in list(kwargs):
            if k in self._COMBOBOX_ONLY:
                kwargs.pop(k)

        values  = kwargs.pop("values", None)
        state   = kwargs.pop("state", None)
        command = kwargs.pop("command", None)

        if values is not None:
            self._values = list(values)
            if self._expanded:
                self._collapse()
        if command is not None:
            self._command = command
        if state is not None:
            self._apply_disabled(state == "disabled")
        if kwargs:
            try:
                super().configure(**kwargs)
            except Exception:
                pass

    def _on_var_write(self, *_) -> None:
        if self._variable is not None:
            try:
                val = self._variable.get()
                self._current = val
                self._value_lbl.configure(text=val)
            except Exception:
                pass

    # ── expand / collapse ─────────────────────────────────────────────────────

    def _toggle(self) -> None:
        if self._disabled:
            return
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True

        try:
            self._arrow_lbl.configure(text="▴")
        except Exception:
            pass

        root = self.winfo_toplevel()
        self.update_idletasks()

        trigger_x = self.winfo_rootx() - root.winfo_rootx()
        trigger_y = self.winfo_rooty() - root.winfo_rooty()
        trigger_w = self.winfo_width()
        trigger_h = self.winfo_height()

        # Popup floats on the root window — same visual style as the trigger.
        # Using plain tk.Frame so place(width=, height=) is unrestricted.
        popup = tk.Frame(
            root,
            bg=theme.INPUT_BG,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
            bd=0,
        )
        self._popup = popup

        options_h = len(self._values) * (self._row_h + 2)
        use_scroll = options_h > self._MAX_OPTIONS_H

        if use_scroll:
            scroll = ctk.CTkScrollableFrame(
                popup,
                height=self._MAX_OPTIONS_H,
                fg_color=theme.INPUT_BG,
                corner_radius=0,
                border_width=0,
                scrollbar_fg_color=theme.INPUT_BG,
                scrollbar_button_color=theme.BORDER,
                scrollbar_button_hover_color=theme.INPUT_HIGHLIGHT,
            )
            scroll.pack(fill="both", expand=True)
            parent = scroll
        else:
            parent = popup

        for val in self._values:
            is_sel = val == self._current
            btn = ctk.CTkButton(
                parent,
                text=f"  {val}",
                height=self._row_h,
                corner_radius=0,
                fg_color=theme.ACCENT_SUBTLE if is_sel else theme.INPUT_BG,
                hover_color=theme.INPUT_HIGHLIGHT,
                text_color=theme.TEXT_LINK if is_sel else theme.TEXT_PRIMARY,
                anchor="w",
                font=ctk.CTkFont(size=13),
                command=lambda v=val: self._select(v),
            )
            btn.pack(fill="x")

        # Measure content then place popup
        popup.update_idletasks()
        popup_h = popup.winfo_reqheight()

        # Prefer below; flip above if popup would overflow the window bottom
        y_below = trigger_y + trigger_h - 1  # -1 to overlap the bottom border
        y_above = trigger_y - popup_h + 1
        root_h  = root.winfo_height()
        y = y_above if (y_below + popup_h > root_h) else y_below

        popup.place(x=trigger_x, y=y, width=trigger_w, height=popup_h)
        popup.lift()
        _floating_open.add(self)

        # Collapse on any click outside both trigger and popup
        def _on_outside_click(event) -> None:
            if not self._expanded:
                return
            try:
                # inside trigger?
                tx, ty = self.winfo_rootx(), self.winfo_rooty()
                tw, th = self.winfo_width(), self.winfo_height()
                if tx <= event.x_root <= tx + tw and ty <= event.y_root <= ty + th:
                    return
                # inside popup?
                if self._popup is not None:
                    px = self._popup.winfo_rootx()
                    py = self._popup.winfo_rooty()
                    pw = self._popup.winfo_width()
                    ph = self._popup.winfo_height()
                    if px <= event.x_root <= px + pw and py <= event.y_root <= py + ph:
                        return
            except Exception:
                pass
            self._collapse()

        self._root_bid = root.bind("<ButtonPress-1>", _on_outside_click, add="+")

    def _collapse(self) -> None:
        if not self._expanded:
            return
        self._expanded = False
        _floating_open.discard(self)

        try:
            self._arrow_lbl.configure(text="▾")
        except Exception:
            pass
        try:
            self.configure(fg_color=theme.INPUT_BG)
        except Exception:
            pass

        popup = self._popup
        self._popup = None
        if popup is not None:
            try:
                popup.place_forget()
                popup.destroy()
            except Exception:
                pass

        bid = self._root_bid
        self._root_bid = None
        if bid is not None:
            _safe_unbind(self.winfo_toplevel(), "<ButtonPress-1>", bid)

    def _select(self, value: str) -> None:
        self._collapse()
        self.set(value)
        if self._command is not None:
            try:
                self._command(value)
            except Exception:
                pass

    def _cleanup(self) -> None:
        _floating_open.discard(self)
        bid = self._root_bid
        self._root_bid = None
        if bid is not None:
            _safe_unbind(self.winfo_toplevel(), "<ButtonPress-1>", bid)
        popup = self._popup
        self._popup = None
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass


# ── ThemedRangePicker ─────────────────────────────────────────────────────────

class ThemedRangePicker(ctk.CTkFrame):
    """
    Date range picker with a floating calendar popup.

    The widget occupies only a single row of two date-field buttons.
    Clicking either button opens a floating tk.Frame calendar placed on the
    root window (same technique as ThemedDropdown), so the calendar never
    shifts or reflows surrounding layout elements.

    Public API
    ----------
    get_from_date() -> date | None
    get_to_date()   -> date | None
    get_range()     -> tuple[date, date] | None
    set_range(start, end)
    open_calendar()   — programmatically open the floating popup
    close_calendar()  — programmatically close the floating popup
    """

    _DOW     = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    _POPUP_W = 460
    _POPUP_H = 420
    _CELL_W  = 44
    _CELL_H  = 40

    def __init__(
        self,
        master,
        on_change=None,
        initial_from: date | None = None,
        initial_to:   date | None = None,
        height: int = 36,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._on_change = on_change
        self._from_date = initial_from
        self._to_date   = initial_to
        self._selecting = "from"
        self._btn_height = height

        self._popup:    tk.Frame | None = None
        self._root_bid: str | None = None

        # refs valid only while popup is open
        self._month_lbl = None
        self._hint_lbl  = None
        self._range_lbl = None
        self._day_grid  = None

        today = date.today()
        self._year  = (initial_from or today).year
        self._month = (initial_from or today).month

        self.grid_columnconfigure(0, weight=1)
        self._build_fields()
        self._refresh_fields()
        self.bind("<Destroy>", lambda _: self._cleanup())

    # ── trigger row ───────────────────────────────────────────────────────────

    def _build_fields(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(2, weight=1)

        self._from_btn = ctk.CTkButton(
            row, text="", height=self._btn_height,
            fg_color=theme.INPUT_BG, hover_color=theme.INPUT_HIGHLIGHT,
            text_color=theme.TEXT_MUTED, border_width=1, border_color=theme.BORDER,
            corner_radius=8, anchor="w", font=ctk.CTkFont(size=13),
            command=lambda: self._toggle("from"),
        )
        self._from_btn.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            row, text="→", font=ctk.CTkFont(size=14),
            text_color=theme.TEXT_MUTED, width=32,
        ).grid(row=0, column=1, padx=6)

        self._to_btn = ctk.CTkButton(
            row, text="", height=self._btn_height,
            fg_color=theme.INPUT_BG, hover_color=theme.INPUT_HIGHLIGHT,
            text_color=theme.TEXT_MUTED, border_width=1, border_color=theme.BORDER,
            corner_radius=8, anchor="w", font=ctk.CTkFont(size=13),
            command=lambda: self._toggle("to"),
        )
        self._to_btn.grid(row=0, column=2, sticky="ew")

    # ── popup lifecycle ───────────────────────────────────────────────────────

    def _toggle(self, field: str) -> None:
        if self._popup is not None:
            if self._selecting == field:
                self._close_popup()
            else:
                self._selecting = field
                self._update_hint()
                self._refresh_fields()
        else:
            self._selecting = field
            self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is not None:
            return

        root = self.winfo_toplevel()
        # Use an explicit anchor widget when popup is triggered externally
        anchor = getattr(self, '_popup_anchor', None) or self
        anchor.update_idletasks()

        popup = tk.Frame(
            root,
            bg=theme.BG_SURFACE,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
            bd=0,
        )
        self._popup = popup
        self._build_popup_content(popup)

        self.update_idletasks()
        tx = anchor.winfo_rootx() - root.winfo_rootx()
        ty = anchor.winfo_rooty() - root.winfo_rooty()
        tw = anchor.winfo_width()
        th = anchor.winfo_height()
        rh = root.winfo_height()
        rw = root.winfo_width()

        y = ty + th + 4
        if y + self._POPUP_H > rh:
            y = max(0, ty - self._POPUP_H - 4)
        # Center popup horizontally under the full From→To widget
        x = tx + tw // 2 - self._POPUP_W // 2
        x = max(0, min(x, rw - self._POPUP_W))

        # No explicit height — let tk auto-size from grid content.
        # Constraining height before CTk widgets finish rendering clips the popup.
        popup.place(x=x, y=y, width=self._POPUP_W)
        popup.lift()
        _floating_open.add(self)
        # Re-lift after CTk redraws so the popup stays on top.
        root.after(10, lambda: popup.lift() if self._popup is popup else None)
        self._refresh_fields()
        self._update_hint()

        def _outside(event: tk.Event) -> None:
            if not self._popup:
                return
            try:
                bx, by = self.winfo_rootx(), self.winfo_rooty()
                bw, bh = self.winfo_width(), self.winfo_height()
                if bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh:
                    return
                px, py = self._popup.winfo_rootx(), self._popup.winfo_rooty()
                pw, ph = self._popup.winfo_width(), self._popup.winfo_height()
                if px <= event.x_root <= px + pw and py <= event.y_root <= py + ph:
                    return
            except Exception:
                pass
            self._close_popup()

        self._root_bid = root.bind("<ButtonPress-1>", _outside, add="+")

    def _close_popup(self) -> None:
        self._month_lbl = self._hint_lbl = self._range_lbl = self._day_grid = None
        _floating_open.discard(self)

        popup = self._popup
        self._popup = None
        if popup is not None:
            try:
                popup.place_forget()
                popup.destroy()
            except Exception:
                pass

        bid = self._root_bid
        self._root_bid = None
        if bid is not None:
            _safe_unbind(self.winfo_toplevel(), "<ButtonPress-1>", bid)

        self._refresh_fields()

    # ── popup content ─────────────────────────────────────────────────────────

    def _build_popup_content(self, popup: tk.Frame) -> None:
        PAD = 16
        BG  = theme.BG_SURFACE
        popup.grid_columnconfigure(0, weight=1)

        # Use plain tk.Frame for all layout containers — CTkFrame owns an
        # internal Canvas that can overdraw its children when nested inside
        # another tk.Frame, partially hiding CTkButton text.

        # Navigation
        nav = tk.Frame(popup, bg=BG)
        nav.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(16, 6))
        nav.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            nav, text="‹", width=34, height=34,
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY, corner_radius=8,
            font=ctk.CTkFont(size=20),
            command=self._prev_month,
        ).grid(row=0, column=0)

        self._month_lbl = tk.Label(
            nav, text="",
            bg=BG, fg=theme.TEXT_PRIMARY,
            font=("Segoe UI", 15, "bold"),
            anchor="center",
        )
        self._month_lbl.grid(row=0, column=1)

        ctk.CTkButton(
            nav, text="›", width=34, height=34,
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY, corner_radius=8,
            font=ctk.CTkFont(size=20),
            command=self._next_month,
        ).grid(row=0, column=2)

        # Hint
        self._hint_lbl = tk.Label(
            popup, text="",
            bg=BG, fg=theme.TEXT_SECONDARY,
            font=("Segoe UI", 11),
        )
        self._hint_lbl.grid(row=1, column=0, pady=(0, 8))

        # Day-of-week headers
        hdr = tk.Frame(popup, bg=BG)
        hdr.grid(row=2, column=0, sticky="ew", padx=PAD, pady=(0, 4))
        for i in range(7):
            hdr.grid_columnconfigure(i, weight=1)
        for i, d in enumerate(self._DOW):
            tk.Label(
                hdr, text=d,
                bg=BG, fg=theme.TEXT_SECONDARY,
                font=("Segoe UI", 11, "bold"),
                anchor="center", width=3,
            ).grid(row=0, column=i, padx=3, sticky="ew")

        # Day grid — plain tk.Frame so CTkButton canvases are never overdrawn
        self._day_grid = tk.Frame(popup, bg=BG)
        self._day_grid.grid(row=3, column=0, sticky="ew", padx=PAD, pady=(0, 6))
        for i in range(7):
            self._day_grid.grid_columnconfigure(i, weight=1)

        # Divider
        tk.Frame(popup, bg=theme.BORDER, height=1).grid(
            row=4, column=0, sticky="ew", padx=PAD, pady=(4, 0)
        )

        # Action bar
        bar = tk.Frame(popup, bg=BG)
        bar.grid(row=5, column=0, sticky="ew", padx=PAD, pady=(8, 14))
        bar.grid_columnconfigure(0, weight=1)

        self._range_lbl = tk.Label(
            bar, text="",
            bg=BG, fg=theme.TEXT_PRIMARY,
            font=("Segoe UI", 12),
            anchor="w",
        )
        self._range_lbl.grid(row=0, column=0, sticky="w")

        btns = tk.Frame(bar, bg=BG)
        btns.grid(row=0, column=1)

        ctk.CTkButton(
            btns, text="Clear", width=68, height=32,
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_SECONDARY, corner_radius=6,
            font=ctk.CTkFont(size=13),
            command=self._clear,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns, text="Apply", width=76, height=32,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_PRIMARY, corner_radius=6,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._apply,
        ).pack(side="left")

        self._render_month()

    # ── calendar rendering ────────────────────────────────────────────────────

    def _render_month(self) -> None:
        if self._day_grid is None or self._month_lbl is None:
            return

        for w in list(self._day_grid.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        self._month_lbl.configure(
            text=date(self._year, self._month, 1).strftime("%B %Y")
        )

        today = date.today()
        weeks = _cal_mod.monthcalendar(self._year, self._month)
        while len(weeks) < 6:
            weeks.append([0] * 7)

        _font_normal = ("Segoe UI", 13)
        _font_bold   = ("Segoe UI", 13, "bold")

        for r, week in enumerate(weeks):
            self._day_grid.grid_rowconfigure(r, minsize=self._CELL_H)
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(
                        self._day_grid, text="",
                        bg=theme.BG_SURFACE,
                        width=3, height=1,
                    ).grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
                    continue

                d = date(self._year, self._month, day)
                is_start = d == self._from_date
                is_end   = d == self._to_date
                endpoint = is_start or is_end
                in_range = (
                    self._from_date and self._to_date and
                    self._from_date < d < self._to_date
                )
                is_today = d == today

                if endpoint:
                    bg, fg = theme.ACCENT, "#FFFFFF"
                elif in_range:
                    bg, fg = theme.ACCENT_SUBTLE, theme.TEXT_LINK
                elif is_today:
                    bg, fg = theme.BG_HOVER, theme.TEXT_PRIMARY
                else:
                    bg, fg = theme.BG_SURFACE, theme.TEXT_PRIMARY

                hover_bg = theme.ACCENT_HOVER if endpoint else theme.BG_HOVER
                font = _font_bold if (endpoint or is_today) else _font_normal

                cell = tk.Label(
                    self._day_grid,
                    text=str(day),
                    bg=bg, fg=fg,
                    font=font,
                    cursor="hand2",
                    anchor="center",
                    width=3, height=1,
                )
                cell.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
                cell.bind("<Button-1>", lambda e, _d=d: self._day_click(_d))
                cell.bind("<Enter>",    lambda e, w=cell, h=hover_bg: w.configure(bg=h))
                cell.bind("<Leave>",    lambda e, w=cell, n=bg: w.configure(bg=n))

        self._update_range_label()

    # ── interaction ───────────────────────────────────────────────────────────

    def _day_click(self, d: date) -> None:
        if self._selecting == "from" or self._from_date is None:
            self._from_date = d
            self._to_date   = None
            self._selecting = "to"
        else:
            if d < self._from_date:
                self._from_date, self._to_date = d, self._from_date
            else:
                self._to_date = d
            self._selecting = "from"

        self._refresh_fields()
        self._update_hint()
        self._render_month()

    def _prev_month(self) -> None:
        if self._month == 1:
            self._month, self._year = 12, self._year - 1
        else:
            self._month -= 1
        self._render_month()

    def _next_month(self) -> None:
        if self._month == 12:
            self._month, self._year = 1, self._year + 1
        else:
            self._month += 1
        self._render_month()

    def _clear(self) -> None:
        self._from_date = self._to_date = None
        self._selecting = "from"
        self._refresh_fields()
        self._update_hint()
        self._render_month()

    def _apply(self) -> None:
        from_d, to_d = self._from_date, self._to_date
        self._close_popup()
        if self._on_change and from_d and to_d:
            try:
                self._on_change(from_d, to_d)
            except Exception:
                pass

    # ── field / hint helpers ──────────────────────────────────────────────────

    def _fmt(self, d: date | None, placeholder: str) -> str:
        return f"  {d.strftime('%d %b %Y')}" if d else f"  {placeholder}"

    def _refresh_fields(self) -> None:
        open_from = self._popup is not None and self._selecting == "from"
        open_to   = self._popup is not None and self._selecting == "to"
        self._from_btn.configure(
            text=self._fmt(self._from_date, "From date"),
            text_color=theme.TEXT_PRIMARY if self._from_date else theme.TEXT_MUTED,
            border_color=theme.ACCENT if open_from else theme.BORDER,
        )
        self._to_btn.configure(
            text=self._fmt(self._to_date, "To date"),
            text_color=theme.TEXT_PRIMARY if self._to_date else theme.TEXT_MUTED,
            border_color=theme.ACCENT if open_to else theme.BORDER,
        )

    def _update_hint(self) -> None:
        if self._hint_lbl is None:
            return
        if self._selecting == "from" or self._from_date is None:
            self._hint_lbl.configure(text="Click a day to set the start date")
        else:
            self._hint_lbl.configure(text="Now click a day to set the end date")

    def _update_range_label(self) -> None:
        if self._range_lbl is None:
            return
        if self._from_date and self._to_date:
            n = (self._to_date - self._from_date).days + 1
            self._range_lbl.configure(
                text=(
                    f"{self._from_date.strftime('%d %b')} → "
                    f"{self._to_date.strftime('%d %b %Y')}  "
                    f"({n} day{'s' if n != 1 else ''})"
                )
            )
        elif self._from_date:
            self._range_lbl.configure(
                text=f"Start: {self._from_date.strftime('%d %b %Y')}"
            )
        else:
            self._range_lbl.configure(text="")

    # ── cleanup ───────────────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        _floating_open.discard(self)
        bid = self._root_bid
        self._root_bid = None
        if bid is not None:
            _safe_unbind(self.winfo_toplevel(), "<ButtonPress-1>", bid)
        popup = self._popup
        self._popup = None
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    # ── public API ────────────────────────────────────────────────────────────

    def open_calendar(self) -> None:
        """Programmatically open the floating calendar popup."""
        if self._popup is None:
            self._open_popup()

    def close_calendar(self) -> None:
        """Programmatically close the floating calendar popup."""
        self._close_popup()

    def open_popup_anchored_to(self, anchor) -> None:
        """Toggle the calendar popup, positioning it below `anchor` widget.

        Calling this while the popup is already open closes it instead,
        making the anchor button act as a toggle.
        """
        if self._popup is not None:
            self._close_popup()
            return
        self._popup_anchor = anchor
        self._open_popup()
        self._popup_anchor = None

    def get_from_date(self) -> date | None:
        return self._from_date

    def get_to_date(self) -> date | None:
        return self._to_date

    def get_range(self) -> tuple[date, date] | None:
        if self._from_date and self._to_date:
            return self._from_date, self._to_date
        return None

    def set_range(self, start: date, end: date) -> None:
        self._from_date = start
        self._to_date   = end
        self._year  = start.year
        self._month = start.month
        self._refresh_fields()
        if self._popup is not None:
            self._render_month()


# ── SingleDatePicker ──────────────────────────────────────────────────────────

class SingleDatePicker(ctk.CTkFrame):
    """
    Compact single-date selector.

    Renders as one button showing the chosen date (or a placeholder).
    Clicking opens a floating calendar popup; clicking a day immediately
    selects it and closes the popup — no Apply step needed.

    Public API
    ----------
    get_date()  -> date | None
    set_date(d: date | None)
    """

    _POPUP_W = 340
    _POPUP_H = 320
    _CELL_W  = 40
    _CELL_H  = 34

    def __init__(
        self,
        master,
        placeholder: str = "Select date",
        initial_date: date | None = None,
        on_change=None,
        height: int = 36,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._selected: date | None = None
        self._on_change = on_change
        self._popup: tk.Frame | None = None
        self._outside_bid: str | None = None
        self._year  = date.today().year
        self._month = date.today().month
        self._placeholder = placeholder
        self._year_mode:       bool = False
        self._prev_btn        = None
        self._next_btn        = None
        self._month_name_lbl  = None
        self._year_lbl        = None

        self.grid_columnconfigure(0, weight=1)

        self._btn = ctk.CTkButton(
            self,
            text=placeholder,
            height=height,
            fg_color=theme.BG_SURFACE_ALT,
            hover_color=theme.INPUT_HIGHLIGHT,
            text_color=theme.TEXT_MUTED,
            anchor="w",
            corner_radius=6,
            command=self._toggle,
        )
        self._btn.grid(row=0, column=0, sticky="ew")

        if initial_date is not None:
            self._selected = initial_date
            self._year  = initial_date.year
            self._month = initial_date.month
            self._btn.configure(
                text=initial_date.strftime("%d %B %Y"),
                text_color=theme.TEXT_PRIMARY,
            )

    # ── toggle / open / close ────────────────────────────────────────────────

    def _toggle(self) -> None:
        if self._popup is not None:
            self._close()
        else:
            self._open()

    def _open(self) -> None:
        if self._popup is not None:
            return

        root = self.winfo_toplevel()
        self._btn.update_idletasks()

        popup = tk.Frame(
            root,
            bg=theme.BG_SURFACE,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
            bd=0,
        )
        self._popup = popup

        # ── month nav ────────────────────────────────────────────────────────
        # Columns: 0=prev  1=spacer(weight)  2=month_name  3=year_btn  4=spacer(weight)  5=next
        nav = tk.Frame(popup, bg=theme.BG_SURFACE)
        nav.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        nav.grid_columnconfigure(1, weight=1)
        nav.grid_columnconfigure(4, weight=1)

        self._prev_btn = ctk.CTkButton(
            nav, text="‹", width=30, height=28, corner_radius=6,
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
            command=self._prev_month,
        )
        self._prev_btn.grid(row=0, column=0)

        self._month_name_lbl = tk.Label(
            nav, bg=theme.BG_SURFACE, fg=theme.TEXT_PRIMARY,
            font=("Segoe UI", 13, "bold"),
        )
        self._month_name_lbl.grid(row=0, column=2)

        self._year_lbl = tk.Label(
            nav, bg=theme.BG_SURFACE_ALT, fg=theme.TEXT_PRIMARY,
            font=("Segoe UI", 12, "bold"), cursor="hand2",
            padx=7, pady=1,
        )
        self._year_lbl.grid(row=0, column=3, padx=(6, 0))
        self._year_lbl.bind("<Button-1>", lambda _e: self._toggle_year_mode())
        self._year_lbl.bind("<Enter>", lambda _e: self._year_lbl.configure(bg=theme.BG_HOVER))
        self._year_lbl.bind("<Leave>", lambda _e: self._year_lbl.configure(
            bg=theme.BG_HOVER if self._year_mode else theme.BG_SURFACE_ALT))

        self._next_btn = ctk.CTkButton(
            nav, text="›", width=30, height=28, corner_radius=6,
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
            command=self._next_month,
        )
        self._next_btn.grid(row=0, column=5)

        # ── calendar grid  (DOW headers are row 0; days are rows 1-6) ──────────
        self._grid = tk.Frame(popup, bg=theme.BG_SURFACE)
        self._grid.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self._render_month()

        # ── position popup ───────────────────────────────────────────────────
        tx = self._btn.winfo_rootx() - root.winfo_rootx()
        ty = self._btn.winfo_rooty() - root.winfo_rooty()
        tw = self._btn.winfo_width()
        th = self._btn.winfo_height()
        rh, rw = root.winfo_height(), root.winfo_width()

        y = ty + th + 4
        if y + self._POPUP_H > rh:
            y = max(0, ty - self._POPUP_H - 4)
        x = tx + tw // 2 - self._POPUP_W // 2
        x = max(0, min(x, rw - self._POPUP_W))

        popup.place(x=x, y=y, width=self._POPUP_W)
        popup.lift()
        _floating_open.add(self)
        root.after(10, lambda: popup.lift() if self._popup is popup else None)

        def _outside(event: tk.Event) -> None:
            if not self._popup:
                return
            try:
                bx, by = self._btn.winfo_rootx(), self._btn.winfo_rooty()
                bw, bh = self._btn.winfo_width(), self._btn.winfo_height()
                if bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh:
                    return
                px, py = self._popup.winfo_rootx(), self._popup.winfo_rooty()
                pw, ph = self._popup.winfo_width(), self._popup.winfo_height()
                if px <= event.x_root <= px + pw and py <= event.y_root <= py + ph:
                    return
            except Exception:
                pass
            self._close()

        self._outside_bid = root.bind("<ButtonPress-1>", _outside, add="+")

    def _close(self) -> None:
        self._year_mode = False
        self._prev_btn = self._next_btn = None
        self._month_name_lbl = self._year_lbl = None
        self._grid = None
        _floating_open.discard(self)
        popup, self._popup = self._popup, None
        if popup:
            try:
                popup.place_forget()
                popup.destroy()
            except Exception:
                pass
        bid, self._outside_bid = self._outside_bid, None
        if bid:
            _safe_unbind(self.winfo_toplevel(), "<ButtonPress-1>", bid)

    # ── calendar rendering ───────────────────────────────────────────────────

    def _render_month(self) -> None:
        if not self._grid:
            return
        for w in list(self._grid.children.values()):
            try:
                w.destroy()
            except Exception:
                pass

        self._year_mode = False
        if self._prev_btn:
            self._prev_btn.configure(command=self._prev_month)
            self._prev_btn.grid()
        if self._next_btn:
            self._next_btn.configure(command=self._next_month)
            self._next_btn.grid()
        if self._month_name_lbl:
            self._month_name_lbl.configure(text=_cal_mod.month_name[self._month])
        if self._year_lbl:
            self._year_lbl.configure(text=str(self._year), fg=theme.TEXT_PRIMARY,
                                     bg=theme.BG_SURFACE_ALT)

        for col in range(7):
            self._grid.grid_columnconfigure(col, minsize=self._CELL_W, weight=0)

        # DOW headers — same frame, same column widths, row 0
        for col, d in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            tk.Label(
                self._grid, text=d, bg=theme.BG_SURFACE, fg=theme.TEXT_MUTED,
                font=("Segoe UI", 10), width=4, anchor="center",
            ).grid(row=0, column=col, pady=(0, 2))

        today_d = date.today()
        weeks = _cal_mod.monthcalendar(self._year, self._month)
        while len(weeks) < 6:
            weeks.append([0] * 7)

        for r, week in enumerate(weeks):
            self._grid.grid_rowconfigure(r + 1, minsize=self._CELL_H)
            for c, day in enumerate(week):
                if day == 0:
                    tk.Frame(
                        self._grid, bg=theme.BG_SURFACE,
                        width=self._CELL_W, height=self._CELL_H,
                    ).grid(row=r + 1, column=c)
                    continue
                d = date(self._year, self._month, day)
                is_sel   = (self._selected == d)
                is_today = (d == today_d)

                bg = theme.ACCENT if is_sel else (theme.ACCENT_SUBTLE if is_today else theme.BG_SURFACE)
                fg = "#FFFFFF" if is_sel else theme.TEXT_PRIMARY

                lbl = tk.Label(
                    self._grid, text=str(day),
                    bg=bg, fg=fg,
                    font=("Segoe UI", 12, "bold" if is_sel or is_today else "normal"),
                    width=3, height=1, cursor="hand2",
                )
                lbl.grid(row=r + 1, column=c, padx=2, pady=2)
                lbl.bind("<Button-1>", lambda _e, dd=d: self._select(dd))
                hover_bg = theme.ACCENT if is_sel else theme.BG_HOVER
                lbl.bind("<Enter>", lambda _e, l=lbl: l.configure(bg=hover_bg))
                lbl.bind("<Leave>", lambda _e, l=lbl, b=bg: l.configure(bg=b))

    # ── year-picker mode ─────────────────────────────────────────────────────

    def _toggle_year_mode(self) -> None:
        if self._year_mode:
            self._render_month()
        else:
            self._year_mode = True
            self._show_year_grid()

    def _show_year_grid(self) -> None:
        if not self._grid:
            return

        # Hide nav arrows; update header
        if self._prev_btn:
            self._prev_btn.grid_remove()
        if self._next_btn:
            self._next_btn.grid_remove()
        if self._month_name_lbl:
            self._month_name_lbl.configure(text="Select Year")
        if self._year_lbl:
            self._year_lbl.configure(text=str(self._year), fg=theme.TEXT_PRIMARY,
                                     bg=theme.BG_HOVER)

        # Clear previous content
        for w in list(self._grid.children.values()):
            try:
                w.destroy()
            except Exception:
                pass

        # Single expanding column for the scroll frame
        for c in range(7):
            self._grid.grid_columnconfigure(c, weight=0, minsize=0)
        self._grid.grid_columnconfigure(0, weight=1)

        years = list(range(date.today().year + 1, 1899, -1))

        # CTkScrollableFrame provides a themed scrollbar — no native tk.Scrollbar
        scroll = ctk.CTkScrollableFrame(
            self._grid,
            fg_color=theme.BG_SURFACE,
            scrollbar_button_color=theme.BG_SURFACE_ALT,
            scrollbar_button_hover_color=theme.ACCENT,
            height=160,
            corner_radius=6,
        )
        scroll.grid(row=0, column=0, sticky="ew", pady=(4, 4))
        scroll.grid_columnconfigure(0, weight=1)

        for y in years:
            is_sel = (y == self._year)
            bg  = theme.ACCENT      if is_sel else theme.BG_SURFACE
            fg  = "#FFFFFF"         if is_sel else theme.TEXT_PRIMARY
            fnt = ("Segoe UI", 13, "bold") if is_sel else ("Segoe UI", 13)

            lbl = tk.Label(
                scroll,
                text=str(y),
                bg=bg, fg=fg,
                font=fnt,
                cursor="hand2",
                anchor="center",
                height=1,
            )
            lbl.pack(fill="x", padx=6, pady=2)

            if not is_sel:
                lbl.bind("<Enter>", lambda _e, l=lbl: l.configure(bg=theme.BG_HOVER))
                lbl.bind("<Leave>", lambda _e, l=lbl: l.configure(bg=theme.BG_SURFACE))
            lbl.bind("<Button-1>", lambda _e, yr=y: self._select_year(yr))

        # Scroll so selected year is visible near the top of the viewport
        if self._year in years:
            idx = years.index(self._year)
            total = len(years)
            frac = max(0.0, (idx - 3) / total)

            def _scroll_to(_c=scroll, _f=frac):
                try:
                    _c._parent_canvas.yview_moveto(_f)
                except Exception:
                    pass

            self._grid.after(20, _scroll_to)

    def _select_year(self, year: int) -> None:
        self._year = year
        self._render_month()

    # ── month navigation ──────────────────────────────────────────────────────

    def _prev_month(self) -> None:
        self._month -= 1
        if self._month < 1:
            self._month = 12
            self._year -= 1
        self._render_month()

    def _next_month(self) -> None:
        self._month += 1
        if self._month > 12:
            self._month = 1
            self._year += 1
        self._render_month()

    def _select(self, d: date) -> None:
        self._selected = d
        self._btn.configure(
            text=d.strftime("%d %B %Y"),
            text_color=theme.TEXT_PRIMARY,
        )
        self._close()
        if self._on_change:
            try:
                self._on_change(d)
            except Exception:
                pass

    # ── public API ───────────────────────────────────────────────────────────

    def get_date(self) -> date | None:
        return self._selected

    def set_date(self, d: date | None) -> None:
        self._selected = d
        if d:
            self._btn.configure(
                text=d.strftime("%d %B %Y"),
                text_color=theme.TEXT_PRIMARY,
            )
        else:
            self._btn.configure(
                text=self._placeholder,
                text_color=theme.TEXT_MUTED,
            )


# ── AutoScrollFrame ───────────────────────────────────────────────────────────

class AutoScrollFrame(tk.Frame):
    """
    Scrollable container backed by a tk.Canvas.

    The vertical scrollbar is hidden when content fits; it appears only when
    the inner height exceeds the visible area.  The inner frame fills the full
    canvas width and height when there is no overflow (so pages with weight=1
    rows expand normally).

    Mousewheel is active whenever the cursor is anywhere inside this widget,
    regardless of which child widget it is over.  The handler is bound to the
    toplevel with add="+" so other scroll areas (e.g. CTkScrollableFrame
    inside a page) keep their own bindings.
    """

    def __init__(self, master, bg: str = theme.BG_ROOT, **kwargs) -> None:
        super().__init__(master, bg=bg, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview,
        )
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self.inner = tk.Frame(self._canvas, bg=bg)
        self._win_id = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw",
        )

        self.inner.bind("<Configure>", lambda _e: self._sync())
        self._canvas.bind("<Configure>", lambda _e: self._sync())
        self.bind("<Destroy>", self._on_destroy)

        self._sb_shown = False
        self._wheel_bid: str | None = None  # funcid for targeted unbind

    # ── layout sync ──────────────────────────────────────────────────────────

    def _sync(self) -> None:
        self.update_idletasks()
        ch = self._canvas.winfo_height()
        ih = self.inner.winfo_reqheight()
        cw = self._canvas.winfo_width()
        if ch < 2 or cw < 2:
            return

        if ih > ch:
            # Overflow: show scrollbar, give inner its natural height
            self._canvas.itemconfig(self._win_id, width=cw, height=ih)
            self._canvas.configure(scrollregion=(0, 0, cw, ih))
            if not self._sb_shown:
                self._scrollbar.grid(row=0, column=1, sticky="ns")
                self._sb_shown = True
                self._bind_wheel()
        else:
            # Fits: hide scrollbar, stretch inner to fill canvas
            self._canvas.itemconfig(self._win_id, width=cw, height=ch)
            self._canvas.configure(scrollregion=(0, 0, cw, ch))
            self._canvas.yview_moveto(0)
            if self._sb_shown:
                self._scrollbar.grid_forget()
                self._sb_shown = False
                self._unbind_wheel()

    # ── mousewheel ───────────────────────────────────────────────────────────

    def _bind_wheel(self) -> None:
        if self._wheel_bid is not None:
            return
        try:
            # Bind to toplevel with add="+" so other scroll areas keep theirs
            self._wheel_bid = self.winfo_toplevel().bind(
                "<MouseWheel>", self._on_wheel, add="+",
            )
        except Exception:
            pass

    def _unbind_wheel(self) -> None:
        bid, self._wheel_bid = self._wheel_bid, None
        if bid is None:
            return
        try:
            self.winfo_toplevel().unbind("<MouseWheel>", bid)
        except Exception:
            pass

    def _on_wheel(self, event) -> None:
        if not self._sb_shown:
            return
        try:
            px, py = self.winfo_pointerxy()
            x0, y0 = self.winfo_rootx(), self.winfo_rooty()
            if x0 <= px <= x0 + self.winfo_width() and y0 <= py <= y0 + self.winfo_height():
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_destroy(self, _e=None) -> None:
        self._unbind_wheel()
