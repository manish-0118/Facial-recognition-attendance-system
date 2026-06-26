from __future__ import annotations

import time
from typing import Callable

import customtkinter as ctk # pyright: ignore[reportMissingImports]

from core.database import init_db, log_action
from core.scheduler import AttendanceScheduler

from .admin_page import AdminPage
from .archive_page import ArchivePage
from .attendance_page import AttendancePage
from .audit_page import AuditPage
from .export_page import ExportPage
from .login_page import LoginPage
from .dashboard_page import DashboardPage
from .register_page import RegisterPage
from .class_hub_page import ClassHubPage
from gui.settings_page import SettingsPage
from gui import theme
from gui.widgets import AutoScrollFrame


WINDOW_TITLE = "Biometric Attendance System"
WINDOW_SIZE = "1000x650"
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
    def __init__(self) -> None:
        ctk.set_appearance_mode(theme.CTK_MODE)
        ctk.set_default_color_theme("dark-blue")

        init_db()
        super().__init__()

        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(1000, 650)

        self.logged_in_username: str | None = None
        self.logged_in_role: str | None = None
        self._last_activity_at = time.monotonic()
        self._timeout_after_id: str | None = None
        self._toast: ctk.CTkFrame | None = None
        self._current_page: ctk.CTkFrame | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.login_page = LoginPage(self, self.on_login_success)
        self.sidebar = None
        self.content_frame = None
        # start background scheduler to finalize attendance
        try:
            self.scheduler = AttendanceScheduler()
            self.scheduler.start()
        except Exception:
            self.scheduler = None

        self.show_login()
        self._bind_activity_events()
        self._schedule_timeout_check()
        # ensure scheduler stops on window close
        try:
            self.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

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
        self.login_page.grid_forget()
        self._build_sidebar()
        self._build_content_frame()
        self._set_main_grid()
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
        self._nav_buttons: dict[str, ctk.CTkButton] = {}

        nav_items = BASE_NAV_ITEMS[:-1] + (SUPERADMIN_ITEMS if self.logged_in_role == "superadmin" else []) + ["Settings"]
        emoji_map = {
            "Dashboard": "🏠",
            "Classes": "🏫",
            "Students": "👥",
            "Take Attendance": "📷",
            "Records": "📋",
            "Export": "📤",
            "Archive": "📦",
            "Register Student": "📝",
            "Admin Management": "👤",
            "Audit Log": "🔍",
            "Settings": "⚙️",
        }

        for item in nav_items:
            em = emoji_map.get(item)
            label = f"{em} {item}" if em else item
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                command=lambda i=item: self.show_page(i),
                fg_color="transparent",
                hover_color=theme.SIDEBAR_HOVER,
                text_color=theme.TEXT_PRIMARY,
                corner_radius=6,
                height=40,
                font=ctk.CTkFont(family="Segoe UI Emoji", size=15),
                anchor="w",
                compound="left",
                image=None,
            )
            btn.pack(fill="x", padx=20, pady=4)
            self._nav_buttons[item] = btn
        # separator above logout
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=theme.BORDER)
        sep.pack(side="bottom", fill="x", padx=20, pady=(8, 4))

        # logout at bottom with subtle style
        logout_frame = ctk.CTkFrame(self.sidebar, fg_color=self.sidebar.cget("fg_color"))
        logout_frame.pack(side="bottom", fill="x", padx=20, pady=4)

        logout_btn = ctk.CTkButton(
            logout_frame,
            text="Logout",
            command=self._show_logout_confirm,
            fg_color=theme.BTN_DANGER,
            hover_color=theme.BTN_DANGER_HVR,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=6,
            height=36,
            border_width=0,
            font=ctk.CTkFont(family="Segoe UI Emoji", size=15),
            compound="left",
            image=None,
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
                if name == active_name:
                    btn.configure(fg_color=theme.SIDEBAR_ACTIVE)
                else:
                    btn.configure(fg_color="transparent")

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
        dlg.geometry("360x140")
        dlg.transient(self)
        dlg.grab_set()

        # message
        ctk.CTkLabel(
            dlg,
            text="Are you sure you want to logout?",
            font=ctk.CTkFont(size=13),
            wraplength=320,
            justify="center",
        ).pack(padx=20, pady=(18, 8))

        btn_frame = ctk.CTkFrame(dlg, fg_color=dlg.cget("fg_color"))
        btn_frame.pack(padx=20, pady=(8, 18), fill="x")

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
            hover_color=theme.DANGER_HOVER,
            text_color=theme.TEXT_PRIMARY,
            command=_do_logout,
        ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color=theme.BTN_SECONDARY,
            hover_color=theme.BTN_SECONDARY_HVR,
            text_color=theme.TEXT_PRIMARY,
            command=dlg.destroy,
        ).pack(side="left", expand=True, fill="x")

    def show_page(self, page_name: str):
        if self._current_page is not None:
            try:
                self._current_page.destroy()
            except Exception:
                pass
            self._current_page = None

        page_classes = {
            "Dashboard": DashboardPage,
            "Classes": ClassHubPage,
            "Register Student": RegisterPage,
            "Take Attendance": AttendancePage,
            "Export": ExportPage,
            "Archive": ArchivePage,
            "Settings": SettingsPage,
            "Admin Management": AdminPage,
            "Audit Log": AuditPage,
        }
        page_class = page_classes.get(page_name)
        if page_class:
            try:
                wrapper = AutoScrollFrame(self.content_frame)
                wrapper.grid(row=0, column=0, sticky="nsew")
                wrapper.inner.grid_rowconfigure(0, weight=1)
                wrapper.inner.grid_columnconfigure(0, weight=1)

                page = page_class(
                    wrapper.inner,
                    username=self.logged_in_username,
                    role=self.logged_in_role,
                )
                page.grid(row=0, column=0, sticky="nsew")

                self._current_page = wrapper
                try:
                    self._update_active_nav(page_name)
                except Exception:
                    pass
            except Exception as e:
                self._current_page = ctk.CTkLabel(
                    self.content_frame, text=f"Error loading '{page_name}': {e}", text_color="red"
                )
                self._current_page.grid(row=0, column=0, sticky="nsew")
        else:
            self._current_page = ctk.CTkLabel(
                self.content_frame, text=f"Page '{page_name}' not found.", text_color="white"
            )
            self._current_page.grid(row=0, column=0, sticky="nsew")

    def logout(self):
        self.logged_in_username = None
        self.logged_in_role = None
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