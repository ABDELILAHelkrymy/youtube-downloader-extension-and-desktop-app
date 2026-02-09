"""
YouTube Video Downloader
========================
Download videos from YouTube in various formats and qualities.
Requires: pip install yt-dlp
"""

import os
import sys
import re
import shutil
import subprocess

try:
    import yt_dlp
except ImportError:
    print("yt-dlp is not installed. Installing now...")
    os.system(f"{sys.executable} -m pip install yt-dlp")
    import yt_dlp


# ── Configuration ──────────────────────────────────────────────────────
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "YouTube")
CONCURRENT_FRAGMENTS = 16   # parallel fragment downloads (huge speed boost)
BUFFER_SIZE = 1024 * 1024   # 1 MB read buffer
HAS_ARIA2 = shutil.which("aria2c") is not None


# ── FFmpeg detection & auto-install ────────────────────────────────────

def has_ffmpeg():
    """Check if FFmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def install_ffmpeg():
    """Try to install FFmpeg automatically via winget or pip."""
    print("\n  FFmpeg is required to merge video+audio and convert formats.")
    print("  Attempting to install FFmpeg...\n")

    # Try winget first (Windows 10/11)
    if shutil.which("winget"):
        print("  Trying: winget install FFmpeg...")
        result = subprocess.run(
            ["winget", "install", "Gyan.FFmpeg", "--accept-source-agreements", "--accept-package-agreements"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("  FFmpeg installed via winget!")
            print("  NOTE: You may need to restart this terminal for FFmpeg to be on PATH.\n")
            return True

    # Fallback: pip package that bundles ffmpeg
    print("  Trying: pip install ffmpeg-python + imageio-ffmpeg...")
    os.system(f"{sys.executable} -m pip install imageio-ffmpeg")
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_path:
            # Add its directory to PATH for this session
            os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]
            print(f"  FFmpeg available at: {ffmpeg_path}\n")
            return True
    except Exception:
        pass

    print("  Could not auto-install FFmpeg.")
    print("  Please install it manually from: https://ffmpeg.org/download.html")
    print("  Or run: winget install Gyan.FFmpeg\n")
    return False


FFMPEG_AVAILABLE = has_ffmpeg()

if not FFMPEG_AVAILABLE:
    print("  WARNING: FFmpeg not found on PATH.")
    choice = input("  Install FFmpeg automatically? (y/n): ").strip().lower()
    if choice == "y":
        FFMPEG_AVAILABLE = install_ffmpeg()
        if not FFMPEG_AVAILABLE:
            # Try checking again in case PATH was updated
            FFMPEG_AVAILABLE = has_ffmpeg()

if not FFMPEG_AVAILABLE:
    # Last resort: try imageio_ffmpeg if already installed
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_path:
            os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]
            FFMPEG_AVAILABLE = True
    except Exception:
        pass


# ── Format presets ─────────────────────────────────────────────────────
# When FFmpeg IS available: download best video + best audio separately, merge
# When FFmpeg is NOT available: download pre-merged single file (lower quality)

if FFMPEG_AVAILABLE:
    FORMAT_PRESETS = {
        "1": {
            "label": "Best Quality (Video + Audio) — MP4",
            "opts": {
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
            },
        },
        "2": {
            "label": "1080p MP4",
            "opts": {
                "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
                "merge_output_format": "mp4",
            },
        },
        "3": {
            "label": "720p MP4",
            "opts": {
                "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
                "merge_output_format": "mp4",
            },
        },
        "4": {
            "label": "480p MP4 (smaller file)",
            "opts": {
                "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
                "merge_output_format": "mp4",
            },
        },
        "5": {
            "label": "Audio Only (MP3 — 320kbps)",
            "opts": {
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
            },
        },
        "6": {
            "label": "Audio Only (M4A/AAC)",
            "opts": {
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "256",
                }],
            },
        },
        "7": {
            "label": "Audio Only (WAV — lossless)",
            "opts": {
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }],
            },
        },
        "8": {
            "label": "MKV (Best Quality)",
            "opts": {
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mkv",
            },
        },
        "9": {
            "label": "WEBM (Best Quality)",
            "opts": {
                "format": "bestvideo[ext=webm]+bestaudio[ext=webm]/best",
                "merge_output_format": "webm",
            },
        },
    }
else:
    # No FFmpeg — use only pre-merged single-stream formats
    print("\n  Using pre-merged formats (no FFmpeg). Quality may be limited to 720p.")
    print("  Install FFmpeg for full quality and audio conversion.\n")
    FORMAT_PRESETS = {
        "1": {
            "label": "Best Pre-merged Quality (MP4)",
            "opts": {
                "format": "best[ext=mp4]/best",
            },
        },
        "2": {
            "label": "1080p MP4 (if available)",
            "opts": {
                "format": "best[height<=1080][ext=mp4]/best[height<=1080]",
            },
        },
        "3": {
            "label": "720p MP4",
            "opts": {
                "format": "best[height<=720][ext=mp4]/best[height<=720]",
            },
        },
        "4": {
            "label": "480p MP4 (smaller file)",
            "opts": {
                "format": "best[height<=480][ext=mp4]/best[height<=480]",
            },
        },
        "5": {
            "label": "Audio Only (M4A — no conversion)",
            "opts": {
                "format": "bestaudio[ext=m4a]/bestaudio",
            },
        },
        "6": {
            "label": "Audio Only (best available)",
            "opts": {
                "format": "bestaudio/best",
            },
        },
    }


# ── Helpers ────────────────────────────────────────────────────────────

def progress_hook(d):
    """Display download progress."""
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "?%").strip()
        speed = d.get("_speed_str", "?").strip()
        eta = d.get("_eta_str", "?").strip()
        print(f"\r  ⬇  {pct}  |  {speed}  |  ETA: {eta}     ", end="", flush=True)
    elif d["status"] == "finished":
        size = d.get("_total_bytes_str", d.get("total_bytes", "?"))
        print(f"\r  ✓  Download complete ({size})                    ")


def is_valid_url(url):
    """Basic check for YouTube URL."""
    patterns = [
        r"(https?://)?(www\.)?youtube\.com/watch\?v=",
        r"(https?://)?(www\.)?youtu\.be/",
        r"(https?://)?(www\.)?youtube\.com/shorts/",
        r"(https?://)?(www\.)?youtube\.com/playlist\?list=",
    ]
    return any(re.match(p, url) for p in patterns)


def show_video_info(url):
    """Fetch and display video metadata."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,      # Don't fetch every playlist entry
        "playlist_items": "0",     # Only fetch playlist metadata
        "js_runtimes": {"nodejs": {}},
    }
    
    print("  Fetching video info...", end="", flush=True)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print("\r                              \r", end="")

            if info.get("_type") == "playlist" or "entries" in info:
                entries = info.get("entries", [])
                count = len(entries) if entries else info.get("playlist_count", "?")
                print(f"\n  Playlist: {info.get('title', '?')}")
                print(f"     Videos:   {count}")
                info["_is_playlist"] = True
            else:
                duration = info.get("duration", 0) or 0
                mins, secs = divmod(int(duration), 60)
                views = info.get("view_count")
                views_str = f"{views:,}" if views else "?"
                print(f"\n  Title:    {info.get('title', '?')}")
                print(f"     Channel:  {info.get('channel', info.get('uploader', '?'))}")
                print(f"     Duration: {mins}:{secs:02d}")
                print(f"     Views:    {views_str}")
                info["_is_playlist"] = False
            return info
    except Exception as e:
        print(f"\n  ✗ Could not fetch video info: {e}")
        return None


def download(url, format_opts, output_dir):
    """Download a video/playlist with the given format options."""
    os.makedirs(output_dir, exist_ok=True)

    opts = {
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "ignoreerrors": True,
        "no_warnings": False,
        "quiet": False,
        "noprogress": True,      # we handle progress ourselves
        "consoletitle": False,
        # ── JS Runtime (use Node.js instead of Deno) ───────────
        "js_runtimes": {"nodejs": {}},
        # ── Speed optimizations ─────────────────────────────────
        "concurrent_fragment_downloads": CONCURRENT_FRAGMENTS,
        "buffersize": BUFFER_SIZE,
        "http_chunk_size": 10 * 1024 * 1024,  # 10 MB chunks
        "retries": 10,
        "fragment_retries": 10,
        "throttledratelimit": 100_000,  # re-request if throttled below 100KB/s
    }

    # Use aria2c for multi-connection downloads if available
    if HAS_ARIA2:
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = {
            "default": [
                "--min-split-size=1M",
                "--max-connection-per-server=16",
                "--max-concurrent-downloads=16",
                "--split=16",
            ]
        }

    opts.update(format_opts)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        print(f"\n  ✓ Saved to: {output_dir}\n")
    except Exception as e:
        print(f"\n  ✗ Download failed: {e}\n")


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("═══════════════════════════════════════")
    print("       YouTube Video Downloader        ")
    print("═══════════════════════════════════════")
    print(f"  Save directory: {DOWNLOAD_DIR}\n")

    while True:
        # ── Get URL ──────────────────────────────────────────────
        url = input("Enter YouTube URL (or 'q' to quit): ").strip()
        if url.lower() in ("q", "quit", "exit"):
            break
        if not url:
            continue
        if not is_valid_url(url):
            print("  ⚠ This doesn't look like a YouTube URL. Trying anyway…\n")

        # ── Show info ────────────────────────────────────────────
        info = show_video_info(url)
        if not info:
            continue

        # ── Playlist: ask single video or full playlist ──────────
        download_single = False
        if info.get("_is_playlist") and "watch?v=" in url:
            print("\n  This URL contains both a video and a playlist.")
            print("    1. Download only this video")
            print("    2. Download entire playlist")
            pl_choice = input("  Choice (1/2): ").strip()
            if pl_choice == "1":
                download_single = True
                vid_match = re.search(r"[?&]v=([^&]+)", url)
                if vid_match:
                    url = f"https://www.youtube.com/watch?v={vid_match.group(1)}"

        # ── Choose format ────────────────────────────────────────
        print("\n  Choose a format:")
        print("  ─────────────────────────────────────")
        for key in sorted(FORMAT_PRESETS.keys(), key=int):
            print(f"    {key}. {FORMAT_PRESETS[key]['label']}")
        print()

        max_key = max(FORMAT_PRESETS.keys(), key=int)
        choice = input(f"  Select format (1-{max_key}): ").strip()
        if choice not in FORMAT_PRESETS:
            print("  Invalid choice.\n")
            continue

        preset = FORMAT_PRESETS[choice]
        print(f"\n  -> {preset['label']}")
        extra = {}
        if download_single:
            extra["noplaylist"] = True
        fmt_opts = {**preset["opts"], **extra}
        download(url, fmt_opts, DOWNLOAD_DIR)


if __name__ == "__main__":
    main()
