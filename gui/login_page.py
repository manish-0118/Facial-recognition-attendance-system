from __future__ import annotations

import customtkinter as ctk

from core.database import verify_admin, create_superadmin
from core.errors import DatabaseUnavailableError, DatabaseOperationError, LOGIN_DB_ERROR
from gui import theme
from gui.widgets import make_eye_image as _make_eye_image

_SUBTITLE = "Nihareeka College of Management and Information Technology"


class LoginPage(ctk.CTkFrame):
    def __init__(self, master, on_login_success) -> None:
        super().__init__(master, fg_color=theme.BG_ROOT)
        self.app = master
        self.on_login_success = on_login_success

        # ── centering wrapper ──────────────────────────────────────────────
        wrapper = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=12, width=400)
        wrapper.pack(expand=True)
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_rowconfigure(0, weight=1)

        # ── title ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            wrapper,
            text="Biometric Attendance System",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            justify="center",
        ).grid(row=0, column=0, padx=32, pady=(36, 4), sticky="ew")

        ctk.CTkLabel(
            wrapper,
            text=_SUBTITLE,
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
            justify="center",
            wraplength=360,
        ).grid(row=1, column=0, padx=32, pady=(0, 28), sticky="ew")

        # ── username ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            wrapper,
            text="Username",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=2, column=0, padx=32, pady=(0, 6), sticky="w")

        self.username_entry = ctk.CTkEntry(
            wrapper,
            height=42,
            placeholder_text="Enter username",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_SECONDARY,
            corner_radius=6,
        )
        self.username_entry.grid(row=3, column=0, padx=32, pady=(0, 18), sticky="ew")

        # ── password ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            wrapper,
            text="Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=4, column=0, padx=32, pady=(0, 6), sticky="w")

        # password entry with inline eye toggle
        pw_container = ctk.CTkFrame(
            wrapper,
            fg_color=theme.BG_SURFACE_ALT,
            corner_radius=6,
        )
        pw_container.grid_columnconfigure(0, weight=1)
        pw_container.grid(row=5, column=0, padx=32, pady=(0, 22), sticky="ew")

        self.password_entry = ctk.CTkEntry(
            pw_container,
            height=42,
            placeholder_text="Enter password",
            show="*",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_SECONDARY,
            corner_radius=0,
        )
        self.password_entry.grid(row=0, column=0, sticky="ew")

        _eye_pil       = _make_eye_image(18, theme.TEXT_MUTED, slashed=False)
        _eye_slash_pil = _make_eye_image(18, theme.TEXT_MUTED, slashed=True)
        if _eye_pil is not None:
            self._icon_eye = ctk.CTkImage(
                light_image=_eye_pil, dark_image=_eye_pil, size=(18, 18),
            )
            self._icon_eye_slash = ctk.CTkImage(
                light_image=_eye_slash_pil, dark_image=_eye_slash_pil, size=(18, 18),
            )
            _btn_kw: dict = {"text": "", "image": self._icon_eye_slash}
        else:
            self._icon_eye = self._icon_eye_slash = None
            _btn_kw = {"text": "👁"}

        self._eye_btn = ctk.CTkButton(
            pw_container,
            width=34,
            height=34,
            fg_color="transparent",
            hover_color=theme.INPUT_HIGHLIGHT,
            text_color=theme.TEXT_MUTED,
            corner_radius=4,
            command=self._toggle_password,
            **_btn_kw,
        )
        self._eye_btn.grid(row=0, column=1, padx=(0, 4))

        # ── login button ──────────────────────────────────────────────────
        ctk.CTkButton(
            wrapper,
            text="Login",
            command=self.handle_login,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=44,
            corner_radius=6,
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=6, column=0, padx=32, pady=(0, 14), sticky="ew")

        # ── error / status label ──────────────────────────────────────────
        self._error_var = ctk.StringVar(value="")
        self._error_label = ctk.CTkLabel(
            wrapper,
            textvariable=self._error_var,
            font=ctk.CTkFont(size=13),
            text_color=theme.DANGER,
            justify="center",
            wraplength=360,
        )
        self._error_label.grid(row=7, column=0, padx=32, pady=(0, 32), sticky="ew")

        # ── key bindings ──────────────────────────────────────────────────
        self.username_entry.bind("<Return>", lambda _e: self._on_username_return())
        self.password_entry.bind("<Return>", lambda _e: self._on_password_return())

    def _toggle_password(self) -> None:
        if self.password_entry.cget("show") == "":
            self.password_entry.configure(show="*")
            if self._icon_eye_slash is not None:
                self._eye_btn.configure(image=self._icon_eye_slash, text="")
            else:
                self._eye_btn.configure(text="👁")
        else:
            self.password_entry.configure(show="")
            if self._icon_eye is not None:
                self._eye_btn.configure(image=self._icon_eye, text="")
            else:
                self._eye_btn.configure(text="🙈")

    # ── public API expected by app.py ─────────────────────────────────────

    def reset_for_show(self, status_message: str = "") -> None:
        self._error_var.set("")
        # Clear both fields and restore placeholders.
        # CTkEntry.delete() skips _activate_placeholder when _is_focused=True (its initial state),
        # so call _activate_placeholder explicitly to guarantee placeholders re-appear.
        for entry in (self.username_entry, self.password_entry):
            try:
                entry.delete(0, "end")
            except Exception:
                pass
            try:
                entry._activate_placeholder()
            except Exception:
                pass

        # Ensure password is masked and eye icon reset
        try:
            self.password_entry.configure(show="*")
        except Exception:
            pass
        try:
            if self._icon_eye_slash is not None:
                self._eye_btn.configure(image=self._icon_eye_slash, text="")
            else:
                self._eye_btn.configure(text="👁")
        except Exception:
            pass

        self.after(50, self._focus_username_entry)

    @staticmethod
    def _focus_entry(ctk_entry) -> None:
        inner = getattr(ctk_entry, '_entry', None) or getattr(ctk_entry, 'entry', None)
        if inner is not None:
            inner.focus_force()
        else:
            ctk_entry.focus_force()

    def _focus_username_entry(self) -> None:
        self._focus_entry(self.username_entry)

    def focus_username(self) -> None:
        self._focus_username_entry()

    # ── key routing ───────────────────────────────────────────────────────

    def _on_username_return(self) -> None:
        if not self.password_entry.get():
            self._focus_entry(self.password_entry)
        else:
            self.handle_login()

    def _on_password_return(self) -> None:
        if not self.username_entry.get().strip():
            self._focus_entry(self.username_entry)
        else:
            self.handle_login()

    # ── login logic ───────────────────────────────────────────────────────

    def handle_login(self) -> None:
        self._error_var.set("")
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            self._error_var.set("Please enter both username and password.")
            return

        try:
            role = verify_admin(username, password)
        except DatabaseUnavailableError:
            self._error_var.set(LOGIN_DB_ERROR)
            return
        if role is None:
            self._error_var.set("Invalid username or password.")
            self.password_entry.delete(0, "end")
            self._focus_entry(self.password_entry)
            return

        self.on_login_success(username, role)


def _make_pw_row(parent, placeholder: str):
    """Return (container_frame, CTkEntry, eye_button) with an inline eye-toggle."""
    container = ctk.CTkFrame(parent, fg_color=theme.BG_SURFACE_ALT, corner_radius=6)
    container.grid_columnconfigure(0, weight=1)

    entry = ctk.CTkEntry(
        container,
        height=42,
        placeholder_text=placeholder,
        show="*",
        fg_color=theme.BG_SURFACE_ALT,
        border_width=0,
        text_color=theme.TEXT_PRIMARY,
        placeholder_text_color=theme.TEXT_SECONDARY,
        corner_radius=0,
    )
    entry.grid(row=0, column=0, sticky="ew")

    eye_pil       = _make_eye_image(18, theme.TEXT_MUTED, slashed=False)
    eye_slash_pil = _make_eye_image(18, theme.TEXT_MUTED, slashed=True)
    if eye_pil is not None:
        icon_open   = ctk.CTkImage(light_image=eye_pil,       dark_image=eye_pil,       size=(18, 18))
        icon_closed = ctk.CTkImage(light_image=eye_slash_pil, dark_image=eye_slash_pil, size=(18, 18))
        btn_kw: dict = {"text": "", "image": icon_closed}
    else:
        icon_open = icon_closed = None
        btn_kw = {"text": "👁"}

    def _toggle():
        if entry.cget("show") == "":
            entry.configure(show="*")
            btn.configure(**({"image": icon_closed, "text": ""} if icon_closed else {"text": "👁"}))
        else:
            entry.configure(show="")
            btn.configure(**({"image": icon_open, "text": ""} if icon_open else {"text": "🙈"}))

    btn = ctk.CTkButton(
        container,
        width=34, height=34,
        fg_color="transparent",
        hover_color=theme.INPUT_HIGHLIGHT,
        text_color=theme.TEXT_MUTED,
        corner_radius=4,
        command=_toggle,
        **btn_kw,
    )
    btn.grid(row=0, column=1, padx=(0, 4))

    return container, entry, btn


class SetupPage(ctk.CTkFrame):
    """First-run superadmin account setup — shown only when no superadmin exists."""

    def __init__(self, master, on_setup_complete) -> None:
        super().__init__(master, fg_color=theme.BG_ROOT)
        self.on_setup_complete = on_setup_complete

        wrapper = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=12, width=400)
        wrapper.pack(expand=True)
        wrapper.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            wrapper,
            text="Biometric Attendance System",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            justify="center",
        ).grid(row=0, column=0, padx=32, pady=(36, 4), sticky="ew")

        ctk.CTkLabel(
            wrapper,
            text=_SUBTITLE,
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
            justify="center",
            wraplength=360,
        ).grid(row=1, column=0, padx=32, pady=(0, 28), sticky="ew")

        # username
        ctk.CTkLabel(
            wrapper, text="Username",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY, anchor="w",
        ).grid(row=2, column=0, padx=32, pady=(0, 6), sticky="w")

        self._username = ctk.CTkEntry(
            wrapper, height=42,
            placeholder_text="Choose a username",
            fg_color=theme.BG_SURFACE_ALT, border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_SECONDARY,
            corner_radius=6,
        )
        self._username.grid(row=3, column=0, padx=32, pady=(0, 18), sticky="ew")

        # password
        ctk.CTkLabel(
            wrapper, text="Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY, anchor="w",
        ).grid(row=4, column=0, padx=32, pady=(0, 6), sticky="w")

        pw_container, self._password, _ = _make_pw_row(wrapper, "Choose a password")
        pw_container.grid(row=5, column=0, padx=32, pady=(0, 18), sticky="ew")

        # confirm password
        ctk.CTkLabel(
            wrapper, text="Confirm Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY, anchor="w",
        ).grid(row=6, column=0, padx=32, pady=(0, 6), sticky="w")

        cpw_container, self._confirm, _ = _make_pw_row(wrapper, "Re-enter password")
        cpw_container.grid(row=7, column=0, padx=32, pady=(0, 22), sticky="ew")

        # submit button
        ctk.CTkButton(
            wrapper,
            text="Create Superadmin Account",
            command=self._handle_submit,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=44,
            corner_radius=6,
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=8, column=0, padx=32, pady=(0, 14), sticky="ew")

        self._error_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            wrapper,
            textvariable=self._error_var,
            font=ctk.CTkFont(size=13),
            text_color=theme.DANGER,
            justify="center",
            wraplength=360,
        ).grid(row=9, column=0, padx=32, pady=(0, 32), sticky="ew")

        # key bindings
        self._username.bind("<Return>", lambda _e: self._focus_entry(self._password))
        self._password.bind("<Return>", lambda _e: self._focus_entry(self._confirm))
        self._confirm.bind("<Return>", lambda _e: self._handle_submit())

    @staticmethod
    def _focus_entry(ctk_entry) -> None:
        inner = getattr(ctk_entry, "_entry", None) or getattr(ctk_entry, "entry", None)
        (inner or ctk_entry).focus_force()

    def focus_username(self) -> None:
        self.after(50, lambda: self._focus_entry(self._username))

    def _handle_submit(self) -> None:
        self._error_var.set("")
        username = self._username.get().strip()
        password = self._password.get()
        confirm  = self._confirm.get()

        if not username:
            self._error_var.set("Username cannot be empty.")
            return
        if len(username) < 3:
            self._error_var.set("Username must be at least 3 characters.")
            return
        if not password:
            self._error_var.set("Password cannot be empty.")
            return
        if len(password) < 6:
            self._error_var.set("Password must be at least 6 characters.")
            return
        if password != confirm:
            self._error_var.set("Passwords do not match.")
            self._confirm.delete(0, "end")
            self._focus_entry(self._confirm)
            return

        try:
            create_superadmin(username, password)
        except (DatabaseUnavailableError, DatabaseOperationError) as exc:
            self._error_var.set(getattr(exc, "user_message", str(exc)))
            return

        self.on_setup_complete(username)
