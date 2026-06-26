from __future__ import annotations

import customtkinter as ctk # pyright: ignore[reportMissingImports]
from gui import theme

from tkinter import filedialog
import io

try:
    import cv2
except Exception:
    cv2 = None

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from core.database import (
    get_all_classes,
    get_students_by_class,
    log_action,
    soft_delete_student,
    update_student_photo,
)


class StudentPage(ctk.CTkFrame):
    def __init__(self, master, username: str, role: str, on_navigate=None) -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role
        self.on_navigate = on_navigate

        self._classes: list[dict] = []
        self._class_by_label: dict[str, dict] = {}
        self._selected_class_id: int | None = None
        self._table_widgets: list[ctk.CTkBaseClass] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_top_bar()
        self._build_table_card()

        self.refresh()

    def _build_top_bar(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top,
            text="Students",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        self.class_count_label = ctk.CTkLabel(
            top,
            text="0 / 0 students",
            font=ctk.CTkFont(size=14),
            text_color=theme.TEXT_SECONDARY,
        )
        self.class_count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        controls = ctk.CTkFrame(top, fg_color="transparent")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")
        controls.grid_columnconfigure(0, weight=1)

        _dd_frame = ctk.CTkFrame(controls, fg_color="transparent")
        _dd_frame.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        _dd_frame.grid_columnconfigure(0, weight=1)
        self.class_selector = ctk.CTkComboBox(
            _dd_frame,
            values=["Select Class"],
            command=self._on_class_selected,
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            border_color=theme.BG_SURFACE_ALT,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_PRIMARY,
            dropdown_fg_color=theme.BG_SURFACE_ALT,
            dropdown_text_color=theme.TEXT_PRIMARY,
            dropdown_hover_color=theme.BG_HOVER,
            corner_radius=8,
            state="readonly",
        )
        self.class_selector.grid(row=0, column=0, sticky="ew")
        self.class_selector.set("Select Class")

        ctk.CTkButton(
            controls,
            text="Register New Student",
            command=self._handle_navigate_register,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=34,
            corner_radius=6,
        ).grid(row=0, column=1, padx=(0, 10))

        ctk.CTkButton(
            controls,
            text="Refresh",
            command=self.refresh,
            fg_color=theme.BTN_SECONDARY,
            hover_color=theme.BTN_SECONDARY_HVR,
            height=34,
            width=88,
            corner_radius=6,
        ).grid(row=0, column=2)

    def _build_table_card(self) -> None:
        card = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=10)
        card.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 18))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="Students In Selected Class",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 8))

        self.table_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.table_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        headers = ["Student ID", "Name", "Registered By", "Registered Date", "Delete", "Photo"]
        weights = [2, 3, 2, 2, 1, 1]
        for col, weight in enumerate(weights):
            self.table_scroll.grid_columnconfigure(col, weight=weight)

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
            text="Please select a class to view students",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=13),
        )

    def _notify(self, message: str, kind: str) -> None:
        try:
            self.winfo_toplevel().show_notification(message, kind)
        except Exception:
            pass

    def _format_class_label(self, class_row: dict) -> str:
        name    = str(class_row.get("name",    "")).strip()
        section = str(class_row.get("section", "")).strip()
        return f"{name} - {section}"

    def _load_classes(self) -> None:
        self._classes = get_all_classes()
        self._class_by_label.clear()

        labels = ["Select Class"]
        for row in self._classes:
            label = self._format_class_label(row)
            self._class_by_label[label] = row
            labels.append(label)

        self.class_selector.configure(values=labels)

        # Keep selected class if still present.
        if self._selected_class_id is None:
            self.class_selector.set("Select Class")
            return

        for label, row in self._class_by_label.items():
            if int(row.get("id", -1)) == self._selected_class_id:
                self.class_selector.set(label)
                return

        self._selected_class_id = None
        self.class_selector.set("Select Class")

    def _clear_rows(self) -> None:
        for widget in self._table_widgets:
            widget.destroy()
        self._table_widgets.clear()
        self.empty_label.grid_forget()

    def _set_count_text(self, current: int = 0, max_students: int = 0) -> None:
        self.class_count_label.configure(text=f"{current} / {max_students} students")

    def _show_empty_message(self, message: str) -> None:
        self._clear_rows()
        self.empty_label.configure(text=message)
        self.empty_label.grid(row=1, column=0, columnspan=6, sticky="w", padx=10, pady=14)

    def _format_date(self, value) -> str:
        if value is None:
            return "-"
        return str(value)[:19]

    def _display_name(self, row: dict) -> str:
        fn = row.get("first_name")
        if fn:
            parts = [str(fn).strip()]
            mn = row.get("middle_name")
            if mn:
                parts.append(str(mn).strip())
            ln = row.get("last_name")
            if ln:
                parts.append(str(ln).strip())
            return " ".join([p for p in parts if p])
        return str(row.get("name", "-")).strip()

    def _populate_students(self, students: list[dict]) -> None:
        self._clear_rows()

        if not students:
            self._show_empty_message("No students found for selected class")
            return

        for idx, student in enumerate(students, start=1):
            bg = theme.BG_ROW_ODD if idx % 2 else theme.BG_ROW_EVEN
            row_widgets: list[ctk.CTkBaseClass] = []

            values = [
                str(student.get("student_id", "-")),
                self._display_name(student),
                str(student.get("registered_by", "-")),
                self._format_date(student.get("registered_date")),
            ]

            for col, value in enumerate(values):
                label = ctk.CTkLabel(
                    self.table_scroll,
                    text=value,
                    text_color=theme.TEXT_PRIMARY,
                    fg_color=bg,
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                )
                label.grid(row=idx, column=col, sticky="ew", padx=(10, 6), pady=2)
                row_widgets.append(label)

            sid = str(student.get("student_id", "")).strip()
            name = self._display_name(student)
            delete_btn = ctk.CTkButton(
                self.table_scroll,
                text="Delete",
                fg_color=theme.BTN_DANGER,
                hover_color=theme.BTN_DANGER_HVR,
                width=84,
                height=28,
                corner_radius=6,
                command=lambda student_id=sid, student_name=name: self._handle_delete_student(
                    student_id,
                    student_name,
                ),
            )
            delete_btn.grid(row=idx, column=4, sticky="e", padx=(6, 10), pady=2)
            row_widgets.append(delete_btn)
            # Update Photo button next to Delete
            update_btn = ctk.CTkButton(
                self.table_scroll,
                text="Update Photo",
                fg_color=theme.ACCENT,
                hover_color=theme.ACCENT_HOVER,
                width=110,
                height=28,
                corner_radius=6,
                command=lambda student_id=sid: self._open_update_photo_popup(student_id),
            )
            update_btn.grid(row=idx, column=5, sticky="e", padx=(6, 10), pady=2)
            row_widgets.append(update_btn)

            self._table_widgets.extend(row_widgets)

    def _on_class_selected(self, selected_label: str) -> None:
        if selected_label == "Select Class":
            self._selected_class_id = None
            self._set_count_text(0, 0)
            self._show_empty_message("Please select a class to view students")
            return

        class_row = self._class_by_label.get(selected_label)
        if not class_row:
            self._selected_class_id = None
            self._set_count_text(0, 0)
            self._show_empty_message("Please select a class to view students")
            return

        self._selected_class_id = int(class_row["id"])
        self._load_students_for_selected_class()

    def _confirm_delete_dialog(self, student_name: str, student_id: str) -> bool:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Delete")
        dialog.geometry("440x220")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        result = {"ok": False}

        def do_delete() -> None:
            result["ok"] = True
            dialog.destroy()

        card = ctk.CTkFrame(dialog, fg_color=theme.BG_SURFACE_ALT, corner_radius=0)
        card.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            card,
            text="Delete Student",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            card,
            text=f"Soft delete {student_name} ({student_id})?",
            justify="left",
            wraplength=390,
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

    def _open_update_photo_popup(self, student_id: str) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Update Profile Photo")
        dialog.geometry("420x300")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog, fg_color=theme.BG_SURFACE)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        preview_frame = ctk.CTkFrame(frame, fg_color=theme.BG_SURFACE, width=120, height=120)
        preview_frame.grid(row=0, column=1, rowspan=3, padx=(8,0))
        preview_frame.grid_propagate(False)
        preview_label = ctk.CTkLabel(preview_frame, text="No photo selected", text_color=theme.TEXT_SECONDARY)
        preview_label.place(relx=0.5, rely=0.5, anchor="center")

        def _set_preview_from_bytes(b: bytes | None) -> None:
            if not b:
                preview_label.configure(text="No photo selected", image=None)
                return
            if Image is None:
                preview_label.configure(text="Photo selected")
                return
            try:
                img = Image.open(io.BytesIO(b))
                img.thumbnail((120,120))
                tkimg = ImageTk.PhotoImage(img)
                preview_label.configure(image=tkimg, text="")
                preview_label.image = tkimg
            except Exception:
                preview_label.configure(text="No photo selected")

        selected_bytes = {"data": None}

        def take_photo() -> None:
            if cv2 is None:
                self._notify("OpenCV not available for camera capture.", "error")
                return
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self._notify("Unable to open camera.", "error")
                return

            cam_dlg = ctk.CTkToplevel(dialog)
            cam_dlg.title("Capture Photo")
            cam_dlg.geometry("520x420")
            cam_dlg.transient(dialog)
            cam_dlg.grab_set()
            video_label = ctk.CTkLabel(cam_dlg, text="", fg_color="#000000")
            video_label.pack(fill="both", expand=True, padx=8, pady=8)

            def _update():
                ret, frame = cap.read()
                if not ret:
                    cam_dlg.after(30, _update)
                    return
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if Image is not None:
                    pil = Image.fromarray(frame_rgb)
                    pil = pil.resize((480,320))
                    tkimg = ImageTk.PhotoImage(pil)
                    video_label.configure(image=tkimg)
                    video_label.image = tkimg
                cam_dlg.after(30, _update)

            def _capture():
                ret, frame = cap.read()
                if not ret:
                    return
                _, buf = cv2.imencode('.jpg', frame)
                b = buf.tobytes()
                selected_bytes["data"] = b
                _set_preview_from_bytes(b)
                try:
                    cap.release()
                except Exception:
                    pass
                cam_dlg.destroy()

            btn = ctk.CTkButton(cam_dlg, text="Capture", command=_capture, fg_color=theme.ACCENT)
            btn.pack(pady=(0,12))
            _update()

        def upload_file() -> None:
            fname = filedialog.askopenfilename(filetypes=[("Image Files","*.png;*.jpg;*.jpeg"), ("All Files","*.*")])
            if not fname:
                return
            try:
                with open(fname, "rb") as f:
                    b = f.read()
                selected_bytes["data"] = b
                _set_preview_from_bytes(b)
            except Exception:
                self._notify("Failed to load image.", "error")

        def do_update() -> None:
            b = selected_bytes.get("data")
            try:
                update_student_photo(student_id, b)
                log_action(self.username or "system", "UPDATE_STUDENT_PHOTO", f"student_id={student_id}")
            except Exception as e:
                self._notify(f"Failed to update photo: {e}", "error")
                return
            self._notify("Profile photo updated successfully", "success")
            dialog.destroy()

        ctk.CTkButton(frame, text="📷 Take Photo", command=take_photo, fg_color=theme.ACCENT).grid(row=0, column=0, padx=8, pady=(8,4))
        ctk.CTkButton(frame, text="📁 Upload Photo", command=upload_file, fg_color=theme.BTN_SUCCESS).grid(row=1, column=0, padx=8, pady=(4,8))
        ctk.CTkButton(frame, text="Update", command=do_update, fg_color=theme.BTN_SUCCESS).grid(row=2, column=0, padx=8, pady=(8,8))
        ctk.CTkButton(frame, text="Cancel", command=dialog.destroy, fg_color=theme.BTN_SECONDARY).grid(row=3, column=0, padx=8, pady=(0,8))

    def _handle_delete_student(self, student_id: str, student_name: str) -> None:
        if not student_id:
            self._notify("Invalid student ID.", "error")
            return

        if not self._confirm_delete_dialog(student_name, student_id):
            return

        try:
            soft_delete_student(student_id, self.username or "system")
            log_action(
                self.username or "system",
                "SOFT_DELETE_STUDENT",
                f"student_id={student_id}; class_id={self._selected_class_id}",
            )
        except Exception:
            self._notify("Failed to delete student.", "error")
            return

        self._notify("Student deleted successfully.", "success")
        self._load_students_for_selected_class()

    def _load_students_for_selected_class(self) -> None:
        if self._selected_class_id is None:
            self._set_count_text(0, 0)
            self._show_empty_message("Please select a class to view students")
            return

        selected_class = None
        for row in self._classes:
            if int(row.get("id", -1)) == self._selected_class_id:
                selected_class = row
                break

        if not selected_class:
            self._set_count_text(0, 0)
            self._show_empty_message("Please select a class to view students")
            return

        try:
            students = get_students_by_class(self._selected_class_id)
        except Exception:
            self._notify("Failed to load students.", "error")
            return

        max_students = int(selected_class.get("max_students") or 0)
        self._set_count_text(len(students), max_students)
        self._populate_students(students)

    def _handle_navigate_register(self) -> None:
        if self._selected_class_id is None:
            self._notify("Please select a class first.", "error")
            return

        selected_class = None
        for row in self._classes:
            if int(row.get("id", -1)) == self._selected_class_id:
                selected_class = row
                break

        payload = {
            "class_id": self._selected_class_id,
            "class_name": selected_class.get("name") if selected_class else "",
            "section": selected_class.get("section") if selected_class else "",
        }

        try:
            # Preferred callback signature: on_navigate(page_name, context_dict)
            self.on_navigate("Register Student", payload)
        except TypeError:
            try:
                # Fallback: on_navigate(page_name)
                self.on_navigate("Register Student")
            except Exception:
                pass

    def refresh(self) -> None:
        # Reload class list
        try:
            self._load_classes()
        except Exception:
            self._notify("Failed to load class list.", "error")

        # If a class is selected, reload its students. Handle errors separately.
        if self._selected_class_id is None:
            self._set_count_text(0, 0)
            self._show_empty_message("Please select a class to view students")
            return

        try:
            self._load_students_for_selected_class()
        except Exception:
            self._notify("Failed to load students for selected class.", "error")

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role
