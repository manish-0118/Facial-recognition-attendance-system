import customtkinter as ctk


class NotificationManager:
    def __init__(
        self,
        master: ctk.CTk,
        success_color: str,
        success_text_color: str,
        error_color: str,
        error_text_color: str,
    ) -> None:
        self.master = master
        self.success_color = success_color
        self.success_text_color = success_text_color
        self.error_color = error_color
        self.error_text_color = error_text_color
        self.banner_after_id: str | None = None
        self.slide_after_id: str | None = None

        self.banner = ctk.CTkFrame(master, fg_color=success_color, corner_radius=0)
        self.banner.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(
            self.banner,
            text="",
            text_color=success_text_color,
            font=ctk.CTkFont(size=14, weight="bold"),
            justify="center",
        )
        self.label.grid(row=0, column=0, padx=18, pady=10, sticky="ew")

    def show(self, message: str, kind: str = "success") -> None:
        if self.banner_after_id is not None:
            self.master.after_cancel(self.banner_after_id)
            self.banner_after_id = None
        if self.slide_after_id is not None:
            self.master.after_cancel(self.slide_after_id)
            self.slide_after_id = None

        if kind == "error":
            background = self.error_color
            text_color = self.error_text_color
        else:
            background = self.success_color
            text_color = self.success_text_color

        self.banner.configure(fg_color=background)
        self.label.configure(text=message, text_color=text_color)
        self.banner.place(relx=1.0, x=-18, y=18, anchor="ne")
        self.banner.lift()
        self.banner.update_idletasks()
        self.banner_after_id = self.master.after(3000, self._slide_out)

    def _slide_out(self) -> None:
        place_info = self.banner.place_info()
        if not place_info:
            self.banner_after_id = None
            self.slide_after_id = None
            return

        current_x = int(place_info.get("x", -18))
        next_x = current_x + 26
        banner_width = max(self.banner.winfo_width(), 1)
        if next_x >= banner_width + 40:
            self.banner.place_forget()
            self.banner_after_id = None
            self.slide_after_id = None
            return

        self.banner.place_configure(x=next_x)
        self.slide_after_id = self.master.after(16, self._slide_out)
