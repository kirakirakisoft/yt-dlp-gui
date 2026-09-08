# yt-dlp GUI v3.4.0

**KiraKiraKi Soft**

A simple GUI front-end for [yt-dlp](https://github.com/yt-dlp/yt-dlp) — no command line required.
Made for people who want to use yt-dlp but find typing commands every time tedious or difficult.

[日本語のREADMEはこちら → README.md](README.md)

---

## Features

- Paste a URL, press a button, done
- Switch between **Video + Audio (mp4)**, **Audio only (mp3)** and **Chat only (`live_chat.json`)**
- **Time-range download** (save only the section you need) — at the **same full quality** as a complete download
- **Multiple ranges in one go** — write one range per line and every one of them is extracted in a single download (no more repeating the whole job clip by clip when pulling several highlights out of a long stream)
- **Name each section** — add `# best play` at the end of a range line and the extracted file is named after it
- **Choose your download folder** (your settings are remembered)
- Video downloads prefer **H.264 (avc1)** — a format that imports cleanly
  into editors like DaVinci Resolve
- **Pick which ffmpeg to use** — point the app at an ffmpeg 7.1 build, which
  is **required if you use time-range downloads** (see below)
- **Post-download quality check** — the log reports the actual resolution and
  codec of the saved file, and warns if it came down at low quality
- Optional **browser cookie support** for members-only / age-restricted
  videos (OFF by default)
- **Playlist batch download** (toggleable — when OFF, a playlist URL safely downloads only the single video)
- **Record live streams from the start** (download from the beginning of the broadcast even if you join midway)
- **Automatic yt-dlp update** (on download failure, update yt-dlp to the latest version — with confirmation — and retry automatically)
- Real-time log output and a cancel button
- **Custom icon** — place an `icon.png` next to the script and it appears in the header and taskbar (**square PNG of 80x80 or smaller recommended** — it is shown as-is, which looks sharpest. Larger images are auto-shrunk but may look pixelated. Works fine without one)

## Requirements

| Software | Required? | Purpose |
|---|---|---|
| Python 3.9+ | Required | Runs this app |
| yt-dlp | Required | The actual downloader |
| ffmpeg **7.1.x** | Required | Merging video/audio, mp3 conversion, time-range downloads (**8.1.x breaks time ranges** — see below) |
| Node.js | Optional | Needed to resolve some videos (most work without it) |

### Installation (Windows)

1. **Python** — Install from [python.org](https://www.python.org/downloads/).
   On the first installer screen, **make sure to check "Add python.exe to PATH"**.
2. **yt-dlp** — Open Command Prompt and run:
   ```
   pip install -U yt-dlp
   ```
3. **ffmpeg (7.1.x recommended)** — which route you take depends on your use.

   **If you use time-range downloads (7.1.x required):**

   1. Open the [GyanD/codexffmpeg 7.1.1 release page](https://github.com/GyanD/codexffmpeg/releases/tag/7.1.1)
   2. Under Assets, download **`ffmpeg-7.1.1-full_build.zip`**
   3. Extract it and place the contents in `C:\ffmpeg-7.1`
      (so that `C:\ffmpeg-7.1\bin\ffmpeg.exe` exists)
   4. Enter `C:\ffmpeg-7.1\bin` in the app's **"ffmpeg の場所"** (ffmpeg location) field — see below

   **If you don't use time-range downloads:**

   ```
   winget install Gyan.FFmpeg
   ```
   (Open a new Command Prompt or restart your PC afterwards.)

   > ⚠️ **`winget install Gyan.FFmpeg` installs ffmpeg 8.1.x.**
   > 8.1.x merges and converts fine, but **time-range downloads do not work**
   > — the download sits at zero bytes forever and never finishes. This is an
   > ffmpeg-side problem that yt-dlp cannot fix
   > ([yt-dlp Issue #16546](https://github.com/yt-dlp/yt-dlp/issues/16546),
   > labelled `external-issue`), so the workaround is to keep a 7.1 build
   > alongside it and point the app at that. You do not need to uninstall 8.1.x.

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

### Setting the ffmpeg location (required for time-range downloads)

Enter the folder holding your 7.1 build into the **"ffmpeg の場所 (空欄で自動検出)"**
(ffmpeg location — blank to auto-detect) field near the top of the window.

```
C:\ffmpeg-7.1\bin
```

Press Enter and it is saved to your settings and restored on the next launch.
You should see this in the log:

```
ffmpeg: 検出OK (手動指定)
  パス: C:\ffmpeg-7.1\bin\ffmpeg.exe
  バージョン: 7.1.1-full_build-www.gyan.dev
```

- `C:\ffmpeg-7.1` (without `\bin`), or the path to `ffmpeg.exe` itself, also works
- **Leaving it blank auto-detects from PATH.** If winget installed 8.1.x onto
  your PATH, blank means 8.1.x, which means **time ranges will not work**
- If you never use time ranges, leaving it blank is fine

## Usage

1. Paste the video URL
2. Pick a mode (video / audio)
3. Optionally enable the time range and enter the sections you want (see below)
4. Press "Download"

### Writing time ranges

**One range per line.** Write several and they are all extracted in a **single download**.

```
*00:12:00-00:27:00
*01:03:10-01:05:00
```

- The leading `*` is **optional**
- `12:00-27:00` (**mm:ss**) and `720-1620` (**seconds**) also work
- `inf` as the end means **to the end of the video** (e.g. `*01:30:00-inf`)
- **Blank lines** and lines starting with `#` are skipped, so you can keep notes in the box

Each range is appended to the file name as `[start-end]`:

```
Stream title [00-12-00-00-27-00].mp4
Stream title [01-03-10-01-05-00].mp4
```

### Naming each section yourself

Add `# name` **at the end of a line** and that becomes the file name.

```
*00:12:00-00:27:00  # best play
*01:03:10-01:05:00  # greeting
```

```
best play.mp4
greeting.mp4
```

- Everything after `#` is read as a **name**, not as a time (a `#` at the start of a line is still a comment)
- Lines without a name keep the usual `[start-end]` file name
- Characters that cannot be used in a file name (`/ : * ?` and so on) are replaced with their full-width forms
- If the same name appears twice, `-2` / `-3` is appended to the later one
- Names are not applied when downloading a playlist (every video would get the same name)


When the download finishes, the log reports the actual resolution:

```
[確認] 実際の解像度: 1920x1080 / コーデック: h264
```

Anything 480p or below is flagged as a warning (though the source video may
simply not offer anything better).

Use the "変更... (Change)" button to pick a different download folder at
any time. Settings are saved automatically.

Hover over the "(?)" mark next to each toggle to see a description.

### Recording a live stream from the start

Turn the "ライブ配信 (Live)" toggle ON to download a currently-live stream
from the **beginning of the broadcast**, even if you join partway through.

- This only works **if the broadcaster keeps an archive (re-watch enabled)**. Streams with archiving disabled cannot be rewound.
- Downloading from the start may take extra time.

### Automatic yt-dlp updates

Most download failures are caused by an outdated yt-dlp (it updates
frequently to keep up with platform changes).

- **Auto-update OFF (default):** on failure, a dialog asks whether to update yt-dlp to the latest version. Click Yes to update and retry automatically.
- **Auto-update ON:** updates and retries automatically without asking.
- The update runs the equivalent of `pip install -U yt-dlp`. If it fails (e.g. due to permissions), the log explains how to update manually.

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
| **Time range is ON and the download stays at 0 bytes forever** | **ffmpeg 8.1.x is the cause.** Install a 7.1 build and set the ffmpeg location field (step 3 above) |
| It stops saying ffmpeg is required for time ranges | ffmpeg was not found. Enter the folder of your 7.1 build in the ffmpeg location field |
| Saved file is low resolution (e.g. 360p) | Most likely the source offers nothing better. On versions before v3.3.1 there was a bug forcing 360p whenever a time range was used — update to the latest version |
| A 4K video comes down as 1080p | By design. H.264 is preferred for editor compatibility, which caps out at 1080p (4K/1440p exist only as VP9/AV1, with no H.264 variant) |
| `ERROR: Sign in to confirm...` | Turn the cookie feature ON and retry (be logged in via Firefox) |
| Only some videos fail with `ERROR` | Installing Node.js may help. Also try updating: `pip install -U yt-dlp` |
| Garbled file names | Setting your system locale to UTF-8 may help |
| It worked yesterday but not today | Most likely a platform-side change. Update first: `pip install -U yt-dlp` |

## Changelog

- **v3.4.0** — **Sections can now be named.** Write `# best play` at the end of a range line and the extracted file is named after it (`best play.mp4`). Duplicate names get `-2` / `-3`, and characters that cannot be used in a file name are replaced with their full-width forms. Lines without a name keep the usual `[start-end]` name. This release also **fixes identical sections written in different notations (`00:12:00-00:27:00` and `720-1620`) being treated as different ranges** — they produced the same file name, so the second one was silently lost
- **v3.3.0** — **Multiple time ranges can now be given at once.** The time range input changed from separate start/end fields to a multi-line box, and `*00:12:00-00:27:00` can be pasted straight in (without the `*`, as mm:ss, as seconds, or with `inf` too). Every range written is extracted in a single download. Output file names now carry the section start/end, which also fixes multiple sections overwriting each other. This release also **fixes time-range downloads always dropping to 360p** (older versions only considered pre-muxed mp4, which on YouTube is fixed at 640x360), fixes the log appearing frozen during section extraction, and adds a post-download resolution/codec check. **Added a field to choose which ffmpeg folder to use** (**ffmpeg 8.1.x breaks time-range downloads**, so point it at a 7.1 build; a warning is now shown before starting if ffmpeg is 8.x). The startup log shows the ffmpeg path and version in use
- **v3.2.1** — Added a chat-only mode (saves the stream chat as `live_chat.json`). Switched the UI fonts to Japanese-friendly ones (Yu Gothic UI / BIZ UDGothic)
- **v3.2** — Added playlist batch download (ON/OFF), record-live-from-start, automatic yt-dlp update on failure (confirm dialog / auto modes), and hover tooltips on each toggle
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
