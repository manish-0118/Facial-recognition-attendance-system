from __future__ import annotations

import customtkinter as ctk

from core.database import add_class, delete_class, get_all_classes, get_class_count, get_max_classes

AUTO_REFRESH_MS = 30_000


class ClassPage(ctk.CTkFrame):
    def __init__(self, master, username: str, role: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = master
        self.username = username
        self.role = role

        self._rows: list[ctk.CTkBaseClass] = []
        self._refresh_after_id: str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_add_form()
        self._build_table()

        self.refresh()
        self._schedule_auto_refresh()

    def _build_header(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        head.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            head,
            text="Classes",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, sticky="w")

        self.class_count_label = ctk.CTkLabel(
            head,
            text="0 / 0 classes",
            font=ctk.CTkFont(size=14),
            text_color="#888888",
        )
        self.class_count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkButton(
            head,
            text="Refresh",
            command=self.refresh,
            fg_color="#1E88E5",
            hover_color="#1565C0",
            width=110,
            height=34,
            corner_radius=6,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_add_form(self) -> None:
        form_card = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=10)
        form_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 12))
        for i in range(7):
            form_card.grid_columnconfigure(i, weight=0)
        form_card.grid_columnconfigure(1, weight=1)
        form_card.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            form_card,
            text="Add Class",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, columnspan=7, sticky="w", padx=16, pady=(14, 10))

        ctk.CTkLabel(form_card, text="Class Name", text_color="#888888").grid(
            row=1, column=0, sticky="w", padx=(16, 8), pady=(0, 8)
        )
        self.name_entry = ctk.CTkEntry(form_card, placeholder_text="e.g. BSc CSIT", height=36)
        self.name_entry.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=(0, 8))

        ctk.CTkLabel(form_card, text="Section", text_color="#888888").grid(
            row=1, column=2, sticky="w", padx=(0, 8), pady=(0, 8)
        )
        self.section_entry = ctk.CTkEntry(form_card, placeholder_text="e.g. A", height=36)
        self.section_entry.grid(row=1, column=3, sticky="ew", padx=(0, 16), pady=(0, 8))

        ctk.CTkLabel(form_card, text="Max Students", text_color="#888888").grid(
            row=1, column=4, sticky="w", padx=(0, 8), pady=(0, 8)
        )
        self.max_students_entry = ctk.CTkEntry(form_card, width=120, height=36)
        self.max_students_entry.grid(row=1, column=5, sticky="ew", padx=(0, 16), pady=(0, 8))
        self.max_students_entry.insert(0, "30")

        ctk.CTkButton(
            form_card,
            text="Add Class",
            command=self._handle_add_class,
            fg_color="#1E88E5",
            hover_color="#1565C0",
            height=36,
            width=110,
            corner_radius=6,
        ).grid(row=1, column=6, sticky="e", padx=(0, 16), pady=(0, 8))

        # Late / Absent cutoff fields
        ctk.CTkLabel(form_card, text="Late Cutoff (HH:MM)", text_color="#888888").grid(
            row=2, column=0, sticky="w", padx=(16, 8), pady=(6, 12)
        )
        self.late_cutoff_entry = ctk.CTkEntry(form_card, placeholder_text="HH:MM", height=36)
        self.late_cutoff_entry.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=(6, 12))
        self.late_cutoff_entry.insert(0, "06:30")

        ctk.CTkLabel(form_card, text="Absent Cutoff (HH:MM)", text_color="#888888").grid(
            row=2, column=2, sticky="w", padx=(0, 8), pady=(6, 12)
        )
        self.absent_cutoff_entry = ctk.CTkEntry(form_card, placeholder_text="HH:MM", height=36)
        self.absent_cutoff_entry.grid(row=2, column=3, sticky="ew", padx=(0, 16), pady=(6, 12))
        self.absent_cutoff_entry.insert(0, "07:00")

        # Class start/end time fields
        ctk.CTkLabel(form_card, text="Class Start (HH:MM)", text_color="#888888").grid(
            row=3, column=0, sticky="w", padx=(16, 8), pady=(0, 12)
        )
        self.start_time_entry = ctk.CTkEntry(form_card, placeholder_text="HH:MM", height=36)
        self.start_time_entry.grid(row=3, column=1, sticky="ew", padx=(0, 16), pady=(0, 12))
        self.start_time_entry.insert(0, "06:00")

        ctk.CTkLabel(form_card, text="Class End (HH:MM)", text_color="#888888").grid(
            row=3, column=2, sticky="w", padx=(0, 8), pady=(0, 12)
        )
        self.end_time_entry = ctk.CTkEntry(form_card, placeholder_text="HH:MM", height=36)
        self.end_time_entry.grid(row=3, column=3, sticky="ew", padx=(0, 16), pady=(0, 12))
        self.end_time_entry.insert(0, "10:00")

    def _build_table(self) -> None:
        table_card = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=10)
        table_card.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 18))
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            table_card,
            text="All Classes",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 8))

        self.table_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.table_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        headers = ["ID", "Name", "Section", "Max Students", "Created By", "Created Date", "Action"]
        weights = [1, 2, 1, 1, 2, 2, 1]
        for idx, weight in enumerate(weights):
            self.table_scroll.grid_columnconfigure(idx, weight=weight)

        for col, header in enumerate(headers):
            ctk.CTkLabel(
                self.table_scroll,
                text=header,
                text_color="#888888",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=(10, 6), pady=(0, 6))

        self.empty_label = ctk.CTkLabel(
            self.table_scroll,
            text="No classes found.",
            text_color="#888888",
        )

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.app, "show_notification"):
            self.app.show_notification(message, kind)

    def _confirm_delete_dialog(self, class_name: str) -> bool:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Delete")
        dialog.geometry("430x210")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        result = {"ok": False}

        def do_delete() -> None:
            result["ok"] = True
            dialog.destroy()

        card = ctk.CTkFrame(dialog, fg_color="#1E1E1E", corner_radius=0)
        card.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            card,
            text="Delete Class",
            font=ctk.CTkFont(size=19, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            card,
            text=f"Delete class '{class_name}'? This action cannot be undone.",
            justify="left",
            wraplength=380,
            text_color="#D0D0D0",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkButton(actions, text="Cancel", command=dialog.destroy, corner_radius=6).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Delete",
            command=do_delete,
            fg_color="#C62828",
            hover_color="#A51F1F",
            corner_radius=6,
        ).pack(side="right")

        self.wait_window(dialog)
        return bool(result["ok"])

    def _handle_add_class(self) -> None:
        name = self.name_entry.get().strip()
        section = self.section_entry.get().strip()
        max_students_raw = self.max_students_entry.get().strip()

        if not name or not section:
            self._notify("Class name and section are required.", "error")
            return

        try:
            max_students = int(max_students_raw or "30")
            if max_students <= 0:
                raise ValueError
        except ValueError:
            self._notify("Max Students must be a positive number.", "error")
            return

        try:
            current_count = get_class_count()
            max_allowed = get_max_classes()
            if current_count >= max_allowed:
                self._notify(
                    "Class limit reached. Contact superadmin to increase limit.",
                    "error",
                )
                return

            # collect optional cutoffs and class times
            late_raw = None
            absent_raw = None
            start_raw = None
            end_raw = None
            try:
                late_raw = (self.late_cutoff_entry.get() or "").strip() or None
            except Exception:
                late_raw = None
            try:
                absent_raw = (self.absent_cutoff_entry.get() or "").strip() or None
            except Exception:
                absent_raw = None
            try:
                start_raw = (self.start_time_entry.get() or "").strip() or None
            except Exception:
                start_raw = None
            try:
                end_raw = (self.end_time_entry.get() or "").strip() or None
            except Exception:
                end_raw = None

            add_class(
                name,
                section,
                self.username or "system",
                max_students=max_students,
                late_cutoff=late_raw,
                absent_cutoff=absent_raw,
                class_start_time=start_raw,
                class_end_time=end_raw,
            )
        except Exception:
            self._notify("Failed to add class.", "error")
            return

        self.name_entry.delete(0, "end")
        self.section_entry.delete(0, "end")
        self.max_students_entry.delete(0, "end")
        self.max_students_entry.insert(0, "30")
        self._notify("Class added successfully.", "success")
        self.refresh()

    def _handle_delete_class(self, class_id: int, class_name: str) -> None:
        if not self._confirm_delete_dialog(class_name):
            return

        try:
            delete_class(class_id, self.username or "system")
        except Exception:
            self._notify("Failed to delete class.", "error")
            return

        self._notify("Class deleted successfully.", "success")
        self.refresh()

    def _format_created_date(self, raw_date) -> str:
        if raw_date is None:
            return "-"
        value = str(raw_date)
        return value[:19]

    def _clear_table_rows(self) -> None:
        for widget in self._rows:
            widget.destroy()
        self._rows.clear()
        self.empty_label.grid_forget()

    def _populate_table(self, classes: list[dict]) -> None:
        self._clear_table_rows()

        if not classes:
            self.empty_label.grid(row=1, column=0, columnspan=7, sticky="w", padx=10, pady=14)
            return

        for idx, row in enumerate(classes, start=1):
            bg = "#1A1A1A" if idx % 2 else "#202020"
            row_widgets: list[ctk.CTkBaseClass] = []

            values = [
                str(row.get("id", "-")),
                str(row.get("name", "-")),
                str(row.get("section", "-")),
                str(row.get("max_students", "-")),
                str(row.get("created_by", "-")),
                self._format_created_date(row.get("created_date")),
            ]

            for col, value in enumerate(values):
                lbl = ctk.CTkLabel(
                    self.table_scroll,
                    text=value,
                    text_color="white",
                    fg_color=bg,
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                )
                lbl.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                row_widgets.append(lbl)

            btn = ctk.CTkButton(
                self.table_scroll,
                text="Delete",
                fg_color="#C62828",
                hover_color="#A51F1F",
                width=84,
                height=28,
                corner_radius=6,
                command=lambda cid=row.get("id"), cname=row.get("name", ""): self._handle_delete_class(
                    int(cid), str(cname)
                ),
            )
            btn.grid(row=idx, column=6, sticky="e", padx=(6, 10), pady=2)
            row_widgets.append(btn)

            self._rows.extend(row_widgets)

    def _update_count_label(self, current: int, max_allowed: int) -> None:
        self.class_count_label.configure(text=f"{current} / {max_allowed} classes")

    def refresh(self) -> None:
        try:
            classes = get_all_classes()
            current = get_class_count()
            max_allowed = get_max_classes()
        except Exception:
            self._notify("Failed to load classes.", "error")
            return

        self._update_count_label(current, max_allowed)
        self._populate_table(classes)

    def _schedule_auto_refresh(self) -> None:
        if self._refresh_after_id is not None:
            self.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.after(AUTO_REFRESH_MS, self._on_auto_refresh)

    def _on_auto_refresh(self) -> None:
        self._refresh_after_id = None
        self.refresh()
        self._schedule_auto_refresh()

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role
