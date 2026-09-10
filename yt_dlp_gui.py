# -*- coding: utf-8 -*-
"""
yt-dlp GUI v3.3.0  ·  キラキラキソフト / KiraKiraKi Soft
yt-dlp をかんたんに使うためのシンプルなGUIフロントエンドです。
詳しい使い方・注意事項は同梱の README をお読みください。

── v3.3.0 の変更点(公開版 v3.2.1 → v3.3.0) ────────
※ 手元では v3.3.0 / v3.3.1 と名前を付けた試作を経ているが、どちらも
   公開していない。公開版としては v3.2.1 の次がこの v3.3.0 になる。
   そのため試作2本ぶんの変更も、以下にまとめて書いてある。

[変更] 時間指定を「開始」「終了」の2欄から、複数行の入力欄に変えた。
       1行に1範囲で、何個でも書ける。書いた範囲は1回のダウンロードで
       まとめて切り出す(--download-sections を範囲の数だけ渡す)。
       2欄だと1回に1区間しか指定できず、同じ配信から複数の切り抜きを
       作るのに毎回やり直しが必要だったため。
[追加] ブラウザ拡張「TS工房」の書き出し形式「*開始-終了」をそのまま
       貼り付けられるようにした。行頭の * は有っても無くてもよく、
       「12:00-27:00」(分:秒)や「720-1620」(秒)、終了に inf も使える。
[修正] 区間指定時の出力ファイル名に区間の開始/終了を入れるようにした。
       入れないと複数区間が同じ名前になり、2つ目以降が yt-dlp に
       「has already been downloaded」と判定され、黙って消えていた。
[追加] 区間指定で ffmpeg が 8.x のとき、開始前に警告を出すようにした。
       (下記の不具合が区間の数だけ起きるため)
[修正] 時間指定ONのとき、画質が 360p に落ちていた不具合を修正。
       旧版は結合済みmp4(best[ext=mp4] = YouTubeのitag18固定)を
       使っていたため、必ず640x360になっていた。
[修正] 区間切り出し中にログが完全に止まる問題を修正。ffmpegは進捗を\rで
       出力するため、\n単位で読んでいると無反応に見えていた。
[追加] ダウンロード完了後に、実ファイルの解像度・コーデックをログ表示。
[追加] 使用する ffmpeg のフォルダを指定できるようにした。空欄なら従来
       どおり PATH から自動検出する。起動時のログに、実際に使う ffmpeg の
       パスとバージョンを表示する。

【重要】区間(時間指定)ダウンロードには ffmpeg 7.1 系が必要です。
ffmpeg 8.1 系では --download-sections が機能しません(ffmpeg 側の問題。
yt-dlp Issue #16546 / external-issue)。アプリの「ffmpeg の場所」欄に
7.1 系のフォルダ(例: C:\ffmpeg-7.1\bin)を指定してください。

License: MIT
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import shutil
import json
import os
import re
import sys
import time

APP_NAME    = "yt-dlp GUI"
APP_VERSION = "v3.4.2"
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

# 区間切り出しで、指定した秒ちょうどにカットするか。
#   False (既定): 最寄りのキーフレームで切る。再エンコードなしなので高速。
#                 切り口が数秒ズレるが、編集ソフト側でトリムするなら問題ない。
#   True        : 指定秒ちょうどで切る。区間全体を再エンコードするため非常に遅い
#                 (1080p60を15分切り出すと10〜30分かかることがある)。
FORCE_KEYFRAMES_AT_CUTS = False

# 断片をいくつ同時に取るか。
#
# YouTube は動画を細かい断片に分けて配っていて、既定では1つずつ順番に
# 取る。1本の接続あたりの速度は向こうが絞っているので、順番に取ると
# 回線が空いていても 1MB/秒 前後で頭打ちになる。同時に取れば、そのぶん速い。
#
# 4 にしてあるのは、相手に負担をかけずに効果が出るあたりだから。
# 増やしすぎると弾かれることがある。8 くらいまでは試す価値がある。
# 1 にすれば元の挙動（順番に1つずつ）に戻る。
CONCURRENT_FRAGMENTS = 4


# ── 時間範囲(区間)の入力 ─────────────────────
# 1行に1範囲。ブラウザ拡張「TS工房」の書き出し形式「*開始-終了」を
# そのまま貼り付けられるようにするため、以下をすべて受け付ける。
#   *00:12:00-00:27:00 / 00:12:00-00:27:00 / 12:00-27:00 / 720-1620
# 終了に inf と書くと動画の最後まで。
#
# 行末に「# メモ」を書くと、それが切り出したファイルの名前になる。
#   *00:12:00-00:27:00  # 神プレイ   → 「神プレイ.mp4」
# 行頭の「#」はコメント(下の parse_ranges で読み飛ばす)なので、
# 「#」はどちらの位置でも「ここから先は時間ではない」を意味する。
_T = r"\d{1,6}(?::\d{1,2}){0,2}(?:\.\d+)?"
RANGE_RE = re.compile(
    rf"^\*?\s*(?P<s>{_T})\s*-\s*(?P<e>inf|{_T})\s*(?:#\s*(?P<memo>.*?)\s*)?$", re.I)

RANGE_TIP = (
    "切り出したい範囲を1行に1つ書きます。複数書けば、1回のダウンロードで\n"
    "まとめて切り出します。\n"
    "    *00:12:00-00:27:00\n"
    "    *01:03:10-01:05:00\n"
    "行頭の「*」は有っても無くても構いません。\n"
    "「12:00-27:00」(分:秒)や「720-1620」(秒)でも入力できます。\n"
    "終了に inf と書くと動画の最後までになります。\n"
    "空行と、行頭が「#」の行は読み飛ばします。\n"
    "\n"
    "行のうしろに「# 名前」と書くと、その名前で保存されます。\n"
    "    *00:12:00-00:27:00  # 神プレイ    →  神プレイ.mp4\n"
    "    *01:03:10-01:05:00  # 挨拶        →  挨拶.mp4\n"
    "名前を書かない行は「配信タイトル [00-12-00-00-27-00].mp4」に\n"
    "なります。同じ名前が2つあるときは後のほうに -2 が付きます。\n"
    "※ リスト(プレイリスト)取得のときは名前を付けません。\n"
    "\n"
    "※ 区間切り出しには ffmpeg 7.1 系が必要です(8.1 系は無反応になります)。")


def hms_to_sec(text):
    """"H:MM:SS" / "M:SS" / "SS" を秒に変換する。書式違いは None。"""
    parts = text.split(":")
    if len(parts) > 3:
        return None
    try:
        total = 0.0
        for p in parts:
            total = total * 60 + float(p)
    except ValueError:
        return None
    return total


def parse_ranges(text):
    """複数行のテキストを範囲の一覧にする。

    戻り値は (ranges, errors, dupes)。
      ranges = [(開始文字列, 終了文字列, 開始秒, 終了秒 or None, メモ), ...]
      errors = [(行番号, 行の内容), ...]
      dupes  = [(行番号, 開始文字列, 終了文字列, メモ), ...]  まとめた重複行
    どの行がおかしいのか分からないと直しようがないので、
    エラーは「まとめて1件」ではなく行番号付きで全部返す。
    """
    ranges, errors, dupes, seen = [], [], [], set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = RANGE_RE.match(line)
        if not m:
            errors.append((lineno, line))
            continue
        s_str, e_str = m.group("s"), m.group("e")
        memo = (m.group("memo") or "").strip()
        is_inf = e_str.lower() == "inf"
        s_sec = hms_to_sec(s_str)
        e_sec = None if is_inf else hms_to_sec(e_str)
        if s_sec is None or (not is_inf and e_sec is None):
            errors.append((lineno, line))
            continue
        # 同じ範囲が2行あると、出力名も同じになって2本目が
        # 「has already been downloaded」で保存されない。1つにまとめる。
        # メモだけが違う場合も、yt-dlp から見れば同じ区間なので
        # 2本には分けられない。黙って消えると気づけないので呼び出し側に返す。
        #
        # 見比べるのは秒であって書き方ではない。「00:12:00-00:27:00」と
        # 「720-1620」は書き方が違うだけの同じ区間で、文字列で比べると
        # 別物として通ってしまい、2本目が保存されないまま残る。
        if (s_sec, e_sec) in seen:
            dupes.append((lineno, s_str, e_str, memo))
            continue
        seen.add((s_sec, e_sec))
        ranges.append((s_str, e_str, s_sec, e_sec, memo))
    return ranges, errors, dupes


# ── メモをファイル名にする ───────────────────
# Windows のファイル名に使えない文字は全角に置き換える。消してしまうと
# 「E:*」が「E」になるなど意味が変わるため、形の似た全角を当てる。
_FN_TRANS = str.maketrans({
    "\\": "￥", "/": "／", ":": "：", "*": "＊",
    "?": "？", '"': "”", "<": "＜", ">": "＞", "|": "｜",
})
# デバイス名はファイル名にできない(CON.mp4 も不可)。
_FN_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} \
    | {f"LPT{i}" for i in range(1, 10)}


def safe_filename(name, limit=80):
    """メモをファイル名として使える形にする。使えないときは空文字を返す。"""
    name = "".join(ch for ch in name if ch >= " ")   # 制御文字を落とす
    name = name.translate(_FN_TRANS)
    name = re.sub(r"\s+", " ", name).strip()
    name = name[:limit].strip()
    # 末尾の「.」と空白は Windows が勝手に落とすので、こちらで削る
    name = name.rstrip(" .")
    if name.upper().split(".")[0] in _FN_RESERVED:
        name = "_" + name
    return name


def sec_to_hms(sec):
    """秒を「00:09:55」の形にする(進捗表示用)。"""
    s = int(sec)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fmt_left(sec):
    """残り時間を「約4分」「約40秒」の形にする。細かい数字は要らない。"""
    if sec < 60:
        return f"約{max(int(sec), 5) // 5 * 5}秒"
    if sec < 3600:
        return f"約{int(sec / 60) + 1}分"
    return f"約{sec / 3600:.1f}時間"


def sec_to_tag(sec):
    """秒を出力ファイル名に入っている「00-12-00」の形にする。

    yt-dlp の %(section_start>%H-%M-%S)s と同じ結果になる必要がある。
    あちらは時刻として整形するので24時間で一周する。ここでも合わせる。
    """
    s = int(sec) % 86400
    return f"{s // 3600:02d}-{s % 3600 // 60:02d}-{s % 60:02d}"



# ── ffmpeg の解決 ───────────────────────────
# 設定で指定されたフォルダ(空ならPATH)から ffmpeg / ffprobe を探す。
# 8.1 系の --download-sections 不具合を 7.1 と比較検証できるようにするため、
# バージョン違いの ffmpeg を共存させて切り替えられる形にしている。
def _exe_names():
    return ("ffmpeg.exe", "ffprobe.exe") if os.name == "nt" else ("ffmpeg", "ffprobe")


def resolve_ffmpeg(user_dir):
    """(ffmpeg実行ファイル, ffprobe実行ファイル, yt-dlpに渡すフォルダ) を返す。

    user_dir が空なら PATH から自動検出し、フォルダは None(未指定)になる。
    見つからない場合は (None, None, None)。
    """
    ff_name, fp_name = _exe_names()
    if not user_dir:
        return shutil.which("ffmpeg"), shutil.which("ffprobe"), None

    d = os.path.normpath(os.path.expanduser(user_dir.strip().strip('"')))
    cands = []
    if os.path.isfile(d):
        # ffmpeg.exe 自体を指定された場合は、その親フォルダを見る
        cands.append(os.path.dirname(d))
    # bin を付け忘れたケースも救済する (C:\ffmpeg-7.1 -> C:\ffmpeg-7.1\bin)
    cands += [d, os.path.join(d, "bin")]

    for c in cands:
        ff = os.path.join(c, ff_name)
        if os.path.isfile(ff):
            fp = os.path.join(c, fp_name)
            return ff, (fp if os.path.isfile(fp) else shutil.which("ffprobe")), c
    return None, None, None


def ffmpeg_version(exe):
    """ffmpeg -version の1行目からバージョン文字列を取り出す(失敗時 None)。"""
    if not exe:
        return None
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        out = subprocess.run([exe, "-version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=10,
                             creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (out.stdout or "").splitlines()
    if not lines:
        return None
    m = re.match(r"ffmpeg version (\S+)", lines[0])
    return m.group(1) if m else lines[0].strip()


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
        self.resizable(False, True)
        self.geometry("660x920")  # icon.png使用時は自動で+30

        cfg = load_config()
        self.download_dir = cfg.get("download_dir") or default_download_dir()
        if not os.path.isdir(self.download_dir):
            self.download_dir = default_download_dir()

        self.mode        = tk.StringVar(value=cfg.get("mode", "video"))
        self.time_on     = tk.BooleanVar(value=False)
        self.cookies_on  = tk.BooleanVar(value=bool(cfg.get("use_cookies", False)))
        self.browser_var = tk.StringVar(value=cfg.get("browser", "firefox"))
        self.playlist_on = tk.BooleanVar(value=False)
        self.live_on     = tk.BooleanVar(value=False)
        self.chat_on     = tk.BooleanVar(value=False)
        self.autoupd_on  = tk.BooleanVar(value=bool(cfg.get("auto_update", False)))
        self._retried    = False  # 自動更新後の再試行は1回だけ
        # YouTube がアカウント単位で有効にする SABR 配信に当たったか。
        # 当たるとログイン状態では高い画質が一覧から消え、360p の1本しか
        # 残らない。落ちてきた画質が低かったときに理由を言うために持つ。
        self._sabr_hit       = False
        self._cookie_retried = False  # Cookie無しでの落とし直しも1回だけ
        self.running     = False
        self.proc        = None
        self.cancelled   = False

        # 依存ツールの検出
        # ffmpeg_dir_cfg は「利用者が指定したフォルダ」、ffmpeg_path は
        # 実際に使う実行ファイル、ffmpeg_location は yt-dlp に渡すフォルダ。
        # 3つを分けているのは、設定はフォルダ・実行はexe・引数はフォルダと
        # 単位が違うため(1変数に兼ねると取り違える)。
        self.ytdlp_path      = shutil.which("yt-dlp")
        self.node_path       = shutil.which("node")
        self.ffmpeg_dir_cfg  = (cfg.get("ffmpeg_path") or "").strip()
        self.ffmpeg_path     = None
        self.ffprobe_path    = None
        self.ffmpeg_location = None
        self.ffmpeg_ver      = None
        self._resolve_ffmpeg()

        self._build()
        if self.icon_img:
            self.geometry("660x950")
        self.minsize(660, 740)
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
                             fill="white", font=("Yu Gothic UI", 18, "bold"))
        self.hdr.create_text(22, cy + 14, anchor="w",
                             text=f"{BRAND}  ·  Simple front-end for yt-dlp",
                             fill="#ffd6ec", font=("Yu Gothic UI", 9))
        if self.icon_img:
            self.hdr.create_image(600, cy, image=self.icon_img)
            self.hdr.create_text(540, hdr_h - 14, anchor="e", text=APP_VERSION,
                                 fill="#ffd6ec", font=("Yu Gothic UI", 9, "bold"))
        else:
            self.hdr.create_text(640, cy + 14, anchor="e", text=APP_VERSION,
                                 fill="#ffd6ec", font=("Yu Gothic UI", 9, "bold"))

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
                             relief="flat", font=("BIZ UDGothic", 11), bd=8)
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
                                font=("BIZ UDGothic", 10), padx=10, pady=6,
                                anchor="w")
        self.dir_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(sf_in, text="開く", command=self._open_dir,
                  bg=BG2, fg=FG2, activebackground=BG3,
                  activeforeground=FG, relief="flat", bd=0,
                  font=("Yu Gothic UI", 9), cursor="hand2",
                  padx=10).pack(side="right", padx=(0, 4), pady=3)
        tk.Button(sf_in, text="変更...", command=self._choose_dir,
                  bg=BG2, fg=FG, activebackground=BG3,
                  activeforeground=FG, relief="flat", bd=0,
                  font=("Yu Gothic UI", 9), cursor="hand2",
                  padx=10).pack(side="right", padx=4, pady=3)
        self._refresh_dir_label()

        # ffmpeg の場所(空欄なら PATH から自動検出)
        ff_tip = ("使用する ffmpeg を切り替えたいときに、ffmpeg.exe が入っている"
                  "フォルダ(通常は bin)を指定します。\n"
                  "空欄のままなら、これまでどおり PATH から自動で探します。\n"
                  "※ 指定すると、区間切り出しだけでなく映像+音声の結合にも"
                  "そのフォルダの ffmpeg を使います。")
        self._label(body, "ffmpeg の場所 (空欄で自動検出)")
        ff = tk.Frame(body, bg=BG3, highlightbackground="#1e1e1e",
                      highlightthickness=1)
        ff.pack(fill="x", pady=(4, 12))
        ff_in = tk.Frame(ff, bg=BG3)
        ff_in.pack(fill="x")
        self.ffmpeg_var = tk.StringVar(value=self.ffmpeg_dir_cfg)
        ff_entry = tk.Entry(ff_in, textvariable=self.ffmpeg_var,
                            bg=BG3, fg=GREEN_L, insertbackground=GREEN,
                            relief="flat", font=("BIZ UDGothic", 10), bd=6)
        ff_entry.pack(side="left", fill="x", expand=True, padx=(4, 0), pady=3)
        ff_entry.bind("<Return>",   lambda e: self._apply_ffmpeg_path())
        ff_entry.bind("<FocusOut>", lambda e: self._apply_ffmpeg_path())
        self._add_context_menu(ff_entry, with_clear=True)
        self._add_tooltip(ff_entry, ff_tip)
        tk.Button(ff_in, text="選択...", command=self._choose_ffmpeg,
                  bg=BG2, fg=FG, activebackground=BG3,
                  activeforeground=FG, relief="flat", bd=0,
                  font=("Yu Gothic UI", 9), cursor="hand2",
                  padx=10).pack(side="right", padx=4, pady=3)
        ffh = tk.Label(ff_in, text="(?)", bg=BG3, fg=FG3,
                       font=("Yu Gothic UI", 9), cursor="question_arrow")
        ffh.pack(side="right", padx=(4, 6))
        self._add_tooltip(ffh, ff_tip)

        # モード選択
        self._label(body, "ダウンロードモード")
        mf = tk.Frame(body, bg=BG)
        mf.pack(fill="x", pady=(4, 12))
        self.btn_video = self._mode_btn(mf, "▶  動画＋音声", "video")
        self.btn_video.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.btn_audio = self._mode_btn(mf, "♪  音声のみ", "audio")
        self.btn_audio.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.btn_chat = self._mode_btn(mf, "☰  チャットのみ", "chat")
        self.btn_chat.pack(side="left", fill="x", expand=True)
        self._refresh_mode()

        # 時間指定
        self._label(body, "時間指定")
        tf_outer = tk.Frame(body, bg=BG)
        tf_outer.pack(fill="x", pady=(4, 6))
        self.toggle_btn = self._toggle_label(tf_outer, self._toggle_time)
        self.toggle_btn.pack(side="left")
        tk.Label(tf_outer, text="指定した範囲だけダウンロードする",
                 bg=BG, fg=FG2, font=("Yu Gothic UI", 10)).pack(side="left", padx=8)
        rng_help = tk.Label(tf_outer, text="(?)", bg=BG, fg=FG3,
                            font=("Yu Gothic UI", 9), cursor="question_arrow")
        rng_help.pack(side="left")
        self._add_tooltip(rng_help, RANGE_TIP)

        tf = tk.Frame(body, bg=BG)
        tf.pack(fill="x", pady=(0, 10))
        self._range_box(tf).pack(fill="x", expand=True)
        self._update_time_state()

        # ── オプション(2列グリッド) ──
        self._label(body, "オプション")
        grid = tk.Frame(body, bg=BG)
        grid.pack(fill="x", pady=(4, 12))
        grid.columnconfigure(0, weight=1, uniform="opt")
        grid.columnconfigure(1, weight=1, uniform="opt")

        live_tip = ("配信中のライブを、今の時点からではなく配信開始まで遡って"
                    "ダウンロードします。\n"
                    "※ 配信側がアーカイブを残す設定の場合のみ有効です。\n"
                    "※ 開始まで遡る分、時間がかかることがあります。")
        pl_tip = ("再生リストのURLを入れたとき、リスト内の動画をすべて"
                  "ダウンロードします。\n"
                  "リスト名のフォルダを作り、番号付き(001, 002...)で保存します。\n"
                  "※ OFFのときは、リストURLでも先頭の1本だけ落とします。")
        au_tip = ("ダウンロードに失敗したとき、確認なしでyt-dlpを最新版に"
                  "更新して、もう一度試します。\n"
                  "OFFのときは、更新するかどうかを毎回確認します。\n"
                  "(動画が落とせない原因の多くは、yt-dlpが古いことです)")
        ck_tip = ("メンバー限定・年齢制限など、ログインが必要な動画を"
                  "ダウンロードするときにONにします。\n"
                  "※ Firefox推奨。対象サイトにログイン済みである必要があります。\n"
                  "※ 自己責任でご利用ください(READMEを参照)。")
        chat_tip = ("配信のチャット(コメント)も一緒に保存します。\n"
                    "動画の隣に「タイトル.live_chat.json」が出力されます。\n"
                    "※ アーカイブにチャットリプレイが残っている配信のみ有効。\n"
                    "  メンバー限定チャットや、チャットが無効/削除された配信では"
                    "取得できません。")

        # ライブ配信(左上)
        live_cell = self._option_cell(grid, "ライブ最初から",
                                      self._toggle_live, live_tip)
        live_cell.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 8))
        self.live_btn = live_cell._toggle

        # プレイリスト(右上)
        pl_cell = self._option_cell(grid, "プレイリスト",
                                    self._toggle_playlist, pl_tip)
        pl_cell.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 8))
        self.playlist_btn = pl_cell._toggle

        # Cookie(左下・ブラウザ選択つき)
        def cookie_extra(inner):
            row = tk.Frame(inner, bg=BG3)
            row.pack(fill="x", pady=(6, 0))
            self.browser_menu = tk.OptionMenu(row, self.browser_var, *BROWSERS)
            self.browser_menu.config(bg=BG2, fg=FG, activebackground=BG3,
                                     activeforeground=FG, relief="flat",
                                     highlightthickness=1,
                                     highlightbackground=BORDER,
                                     font=("Yu Gothic UI", 9), cursor="hand2")
            self.browser_menu["menu"].config(bg=BG2, fg=FG,
                                             activebackground=PINK,
                                             activeforeground="white")
            self.browser_menu.pack(side="left")
            tk.Label(row, text="Firefox推奨", bg=BG3, fg=FG3,
                     font=("Yu Gothic UI", 8)).pack(side="left", padx=6)

        ck_cell = self._option_cell(grid, "Cookieを使う",
                                    self._toggle_cookies, ck_tip,
                                    extra=cookie_extra)
        ck_cell.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(0, 0))
        self.cookie_btn = ck_cell._toggle
        self._refresh_cookie_state()

        # 自動更新(右下)
        au_cell = self._option_cell(grid, "失敗時に自動更新",
                                    self._toggle_autoupd, au_tip)
        au_cell.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(0, 0))
        self.autoupd_btn = au_cell._toggle
        self._paint_toggle(self.autoupd_btn, self.autoupd_on.get())

        # チャットも保存(3段目・左)
        chat_cell = self._option_cell(grid, "チャットも保存",
                                      self._toggle_chat, chat_tip)
        chat_cell.grid(row=2, column=0, sticky="nsew", padx=(0, 5), pady=(8, 0))
        self.chat_btn = chat_cell._toggle

        # DLボタン
        self.dl_btn = tk.Button(body, text="▼  ダウンロード開始",
                                bg=PINK, fg="white",
                                activebackground="#be185d",
                                activeforeground="white",
                                relief="flat", bd=0,
                                font=("Yu Gothic UI", 13, "bold"),
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
                            font=("Yu Gothic UI", 9))
        self.dot.pack(side="left")
        self.status_lbl = tk.Label(sf2_in, text="待機中",
                                   bg=BG3, fg=FG2, font=("Yu Gothic UI", 10))
        self.status_lbl.pack(side="left", padx=6)

        # ログ
        self._label(body, "ログ")
        log_frame = tk.Frame(body, bg=LOG_BG, highlightbackground="#1a1a1a",
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.log = tk.Text(log_frame, bg=LOG_BG, fg=LOG_FG,
                           font=("BIZ UDGothic", 9), relief="flat", bd=8,
                           wrap="word", state="disabled", height=6)
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
                 bg=BG, fg=FG3, font=("Yu Gothic UI", 8)).pack(side="left")
        tk.Label(ftr, text="利用規約と著作権の範囲でご利用ください",
                 bg=BG, fg=FG3, font=("Yu Gothic UI", 8)).pack(side="right")

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

        self._log_ffmpeg()

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
    # ── ツールチップ ─────────────────────────
    def _add_tooltip(self, widget, text):
        tip = {"win": None}

        def show(_=None):
            if tip["win"] or not text:
                return
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 6
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            win.configure(bg=BORDER)
            lbl = tk.Label(win, text=text, bg="#202020", fg=FG,
                           font=("Yu Gothic UI", 9), justify="left",
                           wraplength=380, padx=10, pady=7,
                           relief="solid", bd=0)
            lbl.pack()
            tip["win"] = win

        def hide(_=None):
            if tip["win"]:
                tip["win"].destroy()
                tip["win"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

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
        # Entry と Text では選択・削除の指定方法が違う(Text に select_range は
        # 無く、削除位置も 0 ではなく "1.0")。両方で同じメニューを使うため
        # ここで吸収する。
        is_text = isinstance(entry, tk.Text)

        def select_all():
            if is_text:
                entry.tag_add("sel", "1.0", "end-1c")
            else:
                entry.select_range(0, "end")

        def clear_paste():
            entry.delete("1.0", "end") if is_text else entry.delete(0, "end")
            entry.event_generate("<<Paste>>")

        menu = tk.Menu(entry, tearoff=0, bg=BG2, fg=FG,
                       activebackground=PINK, activeforeground="white",
                       relief="flat", bd=0)
        menu.add_command(label="貼り付け",
                         command=lambda: entry.event_generate("<<Paste>>"))
        if with_clear:
            menu.add_command(label="消して貼り付け", command=clear_paste)
        menu.add_command(label="コピー",
                         command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="切り取り",
                         command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_separator()
        menu.add_command(label="すべて選択", command=select_all)

        def popup(e):
            if str(entry.cget("state")) == "normal":
                menu.tk_popup(e.x_root, e.y_root)
        entry.bind("<Button-3>", popup)
        entry.bind("<Control-a>", lambda e: (select_all(), "break")[1])

    def _label(self, parent, text):
        tk.Label(parent, text=text.upper(), bg=BG, fg=FG3,
                 font=("Yu Gothic UI", 8, "bold")).pack(anchor="w")

    def _mode_btn(self, parent, text, value):
        return tk.Button(parent, text=text, relief="flat", bd=0,
                         font=("Yu Gothic UI", 10), cursor="hand2", pady=8,
                         command=lambda: self._set_mode(value))

    def _toggle_label(self, parent, command):
        lbl = tk.Label(parent, text="  OFF  ", bg=BORDER, fg=FG3,
                       font=("Yu Gothic UI", 9, "bold"),
                       cursor="hand2", padx=6, pady=3)
        lbl.bind("<Button-1>", lambda e: command())
        return lbl

    def _option_cell(self, parent, title, command, tip, extra=None):
        """2列グリッド用のオプションセル(トグル+タイトル+説明ホバー)を作る。
        トグルのウィジェットを返す。"""
        cell = tk.Frame(parent, bg=BG3, highlightbackground=BORDER,
                        highlightthickness=1)
        inner = tk.Frame(cell, bg=BG3, padx=10, pady=8)
        inner.pack(fill="both", expand=True)

        top = tk.Frame(inner, bg=BG3)
        top.pack(fill="x")
        btn = self._toggle_label(top, command)
        btn.pack(side="left")
        title_lbl = tk.Label(top, text=title, bg=BG3, fg=FG,
                             font=("Yu Gothic UI", 10, "bold"))
        title_lbl.pack(side="left", padx=8)
        if tip:
            help_lbl = tk.Label(top, text="(?)", bg=BG3, fg=FG3,
                                font=("Yu Gothic UI", 9), cursor="question_arrow")
            help_lbl.pack(side="left")
            self._add_tooltip(help_lbl, tip)
            self._add_tooltip(btn, tip)

        if extra is not None:
            extra(inner)

        cell._toggle = btn
        return cell

    def _range_box(self, parent):
        """時間範囲の複数行入力欄を作って返す。

        1行に1範囲。ブラウザ拡張「TS工房」の書き出し形式「*開始-終了」を
        そのまま貼り付けられるようにしてある。開始/終了の2欄だと1回に
        1区間しか指定できず、同じ配信から複数の切り抜きを作るたびに
        やり直しが必要だったため、複数行の欄にした。
        """
        frame = tk.Frame(parent, bg=BG)
        tk.Label(frame, text="時間範囲 (1行に1つ / 例 *00:12:00-00:27:00  # 神プレイ)",
                 bg=BG, fg=FG3, font=("Yu Gothic UI", 8)).pack(anchor="w")
        ef = tk.Frame(frame, bg=BG2, highlightbackground=BORDER,
                      highlightthickness=1)
        ef.pack(fill="x", pady=(3, 0))
        t = tk.Text(ef, height=3, bg=BG2, fg=FG, insertbackground=GREEN,
                    relief="flat", font=("BIZ UDGothic", 11), bd=6,
                    wrap="none", undo=True)
        t.pack(fill="both", expand=True)
        t.insert("1.0", "*00:00:00-00:01:00")
        t.bind("<FocusIn>",  lambda ev: ef.config(highlightbackground=GREEN))
        t.bind("<FocusOut>", lambda ev: ef.config(highlightbackground=BORDER))
        self._add_context_menu(t, with_clear=True)
        # 名前を付けられることは、欄を見ただけでは分からない。
        # ツールチップは (?) に気づいた人しか読まないので、欄の下に出す。
        tk.Label(frame,
                 text="うしろに「# 名前」を書くと、その名前で保存されます"
                      "(例: 神プレイ.mp4)。書かなければ時刻が入った名前になります",
                 bg=BG, fg=FG3, font=("Yu Gothic UI", 8),
                 justify="left").pack(anchor="w", pady=(3, 0))
        frame._entry = t
        self.range_text = t
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

    # ── ffmpeg の場所 ────────────────────────
    def _resolve_ffmpeg(self):
        """設定値から ffmpeg / ffprobe / --ffmpeg-location 用フォルダを求める。"""
        ff, fp, d = resolve_ffmpeg(self.ffmpeg_dir_cfg)
        self.ffmpeg_path     = ff
        self.ffprobe_path    = fp
        self.ffmpeg_location = d
        # バージョンは起動時ログと、区間DL開始前の 8.x 警告の両方で使う。
        # 毎回 ffmpeg を起動し直さないようここで1度だけ取る。
        self.ffmpeg_ver      = ffmpeg_version(ff)

    def _log_ffmpeg(self):
        """今どの ffmpeg を使うのかをログに出す。区間DLの切り分けに使う。"""
        if self.ffmpeg_path:
            src = "手動指定" if self.ffmpeg_dir_cfg else "PATHから自動検出"
            self._log(f"ffmpeg: 検出OK ({src})", "ok")
            self._log(f"  パス: {self.ffmpeg_path}", "info")
            ver = self.ffmpeg_ver
            self._log(f"  バージョン: {ver or '取得できませんでした'}", "info")
        elif self.ffmpeg_dir_cfg:
            self._log(f"ffmpeg: 指定された場所に見つかりません → "
                      f"{self.ffmpeg_dir_cfg}", "warn")
            self._log("  → ffmpeg.exe が入っているフォルダ(通常は bin)を"
                      "指定してください。空欄にすると自動検出に戻ります", "warn")
        else:
            self._log("ffmpeg: 見つかりません。映像と音声の結合やmp3変換に"
                      "失敗する可能性があります(READMEを参照)", "warn")

    def _apply_ffmpeg_path(self):
        new = self.ffmpeg_var.get().strip().strip('"')
        if new == self.ffmpeg_dir_cfg:
            return          # FocusOut は頻繁に飛ぶので、変化が無ければ何もしない
        self.ffmpeg_dir_cfg = new
        self.ffmpeg_var.set(new)
        self._resolve_ffmpeg()
        self._save_cfg()
        if not new:
            self._log("ffmpeg: PATH からの自動検出に戻しました", "info")
        self._log_ffmpeg()

    def _choose_ffmpeg(self):
        init = self.ffmpeg_dir_cfg or self.ffmpeg_location or os.path.expanduser("~")
        d = filedialog.askdirectory(
            initialdir=init if os.path.isdir(init) else os.path.expanduser("~"),
            title="ffmpeg.exe があるフォルダ(通常は bin)を選択")
        if d:
            self.ffmpeg_var.set(os.path.normpath(d))
            self._apply_ffmpeg_path()

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
        m = self.mode.get()
        off = {"bg": BG2, "fg": FG2, "activebackground": BG3}
        self.btn_video.config(**off)
        self.btn_audio.config(**off)
        self.btn_chat.config(**off)
        if m == "video":
            self.btn_video.config(bg=PINK, fg="white", activebackground="#be185d")
        elif m == "audio":
            self.btn_audio.config(bg=GREEN, fg="white", activebackground="#15803d")
        elif m == "chat":
            self.btn_chat.config(bg=PURPLE, fg="white", activebackground="#6d28d9")

    def _toggle_time(self):
        self.time_on.set(not self.time_on.get())
        self._paint_toggle(self.toggle_btn, self.time_on.get())
        self._update_time_state()

    def _toggle_live(self):
        self.live_on.set(not self.live_on.get())
        self._paint_toggle(self.live_btn, self.live_on.get())
        if self.live_on.get():
            self._log("ライブ最初から: ON · 配信開始まで遡ってダウンロードします"
                      "(配信側がアーカイブを残す設定の場合のみ)", "info")

    def _toggle_chat(self):
        self.chat_on.set(not self.chat_on.get())
        self._paint_toggle(self.chat_btn, self.chat_on.get())
        if self.chat_on.get():
            self._log("チャットも保存: ON · 動画の隣に「タイトル.live_chat.json」を"
                      "出力します(チャットリプレイが残っている配信のみ)", "info")

    def _toggle_playlist(self):
        self.playlist_on.set(not self.playlist_on.get())
        self._paint_toggle(self.playlist_btn, self.playlist_on.get())
        if self.playlist_on.get():
            self._log("プレイリスト: ON · リスト内の全動画を専用フォルダに"
                      "まとめて保存します", "info")

    def _toggle_autoupd(self):
        self.autoupd_on.set(not self.autoupd_on.get())
        self._paint_toggle(self.autoupd_btn, self.autoupd_on.get())
        self._save_cfg()
        if self.autoupd_on.get():
            self._log("自動更新: ON · 失敗時は確認なしでyt-dlpを更新して再試行します",
                      "info")
        else:
            self._log("自動更新: OFF · 失敗時に更新するか毎回確認します", "info")

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
                e = child._entry
                # disabledbackground / disabledforeground は Entry 専用で、
                # Text に渡すと TclError になる。ウィジェット種別で分ける。
                if isinstance(e, tk.Text):
                    e.config(state=state, fg=fg_)
                else:
                    e.config(state=state, fg=fg_,
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
            "auto_update":  bool(self.autoupd_on.get()),
            "ffmpeg_path":  self.ffmpeg_dir_cfg,
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
        ranges  = []

        if time_on:
            ranges, errors, dupes = parse_ranges(self.range_text.get("1.0", "end"))
            if errors:
                for lineno, raw in errors:
                    self._log(f"[エラー] {lineno}行目「{raw}」は時間範囲として"
                              "読めません。「*00:12:00-00:27:00」のように"
                              "「開始-終了」の形で書いてください", "warn")
                return
            if not ranges:
                self._log("[エラー] 時間範囲が入力されていません。"
                          "「*00:12:00-00:27:00」の形で、1行に1つ"
                          "書いてください", "warn")
                return
            for s_str, e_str, s_sec, e_sec, _memo in ranges:
                if e_sec is not None and e_sec <= s_sec:
                    self._log(f"[エラー]「{s_str}-{e_str}」は終了が開始より"
                              "前(または同じ)です", "warn")
                    return
            # 同じ区間の行は1つにまとめている。メモが違っていても
            # 分けられないので、どれを使ったのかを知らせる。
            for lineno, s_str, e_str, memo in dupes:
                self._log(f"[注意] {lineno}行目「{s_str}-{e_str}」は"
                          "同じ範囲が既にあるためまとめました"
                          + (f"(メモ「{memo}」は使われません)" if memo else ""),
                          "warn")
            # 出力ファイル名は区間を HH-MM-SS で入れて区別している。
            # 24時間で一周するため、24時間以上離れた区間どうしは
            # 同名になりうる(2つ目以降が保存されない)。
            if any(s >= 86400 for _, _, s, _, _ in ranges) and len(ranges) > 1:
                self._log("[注意] 24時間を超える位置の範囲があります。"
                          "ファイル名の時刻表記は24時間で一周するため、"
                          "24時間ちょうど離れた範囲があると2つ目が"
                          "保存されません", "warn")
            # 区間切り出しは内部で ffmpeg を使うため、無い場合は先に止める。
            # (旧版はここで黙って360pに落としていたが、それをやめた)
            if not self.ffmpeg_path:
                self._log("[エラー] 時間指定には ffmpeg が必要です。"
                          "インストール後にもう一度お試しください"
                          "(READMEを参照)", "warn")
                self._set_status("ffmpeg 未検出", RED)
                return
            # 8.x は --download-sections が動かない。区間の数だけ無反応に
            # なるので、走り出す前に知らせる。
            if (self.ffmpeg_ver or "").startswith("8."):
                self._log(f"[警告] ffmpeg {self.ffmpeg_ver} では区間ダウンロード"
                          "が機能しません(ffmpeg 側の不具合)。反応が無いまま"
                          "止まる場合は、「ffmpeg の場所」に 7.1 系のフォルダを"
                          "指定してください", "warn")

        try:
            os.makedirs(self.download_dir, exist_ok=True)
        except OSError as e:
            self._log(f"[エラー] 保存先を作成できません: {e}", "warn")
            return

        ytdlp = self.ytdlp_path or "yt-dlp"

        if self.playlist_on.get():
            # リスト名のフォルダを作り、番号付きで保存
            out_tpl = os.path.join(self.download_dir,
                                   "%(playlist_title)s",
                                   "%(playlist_index)03d - %(title)s.%(ext)s")
            cmd = [ytdlp, "--encoding", "utf-8", "--yes-playlist"]
        else:
            out_tpl = os.path.join(self.download_dir, "%(title)s.%(ext)s")
            cmd = [ytdlp, "--encoding", "utf-8", "--no-playlist"]

        # 区間指定のときは出力名に区間の開始/終了を入れる。入れないと
        # 複数区間が同じファイル名になり、2つ目以降が yt-dlp に
        # 「has already been downloaded」と判定されて保存されない。
        # %(section_start>%H-%M-%S)s は秒数を時:分:秒に整形する書式で、
        # 00:12:00 から始まる区間なら 00-12-00 になる。
        # チャットのみモードは区間を渡さない(下の cmd 組み立てを参照)ので、
        # ここで名前に入れると section_start が無く「[NA-NA]」になってしまう。
        sections_on = time_on and mode != "chat"
        if sections_on:
            stem, ext = os.path.splitext(out_tpl)      # ext = ".%(ext)s"
            out_tpl = (f"{stem} [%(section_start>%H-%M-%S)s"
                       f"-%(section_end>%H-%M-%S)s]{ext}")

        # ffmpeg の場所が指定されていれば明示的に渡す。
        # 区間切り出しだけでなく、映像+音声の結合(299+140 など)でも
        # ffmpeg を使うため、time_on に関係なく常に付ける。
        if self.ffmpeg_location:
            cmd += ["--ffmpeg-location", self.ffmpeg_location]

        if self.cookies_on.get():
            cmd += ["--cookies-from-browser", self.browser_var.get()]

        # Node.js があれば、一部動画の解析用に JSランタイムを指定
        if self.node_path:
            cmd += ["--js-runtimes", "node", "--remote-components", "ejs:github"]

        if mode == "chat":
            # チャットのみ: 動画/音声は落とさず live_chat.json だけ保存
            cmd += ["--skip-download", "--write-subs", "--sub-langs", "live_chat"]
        elif mode == "audio":
            cmd += ["-f", "bestaudio",
                    "--extract-audio",
                    "--audio-format", "mp3",
                    "--audio-quality", "0"]
        else:
            # 編集ソフト互換重視: H.264(avc1) を最優先で取得する
            # (VP9/AV1 の webm は一部編集ソフトでデコードできないため避ける)
            #
            # ※ v3.2.1 まではここで time_on のとき "best[ext=mp4]" に
            #   差し替えていたが、YouTube で映像+音声が1本になっている
            #   mp4 は itag18 (640x360) しか無いため、時間指定するだけで
            #   強制的に360pになっていた。この差し替えは撤去済み。
            vid_format = (
                "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/"
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo+bestaudio/"
                "best"
            )
            cmd += ["-f", vid_format, "--merge-output-format", "mp4"]

        if mode != "chat":
            if self.live_on.get():
                cmd += ["--live-from-start"]

            if self.chat_on.get():
                # 配信チャットのリプレイを live_chat.json として動画の隣に保存
                cmd += ["--write-subs", "--sub-langs", "live_chat"]

            if time_on:
                for s_str, e_str, _s, _e, _memo in ranges:
                    cmd += ["--download-sections", f"*{s_str}-{e_str}"]
                # 指定秒ちょうどで切る場合のみ。区間全体の再エンコードが
                # 走るため非常に遅い。既定はOFF(ファイル冒頭の定数で切替)。
                if FORCE_KEYFRAMES_AT_CUTS:
                    cmd += ["--force-keyframes-at-cuts"]

        # 断片を同時に取って速度を上げる。チャットのみのときは動画を
        # 落とさないので付けない。
        if mode != "chat" and CONCURRENT_FRAGMENTS > 1:
            cmd += ["-N", str(CONCURRENT_FRAGMENTS)]

        # 進捗を改行区切りで出力させる(GUIのログを行単位で読むため)
        cmd += ["--newline"]

        cmd += ["-o", out_tpl, url]

        # 再試行(自動更新後)のためにコマンドを保持
        self._last_cmd = cmd
        self._retried = False
        # 完了後にメモの名前へ変えるための控え(区間を渡さないときは空)。
        #
        # リスト(プレイリスト)のときは付けない。区間はリストの動画すべてに
        # 同じものが適用されるので、同じメモの名前が動画の数だけできてしまい、
        # どれがどの動画か分からなくなる。番号付きの名前のまま残すほうが良い。
        self._rename_plan = ranges if sections_on and not self.playlist_on.get() else []
        if sections_on and self.playlist_on.get() and any(r[4] for r in ranges):
            self._log("[注意] リスト取得のときは、メモをファイル名にしません"
                      "(動画ごとに同じ名前になってしまうため)", "warn")

        self.running = True
        self.cancelled = False
        self.dl_btn.config(bg="#555", text="■  中止する",
                           activebackground="#444")
        self._set_status("ダウンロード中...", PINK)
        self._log(f"[開始] {url}", "info")
        mode_label = {"video": "動画+音声(mp4)", "audio": "音声のみ(mp3)",
                      "chat": "チャットのみ(live_chat.json)"}.get(mode, mode)
        self._log(f"[モード] {mode_label}", "info")
        if mode == "video":
            self._log("[画質] H.264(avc1) の最高画質で取得します", "info")
        if time_on and mode == "chat":
            self._log("[注意] チャットのみモードでは時間指定は使われません"
                      "(チャットは常に配信全体ぶんが保存されます)", "warn")
        if sections_on:
            note = ("精密カットON: 再エンコードのため時間がかかります"
                    if FORCE_KEYFRAMES_AT_CUTS
                    else "切り口は最寄りのキーフレームに寄ります")
            tag = "warn" if FORCE_KEYFRAMES_AT_CUTS else "info"
            self._log(f"[区間] {len(ranges)}個の範囲を切り出します({note})", tag)
            for n, (s_str, e_str, _s, _e, memo) in enumerate(ranges, 1):
                self._log(f"  {n}. {s_str} - {e_str}"
                          + (f"  → 「{memo}」" if memo else ""), "info")
            # どの ffmpeg で切り出したかをログに残す(不具合の切り分け用)
            self._log(f"[ffmpeg] {self.ffmpeg_path}", "info")

        self._run_download(cmd)

    # 出力ファイルのパスをログから拾うための正規表現
    _OUT_PATTERNS = (
        re.compile(r'^\[download\] Destination:\s*(.+)$'),
        re.compile(r'^\[Merger\] Merging formats into "(.+)"$'),
        re.compile(r'^\[ExtractAudio\] Destination:\s*(.+)$'),
        re.compile(r'^\[download\]\s+(.+?)\s+has already been downloaded'),
    )

    def _capture_out_path(self, line):
        """yt-dlp のログ行から保存先ファイルパスを拾って記憶する。

        あわせて、今どの区間を処理しているのかもここで拾う。保存先の名前に
        区間が入っているので、進捗の分母(区間の長さ)がこれで分かる。
        """
        for pat in self._OUT_PATTERNS:
            m = pat.match(line)
            if m:
                path = m.group(1).strip()
                self._out_files.append(path)
                self._note_section(path)
                return

    def _note_section(self, path):
        """保存先の名前から区間の長さを読み取る(進捗の分母にする)。"""
        m = self._SEC_IN_NAME.search(os.path.basename(path))
        if not m:
            return
        h1, m1, s1, h2, m2, s2 = (int(x) for x in m.groups())
        start, end = h1 * 3600 + m1 * 60 + s1, h2 * 3600 + m2 * 60 + s2
        if end <= start:
            # 24時間を跨いだ区間。名前だけでは長さを出せないので諦める
            return
        if (start, end) == self._cur_sec:
            return          # 同じ区間の2本目(映像と音声)。測り直さない
        self._cur_sec = (start, end)
        self._cur_sec_dur = end - start
        self._cur_sec_t0 = None   # 次の進捗行で測り始める

    def _verify_output(self):
        """落ちてきたファイルの解像度・コーデックを ffprobe で確認してログ表示。

        時間指定などの条件で意図せず低画質が落ちてくる事故を、
        編集を始める前に気づけるようにするための最終チェック。
        """
        # 指定フォルダの ffprobe を優先する。7.1 で落としたファイルを
        # 8.1 の ffprobe で見る、といったちぐはぐを避けるため。
        ffprobe = self.ffprobe_path or shutil.which("ffprobe")
        if not ffprobe:
            return
        # 動画ファイルだけを対象にする(重複は除去し、最後のものを見る)
        vids = [p for p in dict.fromkeys(self._out_files)
                if os.path.splitext(p)[1].lower() in (".mp4", ".mkv", ".webm", ".mov")]
        if not vids:
            return
        path = vids[-1]
        if not os.path.exists(path):
            return
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            out = subprocess.run(
                [ffprobe, "-v", "error",
                 "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,codec_name",
                 "-of", "json", path],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20, creationflags=flags,
            )
            info = json.loads(out.stdout or "{}")
            st = (info.get("streams") or [{}])[0]
            w, h = st.get("width"), st.get("height")
            codec = st.get("codec_name", "?")
        except (OSError, ValueError, subprocess.SubprocessError):
            return
        if not (w and h):
            return
        msg = f"[確認] 実際の解像度: {w}x{h} / コーデック: {codec}"
        if h > 480:
            self._log(msg, "ok")
            return

        self._log(msg, "warn")

        # Cookie が原因のときは、そう言い切る。
        #
        # 以前はここで「元動画がこの画質しか無いか、ffmpeg が正しく
        # 動いていない可能性があります」とだけ出していた。どちらも外れで、
        # 実際は YouTube がアカウントを SABR 配信の対象にしたせいだった。
        # 見当違いの候補を並べると、当たっている所を探しに行けない。
        if self._sabr_hit and self.cookies_on.get():
            self._log("[原因] YouTube がこのアカウントを SABR 配信の対象に"
                      "しています。ログインした状態だと 360p しか渡して"
                      "もらえません。yt-dlp や ffmpeg のせいではありません",
                      "warn")
            self._log("[対処] 「Cookieを使う」のチェックを外して落とし直して"
                      "ください。会員限定・年齢制限の動画以外は、Cookie が"
                      "無くても落とせます", "warn")
            self._offer_cookieless_retry()
            return

        if self.cookies_on.get():
            self._log("[注意] 想定より低い解像度で保存されています。"
                      "まず「Cookieを使う」のチェックを外して試してください"
                      "(ログイン状態だと低い画質しか渡されないことがあります)。"
                      "それでも変わらなければ、元動画がこの画質しか"
                      "持っていない可能性があります", "warn")
            return

        self._log("[注意] 想定より低い解像度で保存されています。"
                  "元動画がこの画質しか無いか、ffmpeg が正しく"
                  "動いていない可能性があります", "warn")

    def _offer_cookieless_retry(self):
        """Cookie を使わずに落とし直すかを聞き、はいなら即やり直す。

        同じファイル名で落とし直すことになるので --force-overwrites を足す。
        付けないと yt-dlp が「has already been downloaded」で何もせずに
        終わり、360p のファイルが残ったままになる。"""
        if self._cookie_retried or not self._last_cmd:
            return
        ans = messagebox.askyesno(
            "低い画質で保存されました",
            "YouTube がこのアカウントを SABR 配信の対象にしているため、\n"
            "ログインした状態では 360p しか取得できません。\n\n"
            "Cookie を使わずに、同じ動画を落とし直しますか?\n"
            "(会員限定・年齢制限の動画では失敗します)",
            icon="question")
        if not ans:
            self._log("[情報] そのままにしました。あとで直すときは"
                      "「Cookieを使う」のチェックを外してください", "info")
            return

        self._cookie_retried = True

        # --cookies-from-browser とその値を取り除く
        cmd, skip = [], False
        for a in self._last_cmd:
            if skip:
                skip = False
                continue
            if a == "--cookies-from-browser":
                skip = True
                continue
            cmd.append(a)
        if "--force-overwrites" not in cmd:
            cmd.insert(1, "--force-overwrites")

        self._log("[再試行] Cookie を使わずに落とし直します", "warn")
        self.running = True
        self.cancelled = False
        self.dl_btn.config(state="disabled", bg="#555", text="■  中止する")
        self._set_status("Cookie無しで再取得中...", PINK)
        self._last_cmd = cmd
        self._run_download(cmd)

    def _rename_by_memo(self):
        """メモ付きの区間で切り出したファイルを、そのメモの名前に変える。

        yt-dlp は1回の実行で「区間ごとに別の名前」を付けられない。
        区間の数だけ yt-dlp を起動し直せば付けられるが、区間ごとに
        取得からやり直すことになるうえ、ffmpeg 7.1 が要る処理を
        区間の数だけ通すことになるので、失敗する機会も待ち時間も増える。
        そこで「1回で全部落として、あとから名前を変える」形にしている。

        どのファイルがどの区間かは、出力名の形をこちらで組み立てて
        いる(「タイトル [00-12-00-00-27-00].mp4」)ので時刻から確定できる。
        yt-dlp のログを読む必要はない。
        """
        plan = [r for r in self._rename_plan if r[4]]
        if not plan:
            return
        try:
            names = os.listdir(self.download_dir)
        except OSError:
            return

        for s_str, e_str, s_sec, e_sec, memo in plan:
            stem = safe_filename(memo)
            if not stem:
                self._log(f"[注意]「{s_str}-{e_str}」のメモはファイル名に"
                          "使える文字が無いので、名前を変えませんでした", "warn")
                continue
            s_tag = sec_to_tag(s_sec)
            if e_sec is None:
                # 終了が inf のときは動画の長さが入るので、こちらでは分からない
                pat = re.compile(rf" \[{s_tag}-[\d\-]+\]$")
            else:
                pat = re.compile(rf" \[{s_tag}-{sec_to_tag(e_sec)}\]$")

            hits = [n for n in names if pat.search(os.path.splitext(n)[0])]
            if not hits:
                self._log(f"[注意]「{s_str}-{e_str}」のファイルが見つからず、"
                          f"「{stem}」に変えられませんでした", "warn")
                continue

            exts = [os.path.splitext(n)[1] for n in hits]
            final = self._uniq_stem(stem, exts)
            for name, ext in zip(hits, exts):
                src = os.path.join(self.download_dir, name)
                dst = os.path.join(self.download_dir, final + ext)
                try:
                    os.rename(src, dst)
                except OSError as e:
                    self._log(f"[注意]「{name}」の名前を変えられませんでした"
                              f"({e.strerror or e})", "warn")
                    continue
                names.remove(name)
                names.append(final + ext)
                # あとの処理が古いパスを見ないように差し替えておく
                self._out_files = [dst if p == src else p for p in self._out_files]
                self._log(f"[名前] {final + ext}", "ok")

    def _uniq_stem(self, stem, exts):
        """同じ名前のファイルがあるときに「-2」「-3」を足して避ける。"""
        cand, n = stem, 1
        while any(os.path.exists(os.path.join(self.download_dir, cand + e))
                  for e in exts):
            n += 1
            cand = f"{stem}-{n}"
        return cand

    # ffmpeg の進捗行(frame= 123 fps= 45 ... time=00:01:23.45 ...)
    _FFMPEG_PROGRESS = re.compile(r'^(frame|size)=')
    _FFMPEG_TIME     = re.compile(r'time=(\d{2}:\d{2}:\d{2})')
    # 出力ファイル名に入れている区間「 [00-12-00-00-27-00]」
    _SEC_IN_NAME = re.compile(
        r' \[(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})\]')

    def _handle_line(self, line):
        """yt-dlp / ffmpeg の出力1行を振り分ける(ワーカースレッドから呼ばれる)。"""
        # ffmpeg の進捗はログに流すと大量になるので、ステータス表示だけ更新する
        if self._FFMPEG_PROGRESS.match(line):
            m = self._FFMPEG_TIME.search(line)
            if not m:
                self.after(0, self._set_status, "切り出し中... 処理中", PINK)
                return
            pos = m.group(1)
            # 区間の長さが分かるときは、割合と残り時間まで出す。
            # 「00:05:22」だけだと、あと何分なのかが分からず
            # 止まっているようにしか見えない(実際そう言われた)。
            dur = self._cur_sec_dur
            if not dur:
                self.after(0, self._set_status, f"切り出し中... {pos}", PINK)
                return
            done = hms_to_sec(pos) or 0
            p = min(done / dur, 1.0)
            text = f"切り出し中... {pos} / {sec_to_hms(dur)} ({p * 100:.0f}%)"
            if self._cur_sec_t0 is None:
                self._cur_sec_t0 = time.monotonic()
            # 序盤は見積もりが大きく振れるので1割進むまで出さない。
            # 終わりかけで「残り約5秒」と出すのも意味が無いので出さない。
            elif 0.1 <= p < 0.99:
                left = (time.monotonic() - self._cur_sec_t0) * (1 - p) / p
                text += f"  残り{fmt_left(left)}"
            self.after(0, self._set_status, text, PINK)
            return

        tag = "info"
        if "[download]" in line or "Destination" in line:
            tag = "ok"
        elif "WARNING" in line or "ERROR" in line:
            tag = "warn"
            self._err_lines.append(line)
            # 「SABR-only streaming experiment for your account」。
            # これが出た回は、ログインしているせいで高い画質が消えている。
            if "SABR" in line:
                self._sabr_hit = True
        self._capture_out_path(line)
        self.after(0, self._log, line, tag)

    def _run_download(self, cmd):
        """cmd を別スレッドで実行し、終了時に _on_done を呼ぶ。"""
        self._err_lines = []  # エラー診断用にERROR/WARNING行を収集
        self._out_files = []  # 保存されたファイルのパス(完了後の画質確認用)
        self._sabr_hit = False
        # 進捗表示用。今どの区間を、どれだけの長さで処理しているか
        self._cur_sec = None
        self._cur_sec_dur = None
        self._cur_sec_t0 = None
        if not hasattr(self, "_rename_plan"):
            self._rename_plan = []
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
                # ffmpeg は進捗を \r(復帰)で上書き出力するため、
                # 行単位(\n)で読むと区間切り出し中に完全に無反応になる。
                # \r と \n の両方を区切りとして扱う。
                buf = []
                while True:
                    ch = self.proc.stdout.read(1)
                    if not ch:
                        break
                    if ch in ("\r", "\n"):
                        line = "".join(buf).strip()
                        buf = []
                        if line:
                            self._handle_line(line)
                        continue
                    buf.append(ch)
                if buf:
                    line = "".join(buf).strip()
                    if line:
                        self._handle_line(line)

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

    def _diagnose_error(self):
        """収集したエラー行から、利用者向けのヒントを返す(なければ None)。"""
        blob = "\n".join(getattr(self, "_err_lines", [])).lower()
        if not blob:
            return None
        # ログイン/Cookie が必要なケース
        if ("sign in" in blob or "confirm you" in blob or "not a bot" in blob
                or "login required" in blob or "members-only" in blob
                or "members only" in blob or "this video is available to"
                in blob or "cookies" in blob or "age" in blob and "restrict" in blob):
            if not self.cookies_on.get():
                return ("💡 ログインが必要な動画のようです。"
                        "「Cookieを使う」をONにして、対象サイトに"
                        "ログイン済みのブラウザ(Firefox推奨)を選んでから"
                        "もう一度お試しください。")
            else:
                return ("💡 ログインが必要なようですが、Cookieは既にONです。"
                        "選んだブラウザで対象サイトにログインしているか、"
                        "別のブラウザを選んで試してみてください。")
        # フォーマット関連
        if "requested format is not available" in blob or "format is not available" in blob:
            return ("💡 指定した形式が見つかりませんでした。"
                    "時間指定やモードを変えると落とせる場合があります。")
        # 動画が存在しない/非公開/削除
        if ("video unavailable" in blob or "private video" in blob
                or "has been removed" in blob or "does not exist" in blob):
            return ("💡 動画が非公開・削除済み、またはURLが間違っている"
                    "可能性があります。URLを確認してください。")
        # ネットワーク系
        if ("unable to download" in blob and "http error" in blob) or \
           "connection" in blob or "timed out" in blob:
            return ("💡 通信エラーの可能性があります。"
                    "ネット接続を確認して、もう一度お試しください。")
        return None

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

        if success:
            self.dl_btn.config(state="normal", bg=PINK,
                               activebackground="#be185d",
                               text="▼  ダウンロード開始")
            self._set_status("完了！", GREEN)
            self._log(f"[完了] 保存先: {self.download_dir}", "ok")
            self._verify_output()
            self._rename_by_memo()
            return

        if self.cancelled:
            self.dl_btn.config(state="normal", bg=PINK,
                               activebackground="#be185d",
                               text="▼  ダウンロード開始")
            self._set_status("中止しました", "#f59e0b")
            return

        # ── 失敗時 ──
        # まだ自動更新を試していない & yt-dlpが存在する場合のみ、更新を提案/実行
        if not self._retried and self.ytdlp_path:
            if self.autoupd_on.get():
                # トグルON: 確認なしで更新→再試行
                self._log("[自動更新] ダウンロードに失敗しました。"
                          "yt-dlpを更新して再試行します...", "warn")
                self._retried = True
                self._update_and_retry()
                return
            else:
                # トグルOFF: ダイアログで確認
                self.dl_btn.config(state="normal", bg=PINK,
                                   activebackground="#be185d",
                                   text="▼  ダウンロード開始")
                self._set_status("失敗 — 更新を確認中", RED)
                ans = messagebox.askyesno(
                    "ダウンロードに失敗しました",
                    "yt-dlp が古いことが原因かもしれません。\n\n"
                    "yt-dlp を最新版にアップデートして、もう一度試しますか?",
                    icon="question")
                if ans:
                    self._retried = True
                    self._update_and_retry()
                    return

        # ここに来たら最終的な失敗
        self.dl_btn.config(state="normal", bg=PINK,
                           activebackground="#be185d",
                           text="▼  ダウンロード開始")
        self._set_status("エラーが発生しました", RED)
        hint = self._diagnose_error()
        if hint:
            self._log(hint, "warn")
        else:
            self._log("[エラー] ダウンロードに失敗しました。ログ上部のERROR行と"
                      "READMEのトラブルシューティングを確認してください", "warn")

    def _update_and_retry(self):
        """yt-dlp を更新し、成功したら直前のコマンドを再実行する。"""
        self.running = True
        self.dl_btn.config(state="disabled", bg="#555",
                           text="yt-dlp を更新中...")
        self._set_status("yt-dlpを更新中...", PINK)
        self._log("[更新] yt-dlp を最新版に更新しています。少々お待ちください...", "info")

        def task():
            updated = self._do_update()
            if updated:
                self.after(0, self._log, "[更新] 完了。ダウンロードを再試行します", "ok")
                self.after(0, self._set_status, "再試行中...", PINK)
                self.after(0, self.dl_btn.config,
                           {"text": "■  中止する", "bg": "#555"})
                self.after(0, self._run_download, self._last_cmd)
            else:
                self.after(0, self._log,
                           "[更新] yt-dlp を更新できませんでした。"
                           "コマンドプロンプトで pip install -U yt-dlp を"
                           "手動で実行してみてください(詳細はREADME)", "warn")
                self.after(0, self._finish_failure)

        threading.Thread(target=task, daemon=True).start()

    def _do_update(self):
        """pip版・exe版の両方を試して yt-dlp を更新。成功でTrue。"""
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        ytdlp = self.ytdlp_path or "yt-dlp"

        # 1) pip版として更新を試す(READMEの推奨インストール方法)
        attempts = [
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            [ytdlp, "-U"],  # 2) 単体exe版のフォールバック
        ]
        for cmd in attempts:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   env=env, creationflags=flags, timeout=180)
                out = (r.stdout or "") + (r.stderr or "")
                if out.strip():
                    for ln in out.splitlines():
                        if ln.strip():
                            self.after(0, self._log, "  " + ln.rstrip(), "info")
                if r.returncode == 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                continue
        return False

    def _finish_failure(self):
        self.running = False
        self.proc = None
        self.dl_btn.config(state="normal", bg=PINK,
                           activebackground="#be185d",
                           text="▼  ダウンロード開始")
        self._set_status("エラーが発生しました", RED)


if __name__ == "__main__":
    app = App()
    app.mainloop()
