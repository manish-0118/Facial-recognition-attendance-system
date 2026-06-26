from __future__ import annotations

import threading
import io
import os

import cv2
import customtkinter as ctk
from gui import theme
from tkinter import filedialog

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from core.database import add_student, get_all_classes, log_action, get_all_students, get_archive
from core.face_engine import capture_face_images, train_class_model, cleanup_student_dataset
from gui.widgets import ThemedDropdown


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
        header = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(header, text="Register Student", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(side="left", padx=20, pady=15)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)          # left fluid margin
        body.grid_columnconfigure(1, weight=0, minsize=500)  # fixed-width form column
        body.grid_columnconfigure(2, weight=1)          # right fluid margin
        body.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(body, fg_color=theme.BG_SURFACE, corner_radius=16)
        form.grid(row=0, column=1, sticky="new", pady=24)
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            form,
            text="Student ID",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=22, pady=(14, 4))
        self.id_entry = ctk.CTkEntry(
            form,
            height=36,
            placeholder_text="Enter student ID",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.id_entry.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))

        ctk.CTkLabel(
            form,
            text="First Name",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=2, column=0, sticky="w", padx=22, pady=(0, 4))
        self.first_entry = ctk.CTkEntry(
            form,
            height=36,
            placeholder_text="Enter first name",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.first_entry.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="Middle Name",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=4, column=0, sticky="w", padx=22, pady=(0, 4))
        self.middle_entry = ctk.CTkEntry(
            form,
            height=36,
            placeholder_text="Optional",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.middle_entry.grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="Last Name",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=6, column=0, sticky="w", padx=22, pady=(0, 4))
        self.last_entry = ctk.CTkEntry(
            form,
            height=36,
            placeholder_text="Enter last name",
            fg_color=theme.BG_SURFACE_ALT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            corner_radius=6,
        )
        self.last_entry.grid(row=7, column=0, sticky="ew", padx=22, pady=(0, 10))

        ctk.CTkLabel(
            form,
            text="Class",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=8, column=0, sticky="w", padx=22, pady=(0, 4))
        self.class_dropdown = ThemedDropdown(form, values=["Select Class"], height=36)
        self.class_dropdown.grid(row=9, column=0, sticky="ew", padx=22, pady=(0, 10))
        
    

        # profile photo state
        self.profile_photo_bytes: bytes | None = None
        self._photo_thumbnail = None

        ctk.CTkLabel(
            form,
            text="Profile Photo",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=10, column=0, sticky="w", padx=22, pady=(0, 4))
        self.photo_dropdown = ThemedDropdown(
            form,
            values=["Select Photo", "Take Photo", "Upload Photo"],
            command=self._on_photo_option_selected,
            height=36,
        )
        self.photo_dropdown.grid(row=11, column=0, sticky="ew", padx=22, pady=(0, 10))

        self.capture_button = ctk.CTkButton(
            form,
            text="Start Capture",
            command=self.handle_register_student,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=36,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.capture_button.grid(row=12, column=0, sticky="ew", padx=22, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(form)
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            form,
            text="Fill the form and click Start Capture.",
            text_color=theme.TEXT_SECONDARY,
            wraplength=420,
            justify="left",
        )
        self.status_label.grid(row=14, column=0, sticky="ew", padx=22, pady=(0, 14))

        self.refresh()

    def handle_register_student(self) -> None:
        if self._capture_busy:
            return

        if not self._classes:
            self.status_label.configure(text="Please add a class first", text_color=theme.DANGER)
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
                text_color=theme.DANGER,
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
                self.status_label.configure(text=message, text_color=theme.DANGER)
                self._notify(message, "error")
                return
        except Exception as e:
            self.status_label.configure(text=f"Failed to validate student ID: {e}", text_color=theme.DANGER)
            self._notify("Failed to validate student ID.", "error")
            return

        class_id = int(class_row["id"])
        if middle_name:
            display_name = f"{first_name} {middle_name} {last_name}"
        else:
            display_name = f"{first_name} {last_name}"

        self.progress_bar.grid(row=13, column=0, sticky="ew", padx=22, pady=(0, 6))
        self._open_capture_window(student_id, first_name, middle_name or None, last_name, display_name, class_id)

    def _open_capture_window(
        self,
        student_id: str,
        first_name: str,
        middle_name: str | None,
        last_name: str,
        display_name: str,
        class_id: int,
    ) -> None:
        """Open a live camera preview window and capture face images while showing progress."""
        import os as _os
        import queue as _queue
        from core.face_engine import capture_face_images as _capture

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Capturing — {display_name}")
        dlg.geometry("560x480")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        dlg.resizable(False, False)

        # Header
        ctk.CTkLabel(
            dlg,
            text=f"Capturing face images for {display_name}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white",
        ).pack(pady=(14, 4))

        count_label = ctk.CTkLabel(dlg, text="0 / 50 images captured", text_color=theme.TEXT_SECONDARY)
        count_label.pack(pady=(0, 6))

        # Camera feed
        video_label = ctk.CTkLabel(dlg, text="", fg_color=theme.BG_SURFACE_ALT)
        video_label.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # Progress bar
        prog = ctk.CTkProgressBar(dlg, width=500)
        prog.pack(padx=14, pady=(0, 6))
        prog.set(0)

        status_lbl = ctk.CTkLabel(dlg, text="Position your face in the frame...", text_color=theme.TEXT_SECONDARY)
        status_lbl.pack(pady=(0, 10))

        # shared state
        _stop = threading.Event()
        _frame_queue: _queue.Queue = _queue.Queue(maxsize=2)
        _progress_queue: _queue.Queue = _queue.Queue()
        _result: dict = {"captured": 0, "error": None, "done": False}

        cap_ref: list = [None]

        def _capture_worker():
            import os as _os2
            from pathlib import Path
            import cv2 as _cv2
            from core.face_engine import _ensure_dir, _CASCADE_PATH, _BASE

            folder_name = f"{str(student_id).zfill(3)}_{display_name}"
            save_dir = _os2.path.join(_BASE, 'dataset', str(class_id), folder_name)
            _ensure_dir(save_dir)

            existing = [f for f in _os2.listdir(save_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            max_idx = 0
            for fn in existing:
                try:
                    idx = int(_os2.path.splitext(fn)[0])
                    if idx > max_idx:
                        max_idx = idx
                except Exception:
                    pass
            next_idx = max_idx + 1

            face_cascade = _cv2.CascadeClassifier(_CASCADE_PATH)
            target = self._capture_target_count
            saved = 0
            error_msg = None

            try:
                cap = _cv2.VideoCapture(0)
                cap_ref[0] = cap
                if not cap.isOpened():
                    raise RuntimeError("Could not open webcam. Check camera permissions.")

                while saved < target and not _stop.is_set():
                    ret, frame = cap.read()
                    if not ret:
                        continue

                    gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY)
                    rects = face_cascade.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                    )

                    display_frame = frame.copy()
                    for (x, y, w, h) in rects:
                        _cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 200, 80), 2)

                    # push frame for preview
                    rgb = _cv2.cvtColor(display_frame, _cv2.COLOR_BGR2RGB)
                    while True:
                        try:
                            _frame_queue.put_nowait(rgb)
                            break
                        except _queue.Full:
                            try:
                                _frame_queue.get_nowait()
                            except _queue.Empty:
                                break

                    if len(rects) > 0:
                        x, y, w, h = max(rects, key=lambda r: r[2] * r[3])
                        pad = int(0.1 * max(w, h))
                        fh_f, fw_f = frame.shape[:2]
                        x1 = max(0, x - pad)
                        y1 = max(0, y - pad)
                        x2 = min(fw_f, x + w + pad)
                        y2 = min(fh_f, y + h + pad)
                        face_img = frame[y1:y2, x1:x2]
                        if face_img.size > 0:
                            out_path = _os2.path.join(save_dir, f"{next_idx:04d}.jpg")
                            _cv2.imwrite(out_path, face_img)
                            saved += 1
                            next_idx += 1
                            _progress_queue.put(saved)

            except Exception as exc:
                error_msg = str(exc)
            finally:
                try:
                    if cap_ref[0]:
                        cap_ref[0].release()
                except Exception:
                    pass
                _result["captured"] = saved
                _result["error"] = error_msg
                _result["done"] = True

        def _update_ui():
            # drain progress queue
            latest = None
            while True:
                try:
                    latest = _progress_queue.get_nowait()
                except _queue.Empty:
                    break
            if latest is not None:
                pct = min(latest / self._capture_target_count, 1.0)
                prog.set(pct)
                count_label.configure(text=f"{latest} / {self._capture_target_count} images captured")
                status_lbl.configure(text="Face detected — capturing..." if latest < self._capture_target_count else "Capture complete!")

            # update camera preview
            frame_data = None
            while True:
                try:
                    frame_data = _frame_queue.get_nowait()
                except _queue.Empty:
                    break
            if frame_data is not None and Image is not None:
                try:
                    pil = Image.fromarray(frame_data)
                    pil = pil.resize((500, 300))
                    tkimg = ctk.CTkImage(light_image=pil, size=(500, 300))
                    video_label.configure(image=tkimg)
                    video_label._tkimg = tkimg
                except Exception:
                    pass

            if _result["done"]:
                _on_capture_complete()
                return

            dlg.after(30, _update_ui)

        def _on_capture_complete():
            try:
                dlg.grab_release()
            except Exception:
                pass
            try:
                dlg.destroy()
            except Exception:
                pass

            if _result["error"]:
                self.status_label.configure(text=f"Capture failed: {_result['error']}", text_color=theme.DANGER)
                self._notify(f"Capture failed: {_result['error']}", "error")
                self._set_busy(False)
                return

            if not _result["captured"]:
                self.status_label.configure(text="No faces captured. Try again.", text_color=theme.DANGER)
                self._notify("No faces captured. Try again.", "error")
                self._set_busy(False)
                return

            # now register in DB and train — run in thread so UI stays responsive
            self._set_busy(True)
            self.status_label.configure(text="Saving student and training model...", text_color=theme.TEXT_SECONDARY)
            self.progress_bar.set(0.95)

            def _finish_worker():
                try:
                    add_student(
                        student_id, first_name, middle_name, last_name,
                        class_id, self.username or "system",
                        getattr(self, "profile_photo_bytes", None),
                    )
                    train_class_model(class_id)
                    log_action(
                        self.username or "system",
                        "REGISTER_STUDENT",
                        f"student_id={student_id}; class_id={class_id}",
                    )
                    self.after(0, self._on_register_success)
                except Exception as err:
                    try:
                        cleanup_student_dataset(student_id, class_id)
                    except Exception:
                        pass
                    self.after(0, lambda e=err: self._on_register_failure(e))
                finally:
                    self.after(0, lambda: self._set_busy(False))

            threading.Thread(target=_finish_worker, daemon=True).start()

        def _cancel():
            _stop.set()
            try:
                if cap_ref[0]:
                    cap_ref[0].release()
            except Exception:
                pass
            try:
                dlg.grab_release()
                dlg.destroy()
            except Exception:
                pass
            self._set_busy(False)
            self.status_label.configure(text="Capture cancelled.", text_color=theme.TEXT_SECONDARY)

        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        ctk.CTkButton(dlg, text="Cancel", fg_color=theme.BTN_DANGER, hover_color=theme.BTN_DANGER_HVR, command=_cancel).pack(pady=(0, 10))

        self._set_busy(True)
        self.status_label.configure(text="Camera window open — capturing...", text_color=theme.TEXT_SECONDARY)
        self.progress_bar.set(0)

        threading.Thread(target=_capture_worker, daemon=True).start()
        dlg.after(30, _update_ui)

    def _on_capture_progress(self, current: int, total: int) -> None:
        self.after(0, lambda: self._apply_progress(current, total))

    def _apply_progress(self, current: int, total: int) -> None:
        if total > 0:
            self.progress_bar.set(min(max(current / total, 0.0), 1.0))
        self.status_label.configure(
            text=f"Capturing image {current} of {total}",
            text_color=theme.TEXT_SECONDARY,
        )

    def _on_register_success(self) -> None:
        self.status_label.configure(
            text="Student registered and model updated successfully",
            text_color=theme.BTN_SUCCESS,
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
        self.status_label.configure(text=f"Registration failed: {error}", text_color=theme.DANGER)
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
            try:
                self.progress_bar.grid_forget()
            except Exception:
                pass

    def _label_for_class(self, row: dict) -> str:
        return f"{row.get('name', '')} - {row.get('section', '')}"

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
            self.status_label.configure(text=f"Failed to load classes: {error}", text_color=theme.DANGER)
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
            self.status_label.configure(text="Please add a class first", text_color=theme.DANGER)
            self.capture_button.configure(state="disabled")
        else:
            if not self._capture_busy:
                self.capture_button.configure(state="normal")
            self.status_label.configure(
                text="Fill the form and click Start Capture.",
                text_color=theme.TEXT_SECONDARY,
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

            video_label = ctk.CTkLabel(dlg, text="", fg_color=theme.BG_SURFACE_ALT)
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

            btn = ctk.CTkButton(dlg, text="Capture", command=do_capture, fg_color=theme.ACCENT)
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

    def _on_photo_option_selected(self, value: str) -> None:
        if value == "Take Photo":
            self._open_camera_capture_popup()
        elif value == "Upload Photo":
            self._upload_photo()

    def _set_profile_photo_bytes(self, data: bytes | None) -> None:
        self.profile_photo_bytes = data
        if data and Image is not None:
            try:
                img = Image.open(io.BytesIO(data))
                img.thumbnail((100, 100))
                self._photo_thumbnail = ImageTk.PhotoImage(img)
            except Exception:
                pass