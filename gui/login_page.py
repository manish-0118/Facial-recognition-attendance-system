from __future__ import annotations

import customtkinter as ctk

from core.database import verify_admin

_CARD_WIDTH = 440
_SUBTITLE = "Nihareeka College of Management and Information Technology"


class LoginPage(ctk.CTkFrame):
    def __init__(self, master, on_login_success) -> None:
        super().__init__(master, fg_color="#0D0D0D")
        self.app = master
        self.on_login_success = on_login_success

        self.app.minsize(500, 400)

        # ── centering wrapper ──────────────────────────────────────────────
        wrapper = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=12, width=400)
        wrapper.pack(expand=True)
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_rowconfigure(0, weight=1)

        # ── title ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            wrapper,
            text="Biometric Attendance System",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="white",
            justify="center",
        ).grid(row=0, column=0, padx=32, pady=(36, 4), sticky="ew")

        ctk.CTkLabel(
            wrapper,
            text=_SUBTITLE,
            font=ctk.CTkFont(size=12),
            text_color="#888888",
            justify="center",
            wraplength=360,
        ).grid(row=1, column=0, padx=32, pady=(0, 28), sticky="ew")

        # ── username ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            wrapper,
            text="Username",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#CCCCCC",
            anchor="w",
        ).grid(row=2, column=0, padx=32, pady=(0, 6), sticky="w")

        self.username_entry = ctk.CTkEntry(
            wrapper,
            height=42,
            placeholder_text="Enter username",
            corner_radius=6,
            fg_color="#252525",
            border_color="#333333",
            border_width=1,
            text_color="white",
        )
        self.username_entry.grid(row=3, column=0, padx=32, pady=(0, 18), sticky="ew")

        # ── password ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            wrapper,
            text="Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#CCCCCC",
            anchor="w",
        ).grid(row=4, column=0, padx=32, pady=(0, 6), sticky="w")

        # password entry with show/hide toggle
        pw_container = ctk.CTkFrame(wrapper, fg_color="#1A1A1A", corner_radius=0)
        pw_container.grid_columnconfigure(0, weight=1)
        pw_container.grid(row=5, column=0, padx=32, pady=(0, 22), sticky="ew")

        self.password_entry = ctk.CTkEntry(
            pw_container,
            height=42,
            placeholder_text="Enter password",
            show="*",
            corner_radius=6,
            fg_color="#252525",
            border_color="#333333",
            border_width=1,
            text_color="white",
        )
        self.password_entry.grid(row=0, column=0, sticky="ew")

        self._show_password_btn = ctk.CTkButton(
            pw_container,
            text="Show",
            width=70,
            height=30,
            fg_color="#2A2A2A",
            hover_color="#333333",
            command=self._toggle_password,
        )
        self._show_password_btn.grid(row=0, column=1, padx=(8, 0), sticky="e")

        # ── login button ──────────────────────────────────────────────────
        ctk.CTkButton(
            wrapper,
            text="Login",
            command=self.handle_login,
            fg_color="#1f538d",
            hover_color="#1a4a7a",
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
            text_color="#FF5252",
            justify="center",
            wraplength=360,
        )
        self._error_label.grid(row=7, column=0, padx=32, pady=(0, 32), sticky="ew")

        # ── key bindings ──────────────────────────────────────────────────
        self.username_entry.bind("<Return>", lambda _e: self.handle_login())
        self.password_entry.bind("<Return>", lambda _e: self.handle_login())

    def _toggle_password(self) -> None:
        current = self.password_entry.cget("show")
        if current == "":
            self.password_entry.configure(show="*")
            self._show_password_btn.configure(text="Show")
        else:
            self.password_entry.configure(show="")
            self._show_password_btn.configure(text="Hide")

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

        # Ensure password is masked and toggle shows correct label
        try:
            self.password_entry.configure(show="*")
        except Exception:
            pass
        try:
            self._show_password_btn.configure(text="Show")
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
