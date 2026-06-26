from __future__ import annotations

import customtkinter as ctk

from core.database import verify_admin
from gui import theme
from gui.widgets import make_eye_image as _make_eye_image

_CARD_WIDTH = 440
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
            placeholder_text_color=theme.TEXT_MUTED,
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
            placeholder_text_color=theme.TEXT_MUTED,
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
        self.username_entry.bind("<Return>", lambda _e: self.handle_login())
        self.password_entry.bind("<Return>", lambda _e: self.handle_login())

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
        # Clear both fields to remove any saved/remembered credentials
        try:
            self.username_entry.delete(0, "end")
        except Exception:
            pass
        try:
            self.password_entry.delete(0, "end")
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

        self.username_entry.focus()

    def focus_username(self) -> None:
        self.username_entry.focus()

    # ── login logic ───────────────────────────────────────────────────────

    def handle_login(self) -> None:
        self._error_var.set("")
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            self._error_var.set("Please enter both username and password.")
            return

        role = verify_admin(username, password)
        if role is None:
            self._error_var.set("Invalid username or password.")
            self.password_entry.delete(0, "end")
            self.password_entry.focus()
            return

        self.on_login_success(username, role)
