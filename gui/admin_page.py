from __future__ import annotations

import customtkinter as ctk
from core.database import add_admin, delete_admin, get_all_admins, log_action
from gui import theme
from gui.widgets import ThemedDropdown


class AdminPage(ctk.CTkFrame):
    def __init__(self, master, username: str = "", role: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role
        self._row_widgets: list[ctk.CTkBaseClass] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(header, text="Admin Management", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left", padx=20, pady=15)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)           # left fluid margin
        body.grid_columnconfigure(1, weight=0, minsize=500)  # centered form column
        body.grid_columnconfigure(2, weight=1)           # right fluid margin
        body.grid_rowconfigure(1, weight=1)              # table row expands

        self._build_add_form(body)
        self._build_table(body)

        self.refresh()

    def _build_add_form(self, parent) -> None:
        form = ctk.CTkFrame(parent, fg_color=theme.BG_SURFACE, corner_radius=16)
        form.grid(row=0, column=1, sticky="new", pady=24)
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            form,
            text="Username",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=22, pady=(14, 4))
        self.username_entry = ctk.CTkEntry(
            form,
            height=36,
            placeholder_text="Enter username",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.username_entry.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))

        ctk.CTkLabel(
            form,
            text="Password",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=2, column=0, sticky="w", padx=22, pady=(0, 4))
        self.password_entry = ctk.CTkEntry(
            form,
            height=36,
            placeholder_text="Enter password",
            show="*",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.password_entry.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 10))

        ctk.CTkLabel(
            form,
            text="Confirm Password",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=4, column=0, sticky="w", padx=22, pady=(0, 4))
        self.confirm_password_entry = ctk.CTkEntry(
            form,
            height=36,
            placeholder_text="Confirm password",
            show="*",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.confirm_password_entry.grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 10))

        ctk.CTkLabel(
            form,
            text="Role",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=6, column=0, sticky="w", padx=22, pady=(0, 4))
        self.role_option = ThemedDropdown(form, values=["admin", "superadmin"], height=36)
        self.role_option.grid(row=7, column=0, sticky="ew", padx=22, pady=(0, 10))

        self.add_admin_button = ctk.CTkButton(
            form,
            text="Add Admin",
            command=self._handle_add_admin,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=36,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.add_admin_button.grid(row=8, column=0, sticky="ew", padx=22, pady=(0, 14))

    def _build_table(self, parent) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.BG_SURFACE, corner_radius=10)
        card.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=20, pady=(0, 20))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        self.count_label = ctk.CTkLabel(
            card,
            text="0 admins",
            font=ctk.CTkFont(size=13),
            text_color=theme.TEXT_SECONDARY,
        )
        self.count_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 8))

        self.table_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.table_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        headers = ["Username", "Role", "Created By", "Created Date", "Delete"]
        weights = [2, 1, 2, 2, 1]
        for col, weight in enumerate(weights):
            self.table_scroll.grid_columnconfigure(col, weight=weight)

        for col, header in enumerate(headers):
            ctk.CTkLabel(
                self.table_scroll,
                text=header,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=(10, 6), pady=(0, 6))

        self.empty_label = ctk.CTkLabel(
            self.table_scroll,
            text="No admin accounts found.",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=13),
        )

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, "show_notification"):
            try:
                self.master_frame.show_notification(message, kind)
                return
            except Exception:
                pass
        if hasattr(self.master_frame, "notifications") and hasattr(self.master_frame.notifications, "show"):
            try:
                self.master_frame.notifications.show(message, kind=kind)
            except Exception:
                pass

    def _is_superadmin(self) -> bool:
        return self.role == "superadmin"

    def _clear_rows(self) -> None:
        for widget in self._row_widgets:
            widget.destroy()
        self._row_widgets.clear()
        self.empty_label.grid_forget()

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.username_entry.configure(state=state)
        self.password_entry.configure(state=state)
        self.confirm_password_entry.configure(state=state)
        self.role_option.configure(state=state)
        self.add_admin_button.configure(state=state)

    def _confirm_delete(self, username: str) -> bool:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Delete Admin")
        dialog.geometry("430x220")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        result = {"ok": False}

        def confirm() -> None:
            result["ok"] = True
            dialog.destroy()

        card = ctk.CTkFrame(dialog, fg_color=theme.BG_SURFACE, corner_radius=0)
        card.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            card,
            text=f"Delete admin account '{username}'?",
            justify="left",
            wraplength=380,
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=18, pady=(0, 16))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(actions, text="Cancel", command=dialog.destroy, corner_radius=6).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Delete",
            command=confirm,
            fg_color=theme.BTN_DANGER,
            hover_color=theme.BTN_DANGER_HVR,
            corner_radius=6,
        ).pack(side="right")

        self.wait_window(dialog)
        return bool(result["ok"])

    def _handle_add_admin(self) -> None:
        if not self._is_superadmin():
            self._notify("Only superadmin can access admin management.", "error")
            return

        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        confirm_password = self.confirm_password_entry.get()
        role = self.role_option.get()

        if not username or not password or not confirm_password or not role:
            self._notify("All fields are required.", "error")
            return

        if password != confirm_password:
            self._notify("Password and confirm password do not match.", "error")
            return

        try:
            existing_admins = get_all_admins()
        except Exception as error:
            self._notify("Unable to validate admin username.", "error")
            if hasattr(self.master_frame, "show_action_error"):
                try:
                    self.master_frame.show_action_error("Admin Management", "Unable to validate admin username.", error)
                except Exception:
                    pass
            return

        existing_usernames = {str(admin.get("username", "")).strip().lower() for admin in existing_admins}
        if username.lower() in existing_usernames:
            self._notify("Username already taken.", "error")
            return

        try:
            add_admin(username, password, role, self.username or "system")
            log_action(self.username or "system", "ADD_ADMIN", f"username={username}; role={role}")
        except Exception as error:
            self._notify("Failed to create admin.", "error")
            if hasattr(self.master_frame, "show_action_error"):
                try:
                    self.master_frame.show_action_error("Admin Management", "Unable to create admin account.", error)
                except Exception:
                    pass
            return

        self.username_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        self.confirm_password_entry.delete(0, "end")
        self.role_option.set("admin")
        self.refresh()
        self._notify("Admin created successfully", "success")

    def _handle_delete_admin(self, target_username: str, target_role: str) -> None:
        if not self._is_superadmin():
            self._notify("Only superadmin can access admin management.", "error")
            return

        if target_role == "superadmin":
            self._notify("Cannot delete superadmin accounts.", "error")
            return

        if not self._confirm_delete(target_username):
            return

        try:
            delete_admin(target_username)
            log_action(self.username or "system", "DELETE_ADMIN", f"username={target_username}")
        except Exception as error:
            self._notify("Failed to delete admin.", "error")
            if hasattr(self.master_frame, "show_action_error"):
                try:
                    self.master_frame.show_action_error("Admin Management", "Unable to delete admin account.", error)
                except Exception:
                    pass
            return

        self.refresh()
        self._notify("Admin deleted successfully", "success")

    def _render_rows(self, rows: list[dict]) -> None:
        self._clear_rows()
        self.count_label.configure(text=f"{len(rows)} admins")

        if not rows:
            self.empty_label.grid(row=1, column=0, columnspan=5, sticky="w", padx=10, pady=14)
            return

        for idx, row in enumerate(rows, start=1):
            bg = "#1A1A1A" if idx % 2 else "#202020"
            username = str(row.get("username", "-"))
            role = str(row.get("role", "-"))
            values = [
                username,
                role,
                str(row.get("created_by", "-")),
                str(row.get("created_date", "-"))[:19],
            ]

            for col, value in enumerate(values):
                label = ctk.CTkLabel(
                    self.table_scroll,
                    text=value,
                    font=ctk.CTkFont(size=12),
                    text_color="white",
                    fg_color=bg,
                    anchor="w",
                    corner_radius=4,
                )
                label.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                self._row_widgets.append(label)

            can_delete = self._is_superadmin() and role != "superadmin"
            delete_button = ctk.CTkButton(
                self.table_scroll,
                text="Delete",
                command=lambda target=username, target_role=role: self._handle_delete_admin(target, target_role),
                fg_color="#C62828",
                hover_color="#A51F1F",
                width=88,
                height=30,
                corner_radius=6,
                state="normal" if can_delete else "disabled",
            )
            delete_button.grid(row=idx, column=4, sticky="e", padx=(6, 10), pady=2)
            self._row_widgets.append(delete_button)

    def refresh(self) -> None:
        try:
            rows = get_all_admins()
        except Exception as error:
            self._notify("Failed to load admins.", "error")
            if hasattr(self.master_frame, "show_action_error"):
                try:
                    self.master_frame.show_action_error("Admin Management", "Unable to load admin accounts.", error)
                except Exception:
                    pass
            return

        self._set_controls_enabled(self._is_superadmin())
        self._render_rows(rows)

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role
        self.refresh()
