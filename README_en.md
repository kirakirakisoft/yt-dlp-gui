# yt-dlp GUI v3.0

**KiraKiraKi Soft**

A simple GUI front-end for [yt-dlp](https://github.com/yt-dlp/yt-dlp) — no command line required.
Made for people who want to use yt-dlp but find typing commands every time tedious or difficult.

[日本語のREADMEはこちら → README.md](README.md)

---

## Features

- Paste a URL, press a button, done
- Switch between **Video + Audio (mp4)** and **Audio only (mp3)**
- **Time-range download** (save only the section you need)
- **Choose your download folder** (your settings are remembered)
- Video downloads prefer **H.264 (avc1)** — a format that imports cleanly
  into editors like DaVinci Resolve
- Optional **browser cookie support** for members-only / age-restricted
  videos (OFF by default)
- Real-time log output and a cancel button
- **Custom icon** — place an `icon.png` next to the script and it appears in the header and taskbar (**square PNG of 80x80 or smaller recommended** — it is shown as-is, which looks sharpest. Larger images are auto-shrunk but may look pixelated. Works fine without one)

## Requirements

| Software | Required? | Purpose |
|---|---|---|
| Python 3.9+ | Required | Runs this app |
| yt-dlp | Required | The actual downloader |
| ffmpeg | Required | Merging video/audio, mp3 conversion |
| Node.js | Optional | Needed to resolve some videos (most work without it) |

### Installation (Windows)

1. **Python** — Install from [python.org](https://www.python.org/downloads/).
   On the first installer screen, **make sure to check "Add python.exe to PATH"**.
2. **yt-dlp** — Open Command Prompt and run:
   ```
   pip install -U yt-dlp
   ```
3. **ffmpeg** — In Command Prompt:
   ```
   winget install Gyan.FFmpeg
   ```
   (Open a new Command Prompt or restart your PC afterwards.)
4. **Node.js (optional)** — Only if some videos fail with errors:
   ```
   winget install OpenJS.NodeJS.LTS
   ```

### Launch

Double-click `yt_dlp_gui.py`, or run:

```
python yt_dlp_gui.py
```

Tip: rename the file to `yt_dlp_gui.pyw` if you don't want a console
window to appear on double-click.

On startup the app checks for yt-dlp / ffmpeg / Node.js and tells you in
the log panel if anything is missing.

## Usage

1. Paste the video URL
2. Pick a mode (video / audio)
3. Optionally enable the time range and enter start/end (`HH:MM:SS`)
4. Press "Download"

Use the "変更... (Change)" button to pick a different download folder at
any time. Settings are saved automatically.

## About the browser cookie feature (important)

Only needed for content that requires login, such as members-only or
age-restricted videos. It is OFF by default.

- **Firefox is recommended.** Chromium-based browsers have strengthened
  cookie encryption in recent years, which often prevents external tools
  from reading them. Log in to the site in Firefox, then turn this ON.
- **Use at your own risk.** Using a download tool while logged in may be
  detected by the platform as automated tool usage, and **there is a
  non-zero chance of restrictions being placed on your account**.
  Consider using a secondary account rather than your main one.
- This app never transmits your cookies anywhere. They are only passed
  to yt-dlp locally on your own machine.

## Please read before use

This tool is distributed for **legitimate purposes**, such as:

- Backing up content you uploaded yourself
- Saving content whose rights holder explicitly permits downloading
- Uses permitted by law in your jurisdiction (e.g. private use where allowed)

Please note:

- **Downloading content that you know was uploaded illegally is itself
  illegal in many jurisdictions, including Japan.** Do not do it.
- Platform terms of service may restrict downloading. Checking and
  complying with those terms is your own responsibility.
- Do not redistribute or repost downloaded content without permission
  from the rights holder.

## Disclaimer

- This software is provided as-is, without warranty of any kind. The
  author accepts no liability for any damage arising from its use.
- All legal responsibility for how this software is used, including any
  downloading activity, rests with the user.
- Changes on the platform side or in yt-dlp may break functionality
  without notice.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "yt-dlp not found" | Run `pip install -U yt-dlp`. If it persists, check that Python was installed with the PATH option enabled |
| Video and audio saved separately / no mp3 | ffmpeg is missing — install it using the steps above |
| `ERROR: Sign in to confirm...` | Turn the cookie feature ON and retry (be logged in via Firefox) |
| Only some videos fail with `ERROR` | Installing Node.js may help. Also try updating: `pip install -U yt-dlp` |
| Garbled file names | Setting your system locale to UTF-8 may help |
| It worked yesterday but not today | Most likely a platform-side change. Update first: `pip install -U yt-dlp` |

## Changelog

- **v3.1** — Added right-click context menu (paste / clear & paste / copy etc.), custom icon.png support, and a bundled .pyw version for silent launch
- **v3.0** — First public release. Added download-folder picker with
  saved settings, cookie ON/OFF with browser selection, startup
  dependency checks, cancel button, URL/time validation, gradient header
- v2.x — Personal-use versions (H.264-first format selection, freeze
  fixes, UTF-8 handling)

## License

MIT License — see [LICENSE](LICENSE).

This app is a front-end for [yt-dlp](https://github.com/yt-dlp/yt-dlp).
yt-dlp itself is not bundled and is governed by its own license.

---

*KiraKiraKi Soft makes small tools that make tedious tasks a little easier.*
