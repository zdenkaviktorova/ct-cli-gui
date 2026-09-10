import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

SCRIPT_DIR = Path(__file__).resolve().parent
DOWNLOADER_SCRIPT = SCRIPT_DIR / "ct_downloader.py"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Videos"
DOWNLOAD_DIR = Path(os.environ.get("CT_DOWNLOAD_DIR", str(DEFAULT_DOWNLOAD_DIR))).expanduser()

# Modern minimalist palette
COLORS = {
    "bg": "#F7F7F8",
    "surface": "#FFFFFF",
    "text": "#1A1A1A",
    "muted": "#6B6B6B",
    "accent": "#E2001A",
    "accent_active": "#B30015",
    "border": "#D9D9DE",
}


def get_console_python():
    executable = Path(sys.executable)
    if sys.platform == "win32" and executable.name.lower() == "pythonw.exe":
        return executable.with_name("python.exe")
    return executable


def get_downloader_command():
    # When running as a frozen (PyInstaller) binary, invoke the downloader
    # in-process rather than shelling out to a separate .py script.
    if getattr(sys, "frozen", False):
        return None

    configured_path = os.environ.get("CT_DOWNLOADER_PATH")
    if configured_path:
        configured = Path(configured_path).expanduser()
        if not configured.is_file():
            raise FileNotFoundError(f"Configured downloader was not found: {configured}")
        return [str(get_console_python()), str(configured)]

    installed_command = shutil.which("ct-dlp")
    if installed_command:
        return [installed_command]

    installed_script = shutil.which("ct_downloader.py")
    if installed_script:
        return [str(get_console_python()), installed_script]

    if DOWNLOADER_SCRIPT.is_file():
        return [str(get_console_python()), str(DOWNLOADER_SCRIPT)]

    raise FileNotFoundError(
        "ct_downloader.py was not found. Set CT_DOWNLOADER_PATH or install ct-cli-gui."
    )


def parse_urls(raw_text):
    """Split pasted content into a list of URLs.

    Accepts newline-, comma-, and whitespace-separated content.
    """
    tokens = re.split(r"[\s,]+", raw_text.strip())
    return [token for token in tokens if token]


def _shell_command_with_pause(command, cwd):
    """Return a POSIX shell command string that runs *command* in *cwd* and
    pauses at the end so the terminal window stays open."""
    inner = " ".join(shlex.quote(argument) for argument in command)
    return (
        f"cd {shlex.quote(str(cwd))} && {inner}; "
        'echo; read -p "Press Enter to close..."'
    )


# Terminals that follow the xterm convention (command passed via -e).
_XTERM_STYLE_TERMINALS = ("x-terminal-emulator", "konsole", "xfce4-terminal")
# Terminals that accept a command after a -- separator.
_DASH_STYLE_TERMINALS = ("gnome-terminal",)


def _find_linux_terminal():
    for candidate in (
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "x-terminal-emulator",
    ):
        if shutil.which(candidate):
            return candidate
    return None


def launch_download(command, cwd):
    options = {"cwd": cwd}
    if sys.platform == "win32":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        # Keep the console open after the run so output/errors are visible.
        inner = subprocess.list2cmdline(command)
        launch = ["cmd", "/k", inner]
        subprocess.Popen(launch, **options)
        return
    if sys.platform == "darwin":
        shell_command = _shell_command_with_pause(command, cwd)
        launch = [
            "osascript",
            "-e",
            f'tell app "Terminal" to do script {json.dumps(shell_command)}',
        ]
        subprocess.Popen(launch, **options)
        return
    if sys.platform.startswith("linux"):
        terminal = _find_linux_terminal()
        if terminal:
            shell_command = _shell_command_with_pause(command, cwd)
            if terminal in _DASH_STYLE_TERMINALS:
                launch = [terminal, "--", "sh", "-c", shell_command]
            else:
                # xterm-style terminals (incl. the gnome-terminal.wrapper behind
                # x-terminal-emulator) expect the command via -e.
                launch = [terminal, "-e", f"sh -c {shlex.quote(shell_command)}"]
            try:
                subprocess.Popen(launch, **options)
                return
            except OSError:
                pass  # fall through to headless run
    # Fallback: no terminal available (or launch failed) — run headless so the
    # download still proceeds.
    subprocess.Popen(command, **options)



def build_download_command(
    urls,
    selected_quality,
    download_mode="video",
    subtitle_format="srt",
    output_dir=None,
    series_folders=False,
):
    """Build the downloader CLI command.

    *urls* may be a single URL string or a list of URLs.  Returns ``None`` in
    frozen mode (handled in-process).
    """
    base = get_downloader_command()
    if base is None:
        return None
    if isinstance(urls, str):
        urls = [urls]
    command = list(base)
    if download_mode != "video":
        command.extend(["--mode", download_mode])
    if subtitle_format == "srt,txt":
        command.extend(["--subtitle-format", "both"])
    elif subtitle_format == "txt":
        command.extend(["--subtitle-format", "txt"])
    if selected_quality != "Highest Available":
        command.extend(["--quality", selected_quality.replace("p", "")])
    if output_dir:
        command.extend(["--output-dir", str(output_dir)])
    if series_folders:
        command.append("--series-folders")
    command.extend(urls)
    return command


def _run_frozen_download(urls, quality, mode, subtitle_format, output_dir, series_folders):
    """Run the downloader in-process when the GUI is a frozen binary."""
    import ct_downloader

    if isinstance(urls, str):
        urls = [urls]
    normalized_quality = quality.lower().replace("p", "") if quality != "Highest Available" else None
    fmt = "both" if subtitle_format == "srt,txt" else subtitle_format

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        os.chdir(output_dir)

    for url in urls:
        ct_downloader.process_url(url, normalized_quality, mode, fmt, series_folders)


def start_download():
    raw = url_text.get("1.0", tk.END)
    urls = parse_urls(raw)
    selected_quality = quality_var.get()
    selected_mode = mode_var.get()
    selected_subtitle_format = subtitle_format_var.get()
    selected_output = output_var.get().strip() or str(DOWNLOAD_DIR)
    organize = bool(series_var.get())

    if not urls:
        return

    output_path = Path(selected_output).expanduser()
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        command = build_download_command(
            urls,
            selected_quality,
            selected_mode,
            selected_subtitle_format,
            output_dir=str(output_path),
            series_folders=organize,
        )
        if command is None:
            original_dir = os.getcwd()
            try:
                _run_frozen_download(
                    urls,
                    selected_quality,
                    selected_mode,
                    selected_subtitle_format,
                    str(output_path),
                    organize,
                )
            finally:
                os.chdir(original_dir)
        else:
            launch_download(command, cwd=str(output_path))
    except OSError as error:
        messagebox.showerror("Unable to start download", str(error))
        return

    url_text.delete("1.0", tk.END)


def _browse_output():
    chosen = filedialog.askdirectory(initialdir=output_var.get() or str(DOWNLOAD_DIR))
    if chosen:
        output_var.set(chosen)


def _configure_style():
    style = ttk.Style()
    with_theme = "clam" if "clam" in style.theme_names() else style.theme_use()
    style.theme_use(with_theme)

    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Card.TFrame", background=COLORS["surface"])
    style.configure(
        "TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "Muted.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Title.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=("Segoe UI", 15, "bold"),
    )
    style.configure(
        "TCheckbutton",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=("Segoe UI", 10),
    )
    style.configure("TCombobox", font=("Segoe UI", 10))
    style.configure(
        "Accent.TButton",
        font=("Segoe UI", 11, "bold"),
        foreground="#FFFFFF",
        background=COLORS["accent"],
        borderwidth=0,
        focusthickness=0,
        padding=(10, 8),
    )
    style.map(
        "Accent.TButton",
        background=[("active", COLORS["accent_active"]), ("pressed", COLORS["accent_active"])],
        foreground=[("disabled", "#EEEEEE")],
    )
    style.configure("Ghost.TButton", font=("Segoe UI", 9), padding=(8, 4))
    return style


def main():
    global quality_var, url_text, mode_var, subtitle_format_var, output_var, series_var

    root = tk.Tk()
    root.title("ČT Downloader")
    root.geometry("620x520")
    root.minsize(520, 460)
    root.configure(bg=COLORS["bg"])

    _configure_style()

    container = ttk.Frame(root, style="TFrame", padding=24)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)

    ttk.Label(container, text="Česká televize Downloader", style="Title.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, 2)
    )
    ttk.Label(
        container,
        text="Paste one or more iVysílání URLs (newline, comma, or space separated).",
        style="Muted.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(0, 12))

    # --- URLs (multi-line, scrollable) ---
    url_frame = ttk.Frame(container, style="TFrame")
    url_frame.grid(row=2, column=0, sticky="nsew")
    url_frame.columnconfigure(0, weight=1)
    url_frame.rowconfigure(0, weight=1)
    container.rowconfigure(2, weight=1)

    url_text = tk.Text(
        url_frame,
        height=4,
        wrap="none",
        font=("Segoe UI", 10),
        relief="flat",
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        bg=COLORS["surface"],
        fg=COLORS["text"],
        insertbackground=COLORS["text"],
        padx=8,
        pady=6,
    )
    url_text.grid(row=0, column=0, sticky="nsew")
    url_scroll = ttk.Scrollbar(url_frame, orient="vertical", command=url_text.yview)
    url_text.configure(yscrollcommand=url_scroll.set)
    url_scroll.grid(row=0, column=1, sticky="ns")

    def _grow_url_box(_event=None):
        line_count = int(url_text.index("end-1c").split(".")[0])
        url_text.configure(height=max(4, min(line_count, 12)))

    url_text.bind("<KeyRelease>", _grow_url_box)

    # --- Destination folder ---
    dest_frame = ttk.Frame(container, style="TFrame")
    dest_frame.grid(row=3, column=0, sticky="ew", pady=(14, 0))
    dest_frame.columnconfigure(0, weight=1)
    ttk.Label(dest_frame, text="Destination folder").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
    )
    output_var = tk.StringVar(value=str(DOWNLOAD_DIR))
    dest_entry = tk.Entry(
        dest_frame,
        textvariable=output_var,
        font=("Segoe UI", 10),
        relief="flat",
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        bg=COLORS["surface"],
        fg=COLORS["text"],
    )
    dest_entry.grid(row=1, column=0, sticky="ew", ipady=5)
    ttk.Button(dest_frame, text="Browse…", style="Ghost.TButton", command=_browse_output).grid(
        row=1, column=1, sticky="e", padx=(8, 0)
    )

    # --- Options row ---
    options = ttk.Frame(container, style="TFrame")
    options.grid(row=4, column=0, sticky="ew", pady=(14, 0))
    for col in range(3):
        options.columnconfigure(col, weight=1)

    ttk.Label(options, text="Quality").grid(row=0, column=0, sticky="w")
    quality_var = tk.StringVar(value="Highest Available")
    quality_dropdown = ttk.Combobox(
        options, textvariable=quality_var, state="readonly", font=("Segoe UI", 9), width=16
    )
    quality_dropdown["values"] = ("Highest Available", "1080p", "720p", "540p", "360p")
    quality_dropdown.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(2, 0))

    ttk.Label(options, text="Mode").grid(row=0, column=1, sticky="w")
    mode_var = tk.StringVar(value="video")
    mode_dropdown = ttk.Combobox(
        options, textvariable=mode_var, state="readonly", font=("Segoe UI", 9), width=16
    )
    mode_dropdown["values"] = ("video", "subtitles")
    mode_dropdown.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(2, 0))

    ttk.Label(options, text="Subtitle format").grid(row=0, column=2, sticky="w")
    subtitle_format_var = tk.StringVar(value="srt")
    subtitle_format_dropdown = ttk.Combobox(
        options, textvariable=subtitle_format_var, state="readonly", font=("Segoe UI", 9), width=16
    )
    subtitle_format_dropdown["values"] = ("srt", "txt", "srt,txt")
    subtitle_format_dropdown.grid(row=1, column=2, sticky="ew", pady=(2, 0))

    # --- Organize checkbox (default OFF) ---
    series_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        container,
        text="Organize into series / season folders",
        variable=series_var,
    ).grid(row=5, column=0, sticky="w", pady=(16, 0))

    # --- Download button ---
    ttk.Button(
        container,
        text="Download",
        style="Accent.TButton",
        command=start_download,
    ).grid(row=6, column=0, sticky="ew", pady=(20, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
