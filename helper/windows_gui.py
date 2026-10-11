"""Branded Tkinter GUI installer entry for PearPlay Windows setup.
Dedicated --windowed build artifact. Uses dependency injection for tests.
No production bypass flags, no raw paths/errors exposed to owner.
Shared receipt/lease/registry from windows_setup unchanged.
"""
import sys
import threading
# Tk is imported only when a real GUI is created.
from pathlib import Path
from typing import Callable, Optional, Any
import queue

# Use exact original asset
ASSET_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
ICON_PATH = ASSET_ROOT / 'assets' / 'brand' / 'pearplay.ico'
LOGO_PATH = ASSET_ROOT / 'assets' / 'store' / 'icon-1024.png'

PEARPLAY_COLORS = {
    'bg': '#111914',
    'accent': '#c1e67a',
    'text': '#ffffff',
    'success': '#4ade80',
    'error': '#f87171',
}

class PearPlayGUI:
    """One branded window with confirmation/progress/success/failure states.
    Background thread for operation. DI hooks for synthetic tests.
    """
    def __init__(self, title: str = "PearPlay Setup",
                 run_operation: Optional[Callable[[], dict]] = None,
                 on_success: Optional[Callable[[dict], None]] = None,
                 on_failure: Optional[Callable[[str], None]] = None):
        self.title = title
        self.run_operation = run_operation or install_or_upgrade
        self.on_success = on_success or (lambda r: None)
        self.on_failure = on_failure or (lambda e: None)
        self.root = None
        self.busy = False
        self.status_var = None
        self.progress = None
        self.result_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def _create_window(self):
        import tkinter as tk
        root = tk.Tk()
        root.title(self.title)
        root.configure(bg=PEARPLAY_COLORS['bg'])
        root.geometry("560x480")
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.resizable(False, False)
        root.iconbitmap(str(ICON_PATH))
        return root

    def _build_ui(self, root) -> None:
        import tkinter as tk
        from tkinter import ttk
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background=PEARPLAY_COLORS['bg'])
        style.configure('Title.TLabel', background=PEARPLAY_COLORS['bg'],
                        foreground=PEARPLAY_COLORS['text'], font=('Helvetica', 16, 'bold'))
        style.configure('Status.TLabel', background=PEARPLAY_COLORS['bg'],
                        foreground=PEARPLAY_COLORS['text'], font=('Helvetica', 11))
        style.configure('Accent.TButton', background=PEARPLAY_COLORS['accent'],
                        foreground=PEARPLAY_COLORS['text'])

        main = ttk.Frame(root, padding=20)
        main.pack(fill='both', expand=True)

        self.logo = tk.PhotoImage(file=str(LOGO_PATH)).subsample(16)
        ttk.Label(main, image=self.logo).pack()
        ttk.Label(main, text="PearPlay", style='Title.TLabel').pack(pady=(10, 5))
        ttk.Label(main, text="Chrome Helper Installer", style='Status.TLabel').pack()

        self.status_var = tk.StringVar(value="Install or update PearPlay for Chrome?\n\nClose casting first. This preview is unsigned. No administrator access, firewall changes or TV actions are requested. Saved TV pairing is kept.")
        status_label = ttk.Label(main, textvariable=self.status_var, style='Status.TLabel', wraplength=420)
        status_label.pack(pady=20)

        self.progress = ttk.Progressbar(main, mode='indeterminate', length=300)
        self.progress.pack(pady=10)

        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=15)
        self.install_btn = ttk.Button(btn_frame, text="Install / update", command=self._start_install, style='Accent.TButton')
        self.install_btn.pack(side='left', padx=10)
        self.close_btn = ttk.Button(btn_frame, text="Cancel", command=self._close)
        self.close_btn.pack(side='left')

    def _close(self):
        if not self.busy:
            self.root.destroy()

    def _start_install(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.install_btn.config(state='disabled')
        self.close_btn.config(state='disabled')
        self.progress.start(10)
        self.status_var.set("Installing... please wait")
        self._thread = threading.Thread(target=self._run_bg, daemon=False)
        self._thread.start()
        self.root.after(100, self._check_queue)

    def _run_bg(self) -> None:
        try:
            result = self.run_operation()
            self.result_queue.put(('success', result))
        except Exception:
            # Sanitized message only, no raw paths or stack
            safe = "Setup could not complete. Close Chrome and any PearPlay session, then try again. If it still fails, use the Windows setup guide for repair. Saved pairing is kept; no security settings were changed."
            self.result_queue.put(('failure', safe))

    def _check_queue(self) -> None:
        try:
            kind, data = self.result_queue.get_nowait()
            self.progress.stop()
            self.busy = False
            self.close_btn.config(state='normal', text='Close')
            if kind == 'success':
                self.status_var.set("PearPlay is connected to Chrome. Fully quit and reopen Chrome, then choose Check connection in PearPlay.\n\nNo TV action was taken. Saved pairing is kept.")
                self.on_success(data)
                # Keep instructions visible until the owner closes the window.
            else:
                self.status_var.set(data)
                self.on_failure(data)
                self.install_btn.config(state='normal', text='Try again')
                # Keep window open for actionable info, no generic messagebox
        except queue.Empty:
            self.root.after(100, self._check_queue)

    def run(self) -> None:
        self.root = self._create_window()
        self._build_ui(self.root)
        self.root.mainloop()


def install_or_upgrade():
    """Use the same receipt-based transaction and readback as console setup."""
    from helper.windows_setup import Win32, Files, manage
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        raise RuntimeError('requires_frozen_windows_setup')
    api = Win32()
    files = Files(api, api.local_appdata() / 'PearPlay')
    try:
        with files.directory(create=False):
            installed = 'install-receipt.json' in files.inventory()
    except FileNotFoundError:
        installed = False
    payload = (Path(sys._MEIPASS) / 'windows-payload.zip').read_bytes()
    return manage('upgrade' if installed else 'install', payload)


def main(argv=None):
    """Dedicated GUI entry for --windowed PyInstaller build."""
    gui = PearPlayGUI()
    gui.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
