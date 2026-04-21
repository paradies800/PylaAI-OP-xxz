import threading
import tkinter as tk


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
        root = tk.Tk()
        root.title("Pyla Control")
        root.geometry("230x120")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        status_var = tk.StringVar(value="Running")
        button_var = tk.StringVar(value="Pause")

        def refresh():
            paused = self._paused.is_set()
            status_var.set("Paused" if paused else "Running")
            button_var.set("Resume" if paused else "Pause")
            status_label.configure(fg="#d98b1f" if paused else "#2f9e44")
            pause_button.configure(bg="#2f9e44" if paused else "#aa2a2a")

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

        root.protocol("WM_DELETE_WINDOW", on_close)

        title = tk.Label(root, text="PylaAI Bot Control", font=("Arial", 12, "bold"))
        title.pack(pady=(10, 4))

        status_label = tk.Label(root, textvariable=status_var, font=("Arial", 11, "bold"), fg="#2f9e44")
        status_label.pack(pady=(0, 8))

        pause_button = tk.Button(
            root,
            textvariable=button_var,
            command=toggle_pause,
            width=14,
            height=1,
            bg="#aa2a2a",
            fg="white",
            activebackground="#bb3a3a",
            activeforeground="white",
            relief="flat",
            font=("Arial", 11, "bold"),
        )
        pause_button.pack()

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
