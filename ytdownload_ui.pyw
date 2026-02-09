"""
YouTube Video Downloader — GUI
===============================
Modern desktop UI for downloading YouTube videos in various formats.
Requires: pip install yt-dlp
"""

import os
import sys
import re
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse

# Hide the console window on Windows
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0  # SW_HIDE
        )
    except Exception:
        pass

try:
    import yt_dlp
except ImportError:
    os.system(f"{sys.executable} -m pip install yt-dlp")
    import yt_dlp


# ── Configuration ──────────────────────────────────────────────────────
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "YouTube")
CONCURRENT_FRAGMENTS = 16
BUFFER_SIZE = 1024 * 1024
HAS_ARIA2 = shutil.which("aria2c") is not None


# ── FFmpeg detection ───────────────────────────────────────────────────

def detect_ffmpeg():
    if shutil.which("ffmpeg"):
        return True
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path:
            os.environ["PATH"] = os.path.dirname(path) + os.pathsep + os.environ["PATH"]
            return True
    except Exception:
        pass
    return False


FFMPEG_AVAILABLE = detect_ffmpeg()


# ── Format definitions ─────────────────────────────────────────────────

VIDEO_FORMATS = []
AUDIO_FORMATS = []

if FFMPEG_AVAILABLE:
    VIDEO_FORMATS = [
        ("Best Quality — MP4",      {"format": "bestvideo+bestaudio/best", "merge_output_format": "mp4"}),
        ("1080p MP4",               {"format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]", "merge_output_format": "mp4"}),
        ("720p MP4",                {"format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]", "merge_output_format": "mp4"}),
        ("480p MP4",                {"format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]", "merge_output_format": "mp4"}),
        ("Best Quality — MKV",      {"format": "bestvideo+bestaudio/best", "merge_output_format": "mkv"}),
        ("Best Quality — WEBM",     {"format": "bestvideo[ext=webm]+bestaudio[ext=webm]/best", "merge_output_format": "webm"}),
    ]
    AUDIO_FORMATS = [
        ("MP3 (320kbps)",  {"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}]}),
        ("M4A / AAC",      {"format": "bestaudio[ext=m4a]/bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "256"}]}),
        ("WAV (lossless)",  {"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}]}),
    ]
else:
    VIDEO_FORMATS = [
        ("Best Quality — MP4",      {"format": "best[ext=mp4]/best"}),
        ("1080p MP4 (if available)", {"format": "best[height<=1080][ext=mp4]/best[height<=1080]"}),
        ("720p MP4",                {"format": "best[height<=720][ext=mp4]/best[height<=720]"}),
        ("480p MP4",                {"format": "best[height<=480][ext=mp4]/best[height<=480]"}),
    ]
    AUDIO_FORMATS = [
        ("M4A (no conversion)", {"format": "bestaudio[ext=m4a]/bestaudio"}),
        ("Best audio available", {"format": "bestaudio/best"}),
    ]

ALL_FORMATS = VIDEO_FORMATS + AUDIO_FORMATS


# ── Colors / Theme ─────────────────────────────────────────────────────
BG           = "#1e1e2e"
BG_CARD      = "#2a2a3d"
BG_INPUT     = "#363650"
FG           = "#cdd6f4"
FG_DIM       = "#7f849c"
ACCENT       = "#f38ba8"
ACCENT_HOVER = "#f5a0b8"
GREEN        = "#a6e3a1"
BLUE         = "#89b4fa"
YELLOW       = "#f9e2af"
RED          = "#f38ba8"
BORDER       = "#45475a"


# ── HTTP Server for Extension Communication ────────────────────────────

class DownloadRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for receiving download requests from Chrome extension"""
    
    app_instance = None  # Will be set by YouTubeDownloaderApp
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        pass
    
    def _send_json(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self._send_json({})
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/ping':
            self._send_json({'status': 'ok', 'version': '1.0.0'})
        elif self.path == '/status':
            self._send_json({'downloading': self.app_instance.is_downloading if self.app_instance else False})
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/download':
            try:
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                data = json.loads(body.decode())
                
                # Schedule download in main thread
                if self.app_instance:
                    self.app_instance.root.after(0, lambda: self.app_instance.handle_extension_download(data))
                    self._send_json({'status': 'queued', 'message': 'Download started'})
                else:
                    self._send_json({'error': 'App not initialized'}, 500)
            except Exception as e:
                self._send_json({'error': str(e)}, 400)
        else:
            self._send_json({'error': 'Not found'}, 404)


class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("750x700")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(600, 550)

        # State
        self.download_dir = tk.StringVar(value=DEFAULT_DIR)
        self.is_downloading = False
        self.video_info = None

        # HTTP Server for extension
        self.http_server = None
        self.http_thread = None
        
        self._build_ui()
        
        # Start HTTP server after UI is ready (so _log works)
        self.root.after(100, self._start_http_server)

    # ── UI Construction ────────────────────────────────────────────

    def _build_ui(self):
        # Main container with padding
        container = tk.Frame(self.root, bg=BG, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        # ── Title bar ──────────────────────────────────────────────
        title = tk.Label(container, text="YouTube Downloader",
                         font=("Segoe UI", 20, "bold"), bg=BG, fg=FG)
        title.pack(anchor="w")

        subtitle_parts = ["yt-dlp"]
        if FFMPEG_AVAILABLE:
            subtitle_parts.append("FFmpeg")
        if HAS_ARIA2:
            subtitle_parts.append("aria2c")
        status_text = "  |  ".join(subtitle_parts)
        ffmpeg_color = GREEN if FFMPEG_AVAILABLE else YELLOW

        status = tk.Label(container,
                          text=f"Powered by {status_text}"
                               + ("" if FFMPEG_AVAILABLE else "  |  FFmpeg: missing"),
                          font=("Segoe UI", 9), bg=BG, fg=ffmpeg_color)
        status.pack(anchor="w", pady=(0, 12))

        # ── URL input ──────────────────────────────────────────────
        self._section_label(container, "VIDEO URL")

        url_frame = tk.Frame(container, bg=BG)
        url_frame.pack(fill="x", pady=(2, 8))

        self.url_entry = tk.Entry(url_frame, font=("Segoe UI", 12),
                                  bg=BG_INPUT, fg=FG, insertbackground=FG,
                                  relief="flat", bd=0, highlightthickness=1,
                                  highlightbackground=BORDER, highlightcolor=ACCENT)
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.url_entry.bind("<Return>", lambda e: self._fetch_info())

        self.fetch_btn = tk.Button(url_frame, text="Fetch Info",
                                   font=("Segoe UI", 10, "bold"),
                                   bg=ACCENT, fg="#1e1e2e", activebackground=ACCENT_HOVER,
                                   relief="flat", cursor="hand2", padx=16, pady=6,
                                   command=self._fetch_info)
        self.fetch_btn.pack(side="right")

        # Paste button
        paste_btn = tk.Button(url_frame, text="Paste",
                              font=("Segoe UI", 9), bg=BG_CARD, fg=FG_DIM,
                              relief="flat", cursor="hand2", padx=10, pady=6,
                              command=self._paste_url)
        paste_btn.pack(side="right", padx=(0, 4))

        # ── Video info card ────────────────────────────────────────
        self.info_frame = tk.Frame(container, bg=BG_CARD, highlightthickness=1,
                                   highlightbackground=BORDER, padx=14, pady=10)
        self.info_frame.pack(fill="x", pady=(0, 10))

        self.info_title = tk.Label(self.info_frame, text="Paste a YouTube URL and click Fetch Info",
                                   font=("Segoe UI", 11), bg=BG_CARD, fg=FG_DIM,
                                   wraplength=680, justify="left", anchor="w")
        self.info_title.pack(anchor="w")

        self.info_details = tk.Label(self.info_frame, text="",
                                     font=("Segoe UI", 9), bg=BG_CARD, fg=FG_DIM,
                                     anchor="w", justify="left")
        self.info_details.pack(anchor="w", pady=(2, 0))

        # ── Format selection ───────────────────────────────────────
        fmt_row = tk.Frame(container, bg=BG)
        fmt_row.pack(fill="x", pady=(0, 8))

        self._section_label(fmt_row, "FORMAT", pack_side="left")

        self.format_var = tk.StringVar(value=ALL_FORMATS[0][0])
        self.format_combo = ttk.Combobox(fmt_row, textvariable=self.format_var,
                                         values=[f[0] for f in ALL_FORMATS],
                                         state="readonly", width=35,
                                         font=("Segoe UI", 10))
        self.format_combo.pack(side="left", padx=(8, 0))

        # Style the combobox
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=BG_INPUT, background=BG_INPUT,
                        foreground=FG, arrowcolor=FG,
                        borderwidth=1, relief="flat")
        style.map("TCombobox", fieldbackground=[("readonly", BG_INPUT)],
                  foreground=[("readonly", FG)])

        # ── Playlist option ────────────────────────────────────────
        self.playlist_var = tk.BooleanVar(value=False)
        self.playlist_check = tk.Checkbutton(
            fmt_row, text="Download full playlist",
            variable=self.playlist_var,
            font=("Segoe UI", 9), bg=BG, fg=FG_DIM,
            selectcolor=BG_INPUT, activebackground=BG, activeforeground=FG,
            highlightthickness=0)
        self.playlist_check.pack(side="right")

        # ── Download directory ─────────────────────────────────────
        self._section_label(container, "SAVE TO")

        dir_frame = tk.Frame(container, bg=BG)
        dir_frame.pack(fill="x", pady=(2, 10))

        dir_entry = tk.Entry(dir_frame, textvariable=self.download_dir,
                             font=("Segoe UI", 10), bg=BG_INPUT, fg=FG,
                             insertbackground=FG, relief="flat", bd=0,
                             highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=ACCENT)
        dir_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        browse_btn = tk.Button(dir_frame, text="Browse",
                               font=("Segoe UI", 9), bg=BG_CARD, fg=FG,
                               relief="flat", cursor="hand2", padx=12, pady=4,
                               command=self._browse_dir)
        browse_btn.pack(side="right")

        open_btn = tk.Button(dir_frame, text="Open",
                             font=("Segoe UI", 9), bg=BG_CARD, fg=FG_DIM,
                             relief="flat", cursor="hand2", padx=12, pady=4,
                             command=self._open_dir)
        open_btn.pack(side="right", padx=(0, 4))

        # ── Download button ────────────────────────────────────────
        self.dl_btn = tk.Button(container, text="DOWNLOAD",
                                font=("Segoe UI", 13, "bold"),
                                bg=ACCENT, fg="#1e1e2e", activebackground=ACCENT_HOVER,
                                relief="flat", cursor="hand2", pady=10,
                                command=self._start_download)
        self.dl_btn.pack(fill="x", pady=(0, 10))

        # ── Progress area ──────────────────────────────────────────
        prog_frame = tk.Frame(container, bg=BG)
        prog_frame.pack(fill="x", pady=(0, 4))

        self.progress_bar = ttk.Progressbar(prog_frame, mode="determinate", length=300)
        style.configure("TProgressbar", troughcolor=BG_INPUT,
                        background=ACCENT, thickness=6)
        self.progress_bar.pack(fill="x")

        stat_row = tk.Frame(container, bg=BG)
        stat_row.pack(fill="x", pady=(2, 6))

        self.status_label = tk.Label(stat_row, text="Ready",
                                     font=("Segoe UI", 10), bg=BG, fg=FG_DIM,
                                     anchor="w")
        self.status_label.pack(side="left")

        self.speed_label = tk.Label(stat_row, text="",
                                    font=("Segoe UI", 10, "bold"), bg=BG, fg=BLUE,
                                    anchor="e")
        self.speed_label.pack(side="right")

        # ── Log area ──────────────────────────────────────────────
        self._section_label(container, "LOG")

        log_frame = tk.Frame(container, bg=BG_CARD, highlightthickness=1,
                             highlightbackground=BORDER)
        log_frame.pack(fill="both", expand=True, pady=(2, 0))

        self.log_text = tk.Text(log_frame, font=("Consolas", 9),
                                bg=BG_CARD, fg=FG_DIM,
                                relief="flat", bd=0, padx=8, pady=6,
                                wrap="word", state="disabled",
                                insertbackground=FG, highlightthickness=0)
        self.log_text.pack(fill="both", expand=True, side="left")

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview,
                                 bg=BG_CARD, troughcolor=BG_CARD)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Tag colors for log
        self.log_text.tag_configure("success", foreground=GREEN)
        self.log_text.tag_configure("error", foreground=RED)
        self.log_text.tag_configure("info", foreground=BLUE)
        self.log_text.tag_configure("warn", foreground=YELLOW)

    def _section_label(self, parent, text, pack_side=None):
        lbl = tk.Label(parent, text=text, font=("Segoe UI", 8, "bold"),
                       bg=BG, fg=FG_DIM)
        if pack_side:
            lbl.pack(side=pack_side)
        else:
            lbl.pack(anchor="w")

    # ── Actions ────────────────────────────────────────────────────

    def _paste_url(self):
        try:
            text = self.root.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text.strip())
        except tk.TclError:
            pass

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.download_dir.get())
        if d:
            self.download_dir.set(d)

    def _open_dir(self):
        d = self.download_dir.get()
        os.makedirs(d, exist_ok=True)
        os.startfile(d)

    def _log(self, msg, tag=None):
        self.log_text.config(state="normal")
        if tag:
            self.log_text.insert("end", msg + "\n", tag)
        else:
            self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _set_status(self, text, color=FG_DIM):
        self.status_label.config(text=text, fg=color)

    def _set_speed(self, text):
        self.speed_label.config(text=text)

    def _set_progress(self, pct):
        self.progress_bar["value"] = pct

    def _set_buttons_state(self, downloading):
        self.is_downloading = downloading
        state = "disabled" if downloading else "normal"
        self.dl_btn.config(state=state,
                           bg=(BG_CARD if downloading else ACCENT),
                           text=("Downloading..." if downloading else "DOWNLOAD"))
        self.fetch_btn.config(state=state)

    # ── Fetch Info ─────────────────────────────────────────────────

    def _fetch_info(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        self.info_title.config(text="Fetching info...", fg=YELLOW)
        self.info_details.config(text="")
        self.video_info = None
        self.root.update_idletasks()

        threading.Thread(target=self._fetch_info_thread, args=(url,), daemon=True).start()

    def _fetch_info_thread(self, url):
        opts = {
            "quiet": True, "no_warnings": True,
            "skip_download": True, "extract_flat": True,
            "playlist_items": "0",
            "js_runtimes": {"nodejs": {}},
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            is_playlist = info.get("_type") == "playlist" or "entries" in info

            if is_playlist:
                entries = info.get("entries", [])
                count = len(entries) if entries else info.get("playlist_count", "?")
                title = info.get("title", "Unknown Playlist")
                details = f"Playlist  |  {count} videos"
                self.root.after(0, lambda: self.playlist_check.config(state="normal"))
            else:
                title = info.get("title", "Unknown")
                dur = info.get("duration", 0) or 0
                m, s = divmod(int(dur), 60)
                channel = info.get("channel", info.get("uploader", "?"))
                views = info.get("view_count")
                v_str = f"{views:,}" if views else "?"
                details = f"{channel}  |  {m}:{s:02d}  |  {v_str} views"
                self.root.after(0, lambda: self.playlist_check.config(state="disabled"))

            self.video_info = info
            self.root.after(0, lambda: self.info_title.config(text=title, fg=FG))
            self.root.after(0, lambda: self.info_details.config(text=details, fg=FG_DIM))
            self.root.after(0, lambda: self._log(f"Fetched: {title}", "info"))

        except Exception as e:
            self.root.after(0, lambda: self.info_title.config(
                text=f"Error: {e}", fg=RED))
            self.root.after(0, lambda: self._log(f"Fetch error: {e}", "error"))

    # ── Download ───────────────────────────────────────────────────

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a YouTube URL.")
            return
        if self.is_downloading:
            return

        # Get selected format
        selected = self.format_var.get()
        fmt_opts = None
        for label, opts in ALL_FORMATS:
            if label == selected:
                fmt_opts = opts
                break
        if not fmt_opts:
            return

        # Handle playlist URL
        if not self.playlist_var.get() and "watch?v=" in url:
            vid_match = re.search(r"[?&]v=([^&]+)", url)
            if vid_match:
                url = f"https://www.youtube.com/watch?v={vid_match.group(1)}"

        output_dir = self.download_dir.get()
        os.makedirs(output_dir, exist_ok=True)

        self._set_buttons_state(True)
        self._set_progress(0)
        self._set_status("Starting download...", YELLOW)
        self._set_speed("")
        self._log(f"Downloading: {url}", "info")
        self._log(f"Format: {selected}")

        threading.Thread(target=self._download_thread,
                         args=(url, fmt_opts, output_dir),
                         daemon=True).start()

    def _download_thread(self, url, format_opts, output_dir):
        def progress_hook(d):
            if d["status"] == "downloading":
                # Parse percentage
                pct_str = d.get("_percent_str", "0%").strip().replace("%", "")
                try:
                    pct = float(pct_str)
                except ValueError:
                    pct = 0
                speed = d.get("_speed_str", "").strip()
                eta = d.get("_eta_str", "").strip()
                downloaded = d.get("_downloaded_bytes_str", "").strip()
                total = d.get("_total_bytes_str", d.get("_total_bytes_estimate_str", "")).strip()

                status = f"Downloading... {pct_str}%"
                if total:
                    status += f"  ({downloaded} / {total})"
                if eta:
                    status += f"  ETA: {eta}"

                self.root.after(0, lambda: self._set_progress(pct))
                self.root.after(0, lambda: self._set_status(status, YELLOW))
                self.root.after(0, lambda: self._set_speed(speed if speed else ""))

            elif d["status"] == "finished":
                self.root.after(0, lambda: self._set_progress(100))
                self.root.after(0, lambda: self._set_status("Processing...", BLUE))
                self.root.after(0, lambda: self._set_speed(""))
                size = d.get("_total_bytes_str", "")
                self.root.after(0, lambda: self._log(f"Downloaded: {size}", "success"))

        opts = {
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "ignoreerrors": True,
            "no_warnings": True,
            "quiet": True,
            "noprogress": True,
            "consoletitle": False,
            # Use Node.js as JS runtime (Deno not installed)
            "js_runtimes": {"nodejs": {}},
            "concurrent_fragment_downloads": CONCURRENT_FRAGMENTS,
            "buffersize": BUFFER_SIZE,
            "http_chunk_size": 10 * 1024 * 1024,
            "retries": 10,
            "fragment_retries": 10,
            "throttledratelimit": 100_000,
        }

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

        if not self.playlist_var.get():
            opts["noplaylist"] = True

        opts.update(format_opts)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            self.root.after(0, lambda: self._set_progress(100))
            self.root.after(0, lambda: self._set_status("Download complete!", GREEN))
            self.root.after(0, lambda: self._set_speed(""))
            self.root.after(0, lambda: self._log(f"Saved to: {output_dir}", "success"))

        except Exception as e:
            self.root.after(0, lambda: self._set_status(f"Error: {e}", RED))
            self.root.after(0, lambda: self._log(f"Error: {e}", "error"))

        finally:
            self.root.after(0, lambda: self._set_buttons_state(False))

    # ── HTTP Server Methods ────────────────────────────────────────

    def _start_http_server(self):
        """Start HTTP server for extension communication"""
        try:
            # Set reference to this app instance
            DownloadRequestHandler.app_instance = self
            
            # Create and start server on port 9876
            self.http_server = HTTPServer(('127.0.0.1', 9876), DownloadRequestHandler)
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()
            
            self._log("HTTP server started on port 9876 (for Chrome extension)", "info")
        except Exception as e:
            self._log(f"Failed to start HTTP server: {e}", "warn")

    def handle_extension_download(self, data):
        """Handle download request from Chrome extension"""
        try:
            url = data.get('url')
            title = data.get('title', 'Unknown')
            format_choice = data.get('format', '720p')
            
            self._log(f"Extension request: {title}", "info")
            
            # Set URL in entry
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            
            # Map format choice to our format options
            format_map = {
                'best': 0,
                '1080p': 1,
                '720p': 2,
                '480p': 3,
                'audio': len(VIDEO_FORMATS)  # First audio format
            }
            
            format_idx = format_map.get(format_choice, 2)  # Default to 720p
            if format_idx < len(ALL_FORMATS):
                self.format_var.set(ALL_FORMATS[format_idx][0])
            
            # Start download automatically
            self._start_download()
            
        except Exception as e:
            self._log(f"Extension download error: {e}", "error")


# ── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()

    # Try to set DPI awareness for sharp rendering on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = YouTubeDownloaderApp(root)
    root.mainloop()
