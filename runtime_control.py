import threading
import tkinter as tk

import customtkinter as ctk


class RuntimeControlWindow:
    def __init__(self):
        self._paused = threading.Event()
        self._closed = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="PylaRuntimeControl", daemon=True)
        self._thread.start()

    def is_paused(self):
        return self._paused.is_set()

    def close(self):
        self._closed.set()

    def _run(self):
        ctk.set_appearance_mode("dark")

        root = ctk.CTk()
        root.title("Pyla Control")
        root.geometry("280x170")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        status_var = tk.StringVar(value="Running")
        button_var = tk.StringVar(value="Pause Bot")

        card = ctk.CTkFrame(root, fg_color="#242424", corner_radius=8)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        title = ctk.CTkLabel(
            card,
            text="PylaAI Bot Control",
            text_color="#FFFFFF",
            font=("Arial", 17, "bold"),
        )
        title.pack(pady=(14, 2))

        status_label = ctk.CTkLabel(
            card,
            textvariable=status_var,
            text_color="#2FCE66",
            font=("Arial", 14, "bold"),
        )
        status_label.pack(pady=(0, 12))

        def refresh():
            paused = self._paused.is_set()
            status_var.set("Paused" if paused else "Running")
            button_var.set("Resume Bot" if paused else "Pause Bot")
            status_label.configure(text_color="#FFB23F" if paused else "#2FCE66")
            pause_button.configure(
                fg_color="#2F8F4E" if paused else "#AA2A2A",
                hover_color="#3DAF62" if paused else "#BB3A3A",
            )

        def toggle_pause():
            if self._paused.is_set():
                self._paused.clear()
            else:
                self._paused.set()
            refresh()

        def on_close():
            self._paused.clear()
            self._closed.set()
            root.destroy()

        pause_button = ctk.CTkButton(
            card,
            textvariable=button_var,
            command=toggle_pause,
            width=170,
            height=40,
            corner_radius=8,
            fg_color="#AA2A2A",
            hover_color="#BB3A3A",
            text_color="#FFFFFF",
            font=("Arial", 15, "bold"),
        )
        pause_button.pack(pady=(0, 8))

        hint = ctk.CTkLabel(
            card,
            text="Movement stops instantly while paused.",
            text_color="#BEBEBE",
            font=("Arial", 11),
        )
        hint.pack()

        root.protocol("WM_DELETE_WINDOW", on_close)

        def poll_closed():
            if self._closed.is_set():
                try:
                    root.destroy()
                except tk.TclError:
                    pass
                return
            root.after(250, poll_closed)

        refresh()
        poll_closed()
        root.mainloop()
