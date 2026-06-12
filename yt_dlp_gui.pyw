# -*- coding: utf-8 -*-
"""
yt-dlp GUI v3.0  ·  キラキラキソフト / KiraKiraKi Soft
yt-dlp をかんたんに使うためのシンプルなGUIフロントエンドです。
詳しい使い方・注意事項は同梱の README をお読みください。

License: MIT
"""

import tkinter as tk
from tkinter import filedialog
import subprocess
import threading
import shutil
import json
import os
import re
import sys

APP_NAME    = "yt-dlp GUI"
APP_VERSION = "v3.1"
BRAND       = "キラキラキソフト"

# ── カラー定義 ──────────────────────────────
BG        = "#0d0d0d"
BG2       = "#1a1a1a"
BG3       = "#141414"
BORDER    = "#2a2a2a"
PINK      = "#ec4899"
PURPLE    = "#7c3aed"
GREEN     = "#22c55e"
PINK_L    = "#f472b6"
GREEN_L   = "#86efac"
FG        = "#e0e0e0"
FG2       = "#888888"
FG3       = "#555555"
LOG_BG    = "#080808"
LOG_FG    = "#888888"
LOG_OK    = "#86efac"
LOG_WARN  = "#f472b6"
RED       = "#ef4444"

BROWSERS = ["firefox", "chrome", "edge", "brave"]


# ── アイコン画像(任意) ───────────────────────
# スクリプトと同じフォルダに icon.png を置くと、ヘッダー右側に表示されます。
# 推奨サイズ: 80x80 以下の正方形PNG(そのまま表示されます。大きい画像は粗めに自動縮小)
def find_icon_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "icon.png")
    return path if os.path.exists(path) else None


# ── 設定の保存/読込 ─────────────────────────
def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "KiraKiraKiSoft")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.expanduser("~")
    return d


CONFIG_PATH = os.path.join(config_dir(), "ytdlp_gui.json")


def default_download_dir():
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    return d if os.path.isdir(d) else os.path.expanduser("~")


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ── メインアプリ ─────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("660x800")  # icon.png使用時は自動で+30

        cfg = load_config()
        self.download_dir = cfg.get("download_dir") or default_download_dir()
        if not os.path.isdir(self.download_dir):
            self.download_dir = default_download_dir()

        self.mode        = tk.StringVar(value=cfg.get("mode", "video"))
        self.time_on     = tk.BooleanVar(value=False)
        self.cookies_on  = tk.BooleanVar(value=bool(cfg.get("use_cookies", False)))
        self.browser_var = tk.StringVar(value=cfg.get("browser", "firefox"))
        self.running     = False
        self.proc        = None
        self.cancelled   = False

        # 依存ツールの検出
        self.ytdlp_path  = shutil.which("yt-dlp")
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.node_path   = shutil.which("node")

        self._build()
        if self.icon_img:
            self.geometry("660x830")
        self.browser_var.trace_add("write", lambda *a: self._save_cfg())
        self._startup_check()

    # ── UI構築 ───────────────────────────────
    def _build(self):
        # アイコン画像(あれば)を読み込み
        self.icon_img = None
        icon_path = find_icon_path()
        if icon_path:
            try:
                img = tk.PhotoImage(file=icon_path)
                # 高さ約80pxに収まるよう整数倍率で縮小
                factor = max(1, (max(img.width(), img.height()) + 79) // 80)
                if factor > 1:
                    img = img.subsample(factor, factor)
                self.icon_img = img
                try:
                    self.iconphoto(False, self.icon_img)  # タスクバー等のアイコンにも反映
                except tk.TclError:
                    pass
            except tk.TclError:
                self.icon_img = None  # 読めない画像は無視して通常起動

        # ヘッダー(ピンク→紫グラデーション)
        hdr_h = 100 if self.icon_img else 70
        self.hdr = tk.Canvas(self, height=hdr_h, width=660,
                             highlightthickness=0, bd=0, bg=BG)
        self.hdr.pack(fill="x")
        self._draw_gradient(self.hdr, 660, hdr_h, PINK, PURPLE)
        cy = hdr_h // 2
        self.hdr.create_text(20, cy - 12, anchor="w", text=APP_NAME,
                             fill="white", font=("Segoe UI", 18, "bold"))
        self.hdr.create_text(22, cy + 14, anchor="w",
                             text=f"{BRAND}  ·  Simple front-end for yt-dlp",
                             fill="#ffd6ec", font=("Segoe UI", 9))
        if self.icon_img:
            self.hdr.create_image(600, cy, image=self.icon_img)
            self.hdr.create_text(540, hdr_h - 14, anchor="e", text=APP_VERSION,
                                 fill="#ffd6ec", font=("Segoe UI", 9, "bold"))
        else:
            self.hdr.create_text(640, cy + 14, anchor="e", text=APP_VERSION,
                                 fill="#ffd6ec", font=("Segoe UI", 9, "bold"))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        body = tk.Frame(self, bg=BG, padx=20, pady=12)
        body.pack(fill="both", expand=True)

        # URL
        self._label(body, "動画のURL")
        url_frame = tk.Frame(body, bg=BG2, highlightbackground=BORDER,
                             highlightthickness=1)
        url_frame.pack(fill="x", pady=(4, 12))
        self.url_var = tk.StringVar()
        url_entry = tk.Entry(url_frame, textvariable=self.url_var,
                             bg=BG2, fg=FG, insertbackground=PINK,
                             relief="flat", font=("Consolas", 11), bd=8)
        url_entry.pack(fill="x")
        url_entry.bind("<FocusIn>",  lambda e: url_frame.config(highlightbackground=PINK))
        url_entry.bind("<FocusOut>", lambda e: url_frame.config(highlightbackground=BORDER))
        url_entry.bind("<Return>",   lambda e: self._start())
        self._add_context_menu(url_entry, with_clear=True)

        # 保存先
        self._label(body, "保存先")
        sf = tk.Frame(body, bg=BG3, highlightbackground="#1e1e1e",
                      highlightthickness=1)
        sf.pack(fill="x", pady=(4, 12))
        sf_in = tk.Frame(sf, bg=BG3)
        sf_in.pack(fill="x")
        self.dir_lbl = tk.Label(sf_in, text="", bg=BG3, fg=GREEN_L,
                                font=("Consolas", 10), padx=10, pady=6,
                                anchor="w")
        self.dir_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(sf_in, text="開く", command=self._open_dir,
                  bg=BG2, fg=FG2, activebackground=BG3,
                  activeforeground=FG, relief="flat", bd=0,
                  font=("Segoe UI", 9), cursor="hand2",
                  padx=10).pack(side="right", padx=(0, 4), pady=3)
        tk.Button(sf_in, text="変更...", command=self._choose_dir,
                  bg=BG2, fg=FG, activebackground=BG3,
                  activeforeground=FG, relief="flat", bd=0,
                  font=("Segoe UI", 9), cursor="hand2",
                  padx=10).pack(side="right", padx=4, pady=3)
        self._refresh_dir_label()

        # モード選択
        self._label(body, "ダウンロードモード")
        mf = tk.Frame(body, bg=BG)
        mf.pack(fill="x", pady=(4, 12))
        self.btn_video = self._mode_btn(mf, "▶  動画＋音声 (mp4)", "video")
        self.btn_video.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.btn_audio = self._mode_btn(mf, "♪  音声のみ (mp3)", "audio")
        self.btn_audio.pack(side="left", fill="x", expand=True)
        self._refresh_mode()

        # 時間指定
        self._label(body, "時間指定")
        tf_outer = tk.Frame(body, bg=BG)
        tf_outer.pack(fill="x", pady=(4, 6))
        self.toggle_btn = self._toggle_label(tf_outer, self._toggle_time)
        self.toggle_btn.pack(side="left")
        tk.Label(tf_outer, text="指定した範囲だけダウンロードする",
                 bg=BG, fg=FG2, font=("Segoe UI", 10)).pack(side="left", padx=8)

        tf = tk.Frame(body, bg=BG)
        tf.pack(fill="x", pady=(0, 12))
        self.start_var = tk.StringVar(value="00:00:00")
        self.end_var   = tk.StringVar(value="00:01:00")
        self._time_group(tf, "開始 (HH:MM:SS)", self.start_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        self._time_group(tf, "終了 (HH:MM:SS)", self.end_var).pack(
            side="left", fill="x", expand=True)
        self._update_time_state()

        # ブラウザCookie
        self._label(body, "ブラウザのCookieを使う(メンバー限定・年齢制限の動画用)")
        cf = tk.Frame(body, bg=BG)
        cf.pack(fill="x", pady=(4, 12))
        self.cookie_btn = self._toggle_label(cf, self._toggle_cookies)
        self.cookie_btn.pack(side="left")
        self.browser_menu = tk.OptionMenu(cf, self.browser_var, *BROWSERS)
        self.browser_menu.config(bg=BG2, fg=FG, activebackground=BG3,
                                 activeforeground=FG, relief="flat",
                                 highlightthickness=1,
                                 highlightbackground=BORDER,
                                 font=("Segoe UI", 9), cursor="hand2")
        self.browser_menu["menu"].config(bg=BG2, fg=FG,
                                         activebackground=PINK,
                                         activeforeground="white")
        self.browser_menu.pack(side="left", padx=8)
        tk.Label(cf, text="※ Firefox推奨 · 自己責任(READMEを参照)",
                 bg=BG, fg=FG3, font=("Segoe UI", 8)).pack(side="left", padx=4)
        self._refresh_cookie_state()

        # DLボタン
        self.dl_btn = tk.Button(body, text="▼  ダウンロード開始",
                                bg=PINK, fg="white",
                                activebackground="#be185d",
                                activeforeground="white",
                                relief="flat", bd=0,
                                font=("Segoe UI", 13, "bold"),
                                cursor="hand2", pady=10,
                                command=self._start)
        self.dl_btn.pack(fill="x", pady=(0, 10))

        # ステータス
        sf2 = tk.Frame(body, bg=BG3, highlightbackground="#222",
                       highlightthickness=1)
        sf2.pack(fill="x", pady=(0, 10))
        sf2_in = tk.Frame(sf2, bg=BG3, padx=10, pady=5)
        sf2_in.pack(fill="x")
        self.dot = tk.Label(sf2_in, text="●", bg=BG3, fg=GREEN,
                            font=("Segoe UI", 9))
        self.dot.pack(side="left")
        self.status_lbl = tk.Label(sf2_in, text="待機中",
                                   bg=BG3, fg=FG2, font=("Segoe UI", 10))
        self.status_lbl.pack(side="left", padx=6)

        # ログ
        self._label(body, "ログ")
        log_frame = tk.Frame(body, bg=LOG_BG, highlightbackground="#1a1a1a",
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.log = tk.Text(log_frame, bg=LOG_BG, fg=LOG_FG,
                           font=("Consolas", 9), relief="flat", bd=8,
                           wrap="word", state="disabled", height=10)
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_config("ok",   foreground=LOG_OK)
        self.log.tag_config("warn", foreground=LOG_WARN)
        self.log.tag_config("info", foreground=LOG_FG)
        sb = tk.Scrollbar(log_frame, command=self.log.yview,
                          bg=BG2, troughcolor=LOG_BG)
        sb.pack(side="right", fill="y")
        self.log["yscrollcommand"] = sb.set

        # フッター
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        ftr = tk.Frame(self, bg=BG, padx=20, pady=6)
        ftr.pack(fill="x")
        tk.Label(ftr, text=f"{APP_NAME} {APP_VERSION}  ·  {BRAND}",
                 bg=BG, fg=FG3, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(ftr, text="利用規約と著作権の範囲でご利用ください",
                 bg=BG, fg=FG3, font=("Segoe UI", 8)).pack(side="right")

    # ── 起動時チェック ────────────────────────
    def _startup_check(self):
        self._log(f"{APP_NAME} {APP_VERSION} 起動完了", "ok")
        self._log(f"保存先: {self.download_dir}", "info")

        if self.ytdlp_path:
            self._log("yt-dlp: 検出OK", "ok")
        else:
            self._log("yt-dlp: 見つかりません!", "warn")
            self._log("  → コマンドプロンプトで  pip install -U yt-dlp  を実行後、"
                      "このアプリを再起動してください(詳細はREADME)", "warn")
            self.dl_btn.config(state="disabled", bg="#555",
                               text="yt-dlp が見つかりません(READMEを参照)")
            self._set_status("yt-dlp 未検出", RED)

        if self.ffmpeg_path:
            self._log("ffmpeg: 検出OK", "ok")
        else:
            self._log("ffmpeg: 見つかりません。映像と音声の結合やmp3変換に"
                      "失敗する可能性があります(READMEを参照)", "warn")

        if self.node_path:
            self._log("Node.js: 検出OK(一部動画の解析に使用します)", "ok")
        else:
            self._log("Node.js: 未検出。通常は問題ありませんが、一部の動画で"
                      "エラーになる場合はREADMEの手順で導入してください", "info")

        self._log("─" * 48, "info")
        self._log("このツールは、ご自身のコンテンツの保存や、権利者が許可した"
                  "範囲での利用を想定しています。", "info")
        self._log("URLを入力してダウンロードを開始してください", "info")

    # ── ヘルパー ─────────────────────────────
    @staticmethod
    def _draw_gradient(canvas, w, h, c1, c2):
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        for x in range(w):
            t = x / max(w - 1, 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            canvas.create_line(x, 0, x, h, fill=f"#{r:02x}{g:02x}{b:02x}")

    def _add_context_menu(self, entry, with_clear=False):
        menu = tk.Menu(entry, tearoff=0, bg=BG2, fg=FG,
                       activebackground=PINK, activeforeground="white",
                       relief="flat", bd=0)
        menu.add_command(label="貼り付け",
                         command=lambda: entry.event_generate("<<Paste>>"))
        if with_clear:
            def clear_paste():
                entry.delete(0, "end")
                entry.event_generate("<<Paste>>")
            menu.add_command(label="消して貼り付け", command=clear_paste)
        menu.add_command(label="コピー",
                         command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="切り取り",
                         command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_separator()
        menu.add_command(label="すべて選択",
                         command=lambda: entry.select_range(0, "end"))

        def popup(e):
            if str(entry.cget("state")) == "normal":
                menu.tk_popup(e.x_root, e.y_root)
        entry.bind("<Button-3>", popup)

    def _label(self, parent, text):
        tk.Label(parent, text=text.upper(), bg=BG, fg=FG3,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")

    def _mode_btn(self, parent, text, value):
        return tk.Button(parent, text=text, relief="flat", bd=0,
                         font=("Segoe UI", 10), cursor="hand2", pady=8,
                         command=lambda: self._set_mode(value))

    def _toggle_label(self, parent, command):
        lbl = tk.Label(parent, text="  OFF  ", bg=BORDER, fg=FG3,
                       font=("Segoe UI", 9, "bold"),
                       cursor="hand2", padx=6, pady=3)
        lbl.bind("<Button-1>", lambda e: command())
        return lbl

    def _time_group(self, parent, label, var):
        frame = tk.Frame(parent, bg=BG)
        tk.Label(frame, text=label, bg=BG, fg=FG3,
                 font=("Segoe UI", 8)).pack(anchor="w")
        ef = tk.Frame(frame, bg=BG2, highlightbackground=BORDER,
                      highlightthickness=1)
        ef.pack(fill="x", pady=(3, 0))
        e = tk.Entry(ef, textvariable=var, bg=BG2, fg=FG,
                     insertbackground=GREEN, relief="flat",
                     font=("Consolas", 11), justify="center", bd=6)
        e.pack(fill="x")
        e.bind("<FocusIn>",  lambda ev: ef.config(highlightbackground=GREEN))
        e.bind("<FocusOut>", lambda ev: ef.config(highlightbackground=BORDER))
        self._add_context_menu(e)
        frame._entry = e
        return frame

    # ── 保存先 ───────────────────────────────
    def _refresh_dir_label(self):
        d = self.download_dir
        if len(d) > 46:
            d = d[:22] + "…" + d[-22:]
        self.dir_lbl.config(text=f"📁  {d}")

    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.download_dir,
                                    title="保存先フォルダを選択")
        if d:
            self.download_dir = os.path.normpath(d)
            self._refresh_dir_label()
            self._save_cfg()
            self._log(f"保存先を変更: {self.download_dir}", "ok")

    def _open_dir(self):
        try:
            if os.name == "nt":
                os.startfile(self.download_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.download_dir])
            else:
                subprocess.Popen(["xdg-open", self.download_dir])
        except OSError as e:
            self._log(f"[エラー] フォルダを開けませんでした: {e}", "warn")

    # ── トグル/モード ─────────────────────────
    def _set_mode(self, value):
        self.mode.set(value)
        self._refresh_mode()
        self._save_cfg()

    def _refresh_mode(self):
        if self.mode.get() == "video":
            self.btn_video.config(bg=PINK, fg="white", activebackground="#be185d")
            self.btn_audio.config(bg=BG2, fg=FG2, activebackground=BG3)
        else:
            self.btn_video.config(bg=BG2, fg=FG2, activebackground=BG3)
            self.btn_audio.config(bg=GREEN, fg="white", activebackground="#15803d")

    def _toggle_time(self):
        self.time_on.set(not self.time_on.get())
        self._paint_toggle(self.toggle_btn, self.time_on.get())
        self._update_time_state()

    def _toggle_cookies(self):
        self.cookies_on.set(not self.cookies_on.get())
        self._paint_toggle(self.cookie_btn, self.cookies_on.get())
        self._refresh_cookie_state()
        self._save_cfg()
        if self.cookies_on.get():
            self._log(f"Cookie使用: ON ({self.browser_var.get()}) · "
                      "対象ブラウザでログイン済みである必要があります", "info")

    @staticmethod
    def _paint_toggle(lbl, on):
        if on:
            lbl.config(text="  ON   ", bg=GREEN, fg="#0d0d0d")
        else:
            lbl.config(text="  OFF  ", bg=BORDER, fg=FG3)

    def _refresh_cookie_state(self):
        state = "normal" if self.cookies_on.get() else "disabled"
        self.browser_menu.config(state=state)

    def _update_time_state(self):
        state = "normal" if self.time_on.get() else "disabled"
        fg_   = FG if self.time_on.get() else FG3
        for w in self.winfo_children():
            self._set_entry_state(w, state, fg_)

    def _set_entry_state(self, widget, state, fg_):
        for child in widget.winfo_children():
            if hasattr(child, "_entry"):
                child._entry.config(state=state, fg=fg_,
                                    disabledbackground=BG2,
                                    disabledforeground=FG3)
            self._set_entry_state(child, state, fg_)

    # ── ログ/状態 ─────────────────────────────
    def _log(self, text, tag="info"):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def _set_status(self, text, color):
        self.status_lbl.config(text=text)
        self.dot.config(fg=color)

    def _save_cfg(self):
        save_config({
            "download_dir": self.download_dir,
            "use_cookies":  bool(self.cookies_on.get()),
            "browser":      self.browser_var.get(),
            "mode":         self.mode.get(),
        })

    # ── ダウンロード処理 ─────────────────────
    def _start(self):
        if self.running:
            self._cancel()
            return

        url = self.url_var.get().strip()
        if not url:
            self._log("[エラー] URLを入力してください", "warn")
            return
        if not re.match(r"^https?://", url):
            self._log("[エラー] URLは http:// または https:// で始まる必要があります", "warn")
            return

        mode    = self.mode.get()
        time_on = self.time_on.get()
        start   = self.start_var.get().strip()
        end     = self.end_var.get().strip()

        if time_on:
            t_pat = r"^\d{1,2}:\d{2}:\d{2}$"
            if not (re.match(t_pat, start) and re.match(t_pat, end)):
                self._log("[エラー] 時間は HH:MM:SS の形式で入力してください(例 00:05:30)", "warn")
                return

        try:
            os.makedirs(self.download_dir, exist_ok=True)
        except OSError as e:
            self._log(f"[エラー] 保存先を作成できません: {e}", "warn")
            return

        ytdlp = self.ytdlp_path or "yt-dlp"
        out_tpl = os.path.join(self.download_dir, "%(title)s.%(ext)s")

        cmd = [ytdlp, "--encoding", "utf-8", "--no-playlist"]

        if self.cookies_on.get():
            cmd += ["--cookies-from-browser", self.browser_var.get()]

        # Node.js があれば、一部動画の解析用に JSランタイムを指定
        if self.node_path:
            cmd += ["--js-runtimes", "node", "--remote-components", "ejs:github"]

        if mode == "audio":
            cmd += ["-f", "bestaudio",
                    "--extract-audio",
                    "--audio-format", "mp3",
                    "--audio-quality", "0"]
        else:
            # 編集ソフト互換重視: H.264(avc1) を最優先で取得する
            # (VP9/AV1 の webm は一部編集ソフトでデコードできないため避ける)
            vid_format = (
                "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/"
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "best[ext=mp4]/"
                "best"
            )
            # 時間指定ONのときは、フリーズ回避のため結合済みmp4を使う
            if time_on:
                vid_format = "best[ext=mp4]/best"
            cmd += ["-f", vid_format, "--merge-output-format", "mp4"]

        if time_on:
            cmd += ["--download-sections", f"*{start}-{end}"]

        cmd += ["-o", out_tpl, url]

        self.running = True
        self.cancelled = False
        self.dl_btn.config(bg="#555", text="■  中止する",
                           activebackground="#444")
        self._set_status("ダウンロード中...", PINK)
        self._log(f"[開始] {url}", "info")
        self._log(f"[モード] {'動画+音声(mp4)' if mode == 'video' else '音声のみ(mp3)'}", "info")

        def task():
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

                self.proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    creationflags=flags,
                )
                for line in self.proc.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    tag = "info"
                    if "[download]" in line or "Destination" in line:
                        tag = "ok"
                    elif "WARNING" in line or "ERROR" in line:
                        tag = "warn"
                    self.after(0, self._log, line, tag)

                self.proc.wait()
                ok = (self.proc.returncode == 0) and not self.cancelled
                self.after(0, self._on_done, ok)
            except FileNotFoundError:
                self.after(0, self._log,
                           "[エラー] yt-dlp を実行できませんでした。"
                           "READMEの手順でインストールされているか確認してください", "warn")
                self.after(0, self._on_done, False)
            except Exception as e:
                self.after(0, self._log, f"[例外] {e}", "warn")
                self.after(0, self._on_done, False)

        threading.Thread(target=task, daemon=True).start()

    def _cancel(self):
        if self.proc and self.proc.poll() is None:
            self.cancelled = True
            try:
                self.proc.kill()
            except OSError:
                pass
            self._log("[中止] ユーザー操作によりダウンロードを中止しました", "warn")

    def _on_done(self, success):
        self.running = False
        self.proc = None
        self.dl_btn.config(state="normal", bg=PINK,
                           activebackground="#be185d",
                           text="▼  ダウンロード開始")
        if success:
            self._set_status("完了！", GREEN)
            self._log(f"[完了] 保存先: {self.download_dir}", "ok")
        elif self.cancelled:
            self._set_status("中止しました", "#f59e0b")
        else:
            self._set_status("エラーが発生しました", RED)
            self._log("[エラー] ダウンロードに失敗しました。ログ上部のERROR行と"
                      "READMEのトラブルシューティングを確認してください", "warn")


if __name__ == "__main__":
    app = App()
    app.mainloop()
