from __future__ import annotations

import threading
import io
import os

import cv2
import customtkinter as ctk
from tkinter import filedialog

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from core.database import add_student, get_all_classes, log_action, get_all_students, get_archive
from core.face_engine import capture_face_images, train_class_model, cleanup_student_dataset


class RegisterPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        username: str = "",
        role: str = "",
        pre_selected_class_id: int | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.master_frame = master
        self.username = username
        self.role = role
        self.pre_selected_class_id = pre_selected_class_id
        self._classes: list[dict] = []
        self._class_map: dict[str, dict] = {}
        self._capture_target_count = 50
        self._capture_busy = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(header, text="Register Student", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(side="left", padx=20, pady=15)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(body, fg_color="#1A1A1A", corner_radius=16)
        form.grid(row=0, column=0, sticky="n", padx=24, pady=24)
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            form,
            text="Student ID",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, sticky="w", padx=22, pady=(22, 8))
        self.id_entry = ctk.CTkEntry(form, height=40, placeholder_text="Enter student ID")
        self.id_entry.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 16))

        ctk.CTkLabel(
            form,
            text="First Name",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).grid(row=2, column=0, sticky="w", padx=22, pady=(0, 8))
        self.first_entry = ctk.CTkEntry(form, height=40, placeholder_text="Enter first name")
        self.first_entry.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 8))

        ctk.CTkLabel(
            form,
            text="Middle Name",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).grid(row=4, column=0, sticky="w", padx=22, pady=(0, 8))
        self.middle_entry = ctk.CTkEntry(form, height=40, placeholder_text="Optional")
        self.middle_entry.grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 8))

        ctk.CTkLabel(
            form,
            text="Last Name",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).grid(row=6, column=0, sticky="w", padx=22, pady=(0, 8))
        self.last_entry = ctk.CTkEntry(form, height=40, placeholder_text="Enter last name")
        self.last_entry.grid(row=7, column=0, sticky="ew", padx=22, pady=(0, 16))

        ctk.CTkLabel(
            form,
            text="Class",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).grid(row=8, column=0, sticky="w", padx=22, pady=(0, 8))
        self.class_dropdown = ctk.CTkOptionMenu(
            form,
            values=["Select Class"],
            width=420,
            height=40,
            fg_color="#1F1F1F",
            button_color="#1E88E5",
            button_hover_color="#1565C0",
        )
        self.class_dropdown.grid(row=9, column=0, sticky="ew", padx=22, pady=(0, 22))
        self.class_dropdown.set("Select Class")

        # profile photo state
        self.profile_photo_bytes: bytes | None = None
        self._photo_thumbnail = None

        # Profile photo controls (row 10)
        photo_frame = ctk.CTkFrame(form, fg_color="transparent")
        photo_frame.grid(row=10, column=0, sticky="ew", padx=22, pady=(0, 12))
        photo_frame.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(photo_frame, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        right = ctk.CTkFrame(photo_frame, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(left, text="Profile Photo", font=ctk.CTkFont(size=15, weight="bold"), text_color="white").grid(row=0, column=0, sticky="w", padx=(0,8))
        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="w")
        ctk.CTkButton(btn_frame, text="📷 Take Photo", command=self._open_camera_capture_popup, fg_color="#1E88E5", hover_color="#1565C0").grid(row=0, column=0, padx=(0,8))
        ctk.CTkButton(btn_frame, text="📁 Upload Photo", command=self._upload_photo, fg_color="#2A7F62", hover_color="#19674F").grid(row=0, column=1)

        # preview box
        self._photo_preview_frame = ctk.CTkFrame(right, fg_color="#121212", width=100, height=100)
        self._photo_preview_frame.grid(row=0, column=0, sticky="e")
        self._photo_preview_frame.grid_propagate(False)
        self._photo_preview_label = ctk.CTkLabel(self._photo_preview_frame, text="No photo selected", text_color="#888888")
        self._photo_preview_label.place(relx=0.5, rely=0.5, anchor="center")

        # Capture button (moved down)
        self.capture_button = ctk.CTkButton(
            form,
            text="Start Capture",
            command=self.handle_register_student,
            fg_color="#1E88E5",
            hover_color="#1565C0",
            height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.capture_button.grid(row=11, column=0, sticky="ew", padx=22, pady=(0, 12))

        self.progress_bar = ctk.CTkProgressBar(form)
        self.progress_bar.grid(row=12, column=0, sticky="ew", padx=22, pady=(0, 8))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            form,
            text="Fill the form and click Start Capture.",
            text_color="#888888",
            wraplength=420,
            justify="left",
        )
        self.status_label.grid(row=13, column=0, sticky="ew", padx=22, pady=(0, 22))

        self.refresh()

    def handle_register_student(self) -> None:
        if self._capture_busy:
            return

        if not self._classes:
            self.status_label.configure(text="Please add a class first", text_color="#FF5252")
            self._notify("Please add a class first", "error")
            return

        selected_label = self.class_dropdown.get().strip()
        class_row = self._class_map.get(selected_label)
        student_id = self.id_entry.get().strip()
        first_name = self.first_entry.get().strip()
        middle_name = self.middle_entry.get().strip()
        last_name = self.last_entry.get().strip()

        if not student_id or not first_name or not last_name or class_row is None:
            self.status_label.configure(
                text="Please fill Student ID, Student Name, and Class.",
                text_color="#FF5252",
            )
            self._notify("Please fill all required fields.", "error")
            return

        # Pre-capture: ensure student ID is unique across active and archived students
        try:
            all_students = get_all_students() or []
            archive_students = get_archive() or []
            exists_active = any(str(s.get("student_id", "")).strip() == student_id for s in all_students)
            exists_archived = any(str(s.get("student_id", "")).strip() == student_id for s in archive_students)
            if exists_active or exists_archived:
                message = "Student ID already exists in the system. Please use a different ID."
                self.status_label.configure(text=message, text_color="#FF5252")
                self._notify(message, "error")
                return
        except Exception as e:
            # If the check fails, show an error and avoid starting the camera
            self.status_label.configure(text=f"Failed to validate student ID: {e}", text_color="#FF5252")
            self._notify("Failed to validate student ID.", "error")
            return

        class_id = int(class_row["id"])
        self._set_busy(True)
        self.status_label.configure(text="Starting camera capture...", text_color="#888888")
        self.progress_bar.set(0)

        # Build a display name for capture (concatenate parts, skipping empty middle)
        if middle_name:
            display_name = f"{first_name} {middle_name} {last_name}"
        else:
            display_name = f"{first_name} {last_name}"

        worker = threading.Thread(
            target=self._capture_and_register_worker,
            args=(student_id, first_name, middle_name or None, last_name, display_name, class_id),
            daemon=True,
        )
        worker.start()

    def _capture_and_register_worker(
        self,
        student_id: str,
        first_name: str,
        middle_name: str | None,
        last_name: str,
        display_name: str,
        class_id: int,
    ) -> None:
        try:
            captured = capture_face_images(
                student_id,
                display_name,
                class_id,
                count=self._capture_target_count,
                progress_callback=self._on_capture_progress,
            )
            if not captured:
                raise RuntimeError("Face capture did not complete. Please try again.")

            # mark that images were captured; if any subsequent step fails,
            # we should cleanup the dataset for this student
            images_captured = bool(captured)
            # Pass optional profile photo bytes to DB
            add_student(
                student_id,
                first_name,
                middle_name,
                last_name,
                class_id,
                self.username or "system",
                getattr(self, "profile_photo_bytes", None),
            )
            train_class_model(class_id)
            log_action(
                self.username or "system",
                "REGISTER_STUDENT",
                f"student_id={student_id}; class_id={class_id}",
            )

            self.after(0, self._on_register_success)
        except Exception as error:
            # If images were captured earlier in the flow, cleanup the dataset
            try:
                if 'images_captured' in locals() and images_captured:
                    try:
                        cleanup_student_dataset(student_id, class_id)
                    except Exception:
                        pass
            finally:
                self.after(0, lambda e=error: self._on_register_failure(e))
        finally:
            self.after(0, lambda: self._set_busy(False))

    def _on_capture_progress(self, current: int, total: int) -> None:
        self.after(0, lambda: self._apply_progress(current, total))

    def _apply_progress(self, current: int, total: int) -> None:
        if total > 0:
            self.progress_bar.set(min(max(current / total, 0.0), 1.0))
        self.status_label.configure(
            text=f"Capturing image {current} of {total}",
            text_color="#888888",
        )

    def _on_register_success(self) -> None:
        self.status_label.configure(
            text="Student registered and model updated successfully",
            text_color="#6FD36F",
        )
        self._notify("Student registered and model updated successfully", "success")
        self.id_entry.delete(0, "end")
        try:
            self.first_entry.delete(0, "end")
        except Exception:
            pass
        try:
            self.middle_entry.delete(0, "end")
        except Exception:
            pass
        try:
            self.last_entry.delete(0, "end")
        except Exception:
            pass
        self.class_dropdown.set("Select Class")
        self.progress_bar.set(0)
        if hasattr(self.master_frame, "refresh_all_views"):
            self.master_frame.refresh_all_views()

    def _on_register_failure(self, error: Exception) -> None:
        self.status_label.configure(text=f"Registration failed: {error}", text_color="#FF5252")
        self._notify("Registration failed.", "error")

    def _notify(self, message: str, kind: str) -> None:
        if hasattr(self.master_frame, "show_notification"):
            self.master_frame.show_notification(message, kind)
        elif hasattr(self.master_frame, "notifications") and hasattr(self.master_frame.notifications, "show"):
            self.master_frame.notifications.show(message, kind=kind)

    def _set_busy(self, busy: bool) -> None:
        self._capture_busy = busy
        if busy:
            self.capture_button.configure(state="disabled", text="Capturing...")
        else:
            self.capture_button.configure(state="normal", text="Start Capture")

    def _label_for_class(self, row: dict) -> str:
        return f"{row.get('name', '')} - {row.get('section', '')} (ID: {row.get('id', '-')})"

    def _apply_pre_selected_class(self) -> None:
        if self.pre_selected_class_id is None:
            return
        for label, row in self._class_map.items():
            if int(row.get("id", -1)) == int(self.pre_selected_class_id):
                self.class_dropdown.set(label)
                return

    def refresh(self) -> None:
        try:
            self._classes = get_all_classes()
        except Exception as error:
            self.status_label.configure(text=f"Failed to load classes: {error}", text_color="#FF5252")
            return

        self._class_map.clear()
        options = ["Select Class"]
        for class_row in self._classes:
            label = self._label_for_class(class_row)
            self._class_map[label] = class_row
            options.append(label)

        self.class_dropdown.configure(values=options)
        self.class_dropdown.set("Select Class")
        self._apply_pre_selected_class()

        if not self._classes:
            self.status_label.configure(text="Please add a class first", text_color="#FF5252")
            self.capture_button.configure(state="disabled")
        else:
            if not self._capture_busy:
                self.capture_button.configure(state="normal")
            self.status_label.configure(
                text="Fill the form and click Start Capture.",
                text_color="#888888",
            )

    def update_user(self, username: str, role: str) -> None:
        self.username = username
        self.role = role

    def set_pre_selected_class(self, class_id: int | None) -> None:
        self.pre_selected_class_id = class_id
        self._apply_pre_selected_class()

    # ---------- Profile photo helpers ----------
    def _open_camera_capture_popup(self) -> None:
        try:
            dlg = ctk.CTkToplevel(self)
            dlg.title("Capture Photo")
            dlg.geometry("520x420")
            dlg.transient(self.winfo_toplevel())
            dlg.grab_set()

            video_label = ctk.CTkLabel(dlg, text="", fg_color="#000000")
            video_label.pack(fill="both", expand=True, padx=8, pady=8)

            cap = cv2.VideoCapture(0)

            def update_frame():
                if not cap.isOpened():
                    return
                ret, frame = cap.read()
                if not ret:
                    dlg.after(30, update_frame)
                    return
                # store last frame on dialog for capture
                dlg._last_frame = frame
                # convert BGR to RGB
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if Image is not None:
                    pil = Image.fromarray(img)
                    pil = pil.resize((480, 320))
                    tkimg = ImageTk.PhotoImage(pil)
                    video_label.configure(image=tkimg)
                    video_label.image = tkimg
                else:
                    # fallback: write temp file and load (not ideal)
                    tmp = os.path.join(os.getcwd(), "__tmp_capture.png")
                    cv2.imwrite(tmp, frame)
                    try:
                        tkimg = ctk.CTkImage(light_image=None, dark_image=None)
                    except Exception:
                        tkimg = None
                    if tkimg:
                        video_label.configure(image=tkimg)
                dlg.after(30, update_frame)

            def do_capture():
                frame = getattr(dlg, "_last_frame", None)
                if frame is None:
                    return
                # convert to JPEG bytes
                _, buf = cv2.imencode('.jpg', frame)
                b = buf.tobytes()
                self._set_profile_photo_bytes(b)
                try:
                    cap.release()
                except Exception:
                    pass
                dlg.destroy()

            btn = ctk.CTkButton(dlg, text="Capture", command=do_capture, fg_color="#1E88E5")
            btn.pack(pady=(0, 12))

            update_frame()
        except Exception as e:
            self._notify(f"Camera error: {e}", "error")

    def _upload_photo(self) -> None:
        try:
            fname = filedialog.askopenfilename(
                filetypes=[("Image Files", "*.png;*.jpg;*.jpeg" ), ("All Files", "*.*")]
            )
            if not fname:
                return
            with open(fname, "rb") as f:
                data = f.read()
            self._set_profile_photo_bytes(data)
        except Exception as e:
            self._notify(f"Failed to load image: {e}", "error")

    def _set_profile_photo_bytes(self, data: bytes | None) -> None:
        self.profile_photo_bytes = data
        # update preview
        try:
            if not data:
                self._photo_preview_label.configure(text="No photo selected")
                return
            if Image is None:
                # cannot render thumbnail without PIL; show text
                self._photo_preview_label.configure(text="Photo selected")
                return
            img = Image.open(io.BytesIO(data))
            img.thumbnail((100, 100))
            tkimg = ImageTk.PhotoImage(img)
            self._photo_thumbnail = tkimg
            self._photo_preview_label.configure(image=tkimg, text="")
            self._photo_preview_label.image = tkimg
        except Exception:
            self._photo_preview_label.configure(text="No photo selected")
