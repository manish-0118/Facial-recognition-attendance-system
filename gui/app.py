from __future__ import annotations

import os
import time
import tkinter as tk
from typing import Callable

import customtkinter as ctk # pyright: ignore[reportMissingImports]

from core.database import init_db, has_superadmin, log_action
from core.errors import DatabaseUnavailableError
from core.logger import get_logger
from core.mariadb_manager import start_server, stop_server
from core.scheduler import AttendanceScheduler

_log = get_logger(__name__)

from .admin_page import AdminPage
from .archive_page import ArchivePage
from .attendance_page import AttendancePage
from .audit_page import AuditPage, prefetch_audit_data, clear_audit_prefetch
from .export_page import ExportPage
from .login_page import LoginPage, SetupPage
from .dashboard_page import DashboardPage
from .register_page import RegisterPage
from .class_hub_page import ClassHubPage
from gui.settings_page import SettingsPage
from gui import theme
from gui.widgets import AutoScrollFrame, center_dialog


WINDOW_TITLE  = "Biometric Attendance System"
WINDOW_MINSIZE = (1000, 650)

# Segoe MDL2 Assets codepoints — monochrome flat icons built into Windows 10/11
_NAV_ICONS: dict[str, str] = {
    "Dashboard":        "",   # Home
    "Classes":          "",   # ViewAll / grid
    "Take Attendance":  "",   # Camera
    "Export":           "",   # Share / Export
    "Archive":          "",   # Storage
    "Register Student": "",   # PersonAdd
    "Admin Management": "",   # Contact / Admin
    "Audit Log":        "",   # Zoom / Audit
    "Settings":         "",   # Settings gear
}
_LOGOUT_ICON = ""             # SignOut


class _SidebarNavBtn(tk.Frame):
    """
    Sidebar nav item: Segoe MDL2 Assets icon + Segoe UI text.

    Uses plain tk.Frame / tk.Label (no CTk canvas) so that background colour
    changes are applied atomically to every child in one call, eliminating the
    one-frame transparency flicker that CTkFrame's canvas causes.
    """

    def __init__(self, master, icon: str, text: str, command, **kwargs) -> None:
        super().__init__(master, bg=theme.SIDEBAR_BG, cursor="hand2", **kwargs)
        self._command = command
        self._active  = False

        self._icon_lbl = tk.Label(
            self, text=icon,
            font=("Segoe MDL2 Assets", 15),
            bg=theme.SIDEBAR_BG,
            fg=theme.TEXT_PRIMARY,
            width=2, anchor="center",
        )
        self._icon_lbl.pack(side="left", padx=(12, 0), pady=9)

        self._text_lbl = tk.Label(
            self, text=text,
            font=("Segoe UI", 14),
            bg=theme.SIDEBAR_BG,
            fg=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self._text_lbl.pack(side="left", padx=(8, 10), pady=9, fill="x", expand=True)

        for w in (self, self._icon_lbl, self._text_lbl):
            w.bind("<Button-1>", lambda _e: self._command())
            w.bind("<Enter>",    self._on_enter)
            w.bind("<Leave>",    self._on_leave)

    # ── background helper (all three widgets updated in one shot) ─────────

    def _set_bg(self, color: str) -> None:
        self.configure(bg=color)
        self._icon_lbl.configure(bg=color)
        self._text_lbl.configure(bg=color)

    # ── hover ─────────────────────────────────────────────────────────────

    def _is_mouse_over(self) -> bool:
        """Return True if the pointer is currently over this button or any child."""
        try:
            px, py = self.winfo_pointerxy()
            return self.winfo_containing(px, py) in (self, self._icon_lbl, self._text_lbl)
        except Exception:
            return False

    def _on_enter(self, _e=None) -> None:
        if not self._active:
            self._set_bg(theme.SIDEBAR_HOVER)

    def _on_leave(self, _e=None) -> None:
        if self._active:
            return
        # winfo_containing avoids coordinate-space mismatch on high-DPI displays
        if not self._is_mouse_over():
            self._set_bg(theme.SIDEBAR_BG)

    # ── active state ──────────────────────────────────────────────────────

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._set_bg(theme.SIDEBAR_ACTIVE)
            self._icon_lbl.configure(fg=theme.TEXT_PRIMARY)
            self._text_lbl.configure(fg=theme.TEXT_PRIMARY, font=("Segoe UI", 14, "bold"))
        else:
            self._icon_lbl.configure(fg=theme.TEXT_PRIMARY)
            self._text_lbl.configure(fg=theme.TEXT_PRIMARY, font=("Segoe UI", 14))
            # If the mouse is still physically over this button, restore hover
            # rather than snapping to default (avoids the disappearing-hover glitch)
            self._set_bg(theme.SIDEBAR_HOVER if self._is_mouse_over() else theme.SIDEBAR_BG)
SIDEBAR_WIDTH = 220
SESSION_TIMEOUT_SECONDS = 10 * 60
TIMEOUT_CHECK_MS = 30_000

BASE_NAV_ITEMS = [
    "Dashboard",
    "Classes",
    "Take Attendance",
    "Export",
    "Archive",
    "Register Student",
    "Settings",
]
SUPERADMIN_ITEMS = ["Admin Management", "Audit Log"]


class _NotificationProxy:
    def __init__(self, app: "App") -> None:
        self._app = app

    def show(self, message: str, kind: str = "success") -> None:
        self._app.show_notification(message, kind)


class App(ctk.CTk):
    # Registry of all navigable pages — used by show_page and _preload_pages
    _PAGE_CLASSES: dict[str, type] = {
        "Dashboard":        DashboardPage,
        "Classes":          ClassHubPage,
        "Register Student": RegisterPage,
        "Take Attendance":  AttendancePage,
        "Export":           ExportPage,
        "Archive":          ArchivePage,
        "Settings":         SettingsPage,
        "Admin Management": AdminPage,
        "Audit Log":        AuditPage,
    }

    def __init__(self) -> None:
        ctk.set_appearance_mode(theme.CTK_MODE)
        ctk.set_default_color_theme("dark-blue")

        if not start_server():
            import tkinter.messagebox as _mb
            _mb.showerror(
                "Database Error",
                "Could not start the database server.\n\nPlease reinstall the application.",
            )
            raise SystemExit(1)

        try:
            init_db()
        except DatabaseUnavailableError as _exc:
            import tkinter.messagebox as _mb
            _mb.showerror(
                "Database Error",
                f"{_exc.user_message}\n\nThe application cannot start.",
            )
            raise SystemExit(1) from _exc
        super().__init__()

        self.withdraw()            # hide before CTk paints anything — no initial-size flash
        self.title(WINDOW_TITLE)
        self.minsize(*WINDOW_MINSIZE)
        self._apply_icon()

        self.logged_in_username: str | None = None
        self.logged_in_role: str | None = None
        self._last_activity_at = time.monotonic()
        self._timeout_after_id: str | None = None
        self._toast: ctk.CTkFrame | None = None
        self._current_page: ctk.CTkFrame | None = None
        self._page_cache: dict[str, ctk.CTkFrame] = {}  # kept alive for the session
        self._resize_id:   str | None = None
        self._last_wh:     tuple[int, int] = (0, 0)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.login_page = None
        self.setup_page = None
        self.sidebar = None
        self.content_frame = None
        # start background scheduler to finalize attendance
        try:
            self.scheduler = AttendanceScheduler()
            self.scheduler.start()
        except Exception:
            self.scheduler = None

        if has_superadmin():
            self.login_page = LoginPage(self, self.on_login_success)
            self.show_login()
        else:
            self._show_setup()
        self._bind_activity_events()
        self._schedule_timeout_check()
        self.bind('<Configure>', self._on_configure)
        self.after(0, self._present_maximized)
        # ensure scheduler stops on window close
        try:
            self.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

    def _present_maximized(self) -> None:
        """Reveal the window maximized on the first event-loop tick.

        withdraw() in __init__ prevents any flash at the initial small size.
        Deferring state('zoomed') past CTk's own init avoids it being overridden.
        focus_force() gives the OS window focus so the entry focus_set() sticks.
        """
        self.state('zoomed')
        self.deiconify()
        self.update()   # drain event queue — window fully drawn before focus
        if self.setup_page:
            self.setup_page.focus_username()
        elif self.login_page:
            self.login_page.focus_username()

    def _on_close(self) -> None:
        try:
            if getattr(self, "scheduler", None):
                try:
                    self.scheduler.stop()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        stop_server()

    def _apply_icon(self) -> None:
        icon_path = os.path.abspath(os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets", "favicon.ico",
        ))
        if os.path.isfile(icon_path):
            # Defer so CTk's own post-init icon setting doesn't overwrite ours
            self.after(0, lambda: self.iconbitmap(icon_path))

    def _set_main_grid(self):
        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)


    def _set_login_grid(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

    def on_login_success(self, username: str, role: str):
        self.logged_in_username = username
        self.logged_in_role = role
        self._last_activity_at = time.monotonic()

        prefetch_audit_data(role)       # start audit DB fetch in parallel with page building
        self.login_page.grid_forget()
        self._build_sidebar()
        self._build_content_frame()
        self._set_main_grid()
        self._build_all_pages()         # every page fully built before user sees anything
        self.show_page("Dashboard")

    def _build_sidebar(self):
        if self.sidebar:
            self.sidebar.destroy()  # Ensure no duplicate sidebars
        self.sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, fg_color=theme.SIDEBAR_BG)
        self.sidebar.grid(row=0, column=0, sticky="ns")  # Ensure it occupies the correct grid
        self.sidebar.grid_propagate(False)

        # App name / small icon at top
        ctk.CTkLabel(
            self.sidebar,
            text="BAS",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(12, 2))

        ctk.CTkLabel(
            self.sidebar,
            text="Attendance System",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 8))

        # container for nav buttons
        self._nav_buttons: dict[str, _SidebarNavBtn] = {}

        nav_items = BASE_NAV_ITEMS[:-1] + (SUPERADMIN_ITEMS if self.logged_in_role == "superadmin" else []) + ["Settings"]

        for item in nav_items:
            icon = _NAV_ICONS.get(item, "")
            btn = _SidebarNavBtn(
                self.sidebar,
                icon=icon,
                text=item,
                command=lambda i=item: self.show_page(i),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_buttons[item] = btn

        # separator above logout
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=theme.BORDER)
        sep.pack(side="bottom", fill="x", padx=20, pady=(8, 4))

        # logout at bottom
        logout_frame = ctk.CTkFrame(self.sidebar, fg_color=self.sidebar.cget("fg_color"))
        logout_frame.pack(side="bottom", fill="x", padx=20, pady=4)

        logout_btn = ctk.CTkButton(
            logout_frame,
            text="Sign Out",
            command=self._show_logout_confirm,
            fg_color=theme.BTN_DANGER,
            hover_color=theme.BTN_DANGER_HVR,
            text_color="#FFFFFF",
            corner_radius=6,
            height=36,
            border_width=0,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        )
        logout_btn.pack(fill="x", pady=4)

        # Ensure active highlight reflects current page
        try:
            # If a page is already selected, highlight it
            if hasattr(self, "_current_page") and self._current_page:
                # no easy name stored for current page; default to Dashboard
                self._update_active_nav("Dashboard")
        except Exception:
            pass

    def _update_active_nav(self, active_name: str) -> None:
        for name, btn in getattr(self, "_nav_buttons", {}).items():
            btn.set_active(name == active_name)

    def _build_content_frame(self):
        if self.content_frame:
            self.content_frame.destroy()
        self.content_frame = ctk.CTkFrame(self, fg_color=theme.BG_ROOT)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

    def _show_logout_confirm(self) -> None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Confirm Logout")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        center_dialog(dlg, 360, 160)
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(dlg, fg_color=theme.BG_SURFACE, corner_radius=0)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Are you sure you want to logout?",
            font=ctk.CTkFont(size=13),
            text_color=theme.TEXT_PRIMARY,
            wraplength=300,
            justify="center",
        ).pack(padx=24, pady=(28, 16))

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(padx=24, pady=(0, 24), fill="x")

        def _do_logout():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()
            self.logout()

        ctk.CTkButton(
            btn_frame,
            text="Yes, Logout",
            fg_color=theme.BTN_DANGER,
            hover_color=theme.BTN_DANGER_HVR,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=6,
            command=_do_logout,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color=theme.BTN_SECONDARY,
            hover_color=theme.BTN_SECONDARY_HVR,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=6,
            command=dlg.destroy,
        ).pack(side="left", expand=True, fill="x")

    # ── Page management ───────────────────────────────────────────────────────

    def _build_page(self, page_name: str, *, raise_to_top: bool) -> bool:
        """Create one page, cache it, optionally raise it. Returns True on success."""
        page_class = self._PAGE_CLASSES.get(page_name)
        if not page_class or not self.content_frame:
            return False
        try:
            wrapper = AutoScrollFrame(self.content_frame)
            # place() fills content_frame exactly and never triggers grid recalculation
            wrapper.place(relx=0, rely=0, relwidth=1, relheight=1)
            wrapper.inner.grid_rowconfigure(0, weight=1)
            wrapper.inner.grid_columnconfigure(0, weight=1)

            page = page_class(
                wrapper.inner,
                username=self.logged_in_username,
                role=self.logged_in_role,
            )
            page.grid(row=0, column=0, sticky="nsew")

            self._page_cache[page_name] = wrapper
            if raise_to_top:
                wrapper.tkraise()
                self._current_page = wrapper
                self._update_active_nav(page_name)
            else:
                # Push to bottom of z-stack, then settle layout while hidden.
                # update_idletasks() forces Canvas configure/draw events to
                # complete now so that tkraise() later is a true hard cut.
                wrapper.lower()
                self.update_idletasks()
            return True
        except Exception:
            _log.exception("Failed to build page: %s", page_name)
            return False

    def _build_all_pages(self) -> None:
        """Build every page into cache synchronously at login, hidden behind the stack top."""
        order = [
            "Dashboard", "Classes", "Register Student", "Export",
            "Archive", "Take Attendance", "Settings",
        ]
        if self.logged_in_role == "superadmin":
            order += ["Admin Management", "Audit Log"]
        for page_name in order:
            if page_name not in self._page_cache:
                self._build_page(page_name, raise_to_top=False)

    def show_page(self, page_name: str) -> None:
        if page_name not in self._PAGE_CLASSES:
            return

        # Cache hit — raise to top and force a synchronous repaint so the
        # canvas content paints before control returns (eliminates the brief
        # background-flash / "animation" on pages with many canvas widgets).
        if page_name in self._page_cache:
            wrapper = self._page_cache[page_name]
            try:
                wrapper.tkraise()
                self.update_idletasks()
                self._current_page = wrapper
                self._update_active_nav(page_name)
                return
            except Exception:
                _log.exception("Failed to raise cached page: %s", page_name)
                del self._page_cache[page_name]

        # First visit — build, cache, and show
        self._build_page(page_name, raise_to_top=True)

    def logout(self):
        self.logged_in_username = None
        self.logged_in_role = None
        clear_audit_prefetch()
        for wrapper in list(self._page_cache.values()):
            try:
                wrapper.destroy()
            except Exception:
                pass
        self._page_cache.clear()
        self._current_page = None
        if self.sidebar:
            self.sidebar.destroy()
            self.sidebar = None
        if self.content_frame:
            self.content_frame.destroy()
            self.content_frame = None
        if self.login_page:
            self.login_page.destroy()
            self.login_page = None
        self._set_login_grid()
        self.login_page = LoginPage(self, self.on_login_success)
        self.login_page.grid(row=0, column=0, columnspan=2, sticky="nsew")

    def show_login(self):
        # Prepare login page state and show it
        try:
            self.login_page.reset_for_show()
        except Exception:
            pass
        self.login_page.grid(row=0, column=0, columnspan=2, sticky="nsew")

    def _show_setup(self) -> None:
        self._set_login_grid()
        self.setup_page = SetupPage(self, self._on_setup_complete)
        self.setup_page.grid(row=0, column=0, columnspan=2, sticky="nsew")

    def _on_setup_complete(self, username: str) -> None:
        if self.setup_page:
            self.setup_page.destroy()
            self.setup_page = None
        self._set_login_grid()
        self.login_page = LoginPage(self, self.on_login_success)
        self.login_page.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.login_page.focus_username()

    # ── Resize debounce ───────────────────────────────────────────────────────

    def _on_configure(self, event) -> None:
        if event.widget is not self:
            return
        w, h = event.width, event.height
        if (w, h) == self._last_wh:
            return                              # position-only move, ignore
        self._last_wh = (w, h)
        if self._resize_id is None:             # first event of this gesture
            self._hide_background_pages()
        else:
            self.after_cancel(self._resize_id)
        self._resize_id = self.after(150, self._on_resize_done)

    def _hide_background_pages(self) -> None:
        for wrapper in self._page_cache.values():
            if wrapper is not self._current_page:
                try:
                    wrapper.place_forget()
                except Exception:
                    pass

    def _on_resize_done(self) -> None:
        self._resize_id = None
        for wrapper in self._page_cache.values():
            if wrapper is not self._current_page:
                try:
                    wrapper.place(relx=0, rely=0, relwidth=1, relheight=1)
                    wrapper.lower()
                except Exception:
                    pass
        self.update_idletasks()

    # ─────────────────────────────────────────────────────────────────────────

    def _bind_activity_events(self) -> None:
        self.bind_all("<Button>", self._on_activity)
        self.bind_all("<KeyPress>", self._on_activity)

    def _on_activity(self, _event=None) -> None:
        self._last_activity_at = time.monotonic()

    def _schedule_timeout_check(self) -> None:
        if self._timeout_after_id:
            self.after_cancel(self._timeout_after_id)
        self._timeout_after_id = self.after(TIMEOUT_CHECK_MS, self._check_timeout)

    def _check_timeout(self) -> None:
        if time.monotonic() - self._last_activity_at > SESSION_TIMEOUT_SECONDS:
            self.logout()
        else:
            self._schedule_timeout_check()


    def show_notification(self, message: str, kind: str = "success") -> None:
        if self._toast:
            try:
                self._toast.destroy()
            except Exception:
                pass
        color = theme.SUCCESS_BG if kind == "success" else theme.DANGER_BG
        toast = ctk.CTkFrame(self, fg_color=color, corner_radius=0)
        toast.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
        ctk.CTkLabel(toast, text=message, text_color="white", padx=12, pady=8).pack()
        self._toast = toast
        self.after(3000, self._slide_out_toast)

    def _slide_out_toast(self) -> None:
        if self._toast:
            try:
                self._toast.destroy()
            except Exception:
                pass
            self._toast = None


if __name__ == "__main__":
    app = App()
    app.mainloop()