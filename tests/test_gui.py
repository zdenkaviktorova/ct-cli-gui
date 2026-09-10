import importlib.machinery
import importlib.util
from pathlib import Path

GUI_PATH = Path(__file__).parents[1] / "ct_gui.pyw"
loader = importlib.machinery.SourceFileLoader("ct_gui", str(GUI_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ct_gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct_gui)

import ct_downloader  # noqa: E402

DOWNLOADER = str(GUI_PATH.parents[0] / "ct_downloader.py")


def _fake_base(monkeypatch):
    monkeypatch.setattr(
        ct_gui,
        "get_downloader_command",
        lambda: [str(ct_gui.get_console_python()), DOWNLOADER],
    )


# ---------------------------------------------------------------------------
# parse_urls
# ---------------------------------------------------------------------------


def test_parse_urls_newlines():
    assert ct_gui.parse_urls("a\nb\nc") == ["a", "b", "c"]


def test_parse_urls_commas_and_spaces():
    assert ct_gui.parse_urls("a, b  c,\n d") == ["a", "b", "c", "d"]


def test_parse_urls_empty():
    assert ct_gui.parse_urls("   \n  ") == []


# ---------------------------------------------------------------------------
# build_download_command
# ---------------------------------------------------------------------------


def test_build_download_command_without_quality(monkeypatch):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command("https://example.test/episode/123", "Highest Available")

    assert command[1] == DOWNLOADER
    assert command[-1] == "https://example.test/episode/123"
    assert "--quality" not in command


def test_build_download_command_with_quality(monkeypatch):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command("https://example.test/episode/123", "720p")

    assert "--quality" in command
    idx = command.index("--quality")
    assert command[idx + 1] == "720"


def test_build_download_command_with_download_mode(monkeypatch):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
    )

    assert "--mode" in command
    idx = command.index("--mode")
    assert command[idx + 1] == "subtitles"


def test_build_download_command_with_text_subtitle_format(monkeypatch):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
        "txt",
    )

    assert "--subtitle-format" in command
    idx = command.index("--subtitle-format")
    assert command[idx + 1] == "txt"


def test_build_download_command_srt_txt_maps_to_both(monkeypatch):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
        "srt,txt",
    )
    idx = command.index("--subtitle-format")
    assert command[idx + 1] == "both"


def test_build_download_command_subtitle_format_in_video_mode(monkeypatch):
    """Bug 2: subtitle format is emitted even in video mode."""
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "video",
        "srt,txt",
    )
    assert "--subtitle-format" in command
    idx = command.index("--subtitle-format")
    assert command[idx + 1] == "both"


def test_build_download_command_with_output_dir(monkeypatch):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        output_dir="/tmp/dest",
    )
    assert "--output-dir" in command
    idx = command.index("--output-dir")
    assert command[idx + 1] == "/tmp/dest"


def test_build_download_command_with_series_folders(monkeypatch):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        series_folders=True,
    )
    assert "--series-folders" in command


def test_build_download_command_multiple_urls(monkeypatch):
    _fake_base(monkeypatch)
    urls = [
        "https://example.test/episode/1",
        "https://example.test/episode/2",
    ]
    command = ct_gui.build_download_command(urls, "Highest Available")
    assert command[-2:] == urls


# ---------------------------------------------------------------------------
# get_downloader_command
# ---------------------------------------------------------------------------


def test_get_downloader_command_uses_configured_path(monkeypatch, tmp_path):
    downloader = tmp_path / "ct_downloader.py"
    downloader.write_text("")
    monkeypatch.setenv("CT_DOWNLOADER_PATH", str(downloader))
    monkeypatch.setattr(ct_gui, "get_console_python", lambda: Path("python"))

    assert ct_gui.get_downloader_command() == ["python", str(downloader)]


def test_get_downloader_command_uses_installed_cli(monkeypatch):
    monkeypatch.delenv("CT_DOWNLOADER_PATH", raising=False)
    monkeypatch.setattr(ct_gui.shutil, "which", lambda name: "/bin/ct-dlp")

    assert ct_gui.get_downloader_command() == ["/bin/ct-dlp"]


def test_get_downloader_command_reports_missing_configured_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CT_DOWNLOADER_PATH", str(tmp_path / "missing.py"))

    try:
        ct_gui.get_downloader_command()
    except FileNotFoundError as error:
        assert "Configured downloader was not found" in str(error)
    else:
        raise AssertionError("Expected missing configured downloader to fail")


# ---------------------------------------------------------------------------
# launch_download
# ---------------------------------------------------------------------------


def test_launch_download_uses_direct_process_when_no_linux_terminal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(ct_gui.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )

    ct_gui.launch_download(
        ["python", "ct_downloader.py", "https://example.test"], cwd=str(tmp_path)
    )

    # No terminal available -> fall back to running headless.
    assert calls == [
        (
            ["python", "ct_downloader.py", "https://example.test"],
            {"cwd": str(tmp_path)},
        )
    ]


def test_launch_download_falls_back_when_terminal_launch_fails(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(
        ct_gui.shutil,
        "which",
        lambda name: "/usr/bin/gnome-terminal" if name == "gnome-terminal" else None,
    )

    def popen(command, **options):
        # First call = terminal launch, raise to trigger fallback.
        if not calls:
            calls.append((command, options))
            raise OSError("no display")
        calls.append((command, options))

    monkeypatch.setattr(ct_gui.subprocess, "Popen", popen)

    ct_gui.launch_download(["python", "ct_downloader.py"], cwd=str(tmp_path))

    # Second (fallback) call runs the raw command headless.
    assert calls[-1][0] == ["python", "ct_downloader.py"]


def test_launch_download_gnome_terminal_uses_dash_and_pause(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(
        ct_gui.shutil,
        "which",
        lambda name: "/usr/bin/gnome-terminal" if name == "gnome-terminal" else None,
    )
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )

    ct_gui.launch_download(["python", "ct_downloader.py"], cwd=str(tmp_path))

    launched = calls[0][0]
    assert launched[0] == "gnome-terminal"
    assert launched[1] == "--"
    assert launched[2:4] == ["sh", "-c"]
    assert "python ct_downloader.py" in launched[4]
    assert "Press Enter to close" in launched[4]


def test_launch_download_xterm_style_uses_e_flag_and_pause(monkeypatch, tmp_path):
    """x-terminal-emulator (gnome-terminal.wrapper) must use -e, not --."""
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(
        ct_gui.shutil,
        "which",
        lambda name: "/usr/bin/x-terminal-emulator" if name == "x-terminal-emulator" else None,
    )
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )

    ct_gui.launch_download(["python", "ct_downloader.py"], cwd=str(tmp_path))

    launched = calls[0][0]
    assert launched[0] == "x-terminal-emulator"
    assert launched[1] == "-e"
    # The command must be preserved (regression: it used to be dropped via --).
    assert "python ct_downloader.py" in launched[2]
    assert "Press Enter to close" in launched[2]
    assert "--" not in launched


def test_launch_download_prefers_gnome_terminal_over_xterm_shim(monkeypatch, tmp_path):
    """When both exist, prefer gnome-terminal over the x-terminal-emulator shim."""
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(ct_gui.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )

    ct_gui.launch_download(["python", "ct_downloader.py"], cwd=str(tmp_path))

    assert calls[0][0][0] == "gnome-terminal"


def test_launch_download_konsole_uses_e_flag(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(
        ct_gui.shutil,
        "which",
        lambda name: "/usr/bin/konsole" if name == "konsole" else None,
    )
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )

    ct_gui.launch_download(["python", "ct_downloader.py"], cwd=str(tmp_path))

    launched = calls[0][0]
    assert launched[0] == "konsole"
    assert launched[1] == "-e"


def test_launch_download_uses_macos_terminal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "darwin")
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )

    ct_gui.launch_download(["python", "ct_downloader.py", "URL with spaces"], cwd=str(tmp_path))

    assert calls[0][0][0] == "osascript"
    assert "Terminal" in calls[0][0][2]
    assert "Press Enter to close" in calls[0][0][2]


def test_get_console_python_uses_python_on_windows(monkeypatch):
    monkeypatch.setattr(ct_gui.sys, "platform", "win32")
    monkeypatch.setattr(ct_gui.sys, "executable", "/Python/pythonw.exe")

    assert ct_gui.get_console_python().name == "python.exe"


def test_launch_download_uses_windows_console(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "win32")
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )

    ct_gui.launch_download(["python", "ct_downloader.py"], cwd=str(tmp_path))

    # Windows keeps the console open via cmd /k.
    assert calls[0][0][0] == "cmd"
    assert calls[0][0][1] == "/k"
    assert calls[0][1] == {
        "cwd": str(tmp_path),
        "creationflags": getattr(ct_gui.subprocess, "CREATE_NEW_CONSOLE", 0),
    }


# ---------------------------------------------------------------------------
# start_download (GUI widget stubs)
# ---------------------------------------------------------------------------


class _Text:
    def __init__(self, value):
        self.value = value
        self.cleared = False

    def get(self, *_args):
        return self.value

    def delete(self, *_args):
        self.cleared = True


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _setup_gui(monkeypatch, tmp_path, urls, mode="video", fmt="srt", organize=False):
    monkeypatch.setattr(ct_gui, "url_text", _Text(urls), raising=False)
    monkeypatch.setattr(ct_gui, "quality_var", _Value("Highest Available"), raising=False)
    monkeypatch.setattr(ct_gui, "mode_var", _Value(mode), raising=False)
    monkeypatch.setattr(ct_gui, "subtitle_format_var", _Value(fmt), raising=False)
    monkeypatch.setattr(ct_gui, "output_var", _Value(str(tmp_path)), raising=False)
    monkeypatch.setattr(ct_gui, "series_var", _Value(organize), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)


def test_start_download_ignores_empty_url(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "   \n  ")
    monkeypatch.setattr(
        ct_gui,
        "launch_download",
        lambda command, cwd: (_ for _ in ()).throw(AssertionError("not called")),
    )
    _fake_base(monkeypatch)

    ct_gui.start_download()


def test_start_download_launches_and_clears_url(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/video")
    _fake_base(monkeypatch)
    launched = []
    monkeypatch.setattr(ct_gui, "launch_download", lambda command, cwd: launched.append(command))

    ct_gui.start_download()

    assert launched[0][-1] == "https://example.test/video"
    assert ct_gui.url_text.cleared is True


def test_start_download_reports_launch_error(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/video")
    _fake_base(monkeypatch)
    errors = []
    monkeypatch.setattr(
        ct_gui,
        "launch_download",
        lambda command, cwd: (_ for _ in ()).throw(OSError("cannot launch")),
    )
    monkeypatch.setattr(
        ct_gui.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    ct_gui.start_download()

    assert errors == [("Unable to start download", "cannot launch")]


def test_start_download_includes_selected_mode(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/video", mode="subtitles")
    _fake_base(monkeypatch)
    launched = []
    monkeypatch.setattr(ct_gui, "launch_download", lambda command, cwd: launched.append(command))

    ct_gui.start_download()

    assert "--mode" in launched[0]
    idx = launched[0].index("--mode")
    assert launched[0][idx + 1] == "subtitles"


def test_start_download_includes_selected_subtitle_format(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/video", mode="subtitles", fmt="txt")
    _fake_base(monkeypatch)
    launched = []
    monkeypatch.setattr(ct_gui, "launch_download", lambda command, cwd: launched.append(command))

    ct_gui.start_download()

    idx = launched[0].index("--subtitle-format")
    assert launched[0][idx + 1] == "txt"


def test_start_download_includes_srt_txt_subtitle_format(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/video", mode="subtitles", fmt="srt,txt")
    _fake_base(monkeypatch)
    launched = []
    monkeypatch.setattr(ct_gui, "launch_download", lambda command, cwd: launched.append(command))

    ct_gui.start_download()

    idx = launched[0].index("--subtitle-format")
    assert launched[0][idx + 1] == "both"


def test_start_download_includes_output_dir(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/video")
    _fake_base(monkeypatch)
    launched = []
    monkeypatch.setattr(
        ct_gui, "launch_download", lambda command, cwd: launched.append((command, cwd))
    )

    ct_gui.start_download()

    command, cwd = launched[0]
    assert "--output-dir" in command
    assert cwd == str(tmp_path)


def test_start_download_includes_series_folders(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/video", organize=True)
    _fake_base(monkeypatch)
    launched = []
    monkeypatch.setattr(ct_gui, "launch_download", lambda command, cwd: launched.append(command))

    ct_gui.start_download()

    assert "--series-folders" in launched[0]


def test_start_download_multiple_urls(monkeypatch, tmp_path):
    _setup_gui(
        monkeypatch,
        tmp_path,
        "https://example.test/1\nhttps://example.test/2, https://example.test/3",
    )
    _fake_base(monkeypatch)
    launched = []
    monkeypatch.setattr(ct_gui, "launch_download", lambda command, cwd: launched.append(command))

    ct_gui.start_download()

    assert launched[0][-3:] == [
        "https://example.test/1",
        "https://example.test/2",
        "https://example.test/3",
    ]


# ---------------------------------------------------------------------------
# GUI <-> CLI contract tests (real parser)
# ---------------------------------------------------------------------------


def _gui_args(monkeypatch, urls, quality, mode, subtitle_format, output_dir=None, organize=False):
    _fake_base(monkeypatch)
    command = ct_gui.build_download_command(
        urls, quality, mode, subtitle_format, output_dir=output_dir, series_folders=organize
    )
    return command[2:]


def test_gui_srt_command_is_accepted_by_downloader_cli(monkeypatch):
    args = _gui_args(
        monkeypatch,
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "subtitles",
        "srt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.mode == "subtitles"
    assert parsed.subtitle_format == "srt"


def test_gui_txt_command_is_accepted_by_downloader_cli(monkeypatch):
    args = _gui_args(
        monkeypatch,
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "subtitles",
        "txt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.subtitle_format == "txt"


def test_gui_srt_txt_command_is_accepted_by_downloader_cli(monkeypatch):
    args = _gui_args(
        monkeypatch,
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "subtitles",
        "srt,txt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.subtitle_format == "both"


def test_gui_video_command_is_accepted_by_downloader_cli(monkeypatch):
    args = _gui_args(
        monkeypatch,
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "720p",
        "video",
        "srt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.mode == "video"
    assert parsed.quality == "720"


def test_gui_output_and_organize_accepted_by_cli(monkeypatch):
    args = _gui_args(
        monkeypatch,
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "video",
        "srt",
        output_dir="/tmp/dest",
        organize=True,
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.output_dir == "/tmp/dest"
    assert parsed.series_folders is True


def test_gui_multiple_urls_accepted_by_cli(monkeypatch):
    args = _gui_args(
        monkeypatch,
        [
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "https://www.ceskatelevize.cz/porady/123-show/12345678902/",
        ],
        "Highest Available",
        "video",
        "srt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert len(parsed.urls) == 2


# ---------------------------------------------------------------------------
# Frozen-mode tests (sys.frozen)
# ---------------------------------------------------------------------------


def test_get_downloader_command_returns_none_when_frozen(monkeypatch):
    monkeypatch.setattr(ct_gui.sys, "frozen", True, raising=False)
    assert ct_gui.get_downloader_command() is None


def test_build_download_command_returns_none_when_frozen(monkeypatch):
    monkeypatch.setattr(ct_gui.sys, "frozen", True, raising=False)
    result = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
        "txt",
    )
    assert result is None


def test_get_downloader_command_uses_script_when_not_frozen(monkeypatch):
    monkeypatch.delattr(ct_gui.sys, "frozen", raising=False)
    monkeypatch.delenv("CT_DOWNLOADER_PATH", raising=False)
    monkeypatch.setattr(ct_gui.shutil, "which", lambda name: None)
    monkeypatch.setattr(ct_gui, "DOWNLOADER_SCRIPT", GUI_PATH.parents[0] / "ct_downloader.py")

    command = ct_gui.get_downloader_command()
    assert command is not None
    assert "ct_downloader.py" in command[-1]


# ---------------------------------------------------------------------------
# _run_frozen_download tests
# ---------------------------------------------------------------------------


def test_run_frozen_download_dispatches_episode(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "process_url",
        lambda url, quality, mode, fmt, organize: called.append(
            (url, quality, mode, fmt, organize)
        ),
    )

    ct_gui._run_frozen_download(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "video",
        "srt",
        None,
        False,
    )

    assert called == [
        ("https://www.ceskatelevize.cz/porady/123-show/12345678901/", None, "video", "srt", False)
    ]


def test_run_frozen_download_subtitles_maps_srt_txt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "process_url",
        lambda url, quality, mode, fmt, organize: called.append((quality, mode, fmt, organize)),
    )

    ct_gui._run_frozen_download(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "720p",
        "subtitles",
        "srt,txt",
        None,
        True,
    )

    assert called == [("720", "subtitles", "both", True)]


def test_run_frozen_download_multiple_urls(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "process_url",
        lambda url, quality, mode, fmt, organize: called.append(url),
    )

    ct_gui._run_frozen_download(
        ["https://example.test/1", "https://example.test/2"],
        "Highest Available",
        "video",
        "srt",
        None,
        False,
    )

    assert called == ["https://example.test/1", "https://example.test/2"]


def test_run_frozen_download_output_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "dest"
    seen = []
    monkeypatch.setattr(
        ct_downloader,
        "process_url",
        lambda url, quality, mode, fmt, organize: seen.append(ct_gui.os.getcwd()),
    )

    original = ct_gui.os.getcwd()
    try:
        ct_gui._run_frozen_download(
            "https://example.test/1",
            "Highest Available",
            "video",
            "srt",
            str(target),
            False,
        )
    finally:
        ct_gui.os.chdir(original)

    assert target.is_dir()
    assert ct_gui.os.path.realpath(seen[0]) == ct_gui.os.path.realpath(str(target))


def test_start_download_uses_frozen_path(monkeypatch, tmp_path):
    _setup_gui(monkeypatch, tmp_path, "https://example.test/porady/123-show/12345678901/")
    monkeypatch.setattr(ct_gui.sys, "frozen", True, raising=False)

    frozen_calls = []
    monkeypatch.setattr(
        ct_gui,
        "_run_frozen_download",
        lambda urls, quality, mode, fmt, output_dir, organize: frozen_calls.append(urls),
    )

    ct_gui.start_download()

    assert len(frozen_calls) == 1
    assert frozen_calls[0] == ["https://example.test/porady/123-show/12345678901/"]


# ---------------------------------------------------------------------------
# _browse_output + _configure_style + main() UI construction (mocked Tk)
# ---------------------------------------------------------------------------


def test_browse_output_sets_folder(monkeypatch):
    captured = {}

    class _Var:
        def get(self):
            return ""

        def set(self, value):
            captured["value"] = value

    monkeypatch.setattr(ct_gui, "output_var", _Var(), raising=False)
    monkeypatch.setattr(ct_gui.filedialog, "askdirectory", lambda **k: "/chosen/dir")

    ct_gui._browse_output()

    assert captured["value"] == "/chosen/dir"


def test_browse_output_cancelled_keeps_value(monkeypatch):
    events = []

    class _Var:
        def get(self):
            return "/existing"

        def set(self, value):
            events.append(value)

    monkeypatch.setattr(ct_gui, "output_var", _Var(), raising=False)
    monkeypatch.setattr(ct_gui.filedialog, "askdirectory", lambda **k: "")

    ct_gui._browse_output()

    assert events == []


class _FakeWidget:
    """A permissive stand-in for any tk/ttk widget."""

    def __init__(self, *args, **kwargs):
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values.get(key)

    def pack(self, *a, **k):
        return self

    def grid(self, *a, **k):
        return self

    def configure(self, *a, **k):
        return self

    config = configure

    def columnconfigure(self, *a, **k):
        return self

    def rowconfigure(self, *a, **k):
        return self

    def bind(self, *a, **k):
        return self

    def title(self, *a, **k):
        return self

    def geometry(self, *a, **k):
        return self

    def minsize(self, *a, **k):
        return self

    def mainloop(self, *a, **k):
        return self

    def theme_names(self):
        return ("clam", "default")

    def theme_use(self, *a, **k):
        return "clam"

    def set(self, *a, **k):
        return self

    def map(self, *a, **k):
        return self

    def index(self, *a, **k):
        return "1.0"

    def yview(self, *a, **k):
        return self


def test_main_builds_ui(monkeypatch):
    """Exercise main() UI construction with a fully mocked tkinter."""
    monkeypatch.setattr(ct_gui.tk, "Tk", _FakeWidget)
    monkeypatch.setattr(ct_gui.tk, "Text", _FakeWidget)
    monkeypatch.setattr(ct_gui.tk, "Entry", _FakeWidget)
    monkeypatch.setattr(ct_gui.tk, "StringVar", _FakeWidget)
    monkeypatch.setattr(ct_gui.tk, "BooleanVar", _FakeWidget)
    monkeypatch.setattr(ct_gui.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(ct_gui.ttk, "Label", _FakeWidget)
    monkeypatch.setattr(ct_gui.ttk, "Button", _FakeWidget)
    monkeypatch.setattr(ct_gui.ttk, "Combobox", _FakeWidget)
    monkeypatch.setattr(ct_gui.ttk, "Checkbutton", _FakeWidget)
    monkeypatch.setattr(ct_gui.ttk, "Scrollbar", _FakeWidget)
    monkeypatch.setattr(ct_gui.ttk, "Style", _FakeWidget)

    # Should construct the whole UI and return once mainloop is a no-op.
    ct_gui.main()
