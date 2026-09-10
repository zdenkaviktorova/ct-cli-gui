import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid

__version__ = "1.3.4"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 30
SITE_URL = "https://www.ceskatelevize.cz"
STREAM_API_URL = (
    "https://api.ceskatelevize.cz/video/v1/playlist-vod/v1/stream-data/"
    "media/external/{video_id}?canPlayDrm=true&quality=web&streamType=dash"
    "&deviceId={device_id}&origin=ivysilani&client=iVysilaniWeb"
    "&clientVersion=0.37.8"
)


def _resolve_tool(name):
    """Return the path to an external tool (ffmpeg, yt-dlp).

    When running inside a PyInstaller bundle the tool is expected next to the
    unpacked payload.  Otherwise the bare *name* is returned so that the OS
    searches PATH as usual.
    """
    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        ext = ".exe" if sys.platform == "win32" else ""
        candidate = os.path.join(bundle_dir, name + ext)
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which(name)
    if found:
        return found
    return name


def _sanitize(value):
    return re.sub(r'[\\/*?:"<>|]', "-", value)


def parse_episode_title(raw_title):
    """Parse a page <title> into structured episode metadata.

    Returns a dict with keys: clean_title, series_name, season, episode.
    Season is always 1 (Ceska televize titles do not expose a season number).
    """
    name = raw_title.split("|")[0].strip()
    # Some pages use "<Title> - iVysilani" as the full title; strip the site suffix.
    name = re.sub(r"\s+-\s+iVysílání\s*$", "", name)
    name = re.sub(r"\s+-\s+iVysilani\s*$", "", name)
    parts = name.split(" - ")
    if len(parts) >= 2:
        series_name = parts[-1].strip()
        ep_info = " - ".join(parts[:-1]).strip()
        match = re.match(r"^(\d+)/\d+\s+(.*)", ep_info)
        if match:
            ep_num = int(match.group(1))
            ep_title = match.group(2).strip()
            clean_title = _sanitize(f"{series_name} - S1E{ep_num:02d} - {ep_title}")
            return {
                "clean_title": clean_title,
                "series_name": _sanitize(series_name),
                "season": 1,
                "episode": ep_num,
            }
    clean_title = _sanitize(name)
    return {
        "clean_title": clean_title,
        "series_name": _sanitize(name),
        "season": 1,
        "episode": None,
    }


def format_episode_name(raw_title):
    return parse_episode_title(raw_title)["clean_title"]


def build_output_path(clean_title, series_name, season, ext, organize):
    """Return the output path for an artifact.

    When *organize* is True, files are placed in
    ``<series_name>/Season <season>/<clean_title>.<ext>`` and the directories
    are created.  Otherwise a flat ``<clean_title>.<ext>`` is returned.
    """
    filename = f"{clean_title}.{ext}"
    if organize:
        folder = os.path.join(series_name, f"Season {season}")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, filename)
    return filename


def get_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"[-] Error fetching page: {error}")
        return ""


def _srt_to_text(srt_content):
    """Strip SRT index numbers, timestamps and inline tags, returning plain text."""
    lines = []
    for line in srt_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.isdigit() or "-->" in stripped:
            continue
        lines.append(re.sub(r"<[^>]+>", "", stripped))
    return "\n".join(lines)


def _download_subtitles(data, clean_title, subtitle_format="srt", base_path=None):
    """Download subtitles and produce .srt and/or .txt files.

    *base_path* is the artifact path stem (without extension); when omitted it
    defaults to ``clean_title`` in the current directory.  Always produces a
    ``.cs.srt`` (needed for embedding); the ``.cs.txt`` companion is written
    when *subtitle_format* is ``txt`` or ``both``.  Returns the ``.cs.srt``
    path (or ``None`` if no subtitles were found).
    """
    sub_match = re.search(r'"(https://[^"]+\.vtt[^"]*)"', data)
    if not sub_match:
        return None

    stem = base_path if base_path is not None else clean_title
    sub_url = sub_match.group(1).replace("\\/", "/")
    vtt_filename = f"{stem}.cs.vtt"
    srt_filename = f"{stem}.cs.srt"
    try:
        urllib.request.urlretrieve(sub_url, vtt_filename)
        subprocess.run(
            [_resolve_tool("ffmpeg"), "-i", vtt_filename, srt_filename, "-y"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if os.path.exists(srt_filename):
            os.remove(vtt_filename)
            print(f"[+] Generated standard subtitle file: {srt_filename}")
            if subtitle_format in ("txt", "both"):
                txt_filename = f"{stem}.cs.txt"
                with open(srt_filename, encoding="utf-8") as subtitle_file:
                    subtitle_text = _srt_to_text(subtitle_file.read())
                with open(txt_filename, "w", encoding="utf-8") as subtitle_file:
                    subtitle_file.write(subtitle_text + "\n")
                print(f"[+] Also saved as plain-text subtitle file: {txt_filename}")
            return srt_filename
    except (OSError, subprocess.SubprocessError):
        print("[-] Could not download or convert subtitles.")
    return None


def download_episode(
    episode_url,
    quality=None,
    download_mode="video",
    subtitle_format="srt",
    organize=False,
):
    print(f"\nAnalyzing: {episode_url}")

    id_match = re.search(r"/(\d{10,})/?$", episode_url)
    if not id_match:
        print("[-] Could not extract video ID.")
        return
    video_id = id_match.group(1)

    html = get_html(episode_url)
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)

    if title_match:
        meta = parse_episode_title(title_match.group(1))
    else:
        fallback = f"CeskaTelevize_{video_id}"
        meta = {
            "clean_title": fallback,
            "series_name": fallback,
            "season": 1,
            "episode": None,
        }
    clean_title = meta["clean_title"]
    series_name = meta["series_name"]
    season = meta["season"]

    def artifact(ext):
        return build_output_path(clean_title, series_name, season, ext, organize)

    output_filename = artifact("mp4")

    if download_mode == "video" and os.path.exists(output_filename):
        print(f"[!] '{output_filename}' already exists. Skipping...")
        return

    print(f"[+] Found Episode: {clean_title}")
    if quality:
        print(f"[+] Target Quality: {quality}p (or closest match)")

    if download_mode == "video":
        # --- POSTER DOWNLOAD ---
        poster_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if poster_match:
            poster_url = poster_match.group(1).replace("&amp;", "&")
            poster_filename = artifact("jpg")
            if not os.path.exists(poster_filename):
                try:
                    urllib.request.urlretrieve(poster_url, poster_filename)
                    print("[+] Saved episode poster artwork.")
                except OSError:
                    print("[-] Could not download episode poster.")

    device_id = str(uuid.uuid4())
    api_url = STREAM_API_URL.format(video_id=video_id, device_id=device_id)

    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    # The subtitle path stem shares the episode's output location.
    if organize:
        _folder = os.path.join(series_name, f"Season {season}")
        os.makedirs(_folder, exist_ok=True)
        subtitle_stem = os.path.join(_folder, clean_title)
    else:
        subtitle_stem = clean_title

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = response.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"[-] Connection error getting stream: {error}")
        return

    if download_mode == "subtitles":
        srt_filename = _download_subtitles(
            data, clean_title, subtitle_format, base_path=subtitle_stem
        )
        has_subs = srt_filename is not None
        if not has_subs:
            print("[-] Subtitles not found for this episode.")
        elif subtitle_format == "txt" and os.path.exists(srt_filename):
            # txt-only: keep only the .txt on disk.
            os.remove(srt_filename)
        return

    # Video mode: always produce the .srt for embedding; the txt/both
    # companion is written too when requested.
    srt_filename = _download_subtitles(data, clean_title, subtitle_format, base_path=subtitle_stem)
    has_subs = srt_filename is not None

    stream_match = re.search(
        r'"(https://[^\"]+(?:token=[^\"]+|m3u8|mpd[^\"]*))"',
        data,
    )
    if not stream_match:
        print("[-] Error: Stream URL not found. It may be DRM protected.")
        if has_subs:
            os.remove(srt_filename)
        return

    stream_url = stream_match.group(1).replace("\\/", "/")

    def _download_video(stream_url, output_filename, quality):
        """Download the given stream URL to *output_filename* using yt-dlp's Python API.

        This avoids requiring an external 'yt-dlp' executable, which is important
        for standalone PyInstaller builds.
        """

        # Import here so unit tests can monkeypatch this helper without needing
        # the real yt_dlp module.
        import yt_dlp

        ffmpeg_path = _resolve_tool("ffmpeg")
        fmt = "bestvideo+bestaudio/best"
        if quality:
            # Cap the output to <= quality height when possible.
            q = int(quality)
            fmt = f"bestvideo[height<={q}]+bestaudio/best[height<={q}]/best"

        ydl_opts = {
            "outtmpl": output_filename,
            "noplaylist": True,
            "merge_output_format": "mp4",
            "format": fmt,
            "ffmpeg_location": ffmpeg_path,
            "http_headers": {"User-Agent": USER_AGENT},
            # Be resilient to flaky CDN fragments; avoid producing silently corrupted output.
            "socket_timeout": 60,
            "retries": 10,
            "fragment_retries": 50,
            "extractor_retries": 3,
            "abort_on_unavailable_fragments": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.download([stream_url])

    # --- YT-DLP DOWNLOAD (Python API) ---
    print("[+] Starting video download...")
    try:
        rc = _download_video(stream_url, output_filename, quality)
    except FileNotFoundError as error:
        # Typically missing ffmpeg in a frozen bundle.
        print(f"[-] Missing dependency required for download: {error}")
        if has_subs and os.path.exists(srt_filename):
            os.remove(srt_filename)
        return
    except Exception as error:
        print(f"[-] Video download failed: {error}")
        if has_subs and os.path.exists(srt_filename):
            os.remove(srt_filename)
        return

    if rc not in (0, None) or not os.path.exists(output_filename):
        print("[-] Video download failed.")
        if has_subs and os.path.exists(srt_filename):
            os.remove(srt_filename)
        return

    # --- SUBTITLE EMBEDDING ---
    if has_subs and os.path.exists(output_filename):
        print("[+] Embedding subtitles directly into the MP4 file...")
        temp_video = artifact("temp.mp4")
        os.rename(output_filename, temp_video)

        ffmpeg_cmd = [
            _resolve_tool("ffmpeg"),
            "-i",
            temp_video,
            "-i",
            srt_filename,
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=cze",
            "-metadata:s:s:0",
            "title=Czech",
            output_filename,
            "-y",
        ]

        try:
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError as error:
            os.rename(temp_video, output_filename)
            print(f"[-] Failed to embed subtitles: {error}")
            return

        if result.returncode == 0 and os.path.exists(output_filename):
            os.remove(temp_video)
            print("[+] Subtitles successfully embedded!")
        else:
            os.rename(temp_video, output_filename)
            print("[-] Failed to embed subtitles. Kept original video.")

        # Honor external-file retention after embedding.
        if subtitle_format == "txt" and os.path.exists(srt_filename):
            os.remove(srt_filename)
            print("[+] Kept external .txt subtitle only.")


_SUBTITLE_FORMAT_SYNONYMS = {
    "srt": "srt",
    "txt": "txt",
    "both": "both",
    "srt,txt": "both",
    "txt,srt": "both",
    "srt+txt": "both",
    "srt + txt": "both",
}


def _normalize_subtitle_format(value):
    """Normalize a --subtitle-format value to one of {srt, txt, both}."""
    key = value.strip().lower()
    if key not in _SUBTITLE_FORMAT_SYNONYMS:
        accepted = ", ".join(sorted(_SUBTITLE_FORMAT_SYNONYMS))
        raise argparse.ArgumentTypeError(
            f"invalid subtitle format: {value!r} (accepted: {accepted})"
        )
    return _SUBTITLE_FORMAT_SYNONYMS[key]


def build_arg_parser():
    """Build the CLI argument parser for ct_downloader."""
    parser = argparse.ArgumentParser(description="Ceska televize Downloader")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more iVysilani Episode or Series URLs",
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=str,
        help="Max resolution limit (e.g. 1080, 720, 540)",
    )
    parser.add_argument(
        "--mode",
        choices=("video", "subtitles"),
        default="video",
        help="Download video (default) or subtitles only",
    )
    parser.add_argument(
        "--subtitles-only",
        action="store_const",
        const="subtitles",
        dest="mode",
        help="Download subtitles only",
    )
    parser.add_argument(
        "--subtitle-format",
        type=_normalize_subtitle_format,
        default="srt",
        help=(
            "Subtitle output format: srt (default), txt (plain text only),"
            " or both/srt,txt (keep .srt and also save .txt)"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        "--output-dir",
        dest="output_dir",
        type=str,
        help="Destination directory for downloaded files",
    )
    parser.add_argument(
        "--series-folders",
        action="store_true",
        help="Organize files into <Series>/Season 1/ subfolders",
    )
    return parser


def process_url(url, quality, mode, subtitle_format, organize):
    """Dispatch a single URL to episode or series download."""
    episode_match = re.search(r"/porady/\d+-[^/]+/(\d{10,})/?$", url)
    series_match = re.search(r"(/porady/\d+-[^/]+)/?$", url)

    if episode_match:
        download_episode(url, quality, mode, subtitle_format, organize)
    elif series_match:
        print("[+] Series URL detected. Searching for episodes...")
        series_path = series_match.group(1)
        html = get_html(url)

        matches = re.findall(rf"{series_path}/(\d{{10,}})/?", html)
        if not matches:
            # Some 'porady' pages are single movies and don't list episodes.
            idec_match = re.search(r"IDEC=(\d{10,})", html)
            if idec_match:
                vid_id = idec_match.group(1)
                ep_url = f"{SITE_URL}{series_path}/{vid_id}/"
                print("[+] Single-video page detected. Downloading...")
                download_episode(ep_url, quality, mode, subtitle_format, organize)
                return

            print("[-] No episodes found on this page.")
            return

        unique_ids = list(dict.fromkeys(matches))
        print(f"[+] Found {len(unique_ids)} episodes. Starting batch download...\n")

        for vid_id in unique_ids:
            ep_url = f"{SITE_URL}{series_path}/{vid_id}/"
            download_episode(ep_url, quality, mode, subtitle_format, organize)
            print("-" * 60)

        print("\n[+] Batch download complete!")
    else:
        print("[-] Invalid Ceska televize URL format.")


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.urls:
        urls = [u.strip() for u in args.urls if u.strip()]
        quality = args.quality.lower().replace("p", "") if args.quality else None
    else:
        print("=== Ceska televize Downloader ===")
        url = input("Paste the iVysilani URL (Episode or Series): ").strip()
        urls = [url] if url else []
        quality = input("Max resolution (e.g. 1080, 720, 540) [Press Enter for Highest]: ").strip()
        quality = quality.lower().replace("p", "") if quality else None

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        os.chdir(args.output_dir)

    for url in urls:
        process_url(url, quality, args.mode, args.subtitle_format, args.series_folders)


if __name__ == "__main__":
    main()
    # Pause terminal if run directly without arguments
    if len(sys.argv) == 1:
        input("\nPress Enter to exit...")
