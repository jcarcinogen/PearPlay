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

ACTIONS = {
    'auto': ('Install / update', 'Install or update the helper and connect Chrome.'),
    'repair': ('Repair installation', 'Restore missing owned helper files and reconnect Chrome. Changed or unfamiliar files are not overwritten.'),
    'connect': ('Connect Chrome', 'Connect Chrome to the installed helper. No TV action is taken.'),
    'disconnect': ('Disconnect Chrome', 'Disconnect Chrome. Helper files and saved pairing remain.'),
    'uninstall': ('Remove helper', 'Disconnect Chrome and remove unchanged helper-owned files. Changed or unfamiliar files and saved pairing remain.'),
}
SAFE_ERROR = ('Setup could not complete. Close Chrome and any PearPlay session, then try again. '
              'If it still fails, consult the Windows setup guide. Saved TV pairing is kept; '
              'no security settings were changed. An interrupted transaction may require repair.')


def result_text(result):
    action = result.get('action')
    if action in ('install', 'upgrade', 'repair', 'connect'):
        text = 'Chrome registration is ready. Fully quit and reopen Chrome, then choose Check connection in PearPlay to verify the connection.'
    elif action == 'disconnect':
        text = 'Chrome is disconnected. Fully quit and reopen Chrome. Helper files remain installed.'
    elif action == 'uninstall':
        text = 'The removal operation finished. Chrome is disconnected. Unchanged helper-owned files were removed.'
    else:
        raise ValueError('unexpected_setup_result')
    if result.get('preserved'):
        text += '\n\nChanged or unfamiliar files were preserved; removal may be incomplete. Consult the Windows setup guide before deleting anything manually.'
    return text + '\n\nSaved TV pairing is kept. No TV action or security-setting change was made.'


class PearPlayGUI:
    """One branded window with confirmation/progress/success/failure states.
    Background thread for operation. DI hooks for synthetic tests.
    """
    def __init__(self, title: str = "PearPlay Setup",
                 run_operation: Optional[Callable[[], dict]] = None,
                 on_success: Optional[Callable[[dict], None]] = None,
                 on_failure: Optional[Callable[[str], None]] = None,
                 *, installed_host=False, initial_action=None, notice=None):
        self.title = title
        self._custom_operation = run_operation
        self.actions = ('connect', 'disconnect') if installed_host else tuple(ACTIONS)
        self.action = initial_action if initial_action in self.actions else self.actions[0]
        self.notice = notice
        self.confirming = False
        self.exit_code = 0
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
        root.geometry("600x690")
        root.report_callback_exception = self._callback_error
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
                        foreground='#15220d')
        style.configure('TRadiobutton', background=PEARPLAY_COLORS['bg'], foreground=PEARPLAY_COLORS['text'])

        main = ttk.Frame(root, padding=20)
        main.pack(fill='both', expand=True)

        self.logo = tk.PhotoImage(file=str(LOGO_PATH)).subsample(16)
        ttk.Label(main, image=self.logo).pack()
        ttk.Label(main, text="PearPlay", style='Title.TLabel').pack(pady=(10, 5))
        ttk.Label(main, text="Chrome Helper Installer", style='Status.TLabel').pack()

        self.action_var = tk.StringVar(value=self.action)
        self.action_buttons = []
        choices = ttk.Frame(main)
        choices.pack(anchor='w', pady=12)
        for key in self.actions:
            button = ttk.Radiobutton(choices, text=ACTIONS[key][0], value=key, variable=self.action_var, command=self._select_action)
            button.pack(anchor='w', pady=3)
            self.action_buttons.append(button)
        self.status_var = tk.StringVar(value=self.notice or self._instructions())
        status_label = ttk.Label(main, textvariable=self.status_var, style='Status.TLabel', wraplength=520)
        status_label.pack(pady=20)

        self.progress = ttk.Progressbar(main, mode='indeterminate', length=300)
        self.progress.pack(pady=10)

        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=15)
        self.install_btn = ttk.Button(btn_frame, text="Continue", command=self._start_install, style='Accent.TButton')
        self.install_btn.pack(side='left', padx=10)
        self.close_btn = ttk.Button(btn_frame, text="Cancel", command=self._close)
        self.close_btn.pack(side='left')

    def _instructions(self):
        return ACTIONS[self.action][1] + '\n\nEnd casting and fully close Chrome first. This build is unsigned. Saved TV pairing is kept. No administrator access or firewall changes are requested.'

    def _select_action(self):
        if self.busy:
            return
        self.action = self.action_var.get()
        self.confirming = False
        self.status_var.set(self._instructions())
        self.install_btn.config(state='normal', text='Continue')

    def _callback_error(self, *_):
        self.exit_code = 1
        if self.status_var is not None:
            self.status_var.set(SAFE_ERROR)
        # A live transaction stays busy and close-protected.

    def _close(self):
        if not self.busy:
            self.root.destroy()

    def _start_install(self) -> None:
        if self.busy:
            return
        if not self.confirming:
            self.confirming = True
            self.status_var.set('Confirm: ' + ACTIONS[self.action][0] + '?\n\n' + self._instructions())
            self.install_btn.config(text=ACTIONS[self.action][0] + ' now')
            return
        self.busy = True
        self.run_operation = self._custom_operation or (lambda: perform_action(self.action))
        for button in self.action_buttons:
            button.config(state='disabled')
        self.install_btn.config(state='disabled')
        self.close_btn.config(state='disabled')
        self.progress.start(10)
        self.status_var.set("Applying your selected change… please wait")
        self._thread = threading.Thread(target=self._run_bg, daemon=False)
        self._thread.start()
        self.root.after(100, self._check_queue)

    def _run_bg(self) -> None:
        try:
            result = self.run_operation()
            result_text(result)  # Reject malformed results before showing success.
            self.result_queue.put(('success', result))
        except Exception:
            # Sanitized message only, no raw paths or stack
            safe = SAFE_ERROR
            self.result_queue.put(('failure', safe))

    def _check_queue(self) -> None:
        try:
            kind, data = self.result_queue.get_nowait()
            self.progress.stop()
            self.busy = False
            self.confirming = False
            for button in self.action_buttons:
                button.config(state='normal')
            self.install_btn.config(state='normal', text='Continue')
            self.close_btn.config(state='normal', text='Close')
            if kind == 'success':
                self.status_var.set(result_text(data))
                self.on_success(data)
                # Keep instructions visible until the owner closes the window.
            else:
                self.exit_code = 1
                self.status_var.set(data)
                self.on_failure(data)
                self.install_btn.config(state='normal', text='Continue')
                # Keep window open for actionable info, no generic messagebox
        except queue.Empty:
            self.root.after(100, self._check_queue)

    def run(self) -> None:
        self.root = self._create_window()
        self._build_ui(self.root)
        self.root.mainloop()
        return self.exit_code


def perform_action(action):
    """Use the unchanged receipt-based transaction; no GUI policy bypass."""
    from helper.windows_setup import Win32, Files, manage
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        raise RuntimeError('requires_frozen_windows_setup')
    if action == 'auto':
        api = Win32()
        files = Files(api, api.local_appdata() / 'PearPlay')
        try:
            with files.directory(create=False):
                installed = 'install-receipt.json' in files.inventory()
        except FileNotFoundError:
            installed = False
        action = 'upgrade' if installed else 'install'
    if action not in ('install', 'upgrade', 'repair', 'connect', 'disconnect', 'uninstall'):
        raise ValueError('invalid_setup_action')
    payload = (Path(sys._MEIPASS) / 'windows-payload.zip').read_bytes() if action in ('install', 'upgrade', 'repair') else None
    return manage(action, payload)


def install_or_upgrade():
    return perform_action('auto')


def show_setup(**kwargs):
    return PearPlayGUI(**kwargs).run()


def main(argv=None):
    """Dedicated GUI entry for --windowed PyInstaller build."""
    from helper.windows_setup import safe_main as setup_main
    return setup_main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
