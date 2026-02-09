# YouTube Downloader Extension + Desktop App

An IDM-style YouTube downloader with Chrome extension and desktop application.

## 🚀 Quick Start

### 1. Start the Desktop App

```powershell
pythonw c:\Users\elkrymy\scripts\ytdownload_ui.pyw
```

The app will:
- Start HTTP server on `localhost:9876`
- Show "HTTP server started" in the log
- Wait for download requests from the extension

### 2. Install the Chrome Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select folder: `extension`
5. Extension icon will appear in your toolbar

### 3. Download Videos

1. Go to any YouTube video
2. Click the extension icon in your toolbar
3. Select format (720p, 1080p, etc.)
4. Click **Download Video**
5. The desktop app will start downloading automatically!

---

## 📋 How It Works

```
YouTube Page → Extension captures URL → HTTP POST localhost:9876 → Desktop App downloads
```

1. **Extension** runs in your browser with your YouTube session
2. **Extension** captures authenticated video URLs
3. **Extension** sends URL + metadata to desktop app via HTTP
4. **Desktop App** downloads using yt-dlp with Node.js runtime

---

## 🔧 Troubleshooting

### Extension shows "Desktop app not running"
- Make sure `ytdownload_ui.pyw` is running
- Check the app log shows "HTTP server started on port 9876"

### Downloads fail with "video not available"
- This system bypasses most authentication issues
- Still won't work for DRM-protected content
- Some videos may require region-specific workarounds

### Extension not appearing
- Make sure you selected the `extension` folder (not individual files)
- Check icons exist (or use placeholder images for now)
- Reload the extension after code changes

---

## 📁 File Structure

```
youtube-donwloader/
├── extension/
│   ├── manifest.json       # Extension config
│   ├── background.js       # Intercepts requests
│   ├── content.js          # Extracts video metadata
│   ├── popup.html          # UI
│   ├── popup.js            # Logic
│   └── icons/              # Extension icons
├── ytdownload_ui.pyw       # Desktop app with HTTP server
└── ytdownload.py           # CLI version
```

---

## 🎯 Features

✅ Download videos you can watch in your browser  
✅ Multiple quality options (best, 1080p, 720p, 480p, audio only)  
✅ Auto-detects video metadata  
✅ Queue downloads in desktop app  
✅ Works with YouTube Kids and restricted content  

---

## 🔜 Future Enhancements

- System tray icon
- Download queue management UI
- Progress updates in extension popup
- Support for Firefox
- Native messaging (more secure than HTTP)
