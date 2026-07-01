from __future__ import annotations

import customtkinter as ctk
from gui import theme
from gui.widgets import center_dialog

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
        self._add_overlay: ctk.CTkFrame | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
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
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        self.class_count_label = ctk.CTkLabel(
            head,
            text="0 / 0 classes",
            font=ctk.CTkFont(size=14),
            text_color=theme.TEXT_SECONDARY,
        )
        self.class_count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        btn_frame = ctk.CTkFrame(head, fg_color="transparent")
        btn_frame.grid(row=0, column=1, rowspan=2, sticky="e")

        ctk.CTkButton(
            btn_frame,
            text="+ Add Class",
            command=self._open_add_class_dialog,
            fg_color=theme.BTN_SUCCESS,
            hover_color=theme.BTN_ADD_HVR,
            width=120,
            height=36,
            corner_radius=6,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Refresh",
            command=self.refresh,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            width=100,
            height=36,
            corner_radius=6,
        ).pack(side="left")

    def _open_add_class_dialog(self) -> None:
        if self._add_overlay is not None:
            try:
                self._add_overlay.destroy()
            except Exception:
                pass
            self._add_overlay = None

        # Parent must be the root window so the overlay wins all z-order fights
        root = self.winfo_toplevel()

        card = ctk.CTkFrame(
            root,
            fg_color=theme.BG_SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=theme.BORDER,
        )
        self._add_overlay = card
        card.grid_columnconfigure(0, weight=1)

        def _close() -> None:
            try:
                card.place_forget()
            except Exception:
                pass

        # ── title row with X ───────────────────────────────────────────────
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 2))
        title_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_row, text="Add Class",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            title_row, text="✕", width=28, height=28, corner_radius=6,
            fg_color="transparent", hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_MUTED, command=_close,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            card, text="Fill in the details to create a new class.",
            font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY, anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        # ── helpers ────────────────────────────────────────────────────────
        def _lbl(parent, text: str) -> None:
            ctk.CTkLabel(
                parent, text=text,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=theme.TEXT_PRIMARY, anchor="w",
            ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        def _entry(parent, placeholder: str = "", default: str = "") -> ctk.CTkEntry:
            e = ctk.CTkEntry(
                parent, height=36,
                placeholder_text=placeholder,
                fg_color=theme.BG_SURFACE_ALT, border_width=0,
                text_color=theme.TEXT_PRIMARY,
                placeholder_text_color=theme.TEXT_MUTED,
                corner_radius=6,
            )
            e.grid(row=1, column=0, sticky="ew")
            if default:
                e.insert(0, default)
            return e

        def _col(parent, col: int, label: str, placeholder: str = "", default: str = "", padx=(0, 0)) -> ctk.CTkEntry:
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=0, column=col, sticky="ew", padx=padx)
            f.grid_columnconfigure(0, weight=1)
            _lbl(f, label)
            return _entry(f, placeholder, default)

        # ── row: Class Name (full width) ───────────────────────────────────
        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        r2.grid_columnconfigure(0, weight=1)
        _lbl(r2, "Class Name")
        name_entry = _entry(r2, placeholder="e.g. BSc CSIT")

        # ── row: Section + Max Students ────────────────────────────────────
        r3 = ctk.CTkFrame(card, fg_color="transparent")
        r3.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))
        r3.grid_columnconfigure(0, weight=2)
        r3.grid_columnconfigure(1, weight=1)
        section_entry      = _col(r3, 0, "Section",      placeholder="e.g. A", padx=(0, 8))
        max_students_entry = _col(r3, 1, "Max Students", default="30")

        # ── row: Late Cutoff + Absent Cutoff ───────────────────────────────
        r4 = ctk.CTkFrame(card, fg_color="transparent")
        r4.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 10))
        r4.grid_columnconfigure(0, weight=1)
        r4.grid_columnconfigure(1, weight=1)
        late_cutoff_entry   = _col(r4, 0, "Late Cutoff (HH:MM)",   default="06:30", padx=(0, 8))
        absent_cutoff_entry = _col(r4, 1, "Absent Cutoff (HH:MM)", default="07:00")

        # ── row: Class Start + Class End ───────────────────────────────────
        r5 = ctk.CTkFrame(card, fg_color="transparent")
        r5.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 10))
        r5.grid_columnconfigure(0, weight=1)
        r5.grid_columnconfigure(1, weight=1)
        start_time_entry = _col(r5, 0, "Class Start (HH:MM)", default="06:00", padx=(0, 8))
        end_time_entry   = _col(r5, 1, "Class End (HH:MM)",   default="10:00")

        # ── status + actions ───────────────────────────────────────────────
        status_var = ctk.StringVar(value="")
        status_lbl = ctk.CTkLabel(
            card, textvariable=status_var,
            font=ctk.CTkFont(size=12), anchor="w", wraplength=440,
            text_color=theme.DANGER,
        )
        status_lbl.grid(row=6, column=0, sticky="w", padx=20, pady=(0, 2))

        def _submit() -> None:
            name    = name_entry.get().strip()
            section = section_entry.get().strip()
            max_raw = max_students_entry.get().strip()

            if not name or not section:
                status_var.set("Class name and section are required.")
                return
            try:
                max_students = int(max_raw or "30")
                if max_students <= 0:
                    raise ValueError
            except ValueError:
                status_var.set("Max Students must be a positive number.")
                return

            late_raw   = late_cutoff_entry.get().strip()   or None
            absent_raw = absent_cutoff_entry.get().strip() or None
            start_raw  = start_time_entry.get().strip()    or None
            end_raw    = end_time_entry.get().strip()       or None

            try:
                current_count = get_class_count()
                max_allowed   = get_max_classes()
                if current_count >= max_allowed:
                    status_var.set("Class limit reached. Contact superadmin to increase limit.")
                    return
                add_class(
                    name, section, self.username or "system",
                    max_students=max_students,
                    late_cutoff=late_raw,
                    absent_cutoff=absent_raw,
                    class_start_time=start_raw,
                    class_end_time=end_raw,
                )
            except Exception:
                status_var.set("Failed to add class.")
                return

            self._notify("Class added successfully.", "success")
            _close()
            self.refresh()

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=7, column=0, sticky="ew", padx=20, pady=(4, 18))

        ctk.CTkButton(
            actions, text="Cancel", command=_close,
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_SECONDARY, corner_radius=6, height=36,
        ).pack(side="left")

        ctk.CTkButton(
            actions, text="Add Class", command=_submit,
            fg_color=theme.BTN_SUCCESS, hover_color=theme.BTN_ADD_HVR,
            text_color=theme.TEXT_PRIMARY, corner_radius=6, height=36, width=120,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="right")

        # Defer so all widgets are rendered and winfo_* values are valid
        def _place() -> None:
            W, H = 500, 440
            sw = self.winfo_width()
            sh = self.winfo_height()
            # If self isn't mapped yet, fall back to root window dimensions
            if sw < 20 or sh < 20:
                sw = root.winfo_width()
                sh = root.winfo_height()
                x  = (sw - W) // 2
                y  = (sh - H) // 2
            else:
                rx = self.winfo_rootx() - root.winfo_rootx()
                ry = self.winfo_rooty() - root.winfo_rooty()
                x  = rx + (sw - W) // 2
                y  = ry + (sh - H) // 2
            card.place(x=x, y=y, width=W, height=H)
            card.lift()

        self.after(50, _place)

    def _build_table(self) -> None:
        table_card = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=10)
        table_card.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 18))
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            table_card,
            text="All Classes",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
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
                text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=(10, 6), pady=(0, 6))

        self.empty_label = ctk.CTkLabel(
            self.table_scroll,
            text="No classes found.",
            text_color=theme.TEXT_SECONDARY,
        )

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.app, "show_notification"):
            self.app.show_notification(message, kind)

    def _confirm_delete_dialog(self, class_name: str) -> bool:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Delete")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        center_dialog(dialog, 430, 210)

        result = {"ok": False}

        def do_delete() -> None:
            result["ok"] = True
            dialog.destroy()

        card = ctk.CTkFrame(dialog, fg_color=theme.BG_SURFACE, corner_radius=0)
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
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(0, 14))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkButton(actions, text="Cancel", command=dialog.destroy, corner_radius=6).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Delete",
            command=do_delete,
            fg_color=theme.BTN_DANGER,
            hover_color=theme.BTN_DANGER_HVR,
            corner_radius=6,
        ).pack(side="right")

        self.wait_window(dialog)
        return bool(result["ok"])


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
            bg = theme.BG_SURFACE if idx % 2 else theme.BG_SURFACE_ALT
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
                    text_color=theme.TEXT_PRIMARY,
                    fg_color=bg,
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                )
                lbl.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                row_widgets.append(lbl)

            btn = ctk.CTkButton(
                self.table_scroll,
                text="Delete",
                fg_color=theme.BTN_DANGER,
                hover_color=theme.BTN_DANGER_HVR,
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
