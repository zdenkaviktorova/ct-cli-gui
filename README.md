# Česká televize (iVysílání) Downloader 📺

A cross-platform Python toolkit (CLI + GUI) for downloading high-quality, DRM-free shows and documentaries from the Česká televize (iVysílání) archive.

This project bypasses recent site API changes (which break standard extractors) by directly querying the official backend to retrieve raw MPEG-DASH streams. It processes the video, audio, subtitles, and artwork to create clean, Plex-ready media files.

## ✨ Features

* **Plex/Jellyfin Ready:** Automatically parses webpage titles to generate clean `Series - S1E0X - Episode Title.mp4` filenames.
* **Batch Downloading:** Paste a master series link to automatically scrape and download all available episodes sequentially.
* **Smart "Skip Existing":** Checks your local directory and instantly skips episodes you've already downloaded.
* **Automatic Subtitles:** Downloads official Czech closed captions, silently converts them from web `.vtt` to standard `.srt`, and soft-embeds them directly into the `.mp4` file (while keeping the external `.srt` file for media servers).
* **Artwork Fetching:** Scrapes and saves the official high-resolution episode poster as a `.jpg`.
* **Quality Selection:** Choose your maximum resolution limit (1080p, 720p, 540p, 360p) to save hard drive space.
* **Subtitle and Transcript Downloads:** Download only the available subtitles without downloading the video. Subtitles can be saved as `.srt`, plain-text `.txt`, or both.
* **Two Interfaces:** Includes a desktop GUI and command-line wrappers for Windows, Linux, and macOS.
* **Standalone Binaries:** Self-contained executables for Linux, macOS, and Windows (AMD64 and ARM64) that bundle Python, yt-dlp, and ffmpeg — no installation required.

## 🛠️ Prerequisites

To run this tool, you need the following installed and accessible in your `PATH`:
1. **Python 3.9 or newer**
2. **`yt-dlp`** (The core downloading engine)
3. **`ffmpeg`** (Required to merge DASH video/audio streams and embed subtitles)
4. **Tkinter** (required by the GUI; on Debian/Ubuntu install `python3-tk`)

The GUI uses the standard Python Tkinter library. On macOS and Windows it is
normally included with the official Python installer. Linux distributions may
provide it as a separate package.

Python runtime dependencies are listed in `requirements.txt`.

## 🚀 Installation & Setup

Follow the procedure for your operating system. Keep these files together in
one installation directory:

```text
ct_gui.pyw
ct_downloader.py
ct-dlp.bat    # Windows
ct-dlp        # Linux/macOS
```

The GUI normally uses a `ct-dlp` command installed on `PATH`, or the
`ct_downloader.py` file next to `ct_gui.pyw`. If the GUI and downloader are
stored in different directories, install the package/CLI or configure the
script path explicitly before starting the GUI:

```powershell
$env:CT_DOWNLOADER_PATH = "C:\Path\to\ct_downloader.py"
py .\ct_gui.pyw
```

On Windows, the Python Scripts directory containing `ct-dlp.exe` or
`ct_downloader.py` must also be included in `PATH`.

### Windows

1. Install Python 3.9 or newer from [python.org](https://www.python.org/downloads/windows/).
   During setup, enable **Add Python to PATH**.
2. Install `yt-dlp`:
   ```powershell
   py -m pip install --upgrade -r requirements.txt
   ```
3. Install `ffmpeg` and add its `bin` directory to `PATH`.
4. Download or clone this repository, then open PowerShell in its directory.
5. Run the GUI by double-clicking `ct_gui.pyw`, or create a desktop shortcut.
6. To use the CLI, add the repository directory to `PATH`, then run:
   ```powershell
   .\ct-dlp.bat "https://www.ceskatelevize.cz/porady/..."
   ```

### Linux

1. Install Python, Tkinter, and FFmpeg using your distribution's package manager.
   On Debian or Ubuntu:
   ```sh
   sudo apt update
   sudo apt install python3 python3-tk python3-pip ffmpeg
   ```
2. Install `yt-dlp`:
   ```sh
   python3 -m pip install --user --upgrade -r requirements.txt
   ```
3. Download or clone this repository, then open a terminal in its directory.
4. Make the CLI launcher executable:
   ```sh
   chmod +x ct-dlp
   ```
5. Start the GUI:
   ```sh
   python3 ct_gui.pyw
   ```
6. Run the CLI:
   ```sh
   ./ct-dlp "https://www.ceskatelevize.cz/porady/..."
   ```

### macOS

1. Install Python 3.9 or newer from [python.org](https://www.python.org/downloads/macos/)
   or with Homebrew:
   ```sh
   brew install python
   ```
2. Install FFmpeg with Homebrew:
   ```sh
   brew install ffmpeg
   ```
3. Install `yt-dlp`:
   ```sh
   python3 -m pip install --user --upgrade -r requirements.txt
   ```
4. Download or clone this repository, then open Terminal in its directory.
5. Make the CLI launcher executable:
   ```sh
   chmod +x ct-dlp
   ```
6. Start the GUI:
   ```sh
   python3 ct_gui.pyw
   ```
7. Run the CLI:
   ```sh
   ./ct-dlp "https://www.ceskatelevize.cz/porady/..."
   ```

### Optional download directory

The default output directory is the current user's `Videos` folder. Set
`CT_DOWNLOAD_DIR` before starting the GUI to choose another location:

```powershell
# Windows PowerShell
$env:CT_DOWNLOAD_DIR = "D:\Media\Ceska televize"
py .\ct_gui.pyw
```

```sh
# Linux/macOS
export CT_DOWNLOAD_DIR="$HOME/Videos/Ceska televize"
python3 ct_gui.pyw
```

## 📦 Install the CLI from PyPI

The command-line downloader can be installed as a Python package:

```sh
python -m pip install ct-cli-gui
ct-dlp "https://www.ceskatelevize.cz/porady/..."
```

This package installs the `ct-dlp` CLI and its `yt-dlp` dependency. It does
not install the Tkinter GUI or FFmpeg; install Tkinter and FFmpeg through your
operating system and use `ct_gui.pyw` from the repository for the desktop GUI.

To publish a new package version, update the `version` field in `pyproject.toml`,
create a matching tag such as `v1.0.1`, and push the tag. The package workflow
builds the wheel and source distribution and publishes them to PyPI using
trusted publishing. Configure a PyPI project named `ct-cli-gui` and a
repository publishing environment named `pypi` before the first release.

## 🔧 Standalone binaries (no Python required)

Self-contained executables that bundle Python, yt-dlp, and ffmpeg are available
from the [GitHub Releases](../../releases) page. Download the binary for your
platform and run it directly — no installation needed.

| Platform | CLI binary | GUI binary |
|---|---|---|
| Linux AMD64 | `ct-dlp-linux-amd64` | `ct-gui-linux-amd64` |
| Linux ARM64 | `ct-dlp-linux-arm64` | `ct-gui-linux-arm64` |
| macOS Apple Silicon | `ct-dlp-macos-arm64` | `ct-gui-macos-arm64` |
| Windows AMD64 | `ct-dlp-windows-amd64.exe` | `ct-gui-windows-amd64.exe` |

> **Note:** macOS Intel (x86_64) binaries are not available — GitHub-hosted
> Intel-Mac runners are unavailable. Intel Mac users can install via PyPI
> (`pip install ct-cli-gui`) or run from source; the Apple Silicon binary
> also works on Intel Macs via Rosetta 2.
>
> Binaries are unsigned and may trigger Gatekeeper (macOS) or SmartScreen
> (Windows) warnings on first run. On macOS, right-click → **Open**. On
> Windows, click **More info** → **Run anyway**.

## 💻 Usage

There are three ways to use this project. All three are fully supported:

### Option 1: Run from source (local Python interpreter)

Clone the repository, install runtime dependencies (`requirements.txt`), and
ensure `yt-dlp` and `ffmpeg` are on your `PATH`:

```sh
python ct_gui.pyw            # Desktop GUI
python ct_downloader.py URL  # CLI directly
```

The desktop GUI lets you paste **multiple URLs** (newline-, comma-, or
space-separated), choose a **destination folder**, pick quality / mode /
subtitle format, and toggle **series/season folder organization**.

Shell wrappers are provided for convenience:

```sh
./ct-dlp URL       # Linux/macOS — thin sh wrapper that calls python ct_downloader.py
ct-dlp.bat URL     # Windows — thin batch wrapper
```

> **Note:** `ct-dlp` and `ct-dlp.bat` are shell launcher scripts, not Python
> files. Invoke them directly (not via `python`).

### Option 2: Install from PyPI

```sh
pip install ct-cli-gui
ct-dlp URL
```

Provides the `ct-dlp` command. Requires `ffmpeg` on `PATH`.

### Option 3: Standalone binaries

Download from the [Releases](../../releases) page and run directly — no
Python, yt-dlp, or ffmpeg installation required (all bundled).

**Download a single episode:**
```text
# Windows
ct-dlp.bat "https://www.ceskatelevize.cz/porady/11248773911-habsburkove/215562260670001/"

# Linux/macOS
ct-dlp "https://www.ceskatelevize.cz/porady/11248773911-habsburkove/215562260670001/"
```

**Download only subtitles:**
```text
ct-dlp --mode subtitles "https://www.ceskatelevize.cz/porady/..."
ct-dlp --subtitles-only "https://www.ceskatelevize.cz/porady/..."
ct-dlp --mode subtitles --subtitle-format txt "https://www.ceskatelevize.cz/porady/..."
ct-dlp --mode subtitles --subtitle-format both "https://www.ceskatelevize.cz/porady/..."
```

The `--subtitles-only` alias is also available. These options work for both
episode and series URLs and skip media and poster downloads.

The `--subtitle-format` flag controls which subtitle files are saved. It now
applies to **video downloads too** (not only subtitles-only mode):

| Mode | `--subtitle-format` | `.mp4` (embedded) | external `.srt` | external `.txt` |
|---|---|---|---|---|
| video | `srt` (default) | ✅ | ✅ | ❌ |
| video | `srt,txt` / `both` | ✅ | ✅ | ✅ |
| video | `txt` | ✅ | ❌ | ✅ |
| subtitles | `srt` | — | ✅ | ❌ |
| subtitles | `srt,txt` / `both` | — | ✅ | ✅ |
| subtitles | `txt` | — | ❌ | ✅ |

If subtitles are unavailable, the downloader reports that episode and
continues processing the remaining episodes in a series.

**Choose an output directory:**
```text
ct-dlp -o "/path/to/downloads" "https://www.ceskatelevize.cz/porady/..."
ct-dlp --output-dir "/path/to/downloads" "https://www.ceskatelevize.cz/porady/..."
```
If no output directory is given, files are saved to the current working
directory.

**Organize into series/season folders:**
```text
ct-dlp --series-folders "https://www.ceskatelevize.cz/porady/..."
```
When enabled, files are placed in `<Series>/Season 1/<file>` subfolders
(default: OFF). Note: Česká televize titles do not expose a season number, so
the season folder is always `Season 1`.

**Download multiple URLs at once:**
```text
ct-dlp URL1 URL2 URL3
```
Each URL (episode or series) is processed in turn. Combined with
`--series-folders`, this keeps downloads from multiple shows organized.

**Download a series:**

```text
# Windows
ct-dlp.bat "https://www.ceskatelevize.cz/porady/..."

# Linux/macOS
./ct-dlp "https://www.ceskatelevize.cz/porady/..."
```

## ✅ Development checks

Install the development dependencies and run the same checks used by GitHub
Actions:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m ruff check .
python3 -m ruff format --check .
python3 -m compileall -q .
python3 -m pytest --cov=ct_downloader --cov=ct_gui --cov-branch --cov-report=term-missing --cov-fail-under=85 -q
```

The tests use mocked network, terminal, and subprocess calls, so they do not
contact Česká televize or download media files. Coverage includes both the
video workflow and the subtitle-only workflows, including episode and series
dispatch. The GitHub Actions workflow runs linting, formatting,
compilation, and branch-coverage checks on Windows, Linux, and macOS.

## 📤 Publishing a release

Releases are created **automatically** when the `version` field in
`pyproject.toml` is updated and merged to `main`:

1. Update `version` in `pyproject.toml`.
2. Commit and merge the change into `main`.
3. The `auto-release.yml` workflow detects the new version, creates a git tag
   (`v<version>`), and creates a GitHub Release with auto-generated notes.
4. The tag push triggers:
   - `binaries.yml` — builds self-contained CLI and GUI executables for
     Linux, macOS, and Windows (AMD64 + ARM64) and attaches them to the
     Release.
   - `package.yml` — builds and publishes the Python package to PyPI via
     Trusted Publishing.

Dependabot keeps dependencies current. When a Dependabot PR passes CI it is
auto-merged, the patch version is bumped, and the cycle above repeats — so
updated binaries are released automatically whenever dependencies change.

To install a published release:
```sh
python -m pip install --upgrade ct-cli-gui
ct-dlp --version
```

The workflow publishes through PyPI Trusted Publishing and does not store a
PyPI API token in the repository.