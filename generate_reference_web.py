# -*- coding: utf-8 -*-
"""
参考書の「スマホ最適化 Web 版」を生成する（PDF 版 = generate_reference_book.py の兄弟）。

PDF は A4 紙面・印刷・所有用、Web 版はスマホで読む「レッスンプレイヤー」:
- 上部タブ（🏠＋単元番号）で単元を切り替え
- 単元の中身は 1 ステップずつ表示（わかること → 節1 → 節2 → … → 重要語 → まとめ）
  「つぎへ」ボタン or 左右スワイプで進む。進捗バーと ページ位置（2/6）を常時表示
- 進捗は localStorage に保存し、目次に ✓済 / つづきから を出す
- URL ハッシュ（#t3s2）でどの画面にも直リンクできる
- QR コードの代わりに「LINEでAI先生に質問」タップボタン（QR はスマホでは読めないため）

データは PDF 版と同じ reference/{章}.json（教材の一元管理を保つ）。

使い方:
  python -X utf8 generate_reference_web.py            # 全19冊 → output/web/ref/{NN}/index.html
  python -X utf8 generate_reference_web.py --deploy 04  # 指定の章を配信ビルド dist-web/ref/ へ

デプロイ先: dist-web/ref/{NN}/（tsudumon.jp/ref/{NN}/）
※ 現状は検証・サンプル用の限定公開（LP からリンクしない・noindex）。
   全巻の購入者向け公開はライセンスゲートの設計が決まってから。
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import urllib.parse
from pathlib import Path

BASE = Path(__file__).parent
REF_DIR = BASE / "reference"
BOOKS_DIR = BASE / "books"
OUT_DIR = BASE / "output" / "web" / "ref"
ASSET_DIR = BASE / "assets" / "reference"

# Firebase Web SDK 設定（ブラウザに配布される公開クライアント設定）。
# 秘密ではないが、ソースへ直書きしないよう env（VITE_FIREBASE_*）から読む。
#
# 探索順は pdf-workbook/.env → marutto-study/.env（どちらも gitignore 済み）。
# つづもんは独自ドメイン化で配信面が marutto-study から独立したが、Firebase プロジェクト
# （chatstudy-63477）は共有のままなので設定値は同じ。pdf-workbook 単体でもビルドできるよう
# 自前の .env を先に見て、無ければ従来どおり marutto-study 側にフォールバックする。
_FB_ENV_CANDIDATES = [
    BASE / ".env",
    BASE.parent / "marutto-study" / ".env",
]


def _load_env_file(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def firebase_web_config() -> dict:
    # 後ろの候補ほど優先度が低いので、先に見つかった値が勝つように逆順で重ねる
    env = {}
    for path in reversed(_FB_ENV_CANDIDATES):
        env.update(_load_env_file(path))
    env.update(os.environ)
    cfg = {
        "apiKey": env.get("VITE_FIREBASE_API_KEY", ""),
        "authDomain": env.get("VITE_FIREBASE_AUTH_DOMAIN", ""),
        "projectId": env.get("VITE_FIREBASE_PROJECT_ID", ""),
        "appId": env.get("VITE_FIREBASE_APP_ID", ""),
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        raise SystemExit(
            "Firebase Web 設定が未取得です（" + ", ".join(missing) + "）。\n"
            "pdf-workbook/.env（または marutto-study/.env）に "
            "VITE_FIREBASE_API_KEY / _AUTH_DOMAIN / _PROJECT_ID / _APP_ID "
            "を設定してから再生成してください。"
        )
    return cfg
# Web埋め込み用のコンパクト版単元表紙（codex量産: gen_web_topic_covers.py）
WEB_COVER_DIR = BASE / "covers" / "out" / "webtopics"
DEPLOY_DIR = BASE / "dist-web" / "ref"

LIFF_ID_UNITS = "2009587166-LjyCza2c"

BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def esc(s: str) -> str:
    return html.escape(s)


def rich(s: str) -> str:
    out, pos = [], 0
    for m in BOLD_RE.finditer(s):
        out.append(esc(s[pos:m.start()]))
        out.append(f'<span class="mark">{esc(m.group(1))}</span>')
        pos = m.end()
    out.append(esc(s[pos:]))
    return "".join(out)


# ── 本文ルビ（難読の用語に、その単元での初出1回だけ振る）──
# 読みは terms[].reading をそのまま使う（教材データの一元管理）。
# 何度も振ると紙面がうるさく、読みが目に入って覚えなくなるので「初出だけ」。
KANJI_RE = re.compile(r"[一-鿿]")


def ruby_pairs(terms: list) -> list:
    """[(用語, よみ), …] を長い順に。漢字を含む2文字以上だけルビ対象。"""
    pairs = []
    for x in terms or []:
        term, rd = (x.get("term") or "").strip(), (x.get("reading") or "").strip()
        if term and rd and len(term) >= 2 and KANJI_RE.search(term):
            pairs.append((term, rd))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs


def make_rich(pairs: list, used: set):
    """rich() と同じ（**強調**）に加えて、初出の用語へルビを振るレンダラを返す。"""
    def ruby_text(s: str) -> str:
        if not pairs:
            return esc(s)
        out, i, n = [], 0, len(s)
        while i < n:
            hit = None
            for term, rd in pairs:                    # 長い語から見るので最長一致
                if term not in used and s.startswith(term, i):
                    hit = (term, rd)
                    break
            if hit:
                used.add(hit[0])
                out.append(f"<ruby>{esc(hit[0])}<rt>{esc(hit[1])}</rt></ruby>")
                i += len(hit[0])
            else:
                out.append(esc(s[i]))
                i += 1
        return "".join(out)

    def render(s: str) -> str:
        out, pos = [], 0
        for m in BOLD_RE.finditer(s):
            out.append(ruby_text(s[pos:m.start()]))
            out.append(f'<span class="mark">{ruby_text(m.group(1))}</span>')
            pos = m.end()
        out.append(ruby_text(s[pos:]))
        return "".join(out)

    return render


# つづもん公式LINEのベーシックID。`oaMessage` はトークを開いて**本文を下書き**する。
# 生徒は送信ボタンを押すだけ＝Botは reply で返せる（**配信枠を消費しない**）。
# 旧 LIFF（line.chatstudy.jp 側）はつづもんから切り離したので使わない。
TSUDUMON_OA_ID = "@215uijik"


def line_ask_url(ch_no: str, title: str) -> str:
    """
    読んだ単元について LINE で質問するためのリンク。

    トークを開いて**本文を下書き**するので、生徒は送信を押すだけ。
    Botは reply で返せる＝**配信枠を消費しない**。
    本文に **第N章** を入れておくと、Bot側が単元を特定して
    その単元に合った受け答えができる（`tsudumonDoneReport`）。
    """
    text = f"「{title}」（第{int(ch_no)}章）を読んだよ"
    return (f"https://line.me/R/oaMessage/{TSUDUMON_OA_ID}/"
            f"?{urllib.parse.quote(text)}")



# ── 読み上げ音声（tools/gen_ref_narration.js が作った narration.json と対応づける）──
# 音声は「文」単位で作り、ハイライトは「読点で切った句」単位。
# ここでの分け方は gen_ref_narration.js と完全に一致させること（ズレるとハイライトが狂う）。
TTS_DIR = BASE / "output" / "web" / "tts"
TTS_URLS = BASE / "dist" / "tts" / "_urls.json"
MIN_CLAUSE = 8


def split_sentences(full: str) -> list[str]:
    out, buf, depth = [], "", 0
    for ch in str(full):
        buf += ch
        if ch in "「（『":
            depth += 1
        elif ch in "」）』":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in "。！？":
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return [x for x in out if x.strip()]


def split_clauses(sentence: str) -> list[str]:
    raw, buf, bold = [], "", False
    chars = list(str(sentence))
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch == "*" and i + 1 < len(chars) and chars[i + 1] == "*":
            bold = not bold
            buf += "**"
            i += 2
            continue
        buf += ch
        if not bold and ch == "、":
            raw.append(buf)
            buf = ""
        i += 1
    if buf:
        raw.append(buf)
    out: list[str] = []
    for c in raw:
        if out and (len(strip_bold(c)) < MIN_CLAUSE or len(strip_bold(out[-1])) < MIN_CLAUSE):
            out[-1] += c
        else:
            out.append(c)
    return out or [sentence]


def strip_bold(s: str) -> str:
    return BOLD_RE.sub(lambda m: m.group(1), str(s))


class Narration:
    """1単元ぶんの読み上げ。ブロックを読む順に spans() へ渡すと、
    narration.json の chunk 順（hook→(見出し・リード・本文・ここだけ)×節→30秒まとめ）と
    そろった <span class="s" data-i="…"> を返す。"""

    def __init__(self, ch_no: str, topic_id: str, urls: dict):
        self.key = f"{ch_no}-{topic_id}"
        self.url = urls.get(self.key)
        self.chunks: list[dict] = []
        self.steps: list[int] = []      # 句ごとの「そのマスがあるステップ番号」
        self.i = 0
        self.step = 0
        path = TTS_DIR / self.key / "narration.json"
        if self.url and path.exists():
            self.chunks = json.loads(path.read_text(encoding="utf-8"))["chunks"]

    @property
    def ok(self) -> bool:
        return bool(self.url and self.chunks)

    def spans(self, text: str, renderer=rich) -> str:
        """読み上げ対象のテキストを句ごとの span で包む（音声が無ければ素通し）。"""
        if not self.ok:
            return renderer(text)
        out = []
        for sent in split_sentences(text):
            for c in split_clauses(sent):
                out.append(f'<span class="s" data-i="{self.i}">{renderer(c)}</span>')
                self.steps.append(self.step)
                self.i += 1
        return "".join(out)

    def timeline(self) -> list:
        """[[開始秒, 長さ, そのマスがあるステップ番号], …]。ステップは spans() 呼び出し時の値。"""
        return [[c["start"], c["dur"], self.steps[k] if k < len(self.steps) else 0]
                for k, c in enumerate(self.chunks)]


# 教材ゲート（中間案・ゆるめ「頭出しは見せる」）。
# 無料体験の単元は tsudumonCore.TSUDUMON_FREE_REFERENCE_KEYS と一致させる。
FREE_REFERENCE_KEYS = {"04-ritsuryo-nara"}
# 頭出し = 表紙(step0)+節1+節2 まで。step>=3 で購入者判定。
# （2→3 に緩和: 1節だけでは「読んだ感」が出ず、体験開始まで届かないため）
REF_LOCK_FROM = 3


def grade_of_ch(ch_no: str) -> str:
    n = int(ch_no)
    return "中1" if n <= 6 else "中2" if n <= 12 else "中3"


def build(chapter: str) -> tuple[str, list[str]]:
    """(HTML, 使用した画像ファイル名リスト) を返す。"""
    spec = json.loads((REF_DIR / f"{chapter}.json").read_text(encoding="utf-8"))
    ch_no = chapter[:2]
    images: list[str] = []
    # 読み上げ音声（アップロード済みのURL一覧。無ければ音声UIは出ない）
    tts_urls = json.loads(TTS_URLS.read_text(encoding="utf-8")) if TTS_URLS.exists() else {}
    audio: dict[int, dict] = {}

    # 問題集 Web 版の単元 index（topicId → #t番号。t1=年表なので +2）: 相互リンク用
    wb_index = {}
    books_path = BOOKS_DIR / f"{chapter}.json"
    if books_path.exists():
        books_spec = json.loads(books_path.read_text(encoding="utf-8"))
        for i, tid in enumerate(books_spec["topics"]):
            wb_index[tid] = i + 2

    def use_img(name: str):
        if name and (ASSET_DIR / name).exists():
            images.append(str(ASSET_DIR / name) + "|" + name)  # src絶対|出力名
            return f"img/{name}"
        return None

    char_dir = BASE / "assets" / "characters"

    def char_web(name: str, cls: str, bust: bool = False):
        """assets/characters/{name} をページの img/ へ。

        bust=True にすると、出力名に中身のハッシュを入れる
        （例 char_fab_sensei.3f9a2c11.png）。画像は Cache-Control 24時間＋
        Service Worker のキャッシュ優先で配っているので、**同じ名前のまま
        中身を差し替えると、古い絵が最大1日返り続ける**。差し替えの多い
        アイコン類はハッシュ付きにして、名前ごと変わるようにする。"""
        src = char_dir / name
        if not src.exists():
            return ""
        flat = "char_" + name
        if bust:
            stem, ext = flat.rsplit(".", 1)
            h = hashlib.md5(src.read_bytes()).hexdigest()[:8]
            flat = f"{stem}.{h}.{ext}"
        images.append(str(src) + "|" + flat)
        return f'<img class="{cls}" src="img/{flat}" alt="">'

    navi_html = (char_web("char_sensei_m_sm.png", "navi navi-char")
                 or '<div class="navi navi-emoji">🦉</div>')
    # チャットの丸ボタンの中身（AIロボットのアイコン）。無ければ従来の絵文字にフォールバック。
    fab_html = char_web("fab_ai.png", "fab-img", bust=True) or "🤖"

    # ── ホーム（表紙＋目次。進捗表示は JS が data-t を見て差し込む）──
    def toc_thumb(t):
        u = use_img(t.get("image", ""))
        return f'<img class="toc-thumb" src="{u}" alt="" loading="lazy">' if u else '<span class="toc-thumb ph"></span>'
    toc_items = "".join(
        f'<button class="toc-item" data-go="{i}">'
        f'{toc_thumb(t)}'
        f'<span class="toc-no">{i}</span>'
        f'<span class="toc-name">{esc(t["name"])}</span>'
        f'<span class="toc-state" data-state-t="{i}"></span>'
        f'<span class="toc-arrow">›</span></button>'
        for i, t in enumerate(spec["topics"], 1))

    views = [f"""
<section class="view home" data-t="0">
  <div class="home-topline">
    <div class="badge3"><span class="b-vol">{esc(spec['volume'])}</span><span class="b-kind">参考書</span></div>
  </div>
  <header class="top hometop">
    <div class="ht-main">
      <h1 class="ht-title">{esc(spec['title'])}</h1>
      <div class="sub">{esc(spec['subtitle'])}</div>
    </div>
    <div class="ht-mascot">{navi_html}<span class="ht-bubble">いっしょに<br>読もう！</span></div>
  </header>
  <div class="bookprog"><div class="bp-txt" id="bookTxt">読み終えた単元 0 / 0</div>
    <div class="bp-bar"><div class="bp-fill" id="bookFill"></div></div></div>
  <button class="resume" id="resumeBtn" hidden>▶ つづきから読む<span id="resumeWhere"></span></button>
  <nav class="toc">
    <div class="toc-head"><div class="toc-h">単元を選択</div></div>
    {toc_items}
  </nav>
  {f'<a class="wb-home" href="../../wb/{ch_no}/index.html">問題集を開く（この本の問題を解く）</a>' if wb_index else ''}
  <footer class="foot">
    <div>つづもん 参考書</div>
    <div class="foot-note">紙やタブレットでじっくり派には、ダウンロード済みのPDF版もどうぞ。</div>
  </footer>
</section>"""]

    # ── 各単元（ステップに分割）──
    for i, t in enumerate(spec["topics"], 1):
        steps = []
        narr = Narration(ch_no, t["topicId"], tts_urls)
        narr.step = 0
        # この単元の本文レンダラ（**強調** ＋ 初出の用語にルビ）。
        # used は単元ごとに新しく作るので、単元をまたぐと再びルビが付く。
        body_rich = make_rich(ruby_pairs(t.get("terms")), set())

        # step 0: 単元表紙（covers/out/webtopics の表紙画像＝PDF単元表紙と同デザイン
        # を埋め込む。画像が無い場合は従来の HTML 表示にフォールバック）
        hook = (f'<div class="hook">{navi_html}<div class="bubble">{narr.spans(t["hook"])}</div></div>'
                if t.get("hook") else "")
        web_cover = WEB_COVER_DIR / f"{ch_no}-{t['topicId']}.webp"
        if web_cover.exists():
            flat = f"cover-{t['topicId']}.webp"
            images.append(str(web_cover) + "|" + flat)
            steps.append(f"""
    <div class="step" data-label="この単元でわかること">
      <img class="cover-img zoomable" src="img/{flat}"
           alt="{esc(t['name'])}（この単元でわかること）">
      {hook}
    </div>""")
        else:
            hero = use_img(t.get("image", ""))
            hero_html = ""
            if hero:
                cap = (f'<figcaption>{esc(t.get("imageCaption", ""))}</figcaption>'
                       if t.get("imageCaption") else "")
                tilt = " art-even" if i % 2 == 0 else ""
                hero_html = (f'<figure class="cover-art{tilt}">'
                             f'<img class="zoomable" src="{hero}" alt="" loading="lazy">{cap}</figure>')
            learn = t.get("learn") or [s["heading"] for s in t["sections"]]
            learn_html = "".join(
                f'<li><span class="ov-num">{n}</span><span>{rich(x)}</span></li>'
                for n, x in enumerate(learn, 1))
            cheer_char = char_web("sensei_m_banzai.png", "cheer-char")
            cheer_html = (f'<div class="cheer">{cheer_char}'
                          '<div class="cheer-bubble">この単元もがんばろう！</div></div>'
                          ) if cheer_char else ""
            steps.append(f"""
    <div class="step" data-label="この単元でわかること">
      {hook}
      {hero_html}
      <div class="overview">
        <div class="ov-h">この単元でわかること</div>
        <ul class="ov-list">{learn_html}</ul>
      </div>
      {cheer_html}
    </div>""")

        # step 1..n: 各節（本文＋ここだけ覚える＋用語カード）
        used_terms = set()
        for si, s in enumerate(t["sections"]):
            narr.step = si + 1
            heading_html = narr.spans(s["heading"], esc)
            lead = (f'<div class="sec-lead">{narr.spans(s["lead"], esc)}</div>'
                    if s.get("lead") else "")
            body_html = narr.spans(s["body"], body_rich)
            # 節の横帯挿絵（本文の上・フル幅）。無ければ何も出さない。
            sec_img = use_img(s.get("image", ""))
            sec_fig = ""
            if sec_img:
                # 見た目に変化をつける: 既定は左右交互 float、データで
                # imagePos("left"/"right"/"wide")・imageSize("sm"/"lg") 指定があれば優先。
                pos = s.get("imagePos") or ("left" if si % 2 else "right")
                cls = ["sec-fig"]
                if s.get("imageFit") == "contain":  # 図版・地図は切らず全表示
                    cls.append("fig-contain")
                if pos == "left":
                    cls.append("pos-left")
                elif pos == "wide":
                    cls.append("pos-wide")
                if s.get("imageSize"):
                    cls.append("size-" + s["imageSize"])
                cap = (f'<figcaption>{esc(s.get("imageCaption", ""))}</figcaption>'
                       if s.get("imageCaption") else "")
                sec_fig = (f'<figure class="{" ".join(cls)}"><img class="zoomable" src="{sec_img}" alt="" '
                           f'loading="lazy">{cap}</figure>')
            point = (f'<div class="point"><span class="ptag">ここだけ覚える</span>'
                     f'<div class="ptxt">{narr.spans(s["point"], body_rich)}</div></div>'
                     if s.get("point") else "")
            side_items = []
            if s.get("aside"):
                side_items.append(f'<div class="tip">{rich(s["aside"])}</div>')
            for x in t.get("terms", []):
                if x["term"] in used_terms or x["term"] not in s["body"]:
                    continue
                used_terms.add(x["term"])
                rd = (f'<span class="w-rd">{esc(x.get("reading", ""))}</span>'
                      if x.get("reading") else "")
                side_items.append(
                    f'<div class="word"><span class="w-term">{esc(x["term"])}{rd}</span>'
                    f'<span class="w-desc">{esc(x["desc"])}</span></div>')
            side = (f'<div class="words">{"".join(side_items)}</div>'
                    if side_items else "")
            steps.append(f"""
    <div class="step" data-label="{esc(s['heading'])}">
      <h3><span class="sec-no">{si + 1}</span>{heading_html}</h3>
      {lead}
      {sec_fig}
      <p>{body_html}</p>
      {point}
      {side}
    </div>""")

        # step: 重要語チェック（フラッシュカード: タップで表裏。両面表示チェックで一覧）
        if t.get("terms"):
            # 表＝説明（これを読んで用語を当てる）／裏＝用語（答え）。
            # 「🔁 裏表入れ替え」で表裏を反転（用語→意味）もできる。
            cards = "".join(
                f"""<div class="tcell" data-tk="{esc(x['term'])}">
      <button class="tcard" type="button">
      <span class="tcard-inner">
        <span class="tc-face tc-front">
          <span class="tc-desc">{esc(x['desc'])}</span>
          <span class="tc-tap">タップで用語</span>
        </span>
        <span class="tc-face tc-back">
          <span class="tc-term">{esc(x['term'])}</span>
          <span class="tc-rd">{esc(x.get('reading', ''))}</span>
          <span class="tc-tap">タップで説明</span>
        </span>
      </span>
      </button>
      <div class="tmark">
        <button class="tm tm-ok" type="button" data-tm="1">覚えた</button>
        <button class="tm tm-ng" type="button" data-tm="0">まだ</button>
      </div>
    </div>"""
                for x in t["terms"])
            steps.append(f"""
    <div class="step" data-label="重要語チェック" data-terms="{i}">
      <div class="terms-h">重要語チェック<span class="terms-sub">説明を読んで用語を言えるかな？</span></div>
      <div class="terms-count" data-tcount>覚えた 0 / {len(t['terms'])}</div>
      <div class="terms-tools">
        <div class="tt-btns"><button type="button" class="shuffle-btn">シャッフル</button><button type="button" class="swap-btn">裏表入れ替え</button><button type="button" class="only-ng-btn">まだの語だけ</button></div>
        <label class="both-toggle"><input type="checkbox" class="both-chk">両面表示</label>
      </div>
      <div class="tgrid">{cards}</div>
      <div class="terms-empty" hidden>ぜんぶ「覚えた」になったよ！ おつかれさま 🎉</div>
    </div>""")

        # 最終 step: 30秒まとめ ＋ AI先生 ＋ 完了
        # まとめは最終ステップ（表紙1＋節n＋重要語チェック(あれば)）
        narr.step = 1 + len(t["sections"]) + (1 if t.get("terms") else 0)
        s30 = t.get("summary30") or t.get("summary")
        s30_owl = f"""
        <div class="sum30-navi">{char_web("owl_think_sm.png", "navi-char")}
          <div class="sum30-bubble">テスト前は ここを見直すのじゃ！</div></div>"""
        summary = f"""
      <div class="sum30">
        <div class="sum30-h">⏱ 30秒まとめ<span class="sum30-tag">テスト前にここだけ！</span></div>
        <div class="sum30-body">{narr.spans(s30)}</div>
        {s30_owl}
      </div>""" if s30 else ""
        url = line_ask_url(ch_no, t.get("name") or t.get("title") or "")
        wb_btn = ""
        if t["topicId"] in wb_index:
            wb_btn = (f'<a class="wb-btn" href="../../wb/{ch_no}/index.html#t{wb_index[t["topicId"]]}">'
                      f'<span class="ai-main">問題を解く<span class="ai-sub">'
                      f'穴埋め・一問一答・4択・記述</span></span></a>')
        steps.append(f"""
    <div class="step" data-label="30秒まとめ">
      {summary}
      <div class="done">この単元はこれで完了！</div>
      <div class="end-btns">
        {wb_btn}
        <a class="ai-btn" href="{url}" target="_blank" rel="noopener">
          <span class="ai-main">LINEで報告<span class="ai-sub">送信を押すだけ。質問もできます</span></span>
        </a>
      </div>
    </div>""")

        if narr.ok:
            audio[i] = {"url": narr.url, "tl": narr.timeline()}

        _key = f"{ch_no}-{t['topicId']}"
        _lock = "" if _key in FREE_REFERENCE_KEYS else f' data-lock="{REF_LOCK_FROM}"'
        views.append(f"""
<section class="view" data-t="{i}"{_lock}>
  <div class="tband"><span class="tno">{i}</span><h2>{esc(t['name'])}</h2>
    <button class="play-unit" type="button" data-play="{i}" hidden><span class="pu-ic"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg></span>音声で聞く</button></div>
  {''.join(steps)}
</section>""")

    # 単元の選択は「番号の丸タブ横スクロール」をやめてドロワー（一覧シート）に。
    # 19単元では丸タブが見切れて番号も読めず、上部バーの幅も食っていたため。
    drawer = "".join(
        f'<button class="dw-item" data-go="{i}" data-dw="{i}">'
        f'<span class="dw-no">{i}</span>'
        f'<span class="dw-name">{esc(t["name"])}</span>'
        f'<span class="dw-state" data-state-t="{i}"></span></button>'
        for i, t in enumerate(spec["topics"], 1))

    # ページ内チャット用: 単元 t(1..N) → 参考書 topicKey（章番号-topicId）
    topic_keys_json = json.dumps(
        [f"{ch_no}-{t['topicId']}" for t in spec["topics"]], ensure_ascii=False)

    page = (TEMPLATE
            .replace("__TITLE__", f"{spec['volume']} {spec['title']}｜つづもん参考書")
            .replace("__HEADBAR__", f"{esc(spec['volume'])} {esc(spec['title'])}")
            .replace("__DRAWER__", drawer)
            .replace("__FAB__", fab_html)
            .replace("__NTOPICS__", str(len(spec["topics"])))
            .replace("__STORAGE_KEY__", f"tzmref-{ch_no}")
            .replace("__CH_NO__", ch_no)
            .replace("__GRADE__", grade_of_ch(ch_no))
            .replace("__AUDIO__", json.dumps(audio, ensure_ascii=False))
            .replace("__WB_VIEWS__", json.dumps(
                [0] + [wb_index.get(t["topicId"], 0) for t in spec["topics"]]))
            .replace("__TOPIC_KEYS__", topic_keys_json)
            .replace("__FIREBASE_WEB_CONFIG__", json.dumps(firebase_web_config()))
            .replace("__VIEWS__", "".join(views)))
    return page, images


TEMPLATE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<script>if(location.hostname==='tsudumon.web.app'){location.replace('https://tsudumon.jp'+location.pathname+location.search+location.hash);}</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#fffdf8">
<link rel="manifest" href="../../manifest.webmanifest">
<title>__TITLE__</title>
<script>
// 表示設定（文字サイズ・配色・ルビ）は、描画前に当てる（あとから当てるとチラつくため）。
// 設定は tsudumon 全ページ共通の localStorage['tzm-view'] に持つ。
(function () {
  var v = {};
  try { v = JSON.parse(localStorage.getItem('tzm-view') || '{}') || {}; } catch (e) {}
  var th = v.theme || 'auto';
  var dark = th === 'dark' || (th === 'auto' && window.matchMedia
             && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  if (v.fs) document.documentElement.style.setProperty('--fs', v.fs);
  if (v.ruby === 0) document.documentElement.classList.add('noruby');
  window.__tzmView = v;
})();
</script>
<style>
  /* 配色は変数だけで切り替える（下の [data-theme="dark"] が夜モード）。
     --fs は文字サイズ設定（小/中/大）の倍率。 */
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --cream:#fffdf8; --line:#fde68a;
          --ink:#1c1917; --ink2:#44403c; --ink3:#6f675e; --card:#fff; --card2:#fff9ef;
          --edge:#f0e6d2; --edge2:#e2d5bd; --tint:#fffbeb; --shadow:rgba(120,80,20,.14);
          --fs:1; }
  :root[data-theme="dark"] {
    --brand:#f0a355; --deep:#ffd9a8; --amber:#f59e0b; --cream:#17140f; --line:#5c4a1e;
    --ink:#f2ece2; --ink2:#ded5c7; --ink3:#a89d8c; --card:#221d16; --card2:#1e1a14;
    --edge:#3a3128; --edge2:#453a2d; --tint:#2a2318; --shadow:rgba(0,0,0,.5); }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         font-size:calc(16px * var(--fs)); line-height:1.95; color:var(--ink);
         background:var(--cream);
         padding-bottom:86px; }
  /* 読み上げプレーヤーが出ている間は、その高さぶん本文の下に余白を足す
     （足さないと最後の数行がプレーヤーに隠れて読めない） */
  body.has-player { padding-bottom:150px; }
  .wrap { max-width:640px; margin:0 auto; padding:0 16px 24px; }

  .mark { background:linear-gradient(transparent 55%, var(--line) 55%); font-weight:bold; padding:0 1px; }
  /* 本文ルビ（初出の用語だけ）。行が詰まらないよう本文の行間を少し広めに取る */
  ruby { ruby-align:center; }
  ruby rt { font-size:.46em; font-weight:normal; color:var(--ink3); letter-spacing:0; }
  :root.noruby rt { display:none; }        /* 設定で「ルビを消す」を選んだとき */
  /* アニメを減らす設定の端末では、ページめくり等の演出を止める */
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.001ms !important; animation-iteration-count:1 !important;
                             transition-duration:.001ms !important; scroll-behavior:auto !important; }
  }
  :root[data-theme="dark"] .mark { background:linear-gradient(transparent 55%, #6b5520 55%); }

  /* キーボード操作の現在地を必ず見せる */
  :focus-visible { outline:3px solid var(--amber); outline-offset:2px; border-radius:6px; }

  /* ── 読み上げ（音声＋読んでいる句のハイライト）── */
  .s { border-radius:6px; padding:.14em .12em; margin:0 -.12em;
       -webkit-box-decoration-break:clone; box-decoration-break:clone;
       transition:background-color .15s ease, color .15s ease; }
  body.reading .s { cursor:pointer; }
  /* 読み終わった句は「薄く」するが、読み返せる濃さは保つ（#8a8279 は薄すぎた） */
  .s.read { color:var(--ink3); }
  .s.now { background:#fcd34d; color:#1c1917; }
  .s.now .mark { background:none; }
  /* 単元見出しの音声ボタン（タップで読み上げ再生。適度に目立つ塗りボタン＋再生アイコン） */
  .play-unit { display:inline-flex; align-items:center; gap:6px; margin-left:auto; flex:none;
               background:linear-gradient(#f59e0b,#ea7a09); color:#fff;
               border:none; border-radius:20px; padding:7px 15px 7px 9px; font-size:13px; font-weight:bold;
               font-family:inherit; cursor:pointer; box-shadow:0 3px 0 #c2620a, 0 4px 9px rgba(217,119,6,.3);
               transition:transform .12s, filter .12s; }
  .pu-ic { flex:none; width:22px; height:22px; border-radius:50%; background:rgba(255,255,255,.28);
           display:inline-flex; align-items:center; justify-content:center; }
  .pu-ic svg { width:13px; height:13px; fill:#fff; margin-left:1px; }
  .play-unit:active { transform:translateY(2px); box-shadow:0 1px 0 #c2620a; }
  @media (hover:hover) { .play-unit:hover { filter:brightness(1.06); } }
  .play-unit[hidden] { display:none; }
  /* 問題集の「解説を読む」から来たときに出す「問題にもどる」ボタン（すぐ問題へ戻れる） */
  .backpill { position:fixed; left:50%; transform:translateX(-50%);
              bottom:calc(78px + env(safe-area-inset-bottom)); z-index:40;
              background:var(--brand); color:#fff; font-weight:bold; font-size:13.5px;
              border-radius:22px; padding:9px 18px 9px 13px; text-decoration:none;
              box-shadow:0 4px 14px rgba(120,50,10,.35); display:inline-flex; align-items:center; gap:5px; }
  .backpill svg { width:16px; height:16px; fill:none; stroke:#fff; stroke-width:2.4;
                  stroke-linecap:round; stroke-linejoin:round; }
  .backpill[hidden] { display:none; }
  /* 下部プレーヤー（音声のある単元では常設。ナビバーの上に重ねる）。
     ナビバーの実高さ（内側10+12+15+10 ≒ 58px）＋ホームバーぶんを避ける。 */
  .aplayer { position:fixed; left:0; right:0; bottom:calc(58px + env(safe-area-inset-bottom));
             z-index:25;
             background:var(--card2); border-top:1px solid var(--edge);
             box-shadow:0 -3px 12px var(--shadow); padding:7px 0 8px; }
  .aplayer[hidden] { display:none; }
  .ap-in { max-width:640px; margin:0 auto; padding:0 14px; display:flex; align-items:center; gap:9px; }
  .ap-btn { flex:none; width:40px; height:40px; border-radius:50%; border:none; background:var(--brand);
            color:#fff; font-size:16px; cursor:pointer; box-shadow:0 2px 6px rgba(180,83,9,.35); }
  .ap-seek { flex:1; min-width:0; }
  .ap-seek input { width:100%; accent-color:var(--brand); }
  .ap-time { flex:none; font-size:11px; font-weight:bold; color:var(--brand); min-width:74px;
             text-align:right; }
  .ap-rate { flex:none; border:1.5px solid var(--line); background:var(--tint);
             color:var(--brand);
             font-weight:bold; border-radius:16px; padding:4px 9px; font-size:11.5px; cursor:pointer;
             font-family:inherit; }
  /* 停止中は「読み上げる」だけの細いバーにして、常に音声に気づけるようにする。
     速さの切りかえは再生中だけ出す（停止中は横幅を文言に回す）。 */
  .aplayer.idle .ap-seek, .aplayer.idle .ap-time, .aplayer.idle .ap-rate { display:none; }
  .ap-idle-label { display:none; flex:1; min-width:0; font-size:13px; font-weight:bold;
                   color:var(--brand); white-space:nowrap; overflow:hidden;
                   text-overflow:ellipsis; cursor:pointer; }
  .aplayer.idle .ap-idle-label { display:block; }

  /* ── 上部: タイトル＋単元タブ＋進捗バー ── */
  /* 下へ読み進めている間は上部バーを隠す（LINE内ブラウザは上下にLINEのUIが入るため、
     自前のバー＋ナビ＋プレーヤーで本文が3分の1になっていた）。上へスワイプで戻す。 */
  .bar { position:sticky; top:0; z-index:10; background:var(--cream);
         backdrop-filter:blur(6px); border-bottom:1px solid var(--edge);
         transition:transform .22s ease; }
  body.hidebar .bar { transform:translateY(-100%); }
  .bar-in { max-width:640px; margin:0 auto; padding:5px 12px 0; }
  .bar-row { display:flex; align-items:center; gap:8px; }
  /* 参考書⇄問題集の切替（どのページからでも1タップ・相手側は読みかけの位置に着地） */
  /* どのページからでも「本の一覧（すごろく）」へ戻れる常設ボタン。
     タブ列の 🏠 は「この本の目次」なので、こちらは 🗺＋文字でトップだと分かるようにする。 */
  .tophome { flex:none; height:30px; padding:0 12px; font-size:11.5px; font-weight:bold;
             color:#fff; background:var(--deep); border-radius:15px; text-decoration:none;
             display:inline-flex; align-items:center; gap:5px; white-space:nowrap;
             box-shadow:0 2px 0 #5b1e0b; transition:filter .12s; }
  .th-ic { width:14px; height:14px; fill:currentColor; flex:none; }
  @media (hover:hover) { .tophome:hover { filter:brightness(1.12); } }
  /* 狭い画面では「単元一覧」の文字を落としてアイコンだけに。
     いま開いている単元名（unitbtn）を表示する幅を優先する。 */
  @media (max-width:430px) {
    .th-tx { display:none; }
    .tophome { padding:0 9px; }
    .bar-in { padding:5px 10px 0; }
    .bar-row { gap:6px; }
  }
  /* 参考書⇄問題の切りかえタブ。押せると分かるよう、非選択側は白ボタン風＋ホバー反応 */
  .swap { flex:none; display:inline-flex; gap:3px; padding:2px; border-radius:16px;
          background:#f0e2c3; }
  .sw { font-size:11.5px; font-weight:bold; color:var(--brand); padding:4px 12px; text-decoration:none;
        white-space:nowrap; cursor:pointer; border-radius:13px; background:#fff;
        transition:filter .12s, background-color .12s; }
  .sw.on { background:var(--brand); color:#fff; cursor:default; box-shadow:0 1px 2px rgba(180,83,9,.3); }
  @media (hover:hover) { .sw:not(.on):hover { background:#fff8ec; filter:brightness(0.98); } }
  .sw[hidden] { display:none; }
  .bar-title { font-weight:bold; color:var(--deep); font-size:14px; flex:1;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bar-step { flex:none; font-size:11px; font-weight:bold; color:var(--brand); }
  /* 初回だけ出す操作ヒント（PCはキー、スマホはスワイプ） */
  .hintbar { position:fixed; left:50%; transform:translateX(-50%);
             bottom:calc(86px + env(safe-area-inset-bottom)); z-index:35;
             background:rgba(28,25,23,.88); color:#fff; font-size:12.5px; font-weight:bold;
             border-radius:20px; padding:8px 16px; box-shadow:0 4px 14px rgba(0,0,0,.3);
             animation:hintIn .3s ease; }
  .hintbar[hidden] { display:none; }
  @keyframes hintIn { from { opacity:0; transform:translate(-50%,10px); }
                      to { opacity:1; transform:translate(-50%,0); } }
  /* 単元の選択はドロワー（下から出る一覧）。丸タブ横スクロールは19単元では
     見切れて番号も読めず、上部バーの幅も食っていたためやめた。 */
  .unitbtn { flex:1; min-width:0; height:30px; padding:0 8px 0 11px; border:1.5px solid var(--line);
             background:var(--tint); color:var(--brand); border-radius:15px; cursor:pointer;
             font-family:inherit; font-size:12px; font-weight:bold; display:inline-flex;
             align-items:center; gap:6px; overflow:hidden; }
  .ub-name { flex:1; min-width:0; text-align:left; white-space:nowrap; overflow:hidden;
             text-overflow:ellipsis; }
  .ub-caret { flex:none; opacity:.7; }
  @media (hover:hover) { .unitbtn:hover { background:#fff2d6; } }
  /* 設定（文字サイズ・配色） */
  .cfgbtn { flex:none; width:30px; height:30px; border-radius:50%; border:1.5px solid var(--line);
            background:var(--tint); color:var(--brand); cursor:pointer; font-size:14px;
            display:inline-flex; align-items:center; justify-content:center; font-family:inherit; }
  .cfg-ic { width:16px; height:16px; fill:currentColor; }
  .drawer { position:fixed; inset:0; z-index:60; display:flex; align-items:flex-end;
            justify-content:center; }
  .drawer[hidden] { display:none; }
  .dw-back { position:absolute; inset:0; background:rgba(40,26,10,.5); border:none; width:100%; }
  .dw-panel { position:relative; width:100%; max-width:640px; max-height:82vh; display:flex;
              flex-direction:column; background:var(--cream);
              border-radius:20px 20px 0 0; padding-bottom:env(safe-area-inset-bottom);
              box-shadow:0 -8px 30px rgba(0,0,0,.3); animation:dwUp .22s ease; }
  @keyframes dwUp { from { transform:translateY(18px); opacity:.6; } to { transform:none; opacity:1; } }
  .dw-head { display:flex; align-items:center; gap:8px; padding:14px 16px 10px;
             font-size:16px; font-weight:bold; color:var(--deep); border-bottom:1px solid var(--edge); }
  .dw-close { margin-left:auto; border:none; background:none; color:var(--ink3); font-size:26px;
              line-height:1; cursor:pointer; padding:0 6px; font-family:inherit; }
  .dw-list { overflow-y:auto; padding:8px 12px 16px; -webkit-overflow-scrolling:touch; }
  .dw-item { display:flex; align-items:center; gap:10px; width:100%; text-align:left;
             background:var(--card); border:1.5px solid var(--edge); border-radius:12px;
             padding:11px 12px; margin-bottom:7px; font-family:inherit; font-size:14.5px;
             font-weight:bold; color:var(--ink2); cursor:pointer; line-height:1.4; }
  .dw-item.on { border-color:var(--brand); background:var(--tint); }
  .dw-no { flex:none; width:26px; height:26px; border-radius:50%; background:var(--amber); color:#fff;
           display:inline-flex; align-items:center; justify-content:center; font-size:13px; }
  .dw-item.on .dw-no { background:var(--brand); }
  .dw-name { flex:1; min-width:0; }
  .dw-state { flex:none; font-size:11px; font-weight:bold; color:#16a34a; }
  .dw-state.doing { color:var(--brand); }
  .dw-home { justify-content:center; background:var(--tint); }
  @media (hover:hover) { .dw-item:hover { background:#fff8ec; } }
  /* 設定シート（ドロワーの中身を差し替えて使う） */
  .cfg-row { display:flex; align-items:center; gap:10px; padding:10px 4px; flex-wrap:wrap; }
  .cfg-lb { flex:none; font-size:13.5px; font-weight:bold; color:var(--ink2); min-width:5.5em; }
  .cfg-chip { border:1.5px solid var(--edge2); background:var(--card); color:var(--ink2);
              border-radius:16px; padding:7px 16px; font-size:13.5px; font-weight:bold;
              cursor:pointer; font-family:inherit; }
  .cfg-chip.on { background:var(--brand); border-color:var(--brand); color:#fff; }
  /* 説明が要る設定は縦積み（ラベル → 選択肢 → ひとこと説明） */
  .cfg-row.cfg-col { flex-direction:column; align-items:stretch; gap:6px; }
  .cfg-chips { display:flex; gap:8px; flex-wrap:wrap; }
  .cfg-note { font-size:12px; line-height:1.7; color:var(--ink3); }
  .pbar { height:3px; background:#f5ecd8; border-radius:2px; overflow:hidden; margin:0 0 0; }
  .pfill { height:100%; width:0; background:linear-gradient(90deg,var(--amber),#fbbf24);
           border-radius:2px; transition:width .25s ease; }

  /* ── ビュー / ステップ ── */
  .view { display:none; }
  .view.on { display:block; position:relative; animation:vfade .18s ease; }
  @keyframes vfade { from { opacity:.6; } to { opacity:1; } }
  .step { display:none; }
  .step.on { display:block; }
  .step::after { content:""; display:table; clear:both; }  /* 挿絵の float を内包 */
  /* 本物っぽいページめくり（2枚重ね）:
     進む = 今のページ自体が左とじに沿って手前にめくれて去り、下から次のページが現れる。
     戻る = 前のページが手前からめくり戻されて上に着地する。 */
  /* min-height:100% = 下に敷かれた新ページ全体を覆う（絶対配置なので view の実高さに解決される。
     これが無いと、めくれるページより新ページが長いとき下端が透けて見える） */
  .step.turn-out { display:block; position:absolute; top:0; left:0; width:100%; min-height:100%;
                   z-index:3; pointer-events:none; background:var(--cream);
                   transform-origin:left center;
                   animation:turnOut .45s cubic-bezier(.55,.06,.68,.19) forwards; }
  @keyframes turnOut {
    0%   { transform:perspective(1200px) rotateY(0); opacity:1; }
    75%  { opacity:1; }
    100% { transform:perspective(1200px) rotateY(-88deg); opacity:0; } }
  .step.turn-out::after { content:""; position:absolute; inset:0; pointer-events:none;
                          background:linear-gradient(to right, transparent 55%, rgba(124,45,18,.12)); }
  .step.on.turn-in { position:relative; z-index:3; background:var(--cream);
                     transform-origin:left center;
                     animation:turnIn .45s cubic-bezier(.22,.72,.32,1); }
  @keyframes turnIn {
    from { transform:perspective(1200px) rotateY(-88deg); }
    to   { transform:perspective(1200px) rotateY(0); } }
  .step.turn-under { display:block; position:absolute; top:0; left:0; width:100%; z-index:1;
                     pointer-events:none; max-height:100%; overflow:hidden; }

  /* ホーム */
  .top { text-align:center; padding:26px 0 6px; }
  .badge { display:inline-block; background:var(--brand); color:#fff; font-weight:bold;
           padding:4px 16px; border-radius:20px; font-size:13px; }
  .webtag { background:rgba(255,255,255,.25); border-radius:10px; padding:1px 8px;
            font-size:11px; margin-left:4px; }
  .top h1 { font-size:29px; color:var(--deep); margin-top:12px; line-height:1.4; }
  .sub { color:#92400e; font-size:14px; margin-top:4px; }
  /* 目次ページのヘッダー（画像デザイン：3分割バッジ＋左寄せタイトル＋右にマスコット） */
  .home-topline { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:2px; }
  .hometop { display:flex; align-items:flex-start; gap:6px; padding:8px 2px 2px; text-align:left; }
  .ht-main { flex:1; min-width:0; text-align:center; }
  /* 本のラベル（押せない表示）: トグルに見えないようフラットな1トーンのタグに */
  .badge3 { display:inline-flex; align-items:center; gap:6px; border-radius:8px;
            background:#f4ecdb; padding:3px 10px; font-size:11.5px; font-weight:bold; }
  .badge3 span { padding:0; display:inline-flex; align-items:center; white-space:nowrap; }
  .b-vol { color:var(--brand); }
  .b-kind { color:#9a7b4f; }
  .b-web { background:var(--amber); color:#fff; }
  .ht-title { font-size:41px; color:var(--deep); margin:12px 0 0; line-height:1.12; position:relative;
              display:inline-block; padding:0 6px; letter-spacing:.01em; }
  .ht-title::before, .ht-title::after { content:none; }
  .ht-mascot { flex:none; display:flex; align-items:center; flex-direction:row-reverse; gap:9px; }
  .ht-mascot img { height:84px; width:auto; }
  .ht-bubble { position:relative; white-space:nowrap;
               background:#fff; border:2px solid var(--amber); border-radius:12px; padding:6px 11px;
               font-size:11px; font-weight:bold; color:var(--deep); line-height:1.3; text-align:center;
               box-shadow:0 2px 4px rgba(0,0,0,.1); }
  .ht-bubble::after { content:""; position:absolute; right:-8px; top:50%; transform:translateY(-50%);
                      border:5px solid transparent; border-left-color:var(--amber); }
  .cover-navi { display:flex; align-items:center; gap:12px; justify-content:center;
                margin:18px auto 4px; max-width:420px; text-align:left; }
  .navi { width:56px; height:56px; border-radius:50%; object-fit:cover; flex:none;
          box-shadow:0 1px 4px rgba(0,0,0,.15); }
  /* キャラは丸トリミングせず全身を表示（透過PNG） */
  .navi-char { width:auto; border-radius:0; object-fit:contain; background:none; box-shadow:none;
               filter:drop-shadow(0 1px 2px rgba(0,0,0,.18)); }
  .tband .tchar { height:40px; margin-left:auto; }
  .sum30-navi { display:flex; align-items:center; justify-content:flex-end; gap:8px;
                padding:0 12px 10px; margin-top:-2px; }
  .sum30-navi .navi-char { height:46px; }
  .sum30-bubble { position:relative; background:var(--card); border:1.5px solid var(--amber);
                  border-radius:12px; margin-left:6px; min-width:0;
                  padding:6px 12px; font-size:12.5px; font-weight:bold; color:var(--deep); }
  /* しっぽはフクロウ側（左）に。右に出していたため画面外へはみ出して切れていた */
  .sum30-bubble::after { content:""; position:absolute; left:-11px; top:50%; transform:translateY(-50%);
                         border:6px solid transparent; border-right-color:var(--amber); }
  .navi-emoji { background:#fef3c7; display:flex; align-items:center; justify-content:center; font-size:30px; }
  .bubble { position:relative; background:#fff; border:2px solid var(--amber); border-radius:12px;
            padding:8px 14px; font-size:13px; font-weight:bold; color:var(--deep); }
  .bubble::before { content:""; position:absolute; left:-12px; top:50%; transform:translateY(-50%);
                    border:6px solid transparent; border-right-color:var(--amber); }
  .resume { display:block; width:100%; margin:16px 0 0; background:var(--brand); color:#fff;
            border:none; border-radius:14px; padding:13px; font-size:15px; font-weight:bold;
            cursor:pointer; box-shadow:0 3px 8px rgba(180,83,9,.3); }
  .resume span { font-weight:normal; font-size:12px; opacity:.9; margin-left:8px; }
  .toc { margin:16px 0 8px; background:#fff9ef; border:2px solid #f0e2c3; border-radius:16px; padding:12px; }
  .toc-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px; }
  .toc-h { font-weight:bold; color:var(--deep); font-size:16px; display:flex; align-items:center; gap:8px; }
  .toc-h::before { content:""; flex:none; width:30px; height:30px; border-radius:50%;
                   background:var(--brand) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'%3E%3Cpath d='M12 6.6C10.5 5.4 8.4 4.9 6 4.9c-1 0-2 .1-2.8.3v12.9c.8-.2 1.8-.3 2.8-.3 2.4 0 4.5.5 6 1.7 1.5-1.2 3.6-1.7 6-1.7 1 0 2 .1 2.8.3V5.2C20 5 19 4.9 18 4.9c-2.4 0-4.5.5-6 1.7z'/%3E%3C/svg%3E") center/17px no-repeat; }
  /* 単元カード（大きめサムネ＋番号＋名前＋右矢印） */
  .toc-item { display:flex; align-items:center; width:100%; margin-bottom:8px; padding:0;
              background:#fff; border:1.5px solid #f0e2c3; border-radius:12px; overflow:hidden;
              box-shadow:0 2px 0 #ecdcbb; cursor:pointer; color:#44403c; font-weight:bold;
              font-size:15px; text-align:left; font-family:inherit; line-height:1.35; min-height:62px; }
  .toc-item:last-child { margin-bottom:0; }
  .toc-thumb { flex:none; width:80px; align-self:stretch; object-fit:cover; border:none; background:#fff7e6; }
  .toc-thumb.ph { background:linear-gradient(135deg,#fef3c7,#fde68a); align-self:stretch; }
  .toc-no { flex:none; margin-left:12px; width:26px; height:26px; border-radius:50%; background:var(--amber);
            color:#fff; display:inline-flex; align-items:center; justify-content:center; font-size:13px; }
  .toc-name { flex:1; padding:10px 6px 10px 10px; }
  .toc-arrow { flex:none; color:var(--brand); font-size:22px; font-weight:bold; padding:0 12px 0 4px; }
  /* 高さを固定して、✓（環境により絵文字グリフで行ボックスが太る）でも
     行の高さが他の行と変わらないようにする */
  .toc-state { flex:none; font-size:11px; font-weight:bold; line-height:1;
               display:inline-flex; align-items:center; height:20px; }
  .toc-state.done { color:#16a34a; }
  .toc-state.doing { color:var(--brand); background:var(--tint); border:1px solid var(--line);
                     border-radius:10px; padding:1px 8px; }
  /* 読んでから1週間たった単元（忘れたころの復習をうながす） */
  .toc-state.again { color:#b45309; background:#fff7ed; border:1px solid #fdba74;
                     border-radius:10px; padding:1px 8px; }
  /* この本の到達率 */
  .bookprog { margin-top:14px; background:var(--card2); border:1.5px solid var(--edge);
              border-radius:14px; padding:10px 14px; }
  .bp-txt { font-size:12.5px; font-weight:bold; color:var(--brand); margin-bottom:6px; }
  .bp-bar { height:8px; background:#f0e2c3; border-radius:5px; overflow:hidden; }
  .bp-fill { height:100%; width:0; border-radius:5px;
             background:linear-gradient(90deg,var(--amber),#fbbf24); transition:width .3s ease; }
  /* 読み上げソフト向けの通知だけを置く（画面には出さない） */
  .sr-only { position:absolute; width:1px; height:1px; margin:-1px; padding:0; overflow:hidden;
             clip:rect(0 0 0 0); white-space:nowrap; border:0; }

  /* 単元ヘッダー */
  .tband { display:flex; align-items:center; gap:10px; margin:18px 0 14px; }
  .tno { flex:none; width:34px; height:34px; border-radius:50%; background:var(--brand); color:#fff;
         display:inline-flex; align-items:center; justify-content:center; font-size:17px;
         font-weight:bold; box-shadow:0 2px 4px rgba(180,83,9,.3); }
  .tband h2 { font-size:20px; color:var(--deep); border-bottom:3px solid var(--line);
              padding-bottom:2px; flex:1; line-height:1.4; }

  .hook { display:flex; align-items:center; gap:12px; margin-bottom:14px; }
  .hook .bubble { font-weight:normal; font-size:13.5px; line-height:1.8; }

  /* ── 単元表紙デザイン（PDFの単元表紙とおそろい）── */
  .cover-img { width:100%; display:block; margin:2px 0 14px; border-radius:16px;
               box-shadow:0 8px 18px rgba(91,68,53,.14); }
  .cover-art { position:relative; margin:8px 8px 26px; padding:10px;
               background:#fffaf1; border:2px solid rgba(180,83,9,.35); border-radius:14px;
               box-shadow:0 10px 18px rgba(91,68,53,.16); transform:rotate(-1.6deg); }
  .cover-art.art-even { transform:rotate(1.6deg); }
  .cover-art img { width:100%; border-radius:10px; display:block; }
  .cover-art::before, .cover-art::after { content:""; position:absolute; top:-12px;
               width:84px; height:26px; border-radius:5px; background:rgba(217,119,6,.32);
               box-shadow:0 2px 4px rgba(91,68,53,.1); z-index:1; }
  .cover-art::before { left:22px; transform:rotate(-7deg); }
  .cover-art::after { right:22px; transform:rotate(7deg); }
  .cover-art figcaption { font-size:12px; color:var(--ink3); text-align:center; margin-top:6px; }

  .overview { background:rgba(255,255,255,.94); border:2.5px solid rgba(180,83,9,.45);
              border-radius:16px; padding:16px 16px 8px; margin-bottom:14px;
              box-shadow:0 8px 16px rgba(91,68,53,.1); }
  .ov-h { font-weight:bold; font-size:16px; color:var(--deep); margin-bottom:6px; }
  .ov-list { list-style:none; display:flex; flex-direction:column; }
  .ov-list li { display:flex; align-items:flex-start; gap:10px; padding:9px 2px;
                font-size:14px; font-weight:bold; color:#44372e; line-height:1.6; }
  .ov-list li + li { border-top:2px dashed rgba(180,83,9,.22); }
  .ov-num { flex:none; width:24px; height:24px; border-radius:50%; background:var(--brand);
            color:#fff; font-weight:bold; display:inline-flex; align-items:center;
            justify-content:center; font-size:13px; margin-top:2px; }

  .cheer { display:flex; align-items:center; justify-content:center; gap:12px; margin:2px 0 12px; }
  .cheer-char { width:76px; filter:drop-shadow(0 3px 5px rgba(91,68,53,.2)); }
  .cheer-bubble { position:relative; background:#fff; border:2px solid rgba(180,83,9,.55);
                  border-radius:14px; padding:8px 14px; font-size:13.5px; font-weight:bold;
                  color:#5b4435; }
  .cheer-bubble::before { content:""; position:absolute; left:-9px; top:50%; width:14px; height:14px;
                  background:#fff; border-left:2px solid rgba(180,83,9,.55);
                  border-bottom:2px solid rgba(180,83,9,.55);
                  transform:translateY(-50%) rotate(45deg); }

  .hero { margin:0 0 8px; }
  .hero img { width:100%; border-radius:14px; display:block; }
  .hero figcaption { font-size:12px; color:var(--ink3); text-align:center; margin-top:4px; }

  /* 節 */
  .step h3 { font-size:18px; color:var(--deep); display:flex; align-items:center; gap:8px; line-height:1.5; }
  .sec-no { flex:none; width:22px; height:22px; border-radius:50%; background:#fff;
            border:1.5px solid var(--line); color:var(--brand); font-weight:bold;
            display:inline-flex; align-items:center; justify-content:center; font-size:12px; }
  .sec-lead { font-size:13px; color:var(--brand); font-weight:bold; margin:2px 0 4px 30px; }
  /* 節の挿絵：既定は本文の右に小さく回り込ませる（補足的・目立ちすぎない） */
  .sec-fig { float:right; width:46%; max-width:205px; margin:3px 0 8px 12px; }
  .sec-fig.fig-contain { max-width:230px; }
  .sec-fig img { width:100%; max-height:172px; object-fit:cover; display:block;
                 border-radius:10px; border:1px solid #f0e6d2;
                 box-shadow:0 1px 4px rgba(120,80,20,.10); background:#fff; cursor:zoom-in; }
  /* 図版（関係図・地図）は切らずに全体を見せる（日本語ラベルが欠けないように） */
  .sec-fig.fig-contain img { object-fit:contain; max-height:none; background:#fffdf8; }
  .sec-fig figcaption { font-size:11px; color:var(--ink3); text-align:center; margin-top:4px; line-height:1.4; }
  /* 変化をつける: 左回り込み／サイズ違い／横いっぱい */
  .sec-fig.pos-left { float:left; margin:3px 12px 8px 0; }
  .sec-fig.size-sm { max-width:150px; }
  .sec-fig.size-lg { max-width:250px; }
  .sec-fig.pos-wide { float:none; width:auto; max-width:100%; margin:10px 0; }
  .sec-fig.pos-wide img { max-height:260px; }
  .sec-fig.pos-wide.fig-contain img { max-height:340px; }  /* 地図・図はワイドで大きく読める */
  .sec-fig.pos-wide figcaption { font-size:12px; }
  /* 挿絵は狭い画面でも本文に回り込ませる（横いっぱいに大きく出すと、
     本文と絵が分断されて読みにくいという判断）。ただし幅を取りすぎると
     本文が細い柱になるので、狭い画面では少しだけ小さくする。 */
  @media (max-width:430px) {
    .sec-fig { width:42%; }
    .sec-fig.size-lg { max-width:200px; }
  }
  /* 挿絵を含む節でも ⭐ここだけ覚える／用語は画像の下から始める */
  .step .point, .step .words { clear:both; }
  .cover-art img, .cover-img { cursor:zoom-in; }

  /* 画像タップで拡大（ライトボックス） */
  .lightbox { position:fixed; inset:0; z-index:200; background:rgba(20,14,8,.88);
              display:flex; align-items:center; justify-content:center; padding:20px;
              -webkit-tap-highlight-color:transparent; cursor:zoom-out; }
  .lightbox[hidden] { display:none; }
  .lightbox img { max-width:96vw; max-height:90vh; border-radius:10px; background:#fffdf8;
                  box-shadow:0 8px 40px rgba(0,0,0,.55); }
  .lb-close { position:fixed; top:14px; right:16px; width:42px; height:42px; border:none;
              border-radius:50%; background:rgba(255,255,255,.92); color:#7c2d12; font-size:24px;
              line-height:1; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.3); }
  .lb-hint { position:fixed; bottom:20px; left:0; right:0; text-align:center; color:#fff;
             font-size:12px; opacity:.7; pointer-events:none; }
  .step p { margin-top:8px; text-align:justify; }
  .point { background:#fff9c4; border-left:6px solid #fbbf24; border-radius:8px;
           padding:10px 12px; margin-top:12px; font-size:14px; line-height:1.8; }
  .ptag { font-weight:bold; color:var(--brand); }
  .ptxt { color:#44403c; margin-top:2px; }
  .tip { background:#fffbeb; border-radius:10px; padding:10px 12px; font-size:13.5px;
         color:#44403c; line-height:1.8; }
  .words { display:flex; flex-direction:column; gap:6px; margin-top:12px; }
  .word { background:#fff; border:1px solid #f0e6d2; border-radius:10px; padding:8px 12px;
          font-size:13.5px; line-height:1.7; }
  .w-term { font-weight:bold; color:var(--brand); margin-right:8px; }
  .w-rd { font-weight:normal; font-size:11px; color:var(--ink3); margin-left:4px; }
  .w-desc { color:#57534e; }

  /* 重要語チェック */
  .terms-h { font-size:18px; font-weight:bold; color:var(--deep); }
  .terms-sub { font-size:12px; font-weight:normal; color:var(--ink3); margin-left:8px; }
  .terms-tools { display:flex; align-items:center; justify-content:space-between; gap:8px;
                 flex-wrap:wrap; margin:6px 0 10px; }
  .tt-btns { display:flex; gap:8px; flex-wrap:wrap; }
  .shuffle-btn, .swap-btn { flex:none; display:inline-flex; align-items:center; gap:4px;
                 font-family:inherit; font-size:13px; font-weight:bold; cursor:pointer;
                 border-radius:16px; padding:6px 13px; }
  .shuffle-btn { color:#fff; background:var(--brand); border:none; box-shadow:0 2px 6px rgba(180,83,9,.3); }
  .swap-btn { color:var(--brand); background:#fffbeb; border:1.5px solid var(--line); }
  .swap-btn.on { color:#fff; background:var(--brand); border-color:var(--brand); box-shadow:0 2px 6px rgba(180,83,9,.3); }
  .shuffle-btn:active, .swap-btn:active { transform:translateY(1px); }
  .both-toggle { display:inline-flex; align-items:center; gap:6px; font-size:13px;
                 font-weight:bold; color:#57534e; cursor:pointer; }
  .both-toggle input { width:16px; height:16px; accent-color:var(--brand); }
  .tgrid { display:grid; grid-template-columns:1fr 1fr; gap:8px; align-items:start; }
  /* シャッフル時のふわっと再配置アニメ */
  .tgrid.shuffling .tcard { animation:tshuffle .34s ease; }
  @keyframes tshuffle { 0% { opacity:.25; transform:scale(.92); }
                        100% { opacity:1; transform:none; } }
  @media (max-width:400px) { .tgrid { grid-template-columns:1fr; } }
  /* フラッシュカード（タップで表裏。両面表示チェックで従来の一覧に）
     ─ めくりモード: 全カード同じ高さ（150px）・面は絶対配置で重ねて3D回転
     ─ 両面モード: 3Dを使わず通常フローで表＋裏を縦に並べる（崩れ防止） */
  /* カードの高さは中身に合わせる（150px 固定だと余白だらけ／長い説明はスクロールになっていた）。
     表裏は grid の同じマスに重ねるので、高さは「長いほうの面」に自動でそろう。 */
  .tcard { position:relative; width:100%; background:none; border:none; padding:0;
           cursor:pointer; font-family:inherit; text-align:left; perspective:800px; }
  .tcard-inner { display:grid; min-height:104px; transition:transform .35s;
                 transform-style:preserve-3d; }
  .tc-face { grid-area:1 / 1; display:flex; flex-direction:column;
             align-items:center; justify-content:center; text-align:center;
             backface-visibility:hidden; -webkit-backface-visibility:hidden;
             border:1.5px solid var(--line); border-radius:10px; padding:10px; background:var(--card); }
  /* 覚えた／まだ の仕分け（答えを見たあとだけ出す） */
  .tcell { display:flex; flex-direction:column; }
  .tmark { display:none; gap:6px; margin-top:5px; }
  .tcell.flipped .tmark { display:flex; }
  .tm { flex:1; border:1.5px solid var(--edge2); background:var(--card); border-radius:9px;
        padding:6px 4px; font-size:12.5px; font-weight:bold; cursor:pointer; font-family:inherit;
        color:var(--ink3); }
  .tm-ok { color:#15803d; border-color:#bbe3cc; }
  .tm-ng { color:#b45309; border-color:var(--line); }
  .tcell.ok .tm-ok { background:#16a34a; border-color:#16a34a; color:#fff; }
  .tcell.ng .tm-ng { background:var(--brand); border-color:var(--brand); color:#fff; }
  .tcell.ok .tc-face { border-color:#bbe3cc; }
  .terms-count { font-size:12.5px; font-weight:bold; color:var(--brand); margin-top:4px; }
  .terms-empty { text-align:center; font-size:14px; font-weight:bold; color:var(--deep);
                 background:var(--tint); border:1.5px dashed var(--line); border-radius:12px;
                 padding:16px; margin-top:10px; }
  .terms-empty[hidden] { display:none; }
  .only-ng-btn { color:var(--brand); background:var(--tint); border:1.5px solid var(--line); }
  .only-ng-btn.on { color:#fff; background:var(--brand); border-color:var(--brand); }
  /* 「まだの語だけ」表示中は、覚えたカードを隠す */
  .tgrid.only-ng .tcell.ok { display:none; }
  /* 表＝説明（読んで用語を当てる） */
  .tc-front { background:var(--tint); }
  .tc-desc { font-size:13px; color:var(--ink2); line-height:1.6; font-weight:500; }
  /* 裏＝用語（こたえ） */
  .tc-back { transform:rotateY(180deg); }
  .tc-term { font-weight:bold; font-size:17px; color:var(--deep); line-height:1.5; }
  .tc-rd { display:block; font-weight:normal; font-size:11px; color:var(--ink3); margin-top:2px; }
  .tc-tap { font-size:10.5px; color:#8a7a55; margin-top:6px; }
  .tcard.flipped .tcard-inner { transform:rotateY(180deg); }
  /* 裏表入れ替え: 用語を先に見せる（意味→用語 ⇄ 用語→意味） */
  .tgrid.term-first .tcard-inner { transform:rotateY(180deg); }
  .tgrid.term-first .tcard.flipped .tcard-inner { transform:rotateY(0deg); }
  /* 両面表示モード（用語→説明の順に縦並べ） */
  .tgrid.both .tcard { cursor:default; height:auto; perspective:none; }
  .tgrid.both .tcard-inner { transform:none !important; transform-style:flat; min-height:0;
                             display:flex; flex-direction:column; }
  .tgrid.both .tc-face { overflow:visible; align-items:flex-start; text-align:left;
                         backface-visibility:visible; -webkit-backface-visibility:visible; }
  .tgrid.both .tmark { display:flex; }
  .tgrid.both .tc-back { order:0; transform:none; border-bottom:none; border-radius:10px 10px 0 0;
                         padding-bottom:4px; background:#fff; }
  .tgrid.both .tc-front { order:1; border-top:none; border-radius:0 0 10px 10px; }
  .tgrid.both .tc-term { font-size:14px; }
  .tgrid.both .tc-tap { display:none; }

  /* まとめ・完了 */
  .sum30 { border:2px solid var(--amber); border-radius:14px; overflow:hidden;
           box-shadow:0 2px 8px rgba(245,158,11,.14); }
  .sum30-h { background:linear-gradient(90deg,#d97706,var(--amber)); color:#fff; font-weight:bold;
             font-size:15px; padding:8px 14px; display:flex; align-items:center; gap:8px; }
  .sum30-tag { margin-left:auto; font-size:11px; background:rgba(255,255,255,.28);
               padding:2px 10px; border-radius:12px; }
  .sum30-body { padding:14px 16px; font-size:15px; font-weight:bold; color:#44403c; line-height:2.0;
                background:#fffdf5; }
  .sum30-body .mark { background:none; color:#c2410c; padding:0; }
  .done { text-align:center; font-size:16px; font-weight:bold; color:var(--deep); margin:18px 0 10px; }
  .wb-btn { display:flex; align-items:center; gap:12px; text-decoration:none;
            background:var(--brand); color:#fff; border-radius:14px; padding:13px 16px;
            box-shadow:0 3px 8px rgba(180,83,9,.3); margin-bottom:10px; }
  .wb-home { display:block; text-align:center; margin:14px 0 0; text-decoration:none;
             background:var(--brand); color:#fff; border-radius:14px; padding:13px 16px;
             font-size:15px; font-weight:bold; box-shadow:0 3px 8px rgba(180,83,9,.3); }
  .home-link { display:inline-block; margin:10px 0 0; font-size:13px; font-weight:bold;
               color:var(--brand); text-decoration:none; background:#fffbeb;
               border:1.5px solid var(--line); border-radius:16px; padding:6px 14px; }
  @media (hover:hover) { .home-link:hover { filter:brightness(0.96); } }
  /* 単元の終わりの2ボタン。**1行に2つ**並べてコンパクトに（狭い画面では縦に折る）。 */
  .end-btns { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:4px; }
  @media (max-width:360px) { .end-btns { grid-template-columns:1fr; } }
  .ai-btn { display:flex; align-items:center; gap:12px; text-decoration:none;
            background:#06c755; color:#fff; border-radius:14px; padding:13px 16px;
            box-shadow:0 3px 8px rgba(6,199,85,.3); }
  .ai-ico { font-size:24px; flex:none; }
  .ai-main { flex:1; font-weight:bold; font-size:15px; line-height:1.5; }
  .ai-sub { display:block; font-weight:normal; font-size:12px; opacity:.9; }
  .ai-arrow { font-size:22px; opacity:.8; }
  /* グリッドの中では、矢印を消して中央寄せの小さいボタンにする */
  .end-btns .wb-btn, .end-btns .ai-btn { display:block; text-align:center;
            padding:11px 10px; margin:0; border-radius:12px; }
  .end-btns .ai-arrow { display:none; }
  .end-btns .ai-main { font-size:14px; line-height:1.4; }
  .end-btns .ai-sub { font-size:11px; margin-top:2px; opacity:.85; }

  .foot { text-align:center; margin-top:36px; color:var(--ink3); font-size:13px; }
  .foot-note { margin-top:4px; font-size:12px; }

  /* ── 下部ナビ ── */
  /* 教材ゲートのロック案内（頭出しの先） */
  .lock-ov { position:fixed; inset:0; z-index:40; background:rgba(60,40,15,.5);
             display:flex; align-items:center; justify-content:center; padding:20px; }
  .lock-ov[hidden] { display:none; }
  .lock-card { width:100%; max-width:360px; background:#fff; border-radius:18px; padding:24px 20px 18px;
               text-align:center; box-shadow:0 10px 30px rgba(0,0,0,.3); }
  .lock-ic { font-size:40px; }
  .lock-t { font-size:18px; font-weight:bold; color:var(--deep); margin:6px 0 6px; }
  .lock-d { font-size:13px; color:#78716c; line-height:1.8; margin-bottom:16px; }
  .lock-btn { display:block; width:100%; margin-top:10px; border:none; border-radius:13px; padding:13px;
              font-size:15px; font-weight:bold; text-decoration:none; cursor:pointer; font-family:inherit;
              transition:transform .12s ease, box-shadow .12s ease, filter .12s ease, background .12s ease; }
  .lb-trial { background:linear-gradient(135deg,#f59e0b,#d97706); color:#fff; font-size:16px;
              box-shadow:0 4px 12px rgba(217,119,6,.42); }
  .lb-trial:disabled { opacity:.6; cursor:default; box-shadow:none; }
  .lb-line { background:#06c755; color:#fff; box-shadow:0 3px 8px rgba(6,199,85,.3); }
  .lb-buy { background:#fff; color:var(--brand); border:1.5px solid var(--line); }
  .lock-btn[hidden] { display:none; }
  .lock-btn:active:not(:disabled) { transform:translateY(0); }
  @media (hover:hover) {
    .lb-trial:hover:not(:disabled) { filter:brightness(1.07); transform:translateY(-1px);
                                     box-shadow:0 6px 16px rgba(217,119,6,.5); }
    .lb-line:hover { filter:brightness(1.07); transform:translateY(-1px);
                     box-shadow:0 5px 12px rgba(6,199,85,.4); }
    .lb-buy:hover { background:#fffbeb; border-color:var(--brand); transform:translateY(-1px); }
    .lock-sublink:hover:not(:disabled) { color:var(--deep); }
    .lock-close:hover { color:#78716c; }
  }
  .lock-msg { margin-top:13px; padding:10px 12px; border-radius:11px; font-size:13px; line-height:1.7;
              background:#fffbeb; color:#92400e; border:1px solid #fde68a; }
  .lock-msg.ok { background:#ecfdf5; color:#047857; border-color:#a7f3d0; }
  .lock-msg.warn { background:#fef2f2; color:#b91c1c; border-color:#fecaca; }
  .lock-msg[hidden] { display:none; }
  .lock-sublink { display:block; width:100%; margin-top:14px; background:none; border:none; cursor:pointer;
                  color:#92400e; font-size:13px; font-family:inherit; text-decoration:underline; padding:4px; }
  .lock-sublink:disabled { opacity:.6; cursor:default; }
  .lock-sublink[hidden] { display:none; }
  .lock-close { display:block; width:100%; margin-top:12px; background:none; border:none; cursor:pointer;
                color:var(--ink3); font-size:12.5px; font-family:inherit; text-decoration:underline; }

  /* ── 下部ナビ ──
     ページ送りは「‹ ›」の丸ボタン。読み上げプレーヤーが出ると下が2段になって
     本文の見える面積を食っていたので、参考書は横幅を取らない丸ボタンにして、
     プレーヤー表示中は その行の左右に入れて1段にまとめる（下の .nav-merged）。
     文字は残したまま font-size:0 で隠すので、読み上げソフトには「つぎへ」と伝わる。 */
  .navbar { position:fixed; left:0; right:0; bottom:0; z-index:10;
            background:var(--card2); border-top:1px solid var(--edge);
            padding:8px 16px calc(8px + env(safe-area-inset-bottom)); }
  .navbar-in { max-width:640px; margin:0 auto; display:flex; align-items:center;
               justify-content:flex-end; gap:12px; }
  .nb { flex:none; border:none; border-radius:50%; padding:0; font-size:0; font-weight:bold;
        cursor:pointer; font-family:inherit; display:inline-flex; align-items:center;
        justify-content:center; transition:transform .12s, filter .12s; }
  .nb::after { font-size:26px; line-height:1; font-weight:bold; }
  .nb:active { transform:translateY(1px); }
  .nb-prev { width:46px; height:46px; background:var(--card); color:var(--brand);
             border:1.5px solid var(--line); }
  .nb-next { width:54px; height:54px; background:var(--brand); color:#fff;
             box-shadow:0 3px 8px rgba(180,83,9,.3); }
  .nb-next::after { font-size:30px; }
  /* 行き先で記号を変える（目次へ戻るときは矢印ではなく本のマーク） */
  #btnPrev::after { content:"\\2039"; }
  #btnPrev[data-act="home"]::after { content:"\\2261"; font-size:22px; }
  #btnNext::after { content:"\\203A"; }
  #btnNext[data-act="unit"]::after { content:"\\00BB"; font-size:26px; }
  #btnNext[data-act="home"]::after { content:"\\2261"; font-size:24px; }
  .nav-label { position:absolute; left:-9999px; }
  /* プレーヤー表示中: ナビ行をたたみ、丸ボタンをプレーヤーの行の両端へ入れる */
  body.nav-merged .navbar { display:none; }
  body.nav-merged .aplayer { bottom:0; padding:7px 0 calc(8px + env(safe-area-inset-bottom)); }
  body.has-player.nav-merged { padding-bottom:104px; }
  .ap-in .nb { box-shadow:none; }
  .ap-in .nb-prev { width:38px; height:38px; }
  .ap-in .nb-prev::after { font-size:22px; }
  .ap-in .nb-next { width:42px; height:42px; }
  .ap-in .nb-next::after { font-size:25px; }
  /* 1行に収めるため、スマホ幅では時間表示を省く（位置はシークバーで分かる）。
     幅に余裕がある端末では出す。 */
  body.nav-merged .ap-time { display:none; }
  @media (min-width:480px) { body.nav-merged .ap-time { display:block; } }
  body.nav-merged .ap-in { gap:8px; }
  body.nav-merged .ap-rate { padding:4px 8px; font-size:11px; }
  body.nav-merged .aplayer.idle .ap-idle-label { font-size:12.5px; }

  /* ── ホバー: マウスを乗せると「押せる」ことが分かる（タッチ端末では固着しないよう hover 端末限定）── */
  @media (hover: hover) {
    .toc-item, .resume, .shuffle-btn, .swap-btn, .tcard, .ai-btn, .wb-btn, .nb,
    .chat-fab, .chat-close, .chat-login-btn, #chatSend {
      transition: filter .12s ease, background-color .12s ease; }
    /* 色つき（塗り）ボタンは少し濃く */
    .resume:hover, .shuffle-btn:hover, .ai-btn:hover, .nb:hover, .chat-fab:hover,
    .chat-login-btn:hover, #chatSend:hover { filter: brightness(0.94); }
    /* 白・枠線ボタン／リスト／カードは薄いアンバーで下地を変える */
    .toc-item:hover, .swap-btn:hover, .wb-btn:hover, .tcard:hover,
    .chat-close:hover { background-color: #fff8ec; }
  }

  /* ── ページ内チャット（AI）── */
  /* 中身はつづ先生の顔アイコン（丸くトリミングして全面に敷く）。
     下端からの位置は「ナビの高さ（8+54+8=70）＋すこし」。丸ボタン化で低くなったぶん下げる。 */
  .chat-fab { position:fixed; right:14px; bottom:calc(80px + env(safe-area-inset-bottom));
              padding:0; overflow:hidden;
              z-index:20; width:56px; height:56px; border-radius:50%;
              border:none; background:var(--brand); color:#fff; font-size:26px;
              cursor:pointer;
              /* ブランド色のリング＋落ち影。イラストが淡いので、これが無いと
                 クリーム地のページに溶けて「押せるもの」に見えない。 */
              box-shadow:0 0 0 2.5px var(--brand), 0 4px 12px rgba(180,83,9,.4); }
  .chat-fab.hidden { display:none; }
  /* 画像側で「円に切られても欠けない余白」を持たせてあるので、ここでは素直に敷くだけ。 */
  .fab-img { width:100%; height:100%; display:block; border-radius:50%;
             object-fit:contain; }
  /* 読んでいる最中のチャットボタンは主役ではないので、じゃまにならないよう薄くする。
       - スクロール中   … 動かしている間だけ薄く（止まれば戻る）
       - 読み上げ中     … 読み終わる／止めるまでずっと薄いまま
     どちらも押せることは変えない（触れれば元の濃さに戻る）。 */
  .chat-fab { transition:opacity .25s ease, transform .25s ease, bottom .18s ease; }
  .chat-fab.dim { opacity:.3; transform:scale(.82); }
  body.reading .chat-fab { opacity:.22; transform:scale(.78); }
  /* 触れた・押した・キーボードで選んだときは、はっきり出す */
  .chat-fab:active, .chat-fab:focus-visible,
  body.reading .chat-fab:active, body.reading .chat-fab:focus-visible {
    opacity:1; transform:none; }
  @media (hover:hover) {
    .chat-fab:hover, body.reading .chat-fab:hover { opacity:1; transform:none; }
  }
  /* プレーヤーが出ているときは、その1行ぶんだけ上げる。
     ナビとプレーヤーが上下2段だった頃の高さ（146px）のままだと、
     1行に統合したいま、フッターとの間が大きく空いてしまう。 */
  body.nav-merged .chat-fab { bottom:calc(68px + env(safe-area-inset-bottom)); }
  .chat-panel { position:fixed; right:12px; bottom:calc(84px + env(safe-area-inset-bottom));
                z-index:21; width:min(400px, calc(100vw - 24px));
                height:min(540px, calc(100vh - 160px));
                display:flex; flex-direction:column; background:var(--cream);
                border:2px solid var(--line); border-radius:16px;
                box-shadow:0 10px 30px rgba(68,55,46,.25); overflow:hidden; }
  .chat-head { display:flex; align-items:center; gap:8px; padding:10px 12px;
               background:var(--brand); color:#fff; }
  .chat-title { font-weight:bold; font-size:14px; }
  .chat-topic { flex:1; font-size:11px; opacity:.9; white-space:nowrap;
                overflow:hidden; text-overflow:ellipsis; }
  .chat-close { border:none; background:none; color:#fff; font-size:22px;
                line-height:1; cursor:pointer; padding:0 4px; }
  .chat-note { font-size:11px; color:#92400e; background:#fffbeb;
               border-bottom:1px solid #f0e6d2; padding:6px 12px; }
  .chat-body { flex:1; overflow-y:auto; padding:12px; display:flex;
               flex-direction:column; gap:8px; }
  .chat-msg { max-width:85%; padding:8px 12px; border-radius:14px; font-size:13.5px;
              line-height:1.7; white-space:pre-wrap; word-break:break-word; }
  .chat-msg.user { align-self:flex-end; background:var(--brand); color:#fff;
                   border-bottom-right-radius:4px; }
  .chat-msg.model { align-self:flex-start; background:#fff; color:#1c1917;
                    border:1.5px solid var(--line); border-bottom-left-radius:4px; }
  .chat-msg.sys { align-self:center; background:none; color:var(--ink3); font-size:11.5px;
                  text-align:center; }
  .chat-login { padding:16px; text-align:center; border-top:1px solid #f0e6d2; }
  .chat-login p { font-size:12.5px; color:#57534e; margin-bottom:10px; }
  .chat-login-btn { display:inline-block; background:#06c755; color:#fff; font-weight:bold;
                    font-size:14px; padding:10px 22px; border-radius:12px;
                    text-decoration:none; }
  .chat-input { display:flex; gap:8px; padding:10px 12px;
                border-top:1px solid #f0e6d2; background:#fff; }
  .chat-input input { flex:1; border:1.5px solid var(--line); border-radius:12px;
                      padding:9px 12px; font-size:14px; font-family:inherit; }
  .chat-input input:focus { outline:none; border-color:var(--amber); }
  .chat-input button { border:none; background:var(--brand); color:#fff; font-weight:bold;
                       font-size:14px; padding:0 18px; border-radius:12px;
                       cursor:pointer; font-family:inherit; }
  .chat-input button:disabled { opacity:.5; }
  .chat-foot { font-size:10.5px; color:var(--ink3); text-align:center; padding:4px 8px 7px;
               background:#fff; }
  /* display:flex 指定が UA の [hidden]{display:none} に勝ってしまうのを防ぐ */
  .chat-panel[hidden], .chat-input[hidden], .chat-login[hidden] { display:none; }

  /* ── よるモード（配色設定 = dark）──
     個別に色を直書きしている箇所が多いので、面（背景）と枠だけまとめて上書きする。
     文字色は --ink 系に寄せ、白背景のカードだけを暗い面に置き換える。 */
  :root[data-theme="dark"] {
    color-scheme: dark;
  }
  :root[data-theme="dark"] .toc, :root[data-theme="dark"] .toc-item,
  :root[data-theme="dark"] .word, :root[data-theme="dark"] .tc-face,
  :root[data-theme="dark"] .bubble, :root[data-theme="dark"] .cheer-bubble,
  :root[data-theme="dark"] .ht-bubble, :root[data-theme="dark"] .overview,
  :root[data-theme="dark"] .cover-art, :root[data-theme="dark"] .sum30-body,
  :root[data-theme="dark"] .chat-msg.model, :root[data-theme="dark"] .chat-input,
  :root[data-theme="dark"] .chat-foot, :root[data-theme="dark"] .lock-card,
  :root[data-theme="dark"] .sec-no, :root[data-theme="dark"] .home-link,
  :root[data-theme="dark"] .tm, :root[data-theme="dark"] .cfg-chip,
  :root[data-theme="dark"] .dw-item, :root[data-theme="dark"] .sw,
  :root[data-theme="dark"] .nb-prev, :root[data-theme="dark"] .swap-btn,
  :root[data-theme="dark"] .unitbtn, :root[data-theme="dark"] .cfgbtn,
  :root[data-theme="dark"] .tip, :root[data-theme="dark"] .point,
  :root[data-theme="dark"] .lock-msg, :root[data-theme="dark"] .terms-empty,
  :root[data-theme="dark"] .bookprog, :root[data-theme="dark"] .chat-note {
    background:var(--card); color:var(--ink); border-color:var(--edge); }
  :root[data-theme="dark"] .tc-front { background:var(--card2); }
  :root[data-theme="dark"] .point { border-left-color:#a16207; }
  :root[data-theme="dark"] .toc-item, :root[data-theme="dark"] .tc-desc,
  :root[data-theme="dark"] .ptxt, :root[data-theme="dark"] .w-desc,
  :root[data-theme="dark"] .sum30-body, :root[data-theme="dark"] .ov-list li,
  :root[data-theme="dark"] .dw-item { color:var(--ink2); }
  :root[data-theme="dark"] .toc-item { box-shadow:none; }
  :root[data-theme="dark"] .pbar, :root[data-theme="dark"] .bp-bar { background:#3a3128; }
  :root[data-theme="dark"] .swap { background:#2f281e; }
  :root[data-theme="dark"] .navbar, :root[data-theme="dark"] .bar { background:var(--cream); }
  :root[data-theme="dark"] .sum30-body .mark { color:#fdba74; }
  :root[data-theme="dark"] .tl-table td, :root[data-theme="dark"] .tl-table th { border-color:var(--edge2); }
  :root[data-theme="dark"] img.zoomable, :root[data-theme="dark"] .toc-thumb,
  :root[data-theme="dark"] .cover-img { filter:brightness(.88); }
</style></head><body>
<div class="bar"><div class="bar-in">
  <div class="bar-row">
    <a class="tophome" href="../../map/index.html" aria-label="単元一覧へもどる"><svg class="th-ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/></svg><span class="th-tx">単元一覧</span></a>
    <div class="swap" role="tablist" aria-label="参考書と問題の切りかえ"><span class="sw on">参考書</span><a class="sw" id="swWb" role="tab">問題</a></div>
    <button class="unitbtn" id="unitBtn" type="button" aria-haspopup="dialog" aria-label="単元をえらぶ">
      <span class="ub-name" id="unitBtnName">目次</span><span class="ub-caret" aria-hidden="true">▾</span></button>
    <button class="cfgbtn" id="cfgBtn" type="button" aria-label="文字サイズ・配色の設定">
      <svg class="cfg-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18h7v2H4zm0-7h10v2H4zm0-7h16v2H4zm13.5 9L20 18l-2.5 4L15 18z"/></svg></button>
    <div class="bar-step" id="barStep"></div>
  </div>
  <div class="bar-title" hidden>__HEADBAR__</div>
  <div class="pbar"><div class="pfill" id="pfill"></div></div>
</div></div>
<div class="drawer" id="drawer" hidden>
  <button class="dw-back" id="dwBack" type="button" aria-label="閉じる"></button>
  <div class="dw-panel" role="dialog" aria-modal="true" aria-label="単元をえらぶ">
    <div class="dw-head"><span id="dwTitle">単元をえらぶ</span>
      <button class="dw-close" id="dwClose" type="button" aria-label="閉じる">×</button></div>
    <div class="dw-list" id="dwList">
      <button class="dw-item dw-home" data-go="0" type="button">目次（この本のトップ）</button>
      __DRAWER__
    </div>
    <div class="dw-list" id="cfgList" hidden>
      <div class="cfg-row"><span class="cfg-lb">文字サイズ</span>
        <button class="cfg-chip" type="button" data-fs="0.9">小</button>
        <button class="cfg-chip on" type="button" data-fs="1">ふつう</button>
        <button class="cfg-chip" type="button" data-fs="1.15">大</button>
        <button class="cfg-chip" type="button" data-fs="1.3">特大</button></div>
      <div class="cfg-row"><span class="cfg-lb">配色</span>
        <button class="cfg-chip on" type="button" data-theme="light">あかるい</button>
        <button class="cfg-chip" type="button" data-theme="dark">よる</button>
        <button class="cfg-chip" type="button" data-theme="auto">端末にあわせる</button></div>
      <div class="cfg-row"><span class="cfg-lb">ルビ</span>
        <button class="cfg-chip on" type="button" data-ruby="1">表示する</button>
        <button class="cfg-chip" type="button" data-ruby="0">消す</button></div>
      <div class="cfg-row cfg-col"><span class="cfg-lb">読み上げ</span>
        <div class="cfg-chips">
          <button class="cfg-chip on" type="button" data-auto="0">1ページで止まる</button>
          <button class="cfg-chip" type="button" data-auto="1">次のページへ進む</button>
        </div>
        <div class="cfg-note">「次のページへ進む」にすると、読み終わったら自動でページをめくって
          読み続けます（聞きながら復習したいとき用）。</div></div>
    </div>
  </div>
</div>
<a class="backpill" id="backPill" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 6l-6 6 6 6"/></svg>問題にもどる</a>
<main class="wrap" id="views">
__VIEWS__
</main>
<div class="sr-only" id="liveMsg" aria-live="polite" role="status"></div>
<div class="hintbar" id="hintBar" hidden></div>
<div class="aplayer idle" id="aplayer" hidden><div class="ap-in">
  <button class="ap-btn" id="apPlay" aria-label="再生／一時停止">▶</button>
  <div class="ap-idle-label" id="apIdle">読み上げる</div>
  <div class="ap-seek"><input type="range" id="apSeek" min="0" max="1000" value="0" aria-label="再生位置"></div>
  <div class="ap-time" id="apTime">0:00 / 0:00</div>
  <button class="ap-rate" id="apRate" aria-label="読み上げの速さ">1.0×</button>
</div></div>
<audio id="audio" preload="none"></audio>
<div class="lightbox" id="lightbox" hidden>
  <img id="lightboxImg" alt="">
  <button class="lb-close" id="lbClose" aria-label="閉じる">×</button>
  <div class="lb-hint">タップで閉じる</div>
</div>
<div class="navbar" id="navbar" hidden><div class="navbar-in">
  <button class="nb nb-prev" id="btnPrev">← まえへ</button>
  <button class="nb nb-next" id="btnNext">つぎへ →</button>
</div></div>
<div class="lock-ov" id="lockOv" hidden><div class="lock-card">
  <div class="lock-ic">🔒</div>
  <div class="lock-t" id="lockT">つづきも、無料でためせます</div>
  <div class="lock-d" id="lockD">3日間は、ぜんぶの単元がつかえます。<br>気に入ったら、そのまま続けられます。</div>
  <button class="lock-btn lb-trial" id="lockTrial">🎁 3日間無料でためす</button>
  <button class="lock-btn lb-trial" id="lockSubMain" hidden>月額プランに登録（1,280円／月）</button>
  <button class="lock-btn lb-buy" id="lockParent">おうちの人にお願いする</button>
  <a class="lock-btn lb-buy" href="../../index.html">つづもんって？ くわしく見る →</a>
  <button class="lock-btn lb-line" id="lockLogin">LINEでログイン（登録ずみの方）</button>
  <div class="lock-msg" id="lockMsg" hidden></div>
  <button class="lock-sublink" id="lockSub">ためさずに月額プランに登録（1,280円／月）</button>
  <button class="lock-close" id="lockClose">とじる</button>
</div></div>
<button class="chat-fab" id="chatFab" aria-label="AIに質問する">__FAB__</button>
<section class="chat-panel" id="chatPanel" hidden>
  <header class="chat-head">
    <span class="chat-title">🤖 AIに質問</span>
    <span class="chat-topic" id="chatTopic"></span>
    <button class="chat-close" id="chatClose" aria-label="閉じる">×</button>
  </header>
  <div class="chat-note">公式LINEと同じAI。会話はLINEのトークとつながるよ。</div>
  <div class="chat-body" id="chatBody"></div>
  <div class="chat-login" id="chatLogin" hidden>
    <p>LINEログインすると、このページでAIに質問できるよ。<br>会話のつづきは公式LINEでも話せる！</p>
    <a class="chat-login-btn" id="chatLoginBtn" href="/login/">LINEでログイン</a>
  </div>
  <form class="chat-input" id="chatForm" hidden>
    <input type="text" id="chatText" placeholder="この単元の質問をどうぞ！" maxlength="300" autocomplete="off">
    <button type="submit" id="chatSend">送信</button>
  </form>
  <div class="chat-foot" id="chatFoot"></div>
</section>
<script>
(function () {
  var KEY = '__STORAGE_KEY__';
  var CH = '__CH_NO__';
  var GRADE = '__GRADE__';        // この本の学年（中1/中2/中3）
  var ENTITLEMENT_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonEntitlement';
  var WB_VIEWS = __WB_VIEWS__;
  var AUDIO = __AUDIO__;          // {単元t: {url, tl:[[開始秒,長さ,ステップ], …]}}          // 参考書の単元t → 問題集のビュー番号（0＝対応なし）
  var views = [].slice.call(document.querySelectorAll('.view'));
  var tabs = [].slice.call(document.querySelectorAll('.dw-item[data-dw]'));
  var N = views.length - 1; // 単元数
  var state = { t: 0, s: 0 };
  var lastDir = 1;
  var rendered = null; // 直前に表示していた {t, s}（ページめくり演出用）
  var navigating = false;  // popstate 由来の移動中は履歴を積まない

  // ── 表示設定（文字サイズ・配色・ルビ）──
  //   値は head の先読みスクリプトと同じ localStorage['tzm-view'] を使う。
  var VIEWCFG = window.__tzmView || {};
  function saveViewCfg() {
    try { localStorage.setItem('tzm-view', JSON.stringify(VIEWCFG)); } catch (e) {}
  }
  function applyViewCfg() {
    var root = document.documentElement;
    var th = VIEWCFG.theme || 'auto';
    var dark = th === 'dark' || (th === 'auto' && window.matchMedia
               && window.matchMedia('(prefers-color-scheme: dark)').matches);
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    root.style.setProperty('--fs', VIEWCFG.fs || 1);
    root.classList.toggle('noruby', VIEWCFG.ruby === 0);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', dark ? '#17140f' : '#fffdf8');
    [].forEach.call(document.querySelectorAll('#cfgList .cfg-chip'), function (b) {
      if (b.dataset.fs) b.classList.toggle('on', String(VIEWCFG.fs || 1) === b.dataset.fs);
      if (b.dataset.theme) b.classList.toggle('on', th === b.dataset.theme);
      if (b.dataset.ruby) b.classList.toggle('on', String(VIEWCFG.ruby == null ? 1 : VIEWCFG.ruby) === b.dataset.ruby);
      if (b.dataset.auto) b.classList.toggle('on', String(VIEWCFG.autoNext || 0) === b.dataset.auto);
    });
  }
  applyViewCfg();
  if (window.matchMedia) {
    try {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
        if ((VIEWCFG.theme || 'auto') === 'auto') applyViewCfg();
      });
    } catch (e) {}
  }

  // ── 操作ヒント（初回のみ）──
  (function () {
    var bar = document.getElementById('hintBar');
    if (!bar) return;
    // ヒントのキーは参考書／問題集で分ける（操作が違うのに片方で消費されていた）
    try { if (localStorage.getItem('tzmhint-ref') === '1') return; } catch (e) { return; }
    var canHover = window.matchMedia && window.matchMedia('(hover:hover)').matches;
    bar.textContent = canHover ? '⌨️ ← → キーでもページをめくれるよ'
                               : '👆 よこにスワイプでもページをめくれるよ';
    var shown = false;
    window.showHint = function () {
      if (shown || state.t === 0) return;
      shown = true; bar.hidden = false;
      try { localStorage.setItem('tzmhint-ref', '1'); } catch (e) {}
      setTimeout(function () { bar.hidden = true; }, 5000);
    };
    bar.addEventListener('click', function () { bar.hidden = true; });
  })();


  // ── 読み上げ（いま開いているページ＝ステップの音声だけを再生）──
  //   音声ファイルは単元まるごと1本。tl[k]=[開始秒,長さ,そのマスがあるステップ]。
  //   再生するのは「いま見ているステップ」に属する区間だけで、終わったら停止する
  //   （次のページには自動で進まない）。時間表示もそのページ分だけ。
  var au = document.getElementById('audio');
  var apl = document.getElementById('aplayer');
  var reading = { t: 0, step: null, i0: 0, i1: -1, s0: 0, s1: 0, i: -1 };
  var RATES = [1, 1.25, 1.5, 0.75], ri = 0;

  function fmt(x) { x = Math.max(0, x | 0); return (x / 60 | 0) + ':' + ('0' + (x % 60)).slice(-2); }
  function spansOf(t) { return [].slice.call(views[t].querySelectorAll('.s')); }

  // 単元t のステップstep に対応する音声区間（chunk範囲＋開始・終了秒）。無ければ null。
  function stepRange(t, step) {
    var a = AUDIO[t];
    if (!a) return null;
    var tl = a.tl, i0 = -1, i1 = -1;
    for (var i = 0; i < tl.length; i++) {
      if (tl[i][2] === step) { if (i0 < 0) i0 = i; i1 = i; }
    }
    if (i0 < 0) return null;
    return { i0: i0, i1: i1, s0: tl[i0][0], s1: tl[i1][0] + tl[i1][1] };
  }

  // ── プレーヤーの見せ方 ──
  //   音声のあるページでは、再生していなくても細いバーを常設して「読める」ことを示す。
  //   （以前は単元見出しのボタンだけで、読み進めると画面から消えて気づけなかった）
  function syncPlayer() {
    var has = !!stepRange(state.t, state.s);
    var active = reading.step != null;
    apl.hidden = !has && !active;
    apl.classList.toggle('idle', !active);
    document.body.classList.toggle('has-player', !apl.hidden);
    layoutNav(!apl.hidden && state.t > 0);
  }
  // プレーヤーが出ている間は、ページ送りの丸ボタンをプレーヤーの行の両端へ移す。
  //   （プレーヤーとナビが上下に並ぶと、下だけで2段ぶんの高さを取って本文が狭くなる）
  var navMerged = null;
  function layoutNav(merged) {
    if (merged === navMerged) return;
    navMerged = merged;
    var apIn = apl.querySelector('.ap-in');
    var nbIn = document.querySelector('.navbar-in');
    var p = document.getElementById('btnPrev'), n = document.getElementById('btnNext');
    if (!apIn || !nbIn || !p || !n) return;
    if (merged) { apIn.insertBefore(p, apIn.firstChild); apIn.appendChild(n); }
    else { nbIn.appendChild(p); nbIn.appendChild(n); }
    document.body.classList.toggle('nav-merged', !!merged);
  }
  // 読み終わったら次のページへ自動で進むか（設定シートの「読み上げ」で切りかえる）。
  //   プレーヤーの行に置くと、狭い幅では意味を説明できず「押すと何が起きるか」が伝わらないため、
  //   説明文といっしょに設定側へ置いた。
  function contPlay() { return VIEWCFG.autoNext === 1; }

  // いま開いているページを読み上げる。fromChunk を渡すとその句から。
  function playStep(t, step, fromChunk) {
    var r = stepRange(t, step);
    if (!r) return;                       // 音声のないページ（重要語チェック等）
    var a = AUDIO[t];
    var at = (fromChunk != null && a.tl[fromChunk]) ? a.tl[fromChunk][0] : r.s0;
    reading = { t: t, step: step, i0: r.i0, i1: r.i1, s0: r.s0, s1: r.s1, i: -1 };
    document.body.classList.add('reading');
    syncPlayer();
    au.playbackRate = RATES[ri];
    var begin = function () { try { au.currentTime = at; } catch (e) {} au.play(); };
    if (au.dataset.t === String(t) && au.readyState >= 1) { begin(); }
    else {
      au.src = a.url; au.dataset.t = String(t);
      au.addEventListener('loadedmetadata', begin, { once: true });
      au.load();
    }
  }
  function stopAudio() {
    au.pause();
    document.body.classList.remove('reading');
    if (reading.t) spansOf(reading.t).forEach(function (el) { el.classList.remove('now', 'read'); });
    reading = { t: 0, step: null, i0: 0, i1: -1, s0: 0, s1: 0, i: -1 };
    syncPlayer();
  }
  function paintAudio() {
    if (reading.step == null) return;
    var tl = AUDIO[reading.t].tl, k = -1;
    for (var i = reading.i0; i <= reading.i1; i++) { if (au.currentTime >= tl[i][0]) k = i; else break; }
    if (k === reading.i) return;
    reading.i = k;
    var sp = spansOf(reading.t);
    sp.forEach(function (el, i) {
      el.classList.toggle('now', i === k);
      el.classList.toggle('read', i >= reading.i0 && i < k);
    });
    var el = sp[k];
    if (el) {
      var rc = el.getBoundingClientRect();
      if (rc.top < 70 || rc.bottom > innerHeight - 150) {
        scrollTo({ top: scrollY + rc.top - innerHeight * 0.4, behavior: 'smooth' });
      }
    }
  }
  function updateBar(atEnd) {
    var dur = reading.s1 - reading.s0;
    var pos = atEnd ? dur : Math.min(dur, Math.max(0, au.currentTime - reading.s0));
    document.getElementById('apSeek').value = dur ? Math.round(pos / dur * 1000) : 0;
    document.getElementById('apTime').textContent = fmt(pos) + ' / ' + fmt(dur);
  }
  function tickAudio() {
    // ページの終わりまで来たら停止。「続けて」ONなら次のページへ進んで読み続ける。
    if (reading.step != null && au.currentTime >= reading.s1 - 0.02) {
      au.pause();
      var sp = spansOf(reading.t);
      sp.forEach(function (el, i) {
        el.classList.remove('now');
        el.classList.toggle('read', i >= reading.i0 && i <= reading.i1);
      });
      updateBar(true);
      if (contPlay()) advanceAudio();
      return;
    }
    paintAudio();
    updateBar(false);
    if (!au.paused) requestAnimationFrame(tickAudio);
  }
  // 続けて再生: 次に音声のあるページを探して、そこへ移動して読み始める。
  //   同じ単元の中だけ進み、見つからなければ静かに止まる（勝手に次の単元へは行かない）。
  function advanceAudio() {
    var t = reading.t, from = reading.step;
    var last = stepsOf(t).length - 1;
    for (var s = from + 1; s <= last; s++) {
      if (gateBlocks(t, s)) break;                 // 頭出しの先はロック案内に任せる
      if (stepRange(t, s)) {
        var goNext = function (ss) { go(t, ss, 1); setTimeout(function () { playStep(t, ss); }, 260); };
        goNext(s);
        return;
      }
    }
  }
  au.addEventListener('play', function () { document.getElementById('apPlay').textContent = '❚❚'; tickAudio(); });
  au.addEventListener('pause', function () { document.getElementById('apPlay').textContent = '▶'; });
  document.getElementById('apPlay').onclick = function () {
    if (reading.step == null) { playStep(state.t, state.s); return; }   // 停止中バーからの再生
    if (au.paused) {
      if (au.currentTime >= reading.s1 - 0.05) au.currentTime = reading.s0;  // 読み終わっていたら頭から
      au.play();
    } else au.pause();
  };
  document.getElementById('apIdle').onclick = function () { playStep(state.t, state.s); };
  document.getElementById('apSeek').oninput = function () {
    if (reading.step == null) return;
    var dur = reading.s1 - reading.s0;
    au.currentTime = reading.s0 + this.value / 1000 * dur;
    reading.i = -1; paintAudio(); updateBar(false);
  };
  document.getElementById('apRate').onclick = function () {
    ri = (ri + 1) % RATES.length; au.playbackRate = RATES[ri];
    this.textContent = RATES[ri].toFixed(2).replace(/0$/, '') + '×';
  };
  // 「🔊 このページを読む」＝いま開いているページを読む／文字タップでその句から読む
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.play-unit');
    if (b) { playStep(state.t, state.s); return; }
    var sp = e.target.closest && e.target.closest('.s');
    if (sp && AUDIO[state.t]) {
      var k = +sp.dataset.i;
      if (AUDIO[state.t].tl[k]) playStep(state.t, AUDIO[state.t].tl[k][2], k);
    }
  });

  // ── 単元ドロワー（一覧シート）＋表示設定シート ──
  var drawerEl = document.getElementById('drawer');
  var dwListEl = document.getElementById('dwList');
  var cfgListEl = document.getElementById('cfgList');
  var lastFocus = null;
  function openDrawer(mode) {
    lastFocus = document.activeElement;
    var cfg = mode === 'cfg';
    dwListEl.hidden = cfg;
    cfgListEl.hidden = !cfg;
    document.getElementById('dwTitle').textContent = cfg ? '表示の設定' : '単元をえらぶ';
    drawerEl.hidden = false;
    document.body.style.overflow = 'hidden';
    // 背後をキーボード操作の対象から外す（フォーカスが裏に抜けないように）
    [].forEach.call(document.querySelectorAll('body > *:not(#drawer)'), function (el) {
      try { el.inert = true; } catch (e) {}
    });
    var cur = drawerEl.querySelector('.dw-item.on') || drawerEl.querySelector('.dw-item, .cfg-chip');
    if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: 'center' });
    var f = drawerEl.querySelector('.dw-close');
    if (f) f.focus();
  }
  function closeDrawer() {
    if (drawerEl.hidden) return;
    drawerEl.hidden = true;
    document.body.style.overflow = '';
    [].forEach.call(document.querySelectorAll('body > *:not(#drawer)'), function (el) {
      try { el.inert = false; } catch (e) {}
    });
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  document.getElementById('unitBtn').addEventListener('click', function () { openDrawer('units'); });
  document.getElementById('cfgBtn').addEventListener('click', function () { openDrawer('cfg'); });
  document.getElementById('dwClose').addEventListener('click', closeDrawer);
  document.getElementById('dwBack').addEventListener('click', closeDrawer);
  cfgListEl.addEventListener('click', function (e) {
    var b = e.target.closest('.cfg-chip');
    if (!b) return;
    if (b.dataset.fs) VIEWCFG.fs = parseFloat(b.dataset.fs);
    if (b.dataset.theme) VIEWCFG.theme = b.dataset.theme;
    if (b.dataset.ruby) VIEWCFG.ruby = +b.dataset.ruby;
    if (b.dataset.auto) VIEWCFG.autoNext = +b.dataset.auto;
    saveViewCfg();
    applyViewCfg();
  });

  function store() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
  }
  function save(obj) {
    try { localStorage.setItem(KEY, JSON.stringify(obj)); } catch (e) {}
  }
  function stepsOf(t) { return views[t].querySelectorAll('.step'); }

  function render() {
    var t = state.t, s = state.s;
    views.forEach(function (v, i) {
      v.classList.toggle('on', i === t);
      // 表示していないビューは支援技術からも隠す（読み上げが全単元を読んでしまわないように）
      if (i === t) v.removeAttribute('aria-hidden'); else v.setAttribute('aria-hidden', 'true');
    });
    var st0 = store();
    tabs.forEach(function (b) {
      var bt = +b.dataset.go;
      b.classList.toggle('on', bt === t);
      var stt = b.querySelector('.dw-state');
      if (stt) {
        var doing = st0.last && st0.last.t === bt && st0.last.s > 0;
        stt.className = 'dw-state' + (st0['d' + bt] === 1 ? '' : doing ? ' doing' : '');
        stt.textContent = st0['d' + bt] === 1 ? '✓ 読んだ' : doing ? 'つづき' : '';
      }
    });
    var ubn = document.getElementById('unitBtnName');
    if (ubn) {
      var h2 = t > 0 && views[t].querySelector('.tband h2');
      ubn.textContent = t === 0 ? '目次' : (t + '. ' + (h2 ? h2.textContent : ''));
    }
    if (window.showHint) window.showHint();
    var navbar = document.getElementById('navbar');
    var barStep = document.getElementById('barStep');
    var pfill = document.getElementById('pfill');
    if (t === 0) {
      navbar.hidden = true;
      barStep.textContent = '';
      pfill.style.width = '0';
      renderHome();
    } else {
      var steps = stepsOf(t);
      // 同じ単元内のページ送りだけ「めくり」演出（古いページと新しいページを重ねる）
      var animFrom = rendered && rendered.t === t && rendered.s !== s ? rendered.s : null;
      var oldEl = animFrom !== null ? steps[animFrom] : null;
      var newEl = steps[s];
      // クラスを切り替える前に「めくり始める瞬間の旧ページの見え方（画面上の位置・幅）」を測る。
      // これを position:fixed で固定したままめくり、その裏で window を先頭へ戻すことで
      // 「今いる高さのままページがめくれ、めくり終わると新ページは一番上から」を実現する。
      var oldRect = oldEl ? oldEl.getBoundingClientRect() : null;
      var resetTurn = function (el) {
        el.classList.remove('turn-out', 'turn-in', 'turn-under');
        el.style.position = ''; el.style.top = ''; el.style.left = '';
        el.style.width = ''; el.style.transformOrigin = '';
        el.style.maxHeight = ''; el.style.overflow = '';
      };
      [].forEach.call(steps, function (el, i) {
        resetTurn(el);
        el.classList.toggle('on', i === s);
      });
      if (animFrom !== null && oldEl && newEl && oldRect) {
        // 旧ページを、今見えていた画面上の位置・幅にそのまま貼り付けて固定する
        var pin = function (el) {
          el.style.position = 'fixed';
          el.style.top = oldRect.top + 'px';
          el.style.left = oldRect.left + 'px';
          el.style.width = oldRect.width + 'px';
        };
        var clear = function () { resetTurn(oldEl); resetTurn(newEl); };
        if (lastDir > 0) {
          // 進む: 旧ページを今の位置に固定したまま左とじでめくって去らせる。
          // 透視の消失点を今の画面中央に合わせ、スクロール位置に依らず自然に見せる。
          pin(oldEl);
          oldEl.style.transformOrigin = '0 ' + ((innerHeight / 2) - oldRect.top) + 'px';
          oldEl.classList.add('turn-out');      // 今のページがめくれて去る
          oldEl.addEventListener('animationend', clear, { once: true });
        } else {
          // 戻る: 旧（現在）ページを今の位置に固定して下に敷き、前ページを上へめくり戻す。
          pin(oldEl);
          oldEl.style.maxHeight = 'none'; oldEl.style.overflow = 'visible';
          oldEl.classList.add('turn-under');    // 下に敷いたまま
          newEl.classList.add('turn-in');       // 前のページがめくり戻ってくる
          newEl.addEventListener('animationend', clear, { once: true });
        }
        setTimeout(clear, 900); // アニメ未発火時の保険
      }
      navbar.hidden = false;
      barStep.textContent = (s + 1) + ' / ' + steps.length;
      pfill.style.width = (((s + 1) / steps.length) * 100) + '%';
      // 丸ボタンなので、行き先は data-act（記号）と aria-label（読み上げ）で伝える
      var prev = document.getElementById('btnPrev');
      var next = document.getElementById('btnNext');
      prev.dataset.act = s === 0 ? 'home' : 'prev';
      prev.textContent = s === 0 ? '目次へ' : 'まえへ';
      prev.setAttribute('aria-label', prev.textContent);
      prev.title = prev.textContent;
      next.dataset.act = s < steps.length - 1 ? 'next' : (t < N ? 'unit' : 'home');
      next.textContent = s < steps.length - 1 ? 'つぎへ'
                       : (t < N ? '次の単元へ' : '目次にもどる');
      next.setAttribute('aria-label', next.textContent);
      next.title = next.textContent;
      // 進捗保存。「読んだ」は最終ページに着いただけでは付けず、
      // その単元のページを一通り開いたか（8割以上）で判定する（連打で✓が付かないように）。
      var st = store();
      st.last = { t: t, s: s };
      var seen = st['v' + t] || {};
      seen[s] = 1;
      st['v' + t] = seen;
      st['ts' + t] = Date.now();              // 復習おすすめ（最終閲覧日）に使う
      var nSeen = 0;
      for (var k in seen) { if (seen[k] === 1) nSeen++; }
      if (nSeen >= Math.max(2, Math.ceil(steps.length * 0.8))) st['d' + t] = 1;
      save(st);
    }
    window.scrollTo(0, 0);
    var h = '#t' + t + (t > 0 && s > 0 ? 's' + s : '');
    // ページ送りを履歴に積む（replaceState だけだと、戻る操作で1ページ戻らずサイトから出てしまう）。
    // クエリが付いていても落とさない（URL共有時の情報を保つ）
    if (location.hash !== h) {
      var url = location.pathname + location.search + (t === 0 ? '#' : h);
      if (navigating) history.replaceState({ t: t, s: s }, '', url);
      else history.pushState({ t: t, s: s }, '', url);
    }
    updateSwap();
    var pb = views[t] && views[t].querySelector('.play-unit');
    if (pb) pb.hidden = !stepRange(t, s);
    syncPlayer();
    announce();
    rendered = { t: t, s: s };
  }

  // いま何ページ目かを読み上げソフトへ知らせる（見た目には出さない）
  function announce() {
    var live = document.getElementById('liveMsg');
    if (!live) return;
    var steps = state.t > 0 ? stepsOf(state.t) : null;
    var lab = steps && steps[state.s] ? (steps[state.s].dataset.label || '') : '目次';
    live.textContent = lab + (steps ? '（' + (state.s + 1) + ' / ' + steps.length + '）' : '');
  }

  function renderHome() {
    var st = store();
    var doneN = 0;
    [].forEach.call(document.querySelectorAll('.toc-state'), function (el) {
      var t = +el.dataset.stateT;
      el.className = 'toc-state';
      if (st['d' + t] === 1) {
        doneN++;
        el.classList.add('done');
        // 最後に読んでから日が経った単元は「復習しよう」を出す（忘れたころに出す）
        var days = st['ts' + t] ? Math.floor((Date.now() - st['ts' + t]) / 86400000) : 0;
        if (days >= 7) { el.classList.add('again'); el.textContent = '復習しよう'; }
        else { el.textContent = '✓︎ 読んだ'; }
      } else if (st.last && st.last.t === t && st.last.s > 0) {
        el.classList.add('doing'); el.textContent = 'つづき';
      } else { el.textContent = ''; }
    });
    // この本の到達率（何単元読み終えたか）
    var pw = document.getElementById('bookFill'), pt = document.getElementById('bookTxt');
    if (pw && pt) {
      pw.style.width = (N ? Math.round(doneN / N * 100) : 0) + '%';
      pt.textContent = '読み終えた単元 ' + doneN + ' / ' + N
        + (doneN >= N ? '　ぜんぶ読んだ！ 🎉' : '');
    }
    var btn = document.getElementById('resumeBtn');
    if (st.last && st.last.t > 0) {
      btn.hidden = false;
      var name = views[st.last.t].querySelector('.tband h2').textContent;
      document.getElementById('resumeWhere').textContent =
        name + '（' + (st.last.s + 1) + 'ページ目）';
      btn.onclick = function () { go(st.last.t, st.last.s, 1); };
    } else {
      btn.hidden = true;
    }
  }

  // ── 参考書 ⇄ 問題集の行き来 ──────────────────────────────
  //   相手側の保存（tzmwb-{章}）を読んで「読みかけのページ」に着地させる。
  //   同じサイト内なので localStorage をそのまま参照できる。
  function wbHref(t) {
    var base = '../../wb/' + CH + '/index.html';
    var v = WB_VIEWS[t] || 0;
    if (!v) return base;
    var s = 0;
    try {
      var st = JSON.parse(localStorage.getItem('tzmwb-' + CH) || '{}');
      if (st.last && st.last.t === v && st.last.s > 0) s = st.last.s;
    } catch (e) {}
    return base + '#t' + v + (s ? 's' + s : '');
  }
  function updateSwap() {
    var a = document.getElementById('swWb');
    a.href = wbHref(state.t);
  }

  // ── 教材ゲート（中間案・ゆるめ「頭出しは見せる」）──
  //   有料単元は表紙＋最初の1節まで誰でも読める。その先は購入者（この学年のライセンス）だけ。
  //   判定は localStorage['tzm-lic']（v2: {g:開放学年の配列, exp:期限ms}）を見るだけ。ログイン時に entitlement で更新。
  function isLicensed() {
    try {
      var raw = localStorage.getItem('tzm-lic');
      if (!raw) return false;
      var obj = JSON.parse(raw);
      if (Array.isArray(obj)) { localStorage.removeItem('tzm-lic'); return false; }
      if (!obj || !obj.exp || Date.now() >= obj.exp) { localStorage.removeItem('tzm-lic'); return false; }
      return (obj.g || []).indexOf(GRADE) >= 0;
    } catch (e) { return false; }
  }
  function lockFrom(t) { var v = views[t]; return v ? +(v.getAttribute('data-lock') || 0) : 0; }
  function gateBlocks(t, s) {
    var lk = lockFrom(t);
    return lk > 0 && !isLicensed() && s >= lk;
  }
  // ロックカードを出す前に、LINE内ブラウザで未ログインなら一度だけ無操作ログインを試みる。
  //   ログイン状態は module script が公開する window.tzmAuthUser で判定（module はスコープが別）。
  //   sessionStorage['tzm-auto-login'] で「タブ内1回だけ」に制限（失敗しても2度目は普通にロック表示）。
  function tzmMaybeAutoLogin() {
    if (window.tzmAuthUser) return false;
    if (!/ Line\\//.test(navigator.userAgent)) return false;
    try {
      if (sessionStorage.getItem('tzm-auto-login')) return false;
      sessionStorage.setItem('tzm-auto-login', '1');
    } catch (e) { return false; }
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
    return true;
  }
  function showLock() { if (tzmMaybeAutoLogin()) return; var ov = document.getElementById('lockOv'); if (ov) ov.hidden = false; }
  function hideLock() { var ov = document.getElementById('lockOv'); if (ov) ov.hidden = true; }
  // entitlement 反映後に module script から呼ばれる。解除できたらロックを閉じる。
  window.tzmRefreshGate = function () { if (isLicensed()) hideLock(); };
  // 同じく entitlement 反映後に呼ばれる。ロックカードの主ボタンを状況に合わせて入れ替える。
  //   体験がまだ使える人 → 「3日間無料でためす」（既定のまま）
  //   体験ずみ／期限切れ → 「月額プランに登録」を主ボタンへ昇格し、押せば必ず失敗する
  //   体験ボタンは消す（いちばん買う気のある瞬間に、いちばん小さいリンクを探させない）。
  window.tzmApplyLockState = function (st) {
    var used = !!(st && (st.trialUsed || st.result === 'expired'));
    var t = document.getElementById('lockT'), d = document.getElementById('lockD');
    var trial = document.getElementById('lockTrial'), subMain = document.getElementById('lockSubMain');
    var sub = document.getElementById('lockSub'), login = document.getElementById('lockLogin');
    if (!t || !d || !trial || !subMain || !sub) return;
    trial.hidden = used;
    subMain.hidden = !used;
    sub.hidden = used;               // 主ボタンへ昇格したので下の小さいリンクは消す
    if (login) login.hidden = true;  // ここに来る時点でログイン済み
    if (used) {
      t.textContent = 'つづきは、月額プランで';
      d.innerHTML = '無料体験は終了しました。<br>月額1,280円（税込）で、中学歴史ぜんぶ（全19単元）が使えます。いつでも解約できます。';
    }
  };

  function go(t, s, dir) {
    if (typeof reading !== 'undefined' && reading.step != null) stopAudio();
    lastDir = dir || 1;
    state.t = Math.max(0, Math.min(N, t));
    state.s = Math.max(0, s || 0);
    if (state.t > 0) {
      state.s = Math.min(state.s, stepsOf(state.t).length - 1);
      // 頭出しの先へ行こうとしたら、頭出しの最後で止めてロック案内を出す
      if (gateBlocks(state.t, state.s)) {
        state.s = Math.max(0, lockFrom(state.t) - 1);
        render();
        showLock();
        return;
      }
    } else {
      state.s = 0;
    }
    hideLock();
    render();
  }

  function next() {
    var t = state.t, s = state.s;
    if (t === 0) return;
    if (s < stepsOf(t).length - 1) go(t, s + 1, 1);
    else if (t < N) go(t + 1, 0, 1);
    else go(0, 0, 1);
  }
  function prev() {
    var t = state.t, s = state.s;
    if (t === 0) return;
    if (s > 0) go(t, s - 1, -1);
    else go(0, 0, -1);
  }

  // ロック案内のボタン: 3日間無料体験／ログイン（共通ログインページ経由で戻る）／閉じる
  //   体験開始の実処理は module script の window.tzmStartTrial（Firebase Auth が要る）。
  document.getElementById('lockTrial').addEventListener('click', function () {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    if (window.tzmStartTrial) window.tzmStartTrial(here);
  });
  // 月額プラン登録: 体験ボタンと同型のログイン往復 → Stripe Checkout へ遷移
  function tzmGoCheckout() {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    if (window.tzmStartCheckout) window.tzmStartCheckout(here);
  }
  document.getElementById('lockSub').addEventListener('click', tzmGoCheckout);
  document.getElementById('lockSubMain').addEventListener('click', tzmGoCheckout);
  // おうちの人にお願いする: 中学生本人は決済できないので、ここが実際の出口になる。
  // カードを発行して「見せる画面」（QR＋台本）へ遷移する。
  document.getElementById('lockParent').addEventListener('click', function () {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    if (window.tzmStartParentCard) window.tzmStartParentCard(here);
  });
  document.getElementById('lockLogin').addEventListener('click', function () {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    location.href = '../../login/?next=' + encodeURIComponent(here);
  });
  document.getElementById('lockClose').addEventListener('click', hideLock);
  document.getElementById('btnNext').addEventListener('click', next);
  document.getElementById('btnPrev').addEventListener('click', prev);
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-go]');
    if (b) { closeDrawer(); go(+b.dataset.go, 0, 1); return; }
    // 重要語チェックのシャッフル: カードの並びをランダムに入れ替える
    var sh = e.target.closest('.shuffle-btn');
    if (sh) {
      var grid = sh.closest('.step').querySelector('.tgrid');
      if (grid) {
        var cards = [].slice.call(grid.querySelectorAll('.tcell'));
        for (var i = cards.length - 1; i > 0; i--) {
          var j = Math.floor(Math.random() * (i + 1));
          var tmp = cards[i]; cards[i] = cards[j]; cards[j] = tmp;
        }
        cards.forEach(function (c) {
          c.classList.remove('flipped');
          var tc = c.querySelector('.tcard');
          if (tc) tc.classList.remove('flipped');
          grid.appendChild(c);
        });
        grid.classList.remove('shuffling');
        void grid.offsetWidth;              // リフローでアニメを再始動
        grid.classList.add('shuffling');
      }
      return;
    }
    // 裏表入れ替え（説明→用語 ⇄ 用語→説明）。設定は保存し全単元に反映
    var sw = e.target.closest('.swap-btn');
    if (sw) {
      var g0 = document.querySelector('.tgrid');
      var on = !(g0 && g0.classList.contains('term-first'));
      applySwap(on);
      var st2 = store(); st2.swap = on ? 1 : 0; save(st2);
      return;
    }
    // 「まだの語だけ」表示（覚えた語を隠して、できない語だけ回せるようにする）
    var ong = e.target.closest('.only-ng-btn');
    if (ong) {
      var st4 = store();
      var on2 = !(st4.onlyng === 1);
      st4.onlyng = on2 ? 1 : 0; save(st4);
      applyOnlyNg(on2);
      return;
    }
    // 覚えた／まだ の仕分け（用語ごとに保存し、全単元・次回にも引き継ぐ）
    var tm = e.target.closest('.tm');
    if (tm) {
      var cell = tm.closest('.tcell');
      var st5 = store(); st5.tw = st5.tw || {};
      var key = cell.dataset.tk;
      var v = +tm.dataset.tm;
      if (st5.tw[key] === v) delete st5.tw[key]; else st5.tw[key] = v;   // 押し直しで取り消し
      save(st5);
      paintTerms();
      return;
    }
    // 重要語カード: タップで表裏（両面表示中はめくらない）
    var card = e.target.closest('.tcard');
    if (card && !card.closest('.tgrid').classList.contains('both')) {
      card.classList.toggle('flipped');
      var cl = card.closest('.tcell');
      if (cl) cl.classList.toggle('flipped', card.classList.contains('flipped'));
    }
  });

  // 重要語カードの状態（覚えた／まだ・残り枚数）を描き直す
  function paintTerms() {
    var st = store(), tw = st.tw || {};
    [].forEach.call(document.querySelectorAll('.tcell'), function (c) {
      var v = tw[c.dataset.tk];
      c.classList.toggle('ok', v === 1);
      c.classList.toggle('ng', v === 0);
    });
    [].forEach.call(document.querySelectorAll('[data-tcount]'), function (el) {
      var grid = el.closest('.step').querySelector('.tgrid');
      var cells = grid ? [].slice.call(grid.querySelectorAll('.tcell')) : [];
      var ok = cells.filter(function (c) { return c.classList.contains('ok'); }).length;
      el.textContent = '覚えた ' + ok + ' / ' + cells.length;
      var empty = el.closest('.step').querySelector('.terms-empty');
      if (empty) empty.hidden = !(cells.length && ok === cells.length
                                  && grid.classList.contains('only-ng'));
    });
  }
  function applyOnlyNg(on) {
    [].forEach.call(document.querySelectorAll('.tgrid'), function (g) { g.classList.toggle('only-ng', on); });
    [].forEach.call(document.querySelectorAll('.only-ng-btn'), function (b) { b.classList.toggle('on', on); });
    paintTerms();
  }
  applyOnlyNg(store().onlyng === 1);
  paintTerms();

  // 「両面表示にする」チェック（設定は保存して全単元・次回にも反映）
  function applyBoth(on) {
    [].forEach.call(document.querySelectorAll('.both-chk'), function (c) { c.checked = on; });
    [].forEach.call(document.querySelectorAll('.tgrid'), function (g) {
      g.classList.toggle('both', on);
    });
  }
  document.addEventListener('change', function (e) {
    if (e.target.classList && e.target.classList.contains('both-chk')) {
      applyBoth(e.target.checked);
      var st = store(); st.both = e.target.checked ? 1 : 0; save(st);
    }
  });
  applyBoth(store().both === 1);

  // 裏表入れ替え（用語⇄説明のどちらを先に見せるか。全カード共通・保存）
  function applySwap(on) {
    [].forEach.call(document.querySelectorAll('.tgrid'), function (g) {
      [].forEach.call(g.querySelectorAll('.flipped'), function (c) { c.classList.remove('flipped'); });
      g.classList.toggle('term-first', on);
    });
    [].forEach.call(document.querySelectorAll('.swap-btn'), function (b) { b.classList.toggle('on', on); });
  }
  applySwap(store().swap === 1);

  // 左右スワイプでページ送り（縦スクロールと誤爆しないよう横優位のみ）
  var tx = 0, ty = 0;
  document.addEventListener('touchstart', function (e) {
    tx = e.changedTouches[0].clientX; ty = e.changedTouches[0].clientY;
  }, { passive: true });
  document.addEventListener('touchend', function (e) {
    // 画像拡大中・ドロワー表示中はページ送りしない
    // （拡大した地図を横に見ようとしたスワイプで、裏のページがめくれてしまっていた）
    if (!document.getElementById('lightbox').hidden || !drawerEl.hidden) return;
    var dx = e.changedTouches[0].clientX - tx;
    var dy = e.changedTouches[0].clientY - ty;
    if (Math.abs(dx) > 64 && Math.abs(dy) < 48 && state.t > 0) {
      if (dx < 0) next(); else prev();
    }
  }, { passive: true });

  // 画像タップで拡大（ライトボックス）。ページ送りタップ／スワイプと競合しない。
  var lb = document.getElementById('lightbox');
  var lbImg = document.getElementById('lightboxImg');
  function openLb(src) { lbImg.src = src; lb.hidden = false; document.body.style.overflow = 'hidden'; }
  function closeLb() { lb.hidden = true; lbImg.removeAttribute('src'); document.body.style.overflow = ''; }
  document.addEventListener('click', function (e) {
    var z = e.target.closest('img.zoomable');
    if (z) { e.preventDefault(); e.stopPropagation(); openLb(z.currentSrc || z.src); }
  });
  lb.addEventListener('click', closeLb);
  document.getElementById('lbClose').addEventListener('click', function (e) { e.stopPropagation(); closeLb(); });

  // キーボード操作（PC）: ←→ でページ送り、PageUp/Down も同じ、Home で目次へ
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (!lb.hidden) { closeLb(); return; }
      if (!drawerEl.hidden) { closeDrawer(); return; }
    }
    if (!drawerEl.hidden) return;              // シート表示中はページ送りしない
    var tag = e.target && e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === 'Enter') { next(); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { prev(); e.preventDefault(); }
    else if (e.key === 'Home') { go(0, 0, -1); e.preventDefault(); }
  });

  // ハッシュ直リンク（#t3s2）
  function fromHash() {
    var m = /#t(\\d+)(?:s(\\d+))?/.exec(location.hash);
    if (m) go(+m[1], +(m[2] || 0), 1); else go(0, 0, 1);
  }
  // 戻る／進む: 履歴に積んだページへ移動する（サイトから出てしまわないように）
  window.addEventListener('popstate', function () {
    navigating = true;
    fromHash();
    navigating = false;
  });
  fromHash();

  // ── 上部バーの自動しまい込み ＆ チャットボタンの回避 ──
  //   LINE内ブラウザは上下にLINEのUIが入るため、自前のバー・ナビ・プレーヤーで
  //   本文が3分の1しか残らない。下へ読み進める間はバーを隠し、上へ動かすと戻す。
  (function () {
    var lastY = 0, fab = null, fabTimer = 0;
    function onScroll() {
      var y = Math.max(0, window.scrollY || 0);
      var down = y > lastY + 6, up = y < lastY - 6;
      if (down && y > 80) document.body.classList.add('hidebar');
      else if (up || y < 40) document.body.classList.remove('hidebar');
      if (!fab) fab = document.getElementById('chatFab');
      if (fab && (down || up)) {
        fab.classList.add('dim');
        clearTimeout(fabTimer);
        // 指を止めてから戻す。900ms だと連続スクロール中に何度も濃くなって目ざわりだった。
        fabTimer = setTimeout(function () { fab.classList.remove('dim'); }, 1400);
      }
      lastY = y;
    }
    window.addEventListener('scroll', onScroll, { passive: true });
  })();

  // 問題集の「解説を読む」から来たとき（?back=）だけ「問題にもどる」を出す
  (function () {
    var m = /[?&]back=([^&#]+)/.exec(location.search);
    var pill = document.getElementById('backPill');
    if (m && pill) {
      try { pill.href = decodeURIComponent(m[1]); } catch (e) { pill.href = m[1]; }
      pill.hidden = false;
    }
  })();
})();
</script>
<script type="module">
// ── ページ内チャット（AI）──
// 公式LINEの参考書AI（ref_ask）と知識・会話履歴・1日回数枠を共有する。
// 認証は tsudumon.jp/login/ の LINE Login（Firebase Auth）。localStorage 永続化なので、
// 一度 /login/ でログインすればつづもんの全ページで共有される。
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import {
  initializeAuth, browserLocalPersistence, browserSessionPersistence,
  inMemoryPersistence, onAuthStateChanged,
} from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';

var TOPIC_KEYS = __TOPIC_KEYS__;
var API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/referenceChat';

var app = initializeApp(__FIREBASE_WEB_CONFIG__);
var auth = initializeAuth(app, {
  persistence: [browserLocalPersistence, browserSessionPersistence, inMemoryPersistence],
});

var fab = document.getElementById('chatFab');
var panel = document.getElementById('chatPanel');
var body = document.getElementById('chatBody');
var loginBox = document.getElementById('chatLogin');
var form = document.getElementById('chatForm');
var input = document.getElementById('chatText');
var sendBtn = document.getElementById('chatSend');
var foot = document.getElementById('chatFoot');
var topicEl = document.getElementById('chatTopic');

var user = null;
var loadedTopic = null;   // 履歴取得済みの topicKey
var busy = false;

function currentTopicKey() {
  var m = /#t(\\d+)/.exec(location.hash);
  var t = m ? +m[1] : 0;
  var idx = Math.max(1, Math.min(t, TOPIC_KEYS.length)) - 1;
  return TOPIC_KEYS[idx];
}
function msg(role, text) {
  var el = document.createElement('div');
  el.className = 'chat-msg ' + role;
  el.textContent = text;
  body.appendChild(el);
  body.scrollTop = body.scrollHeight;
  return el;
}
function setFoot(remaining) {
  foot.textContent = remaining != null ? 'きょう あと' + remaining + '回 質問できるよ' : '';
}
function showLogin() {
  loginBox.hidden = false;
  form.hidden = true;
  document.getElementById('chatLoginBtn').href =
    '/login/?next=' + encodeURIComponent(location.pathname + location.hash);
}
function showChat() { loginBox.hidden = true; form.hidden = false; }

async function callApi(payload) {
  var idToken = await user.getIdToken();
  var res = await fetch(API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(Object.assign({ idToken: idToken }, payload)),
  });
  var data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  return { status: res.status, data: data || {} };
}

async function loadHistory() {
  var topicKey = currentTopicKey();
  loadedTopic = topicKey;
  body.innerHTML = '';
  var loading = msg('sys', '読み込み中…');
  try {
    var r = await callApi({ topicKey: topicKey, action: 'history' });
    loading.remove();
    if (r.status === 402) { msg('sys', r.data.message || 'この単元は購入者向けです'); form.hidden = true; return; }
    if (r.status !== 200) { msg('sys', 'うまく読み込めなかった。開き直してみてね'); return; }
    topicEl.textContent = r.data.topicName || '';
    var h = r.data.history || [];
    if (h.length === 0) {
      msg('model', 'こんにちは！「' + (r.data.topicName || 'この単元') + '」でわからないことがあったら、なんでも聞いてね😊');
    } else {
      msg('sys', '── ここまでの会話（LINEと共有）──');
      h.forEach(function (turn) { msg(turn.role === 'user' ? 'user' : 'model', turn.text); });
    }
    setFoot(r.data.remaining);
    showChat();
  } catch (e) {
    loading.textContent = '通信エラー。電波のよいところで開き直してみてね';
  }
}

async function send(text) {
  if (busy) return;
  busy = true;
  sendBtn.disabled = true;
  msg('user', text);
  var waiting = msg('sys', 'AIが考え中…');
  try {
    var r = await callApi({ topicKey: loadedTopic || currentTopicKey(), action: 'send', text: text });
    waiting.remove();
    if (r.status === 200) {
      msg('model', r.data.answer);
      setFoot(r.data.remaining);
    } else if (r.data && r.data.message) {
      msg('sys', r.data.message);
    } else {
      msg('sys', 'ごめんね、いまうまく答えられなかった。もう一度送ってみてね');
    }
  } catch (e) {
    waiting.textContent = '通信エラー。もう一度送ってみてね';
  }
  busy = false;
  sendBtn.disabled = false;
}

fab.addEventListener('click', function () {
  panel.hidden = false;
  fab.classList.add('hidden');
  if (!user) { showLogin(); return; }
  if (loadedTopic !== currentTopicKey()) loadHistory();
});
document.getElementById('chatClose').addEventListener('click', function () {
  panel.hidden = true;
  fab.classList.remove('hidden');
});
form.addEventListener('submit', function (e) {
  e.preventDefault();
  var text = input.value.trim();
  if (!text) return;
  input.value = '';
  send(text);
});
// 単元を移動したら（パネルを開いたまま）その単元の会話に切り替える
window.addEventListener('hashchange', function () {
  if (!panel.hidden && user && loadedTopic !== currentTopicKey()) loadHistory();
});

// 教材ゲート用: ログイン済みなら開放学年を取得して localStorage['tzm-lic'] に保存し、
// 通常script のロックを解除できるか再評価する（users/{uid} 1 read）。
var ENTITLEMENT_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonEntitlement';
async function refreshEntitlement(u) {
  try {
    var idToken = await u.getIdToken();
    var res = await fetch(ENTITLEMENT_API, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: idToken }),
    });
    if (!res.ok) return;
    var data = await res.json();
    var grades = (data && data.grades) || [];
    try {
      if (grades.length === 0) {
        localStorage.removeItem('tzm-lic');
      } else {
        var exp = Math.min(Number(data.expiresAtMs) || (Date.now() + 30 * 24 * 3600 * 1000), Date.now() + 30 * 24 * 3600 * 1000);
        localStorage.setItem('tzm-lic', JSON.stringify({ g: grades, exp: exp }));
      }
    } catch (e) {}
    if (window.tzmRefreshGate) window.tzmRefreshGate();
    if (window.tzmApplyLockState) {
      window.tzmApplyLockState({ result: data && data.result, trialUsed: !!(data && data.trialUsed) });
    }
  } catch (e) { /* ゲートは localStorage フォールバックのまま */ }
}

// ── 3日間無料体験（ロックカードの主ボタン）──
//   1 uid 1回。サーバ（tsudumonTrialStart）で判定→成功なら refreshEntitlement で解錠。
var TRIAL_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonTrialStart';
var TRIAL_LABEL = '🎁 3日間無料でためす';
function tzmTrialMsg(text, kind) {
  var el = document.getElementById('lockMsg');
  if (!el) return;
  el.textContent = text;
  el.className = 'lock-msg' + (kind ? ' ' + kind : '');
  el.hidden = false;
}
function tzmTrialBtn(disabled, label) {
  var b = document.getElementById('lockTrial');
  if (!b) return;
  b.disabled = disabled;
  if (label != null) b.textContent = label;
}
async function tzmDoTrial() {
  var u = auth.currentUser;
  if (!u) return;
  tzmTrialBtn(true, '開始しています…');   // 連打防止
  try {
    var idToken = await u.getIdToken();
    var res = await fetch(TRIAL_API, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: idToken }),
    });
    var data = {};
    try { data = await res.json(); } catch (e) {}
    if (res.ok && data && data.ok) {
      tzmTrialBtn(true, '✓ 体験を開始しました');
      tzmTrialMsg('体験開始！' + (data.expiresLabel || '3日後') + 'まで全単元つかえます 🎉', 'ok');
      setTimeout(function () { refreshEntitlement(u); }, 1600);   // 解錠＋ロックを閉じる
      return;
    }
    var reason = data && data.reason;
    if (reason === 'already_licensed') {
      tzmTrialBtn(true, '✓ ご利用いただけます');
      tzmTrialMsg(data.message || 'すでにご利用いただけます。解錠します。', 'ok');
      setTimeout(function () { refreshEntitlement(u); }, 1200);
      return;
    }
    if (reason === 'trial_used') {
      tzmTrialBtn(true, '体験は利用ずみです');
      tzmTrialMsg(data.message || '無料体験はご利用ずみです。購入すると続きが読めます。', 'warn');
      return;
    }
    tzmTrialBtn(false, TRIAL_LABEL);
    tzmTrialMsg((data && data.message) || '体験を開始できませんでした。もう一度お試しください。', 'warn');
  } catch (e) {
    tzmTrialBtn(false, TRIAL_LABEL);
    tzmTrialMsg('通信エラー。電波の良いところでもう一度お試しください', 'warn');
  }
}
// 通常script のクリックハンドラから呼ばれる。ログイン済みなら即実行、未ログインなら
// pending を立ててログインへ（LINE内は無操作／外部はボタン式。戻ってきたら下で継続）。
window.tzmStartTrial = function (next) {
  if (auth.currentUser) { tzmDoTrial(); return; }
  try { localStorage.setItem('tzm-trial-pending', '1'); } catch (e) {}
  var here = next || (location.pathname + location.hash);
  location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
};

// ── 月額サブスク登録（ロックカードの「月額プランに登録」ボタン）──
//   Stripe Checkout 直付け。tzmStartCheckout はログイン往復（trial と同型）→
//   tsudumonCreateCheckout POST → 成功で Checkout URL へ遷移。
var CHECKOUT_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonCreateCheckout';
var SUB_LABEL = 'ためさずに月額プランに登録（1,280円／月）';
var SUB_MAIN_LABEL = '月額プランに登録（1,280円／月）';
// 体験ずみの人には主ボタン（lockSubMain）が出ているので、いま見えているほうを操作する。
function tzmSubEl() {
  var main = document.getElementById('lockSubMain');
  if (main && !main.hidden) return { el: main, label: SUB_MAIN_LABEL };
  var sub = document.getElementById('lockSub');
  return sub ? { el: sub, label: SUB_LABEL } : null;
}
function tzmSubBtn(disabled, label) {
  var t = tzmSubEl();
  if (!t) return;
  t.el.disabled = disabled;
  if (label != null) t.el.textContent = label === SUB_LABEL ? t.label : label;
}
async function tzmDoCheckout() {
  var u = auth.currentUser;
  if (!u) return;
  tzmSubBtn(true, '準備しています…');   // 連打防止（成功時はそのまま遷移）
  try {
    var idToken = await u.getIdToken();
    var res = await fetch(CHECKOUT_API, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: idToken }),
    });
    var data = {};
    try { data = await res.json(); } catch (e) {}
    if (res.ok && data && data.ok && data.url) {
      location.href = data.url;   // Stripe Checkout へ
      return;
    }
    var reason = data && data.reason;
    if (reason === 'already_subscribed') {
      tzmSubBtn(true, '✓ 登録ずみです');
      tzmTrialMsg(data.message || 'すでに月額プランにご登録いただいています。解錠します。', 'ok');
      setTimeout(function () { refreshEntitlement(u); }, 1200);
      return;
    }
    // not_configured / stripe_error / 通信失敗 はいずれも準備中として案内
    tzmSubBtn(false, SUB_LABEL);
    tzmTrialMsg('決済の準備中です。公式LINEでお知らせします。', 'warn');
  } catch (e) {
    tzmSubBtn(false, SUB_LABEL);
    tzmTrialMsg('決済の準備中です。公式LINEでお知らせします。', 'warn');
  }
}
// ログイン済みなら即実行、未ログインなら pending を立ててログインへ（戻ってきたら下で継続）。
window.tzmStartCheckout = function (next) {
  if (auth.currentUser) { tzmDoCheckout(); return; }
  try { localStorage.setItem('tzm-sub-pending', '1'); } catch (e) {}
  var here = next || (location.pathname + location.hash);
  location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
};

// ── おうちの人にわたすカード（ロックカードの「おうちの人にお願いする」）──
//   中学生本人は決済できない。カードを発行して「見せる画面」（QR＋台本）へ送る。
//   設計: pdf-workbook/.steering/20260727-parent-handoff/design.md
var INVITE_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonInviteCreate';
function tzmParentBtn(disabled, label) {
  var el = document.getElementById('lockParent');
  if (!el) return;
  el.disabled = disabled;
  if (label != null) el.textContent = label;
}
async function tzmDoParentCard() {
  var u = auth.currentUser;
  if (!u) return;
  tzmParentBtn(true, '準備しています…');
  try {
    var idToken = await u.getIdToken();
    var res = await fetch(INVITE_API, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: idToken }),
    });
    var data = {};
    try { data = await res.json(); } catch (e) {}
    if (res.ok && data && data.ok && data.handoffUrl) {
      location.href = data.handoffUrl;
      return;
    }
  } catch (e) {}
  tzmParentBtn(false, 'おうちの人にお願いする');
  tzmTrialMsg('いま準備できませんでした。公式LINEの「おうちの人に見せたい」からも出せます。', 'warn');
}
window.tzmStartParentCard = function (next) {
  if (auth.currentUser) { tzmDoParentCard(); return; }
  try { localStorage.setItem('tzm-parent-pending', '1'); } catch (e) {}
  var here = next || (location.pathname + location.hash);
  location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
};

onAuthStateChanged(auth, function (u) {
  user = u;
  window.tzmAuthUser = u || null;   // 通常script のゲート自動ログイン判定用
  if (u) refreshEntitlement(u);
  // 体験／登録ボタン→ログイン往復から戻ってきた継続: pending が立っていれば自動で続行
  if (u) {
    try {
      if (localStorage.getItem('tzm-trial-pending')) {
        localStorage.removeItem('tzm-trial-pending');
        tzmDoTrial();
      } else if (localStorage.getItem('tzm-sub-pending')) {
        localStorage.removeItem('tzm-sub-pending');
        tzmDoCheckout();
      } else if (localStorage.getItem('tzm-parent-pending')) {
        localStorage.removeItem('tzm-parent-pending');
        tzmDoParentCard();
      }
    } catch (e) {}
  }
  if (panel.hidden) return;
  if (!u) { showLogin(); return; }
  loadHistory();
});
</script>

<!-- ── 学習ログの同期（進み具合・時間・正誤をサーバへ）──
     つづもんの進捗はもともと端末の localStorage にしか無く、サーバ側に「どこまで
     進んだか」「何を間違えたか」が一切無かった。AIが個別に対応できるよう、ここで
     まとめてサーバへ送る。
       - 進捗は localStorage 全体（tzmwb-* / tzmref-*）から作る**フル・スナップショット**。
         初回の送信が、そのまま**これまでの学習の吸い上げ**になる。
       - 時間は「このページを見ていた時間」の増分だけを足して送る（送信後に0へ戻す）。
     ログインしていないと送れない（idToken が要る）ので、その間は貯めておく。 -->
<script>
(function () {
  var PROGRESS_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/recordTsudumonProgress';
  var PART = 'ref';               // 'wb'（問題集）or 'ref'（参考書）
  var CH = '__CH_NO__';
  var SIG_KEY = 'tzm-sync-sig';            // 前回送った進捗の指紋（無駄な送信を避ける）
  var MS_KEY = 'tzm-sync-ms-' + PART + CH; // 未送信の滞在時間（タブを閉じても消えない）
  var TICK_MS = 15000;                     // 15秒ごとに可視時間を積む
  var SEND_MS = 60000;                     // 60秒ぶん貯まったら送る
  var IDLE_MAX = 5 * 60 * 1000;            // 5分以上の間隔は「放置」とみなし捨てる

  var pendingMs = 0;
  var lastTick = Date.now();
  var sending = false;
  try { pendingMs = parseInt(localStorage.getItem(MS_KEY) || '0', 10) || 0; } catch (e) {}

  function savePendingMs() { try { localStorage.setItem(MS_KEY, String(pendingMs)); } catch (e) {} }

  function tick() {
    var now = Date.now();
    var d = now - lastTick;
    lastTick = now;
    if (document.visibilityState !== 'visible') return;
    if (d <= 0 || d > IDLE_MAX) return;    // スリープ・放置は学習時間に数えない
    pendingMs += d;
    savePendingMs();
  }

  /** localStorage の生データ（tzm*）をそのまま集める。端末復元用の控え。 */
  function rawSnapshot() {
    var out = {};
    var n = 0;
    try { n = localStorage.length; } catch (e) { return out; }
    for (var i = 0; i < n; i++) {
      var k = null;
      try { k = localStorage.key(i); } catch (e) { continue; }
      if (!/^tzm(wb|ref)-\d{2}$/.test(k || '')) continue;
      try { out[k] = localStorage.getItem(k); } catch (e) {}
    }
    return out;
  }

  /**
   * 端末をまたいだ進捗の取り込み（マージ）。
   * 以前は「ローカルが空のときだけ」復元していたため、新しい端末で1ページでも
   * 進めると、それ以降サーバの控えが二度と戻らなかった。
   * いまはサーバの控えを土台にして、ローカルの記録を上書きで重ねる
   * （読んだ✓・正誤・覚えた語は「どちらかで達成していれば達成」に寄せる）。
   */
  function mergeUnit(remote, local) {
    var out = {};
    var k;
    for (k in remote) out[k] = remote[k];
    for (k in local) {
      var lv = local[k], rv = out[k];
      if (lv && rv && typeof lv === 'object' && typeof rv === 'object') {
        var m = {}, j;
        for (j in rv) m[j] = rv[j];
        for (j in lv) m[j] = lv[j];        // 同じ設問はローカル（新しい端末での結果）を優先
        out[k] = m;
      } else if (/^d\d+$/.test(k)) {
        out[k] = (lv === 1 || rv === 1) ? 1 : lv;   // 読んだ✓は消さない
      } else {
        out[k] = lv;
      }
    }
    return out;
  }
  function restoreFromServer() {
    var u = window.tzmAuthUser;
    if (!u) return;
    try {
      if (sessionStorage.getItem('tzm-restored') === '1') return;
      sessionStorage.setItem('tzm-restored', '1');   // 何度も往復しない
    } catch (e) { return; }
    u.getIdToken().then(function (idToken) {
      return fetch(PROGRESS_API, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify({ idToken: idToken, restore: true }),
      });
    }).then(function (res) { return res && res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data || !data.ok || !data.raw) return;
        var changed = 0;
        for (var k in data.raw) {
          if (!/^tzm(wb|ref)-\d{2}$/.test(k)) continue;
          try {
            var remote = JSON.parse(data.raw[k] || '{}');
            var local = JSON.parse(localStorage.getItem(k) || '{}');
            if (!remote || typeof remote !== 'object') continue;
            var merged = mergeUnit(remote, local && typeof local === 'object' ? local : {});
            var next = JSON.stringify(merged);
            if (next !== JSON.stringify(local)) { localStorage.setItem(k, next); changed++; }
          } catch (e) {}
        }
        if (changed > 0) location.reload();   // 取り込んだ進捗で描き直す
      })
      .catch(function () {});
  }

  /** localStorage 全体から全章の進捗を作る（＝過去ぶんも含む）。 */
  function snapshot() {
    var units = {};
    var n = 0;
    try { n = localStorage.length; } catch (e) { return units; }
    for (var i = 0; i < n; i++) {
      var k = null;
      try { k = localStorage.key(i); } catch (e) { continue; }
      var m = /^tzm(wb|ref)-(\d{2})$/.exec(k || '');
      if (!m) continue;
      var st = null;
      try { st = JSON.parse(localStorage.getItem(k) || '{}'); } catch (e) { continue; }
      if (!st || typeof st !== 'object') continue;
      var u = units[m[2]] || (units[m[2]] = {});
      var steps = 0;
      for (var key in st) { if (/^d\d+$/.test(key) && st[key] === 1) steps++; }
      if (m[1] === 'ref') { u.refSteps = steps; }
      else { u.wbSteps = steps; if (st.r && typeof st.r === 'object') u.r = st.r; }
    }
    // このページの章については、総数（全節数・全設問数）も送る。
    // サーバは「読んだ節 ÷ 全節」「解いた問題 ÷ 全問」で “やり切ったか” を判定する
    // （総数は教材ページにしか無い情報。8割で「やり切った」とみなす）。
    try {
      var here = units[CH] || (units[CH] = {});
      var viewCount = document.querySelectorAll('.view').length - 1;  // 表紙を除く
      if (viewCount > 0) {
        if (PART === 'ref') here.refTotal = viewCount;
        else here.wbTotal = viewCount;
      }
      if (PART === 'wb') {
        here.qTotal = document.querySelectorAll('[data-qid]').length;
      }
    } catch (e) {}
    return units;
  }

  function signature(units) {
    try { return JSON.stringify(units); } catch (e) { return ''; }
  }

  /** @param useBeacon ページ離脱時は sendBeacon（非同期fetchは間に合わない） */
  function send(useBeacon) {
    var u = window.tzmAuthUser;
    if (!u || sending) return;
    tick();
    var units = snapshot();
    var sig = signature(units);
    var lastSig = '';
    try { lastSig = localStorage.getItem(SIG_KEY) || ''; } catch (e) {}
    // 進捗に変化が無く、時間も貯まっていなければ送らない（無駄な書き込みをしない）
    if (sig === lastSig && pendingMs < SEND_MS) return;
    if (pendingMs > 0) {
      units[CH] = units[CH] || {};
      units[CH][PART === 'ref' ? 'msRef' : 'msWb'] = pendingMs;
    }
    var sentMs = pendingMs;

    sending = true;
    u.getIdToken().then(function (idToken) {
      var body = JSON.stringify({
        idToken: idToken,
        units: units,
        raw: rawSnapshot(),   // 端末を変えたときの復元用（サーバに控える）
      });
      var done = function () {
        // 送れたぶんの時間は消す（次回に二重計上しない）
        pendingMs = Math.max(0, pendingMs - sentMs);
        savePendingMs();
        try { localStorage.setItem(SIG_KEY, sig); } catch (e) {}
        sending = false;
      };
      if (useBeacon && navigator.sendBeacon) {
        // Content-Type を application/json にすると preflight が必要になり
        // sendBeacon では送れない。text/plain で送り、サーバ側で JSON.parse する。
        var ok = navigator.sendBeacon(PROGRESS_API, new Blob([body], { type: 'text/plain' }));
        if (ok) done(); else sending = false;
        return;
      }
      fetch(PROGRESS_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body,
        keepalive: true,
      }).then(function (res) {
        if (res.ok) done(); else sending = false;
      }).catch(function () { sending = false; });
    }).catch(function () { sending = false; });
  }

  // オフラインでも開けるように Service Worker を登録（通学中・電波の悪い所むけ）。
  //   実体は /sw.js（サイト直下）。読み込み済みのページと画像をキャッシュから返す。
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('../../sw.js', { scope: '../../' }).catch(function () {});
    });
  }

  // ログインが確定してから復元を試す（未ログインでは何もしない）。
  restoreFromServer();
  setTimeout(restoreFromServer, 2500);   // 認証が遅れて確定する場合の保険

  setInterval(tick, TICK_MS);
  setInterval(function () { send(false); }, SEND_MS);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') send(true);
    else lastTick = Date.now();   // 戻ってきた時点から数え直す
  });
  window.addEventListener('pagehide', function () { send(true); });
  // ログイン直後（体験開始・購入の往復から戻ったとき等）に、過去ぶんをまとめて送る
  setTimeout(function () { send(false); }, 4000);
})();
</script>
</body></html>"""


def generate(chapter: str, dest_root: Path) -> None:
    page, images = build(chapter)
    ch_no = chapter[:2]
    dest = dest_root / ch_no
    (dest / "img").mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(page, encoding="utf-8")
    for pair in sorted(set(images)):
        src, flat = pair.split("|", 1)
        dst = dest / "img" / flat
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    print(f"generated: {dest / 'index.html'}（画像{len(set(images))}枚）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", metavar="NN",
                    help="指定の章番号（例 04）を dist-web/ref/ へ出力")
    args = ap.parse_args()

    if args.deploy:
        matches = [p.stem for p in REF_DIR.glob(f"{args.deploy}-*.json")]
        if not matches:
            raise SystemExit(f"章 {args.deploy} が見つかりません")
        generate(matches[0], DEPLOY_DIR)
    else:
        for jp in sorted(REF_DIR.glob("*.json")):
            generate(jp.stem, OUT_DIR)
