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
  python -X utf8 generate_reference_web.py --deploy 04  # 指定の章を marutto-study の公開ディレクトリへ

デプロイ先: marutto-study/public/tsudumon/ref/{NN}/（chatstudy.jp/tsudumon/ref/{NN}/）
※ 現状は検証・サンプル用の限定公開（LP からリンクしない・noindex）。
   全巻の購入者向け公開はライセンスゲートの設計が決まってから。
"""
import argparse
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
# 秘密ではないが、ソースへ直書きしないよう SPA と同じ env（VITE_FIREBASE_*）から読む。
# 生成時に marutto-study/.env（gitignore 済み）を優先的に読み込む。
_FB_ENV = BASE.parent / "marutto-study" / ".env"


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
    env = {**_load_env_file(_FB_ENV), **os.environ}
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
            "marutto-study/.env に VITE_FIREBASE_API_KEY / _AUTH_DOMAIN / _PROJECT_ID / _APP_ID "
            "を設定してから再生成してください。"
        )
    return cfg
# Web埋め込み用のコンパクト版単元表紙（codex量産: gen_web_topic_covers.py）
WEB_COVER_DIR = BASE / "covers" / "out" / "webtopics"
DEPLOY_DIR = BASE.parent / "marutto-study" / "public" / "tsudumon" / "ref"

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


def ai_url(topic_key: str) -> str:
    return (f"https://liff.line.me/{LIFF_ID_UNITS}/ref"
            f"?t={urllib.parse.quote(topic_key)}")



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

    def char_web(name: str, cls: str):
        src = char_dir / name
        if not src.exists():
            return ""
        flat = "char_" + name
        images.append(str(src) + "|" + flat)
        return f'<img class="{cls}" src="img/{flat}" alt="">'

    navi_html = (char_web("char_owl_sm.png", "navi navi-char")
                 or '<div class="navi navi-emoji">🦉</div>')

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
  <a class="home-link" href="../../index.html">単元一覧にもどる</a>
  <header class="top hometop">
    <div class="ht-main">
      <div class="badge3"><span class="b-vol">{esc(spec['volume'])}</span><span class="b-kind">参考書</span><span class="b-web">Web版</span></div>
      <h1 class="ht-title">{esc(spec['title'])}</h1>
      <div class="sub">{esc(spec['subtitle'])}</div>
    </div>
    <div class="ht-mascot">{navi_html}<span class="ht-bubble">いっしょに<br>読もう！</span></div>
  </header>
  <button class="resume" id="resumeBtn" hidden>▶ つづきから読む<span id="resumeWhere"></span></button>
  <nav class="toc">
    <div class="toc-head"><div class="toc-h">この単元</div></div>
    {toc_items}
  </nav>
  {f'<a class="wb-home" href="../../wb/{ch_no}/index.html">✏️ 問題集Web版を開く（この本の問題を解く）</a>' if wb_index else ''}
  <footer class="foot">
    <div>つづもん 参考書 Web版</div>
    <div class="foot-note">紙やタブレットでじっくり派には、ダウンロード済みのPDF版もどうぞ。</div>
  </footer>
</section>"""]

    # ── 各単元（ステップに分割）──
    for i, t in enumerate(spec["topics"], 1):
        steps = []
        narr = Narration(ch_no, t["topicId"], tts_urls)
        narr.step = 0

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
      <img class="cover-img" src="img/{flat}"
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
                             f'<img src="{hero}" alt="" loading="lazy">{cap}</figure>')
            learn = t.get("learn") or [s["heading"] for s in t["sections"]]
            learn_html = "".join(
                f'<li><span class="ov-num">{n}</span><span>{rich(x)}</span></li>'
                for n, x in enumerate(learn, 1))
            cheer_char = char_web("manabi_banzai.png", "cheer-char")
            cheer_html = (f'<div class="cheer">{cheer_char}'
                          '<div class="cheer-bubble">この単元もがんばろう！</div></div>'
                          ) if cheer_char else ""
            steps.append(f"""
    <div class="step" data-label="この単元でわかること">
      {hook}
      {hero_html}
      <div class="overview">
        <div class="ov-h">🎯 この単元でわかること</div>
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
            body_html = narr.spans(s["body"])
            point = (f'<div class="point"><span class="ptag">⭐ ここだけ覚える</span>'
                     f'<div class="ptxt">{narr.spans(s["point"])}</div></div>'
                     if s.get("point") else "")
            side_items = []
            if s.get("aside"):
                side_items.append(f'<div class="tip">💡 {rich(s["aside"])}</div>')
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
      <p>{body_html}</p>
      {point}
      {side}
    </div>""")

        # step: 重要語チェック（フラッシュカード: タップで表裏。両面表示チェックで一覧）
        if t.get("terms"):
            # 表＝説明（これを読んで用語を当てる）／裏＝用語（答え）。
            # 「🔁 裏表入れ替え」で表裏を反転（用語→意味）もできる。
            cards = "".join(
                f"""<button class="tcard" type="button">
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
    </button>"""
                for x in t["terms"])
            steps.append(f"""
    <div class="step" data-label="重要語チェック">
      <div class="terms-h">📖 重要語チェック<span class="terms-sub">説明を読んで用語を言えるかな？</span></div>
      <div class="terms-tools"><div class="tt-btns"><button type="button" class="shuffle-btn">🔀 シャッフル</button><button type="button" class="swap-btn">🔁 裏表入れ替え</button></div><label class="both-toggle"><input type="checkbox" class="both-chk">両面表示</label></div>
      <div class="tgrid">{cards}</div>
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
        url = ai_url(f"{ch_no}-{t['topicId']}")
        wb_btn = ""
        if t["topicId"] in wb_index:
            wb_btn = (f'<a class="wb-btn" href="../../wb/{ch_no}/index.html#t{wb_index[t["topicId"]]}">'
                      f'<span class="ai-ico">✏️</span>'
                      f'<span class="ai-main">この単元の問題を解く<span class="ai-sub">'
                      f'Web問題集（要点穴埋め・一問一答・4択・記述）</span></span>'
                      f'<span class="ai-arrow">›</span></a>')
        steps.append(f"""
    <div class="step" data-label="30秒まとめ">
      {summary}
      <div class="done">🎉 この単元はこれで完了！</div>
      {wb_btn}
      <a class="ai-btn" href="{url}" target="_blank" rel="noopener">
        <span class="ai-ico">🤖</span>
        <span class="ai-main">AI先生に質問・理解度チェック<span class="ai-sub">LINEが開きます</span></span>
        <span class="ai-arrow">›</span>
      </a>
    </div>""")

        if narr.ok:
            audio[i] = {"url": narr.url, "tl": narr.timeline()}

        views.append(f"""
<section class="view" data-t="{i}">
  <div class="tband"><span class="tno">{i}</span><h2>{esc(t['name'])}</h2>
    <button class="play-unit" type="button" data-play="{i}" hidden>🔊 このページを読む</button></div>
  {''.join(steps)}
</section>""")

    tabs = '<button class="tab tab-home" data-go="0" aria-label="目次">🏠</button>' + "".join(
        f'<button class="tab" data-go="{i}" aria-label="{esc(t["name"])}">{i}</button>'
        for i, t in enumerate(spec["topics"], 1))

    # ページ内チャット用: 単元 t(1..N) → 参考書 topicKey（章番号-topicId）
    topic_keys_json = json.dumps(
        [f"{ch_no}-{t['topicId']}" for t in spec["topics"]], ensure_ascii=False)

    page = (TEMPLATE
            .replace("__TITLE__", f"{spec['volume']} {spec['title']}｜つづもん参考書")
            .replace("__HEADBAR__", f"{esc(spec['volume'])} {esc(spec['title'])}")
            .replace("__TABS__", tabs)
            .replace("__STORAGE_KEY__", f"tzmref-{ch_no}")
            .replace("__CH_NO__", ch_no)
            .replace("__AUDIO__", json.dumps(audio, ensure_ascii=False))
            .replace("__WB_VIEWS__", json.dumps(
                [0] + [wb_index.get(t["topicId"], 0) for t in spec["topics"]]))
            .replace("__TOPIC_KEYS__", topic_keys_json)
            .replace("__FIREBASE_WEB_CONFIG__", json.dumps(firebase_web_config()))
            .replace("__VIEWS__", "".join(views)))
    return page, images


TEMPLATE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>__TITLE__</title>
<style>
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --cream:#fffdf8; --line:#fde68a; }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         font-size:16px; line-height:1.95; color:#1c1917; background:var(--cream);
         padding-bottom:86px; }
  .wrap { max-width:640px; margin:0 auto; padding:0 16px 24px; }

  .mark { background:linear-gradient(transparent 55%, var(--line) 55%); font-weight:bold; padding:0 1px; }

  /* ── 読み上げ（音声＋読んでいる句のハイライト）── */
  .s { border-radius:6px; padding:.14em .12em; margin:0 -.12em;
       -webkit-box-decoration-break:clone; box-decoration-break:clone;
       transition:background-color .15s ease, color .15s ease; }
  body.reading .s { cursor:pointer; }
  .s.read { color:#8a8279; }
  .s.now { background:#fcd34d; color:#1c1917; }
  .s.now .mark { background:none; }
  /* 単元見出しの再生ボタン */
  .play-unit { display:inline-flex; align-items:center; gap:6px; margin-left:auto; flex:none;
               background:#fff; color:var(--brand); border:1.5px solid var(--line);
               border-radius:20px; padding:4px 12px; font-size:12px; font-weight:bold;
               font-family:inherit; cursor:pointer; }
  .play-unit[hidden] { display:none; }
  /* 下部プレーヤー（再生中だけ出す。ナビバーの上に重ねる） */
  .aplayer { position:fixed; left:0; right:0; bottom:58px; z-index:25;
             background:rgba(255,253,248,.98); border-top:1px solid #f0e6d2;
             box-shadow:0 -3px 12px rgba(120,80,20,.14); padding:7px 0 8px; }
  .aplayer[hidden] { display:none; }
  .ap-in { max-width:640px; margin:0 auto; padding:0 14px; display:flex; align-items:center; gap:9px; }
  .ap-btn { flex:none; width:40px; height:40px; border-radius:50%; border:none; background:var(--brand);
            color:#fff; font-size:16px; cursor:pointer; box-shadow:0 2px 6px rgba(180,83,9,.35); }
  .ap-seek { flex:1; min-width:0; }
  .ap-seek input { width:100%; accent-color:var(--brand); }
  .ap-time { flex:none; font-size:11px; font-weight:bold; color:var(--brand); min-width:74px;
             text-align:right; }
  .ap-rate, .ap-close { flex:none; border:1.5px solid var(--line); background:#fffbeb; color:var(--brand);
             font-weight:bold; border-radius:16px; padding:4px 9px; font-size:11.5px; cursor:pointer;
             font-family:inherit; }

  /* ── 上部: タイトル＋単元タブ＋進捗バー ── */
  .bar { position:sticky; top:0; z-index:10; background:rgba(255,253,248,.96);
         backdrop-filter:blur(6px); border-bottom:1px solid #f0e6d2; }
  .bar-in { max-width:640px; margin:0 auto; padding:5px 12px 0; }
  .bar-row { display:flex; align-items:center; gap:8px; }
  /* 参考書⇄問題集の切替（どのページからでも1タップ・相手側は読みかけの位置に着地） */
  /* どのページからでも「本の一覧（すごろく）」へ戻れる常設ボタン。
     タブ列の 🏠 は「この本の目次」なので、こちらは 🗺＋文字でトップだと分かるようにする。 */
  .tophome { flex:none; height:30px; padding:0 12px; font-size:11.5px; font-weight:bold;
             color:#fff; background:var(--deep); border-radius:15px; text-decoration:none;
             display:inline-flex; align-items:center; white-space:nowrap;
             box-shadow:0 2px 0 #5b1e0b; }
  .swap { flex:none; display:inline-flex; border:1.5px solid var(--line); border-radius:20px;
          overflow:hidden; background:#fffbeb; }
  .sw { font-size:11px; font-weight:bold; color:var(--brand); padding:3px 7px; text-decoration:none;
        white-space:nowrap; cursor:pointer; }
  .sw.on { background:var(--brand); color:#fff; }
  .sw[hidden] { display:none; }
  .bar-title { font-weight:bold; color:var(--deep); font-size:14px; flex:1;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bar-step { flex:none; font-size:11px; font-weight:bold; color:var(--brand); }
  /* 初回だけ出す操作ヒント（PCはキー、スマホはスワイプ） */
  .hintbar { position:fixed; left:50%; transform:translateX(-50%); bottom:132px; z-index:35;
             background:rgba(28,25,23,.88); color:#fff; font-size:12.5px; font-weight:bold;
             border-radius:20px; padding:8px 16px; box-shadow:0 4px 14px rgba(0,0,0,.3);
             animation:hintIn .3s ease; }
  .hintbar[hidden] { display:none; }
  @keyframes hintIn { from { opacity:0; transform:translate(-50%,10px); }
                      to { opacity:1; transform:translate(-50%,0); } }
  .tabs-wrap { position:relative; flex:1; min-width:0; }
  /* 端のフェード＋矢印＝「まだ右に単元がある」と一目で分かるようにする */
  .tscroll { position:absolute; top:0; bottom:0; width:20px; border:none; cursor:pointer;
             font-size:17px; font-weight:bold; color:var(--brand); line-height:1; padding:0;
             display:flex; align-items:center; justify-content:center; font-family:inherit; }
  .tscroll[hidden] { display:none; }
  .tsl { left:0; background:linear-gradient(to right, #fffdf8 62%, rgba(255,253,248,0)); }
  .tsr { right:0; background:linear-gradient(to left, #fffdf8 62%, rgba(255,253,248,0)); }
  .tabs { display:flex; gap:5px; overflow-x:auto; padding:4px 0; width:100%;
          scrollbar-width:none; -webkit-overflow-scrolling:touch; }
  .tabs::-webkit-scrollbar { display:none; }
  .tab { flex:none; width:30px; height:30px; border-radius:50%; border:1.5px solid var(--line);
         background:#fffbeb; color:var(--brand); font-size:15px; font-weight:bold;
         display:inline-flex; align-items:center; justify-content:center; cursor:pointer; }
  .tab.done { background:#fef3c7; }
  .tab.done::after { content:""; }
  .tab.on { background:var(--brand); border-color:var(--brand); color:#fff;
            box-shadow:0 2px 6px rgba(180,83,9,.35); }
  .pbar { height:3px; background:#f5ecd8; border-radius:2px; overflow:hidden; margin:0 0 0; }
  .pfill { height:100%; width:0; background:linear-gradient(90deg,var(--amber),#fbbf24);
           border-radius:2px; transition:width .25s ease; }

  /* ── ビュー / ステップ ── */
  .view { display:none; }
  .view.on { display:block; position:relative; animation:vfade .18s ease; }
  @keyframes vfade { from { opacity:.6; } to { opacity:1; } }
  .step { display:none; }
  .step.on { display:block; }
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
  .hometop { display:flex; align-items:flex-start; gap:6px; padding:16px 2px 2px; text-align:left; }
  .ht-main { flex:1; min-width:0; }
  .badge3 { display:inline-flex; border-radius:18px; overflow:hidden; font-size:12px; font-weight:bold;
            box-shadow:0 2px 4px rgba(120,80,20,.2); }
  .badge3 span { padding:4px 11px; display:inline-flex; align-items:center; white-space:nowrap; }
  .b-vol { background:var(--brand); color:#fff; }
  .b-kind { background:#fff; color:var(--deep); }
  .b-web { background:var(--amber); color:#fff; }
  .ht-title { font-size:33px; color:var(--deep); margin:12px 0 0; line-height:1.15; position:relative;
              display:inline-block; padding:0 6px; }
  .ht-title::before { content:"✨"; position:absolute; left:-20px; top:0; font-size:16px; }
  .ht-title::after { content:"✨"; position:absolute; right:-18px; bottom:2px; font-size:13px; }
  .ht-mascot { flex:none; position:relative; width:100px; padding-top:22px; text-align:center; }
  .ht-mascot img { height:74px; width:auto; }
  .ht-bubble { position:absolute; top:0; left:50%; transform:translateX(-50%); white-space:nowrap;
               background:#fff; border:2px solid var(--amber); border-radius:12px; padding:4px 10px;
               font-size:11px; font-weight:bold; color:var(--deep); line-height:1.25; text-align:center;
               box-shadow:0 2px 4px rgba(0,0,0,.1); }
  .ht-bubble::after { content:""; position:absolute; bottom:-8px; left:50%; transform:translateX(-50%);
                      border:5px solid transparent; border-top-color:var(--amber); }
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
  .sum30-bubble { position:relative; background:#fff; border:1.5px solid var(--amber); border-radius:12px;
                  padding:6px 12px; font-size:12.5px; font-weight:bold; color:var(--deep); }
  .sum30-bubble::after { content:""; position:absolute; right:-11px; top:50%; transform:translateY(-50%);
                         border:6px solid transparent; border-left-color:var(--amber); }
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
  .toc-h::before { content:"📖"; display:inline-flex; align-items:center; justify-content:center;
                   width:30px; height:30px; border-radius:50%; background:var(--brand); font-size:15px; }
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
  .toc-state.doing { color:var(--brand); background:#fffbeb; border:1px solid var(--line);
                     border-radius:10px; padding:1px 8px; }

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
  .cover-art figcaption { font-size:12px; color:#a8a29e; text-align:center; margin-top:6px; }

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
  .hero figcaption { font-size:12px; color:#a8a29e; text-align:center; margin-top:4px; }

  /* 節 */
  .step h3 { font-size:18px; color:var(--deep); display:flex; align-items:center; gap:8px; line-height:1.5; }
  .sec-no { flex:none; width:22px; height:22px; border-radius:50%; background:#fff;
            border:1.5px solid var(--line); color:var(--brand); font-weight:bold;
            display:inline-flex; align-items:center; justify-content:center; font-size:12px; }
  .sec-lead { font-size:13px; color:var(--brand); font-weight:bold; margin:2px 0 4px 30px; }
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
  .w-rd { font-weight:normal; font-size:11px; color:#b8b0a6; margin-left:4px; }
  .w-desc { color:#57534e; }

  /* 重要語チェック */
  .terms-h { font-size:18px; font-weight:bold; color:var(--deep); }
  .terms-sub { font-size:12px; font-weight:normal; color:#a8a29e; margin-left:8px; }
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
  .tgrid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  /* シャッフル時のふわっと再配置アニメ */
  .tgrid.shuffling .tcard { animation:tshuffle .34s ease; }
  @keyframes tshuffle { 0% { opacity:.25; transform:scale(.92); }
                        100% { opacity:1; transform:none; } }
  @media (max-width:400px) { .tgrid { grid-template-columns:1fr; } }
  /* フラッシュカード（タップで表裏。両面表示チェックで従来の一覧に）
     ─ めくりモード: 全カード同じ高さ（150px）・面は絶対配置で重ねて3D回転
     ─ 両面モード: 3Dを使わず通常フローで表＋裏を縦に並べる（崩れ防止） */
  .tcard { position:relative; height:150px; background:none; border:none; padding:0;
           cursor:pointer; font-family:inherit; text-align:left; perspective:800px; }
  .tcard-inner { display:block; position:absolute; inset:0; transition:transform .35s;
                 transform-style:preserve-3d; }
  .tc-face { position:absolute; inset:0; display:flex; flex-direction:column;
             align-items:center; justify-content:center; text-align:center; overflow:hidden;
             backface-visibility:hidden; -webkit-backface-visibility:hidden;
             border:1.5px solid var(--line); border-radius:10px; padding:10px; background:#fff; }
  /* 表＝説明（読んで用語を当てる） */
  .tc-front { background:#fffbeb; overflow-y:auto; }
  .tc-desc { font-size:13px; color:#44403c; line-height:1.6; font-weight:500; }
  /* 裏＝用語（こたえ） */
  .tc-back { transform:rotateY(180deg); }
  .tc-term { font-weight:bold; font-size:17px; color:var(--deep); line-height:1.5; }
  .tc-rd { display:block; font-weight:normal; font-size:11px; color:#b8b0a6; margin-top:2px; }
  .tc-tap { font-size:10px; color:#d6c9a8; margin-top:6px; }
  .tcard.flipped .tcard-inner { transform:rotateY(180deg); }
  /* 裏表入れ替え: 用語を先に見せる（意味→用語 ⇄ 用語→意味） */
  .tgrid.term-first .tcard-inner { transform:rotateY(180deg); }
  .tgrid.term-first .tcard.flipped .tcard-inner { transform:rotateY(0deg); }
  /* 両面表示モード（用語→説明の順に縦並べ） */
  .tgrid.both .tcard { cursor:default; height:auto; perspective:none; }
  .tgrid.both .tcard-inner { position:static; transform:none !important; transform-style:flat;
                             display:flex; flex-direction:column; }
  .tgrid.both .tc-face { position:static; overflow:visible; align-items:flex-start; text-align:left;
                         backface-visibility:visible; -webkit-backface-visibility:visible; }
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
  .ai-btn { display:flex; align-items:center; gap:12px; text-decoration:none;
            background:#06c755; color:#fff; border-radius:14px; padding:13px 16px;
            box-shadow:0 3px 8px rgba(6,199,85,.3); }
  .ai-ico { font-size:24px; flex:none; }
  .ai-main { flex:1; font-weight:bold; font-size:15px; line-height:1.5; }
  .ai-sub { display:block; font-weight:normal; font-size:12px; opacity:.9; }
  .ai-arrow { font-size:22px; opacity:.8; }

  .foot { text-align:center; margin-top:36px; color:#a8a29e; font-size:13px; }
  .foot-note { margin-top:4px; font-size:12px; }

  /* ── 下部ナビ ── */
  .navbar { position:fixed; left:0; right:0; bottom:0; z-index:10;
            background:rgba(255,253,248,.97); border-top:1px solid #f0e6d2;
            padding:10px 16px calc(10px + env(safe-area-inset-bottom)); }
  .navbar-in { max-width:640px; margin:0 auto; display:flex; align-items:center; gap:10px; }
  .nb { border:none; border-radius:14px; padding:12px 0; font-size:15px; font-weight:bold;
        cursor:pointer; font-family:inherit; }
  .nb-prev { flex:1; background:#fff; color:var(--brand); border:1.5px solid var(--line); }
  .nb-next { flex:2; background:var(--brand); color:#fff; box-shadow:0 3px 8px rgba(180,83,9,.3); }
  .nav-label { position:absolute; left:-9999px; }

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

  /* ── ページ内チャット（スタ先生）── */
  .chat-fab { position:fixed; right:14px; bottom:calc(84px + env(safe-area-inset-bottom));
              z-index:20; width:56px; height:56px; border-radius:50%;
              border:none; background:var(--brand); color:#fff; font-size:26px;
              cursor:pointer; box-shadow:0 4px 12px rgba(180,83,9,.4); }
  .chat-fab.hidden { display:none; }
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
  .chat-msg.sys { align-self:center; background:none; color:#a8a29e; font-size:11.5px;
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
  .chat-foot { font-size:10.5px; color:#a8a29e; text-align:center; padding:4px 8px 7px;
               background:#fff; }
  /* display:flex 指定が UA の [hidden]{display:none} に勝ってしまうのを防ぐ */
  .chat-panel[hidden], .chat-input[hidden], .chat-login[hidden] { display:none; }
</style></head><body>
<div class="bar"><div class="bar-in">
  <div class="bar-row">
    <a class="tophome" href="../../index.html" aria-label="単元一覧へもどる">単元一覧</a>
    <div class="swap"><span class="sw on">📖 参考書</span><a class="sw" id="swWb">✏️ 問題</a></div>
    <div class="tabs-wrap">
      <nav class="tabs" id="tabs">__TABS__</nav>
      <button class="tscroll tsl" id="tabsL" type="button" hidden aria-label="単元タブを左へ">‹</button>
      <button class="tscroll tsr" id="tabsR" type="button" hidden aria-label="単元タブを右へ">›</button>
    </div>
    <div class="bar-step" id="barStep"></div>
  </div>
  <div class="bar-title" hidden>__HEADBAR__</div>
  <div class="pbar"><div class="pfill" id="pfill"></div></div>
</div></div>
<main class="wrap" id="views">
__VIEWS__
</main>
<div class="hintbar" id="hintBar" hidden></div>
<div class="aplayer" id="aplayer" hidden><div class="ap-in">
  <button class="ap-btn" id="apPlay" aria-label="再生／一時停止">❚❚</button>
  <div class="ap-seek"><input type="range" id="apSeek" min="0" max="1000" value="0"></div>
  <div class="ap-time" id="apTime">0:00 / 0:00</div>
  <button class="ap-rate" id="apRate">1.0×</button>
  <button class="ap-close" id="apClose" aria-label="読み上げを止める">×</button>
</div></div>
<audio id="audio" preload="none"></audio>
<div class="navbar" id="navbar" hidden><div class="navbar-in">
  <button class="nb nb-prev" id="btnPrev">← まえへ</button>
  <button class="nb nb-next" id="btnNext">つぎへ →</button>
</div></div>
<button class="chat-fab" id="chatFab" aria-label="スタ先生に質問する">🤖</button>
<section class="chat-panel" id="chatPanel" hidden>
  <header class="chat-head">
    <span class="chat-title">🤖 スタ先生に質問</span>
    <span class="chat-topic" id="chatTopic"></span>
    <button class="chat-close" id="chatClose" aria-label="閉じる">×</button>
  </header>
  <div class="chat-note">公式LINEと同じAI。会話はLINEのトークとつながるよ。</div>
  <div class="chat-body" id="chatBody"></div>
  <div class="chat-login" id="chatLogin" hidden>
    <p>LINEログインすると、このページでスタ先生に質問できるよ。<br>会話のつづきは公式LINEでも話せる！</p>
    <a class="chat-login-btn" id="chatLoginBtn" href="/welcome">LINEでログイン</a>
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
  var WB_VIEWS = __WB_VIEWS__;
  var AUDIO = __AUDIO__;          // {単元t: {url, tl:[[開始秒,長さ,ステップ], …]}}          // 参考書の単元t → 問題集のビュー番号（0＝対応なし）
  var views = [].slice.call(document.querySelectorAll('.view'));
  var tabs = [].slice.call(document.querySelectorAll('.tab'));
  var N = views.length - 1; // 単元数
  var state = { t: 0, s: 0 };
  var lastDir = 1;
  var rendered = null; // 直前に表示していた {t, s}（ページめくり演出用）

  // ── 操作ヒント（初回のみ）＋タブ列のホイール操作 ──
  (function () {
    var el = document.getElementById('tabs');
    if (el) el.addEventListener('wheel', function (e) {
      // PC でも横スクロールできるよう、縦ホイールを横移動に変換する
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) { el.scrollLeft += e.deltaY; e.preventDefault(); }
    }, { passive: false });

    var bar = document.getElementById('hintBar');
    if (!bar) return;
    try { if (localStorage.getItem('tzmhint') === '1') return; } catch (e) { return; }
    var canHover = window.matchMedia && window.matchMedia('(hover:hover)').matches;
    bar.textContent = canHover ? '⌨️ ← → キーでもページをめくれるよ'
                               : '👆 よこにスワイプでもページをめくれるよ';
    var shown = false;
    window.showHint = function () {
      if (shown || state.t === 0) return;
      shown = true; bar.hidden = false;
      try { localStorage.setItem('tzmhint', '1'); } catch (e) {}
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

  // いま開いているページを読み上げる。fromChunk を渡すとその句から。
  function playStep(t, step, fromChunk) {
    var r = stepRange(t, step);
    if (!r) return;                       // 音声のないページ（重要語チェック等）
    var a = AUDIO[t];
    var at = (fromChunk != null && a.tl[fromChunk]) ? a.tl[fromChunk][0] : r.s0;
    reading = { t: t, step: step, i0: r.i0, i1: r.i1, s0: r.s0, s1: r.s1, i: -1 };
    document.body.classList.add('reading');
    apl.hidden = false;
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
    apl.hidden = true;
    if (reading.t) spansOf(reading.t).forEach(function (el) { el.classList.remove('now', 'read'); });
    reading = { t: 0, step: null, i0: 0, i1: -1, s0: 0, s1: 0, i: -1 };
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
    // ページの終わりまで来たら、そのページで停止（次ページには進まない）
    if (reading.step != null && au.currentTime >= reading.s1 - 0.02) {
      au.pause();
      var sp = spansOf(reading.t);
      sp.forEach(function (el, i) {
        el.classList.remove('now');
        el.classList.toggle('read', i >= reading.i0 && i <= reading.i1);
      });
      updateBar(true);
      return;
    }
    paintAudio();
    updateBar(false);
    if (!au.paused) requestAnimationFrame(tickAudio);
  }
  au.addEventListener('play', function () { document.getElementById('apPlay').textContent = '❚❚'; tickAudio(); });
  au.addEventListener('pause', function () { document.getElementById('apPlay').textContent = '▶'; });
  document.getElementById('apPlay').onclick = function () {
    if (reading.step == null) return;
    if (au.paused) {
      if (au.currentTime >= reading.s1 - 0.05) au.currentTime = reading.s0;  // 読み終わっていたら頭から
      au.play();
    } else au.pause();
  };
  document.getElementById('apClose').onclick = stopAudio;
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

  // 単元タブの左右矢印: まだ隠れているタブがある側だけ出す
  function updateTabArrows() {
    var el = document.getElementById('tabs');
    var L = document.getElementById('tabsL'), R = document.getElementById('tabsR');
    if (!el || !L || !R) return;
    var max = el.scrollWidth - el.clientWidth;
    L.hidden = el.scrollLeft <= 2;
    R.hidden = el.scrollLeft >= max - 2;
  }
  (function () {
    var el = document.getElementById('tabs');
    var L = document.getElementById('tabsL'), R = document.getElementById('tabsR');
    if (!el || !L || !R) return;
    function by(d) { el.scrollBy({ left: d * Math.max(80, el.clientWidth * 0.7), behavior: 'smooth' }); }
    L.addEventListener('click', function (e) { e.stopPropagation(); by(-1); });
    R.addEventListener('click', function (e) { e.stopPropagation(); by(1); });
    el.addEventListener('scroll', updateTabArrows, { passive: true });
    window.addEventListener('resize', updateTabArrows);
    setTimeout(updateTabArrows, 0);
  })();

  function store() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
  }
  function save(obj) {
    try { localStorage.setItem(KEY, JSON.stringify(obj)); } catch (e) {}
  }
  function stepsOf(t) { return views[t].querySelectorAll('.step'); }

  function render() {
    var t = state.t, s = state.s;
    views.forEach(function (v, i) { v.classList.toggle('on', i === t); });
    tabs.forEach(function (b) {
      var bt = +b.dataset.go;
      b.classList.toggle('on', bt === t);
      b.classList.toggle('done', bt > 0 && store()['d' + bt] === 1);
    });
    var tabEl = tabs[t];
    if (tabEl && tabEl.scrollIntoView) {
      tabEl.scrollIntoView({ block: 'nearest', inline: 'center' });
    }
    updateTabArrows();
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
      [].forEach.call(steps, function (el, i) {
        el.classList.remove('turn-out', 'turn-in', 'turn-under');
        el.classList.toggle('on', i === s);
      });
      if (animFrom !== null && steps[animFrom] && steps[s]) {
        var oldEl = steps[animFrom], newEl = steps[s];
        var clear = function () {
          oldEl.classList.remove('turn-out', 'turn-under');
          newEl.classList.remove('turn-in');
        };
        if (lastDir > 0) {
          oldEl.classList.add('turn-out');      // 今のページがめくれて去る
          oldEl.addEventListener('animationend', clear, { once: true });
        } else {
          oldEl.classList.add('turn-under');    // 下に敷いたまま
          newEl.classList.add('turn-in');       // 前のページがめくり戻ってくる
          newEl.addEventListener('animationend', clear, { once: true });
        }
        setTimeout(clear, 700); // アニメ未発火時の保険
      }
      navbar.hidden = false;
      barStep.textContent = (s + 1) + ' / ' + steps.length;
      pfill.style.width = (((s + 1) / steps.length) * 100) + '%';
      var prev = document.getElementById('btnPrev');
      var next = document.getElementById('btnNext');
      prev.textContent = s === 0 ? '🏠 目次' : '← まえへ';
      if (s < steps.length - 1) {
        next.textContent = 'つぎへ →';
      } else {
        next.textContent = t < N ? '次の単元へ →' : '🏠 目次にもどる';
      }
      // 進捗保存
      var st = store();
      st.last = { t: t, s: s };
      if (s === steps.length - 1) st['d' + t] = 1;
      save(st);
    }
    window.scrollTo(0, 0);
    var h = '#t' + t + (t > 0 && s > 0 ? 's' + s : '');
    // クエリが付いていても落とさない（URL共有時の情報を保つ）
    if (location.hash !== h) history.replaceState(null, '', location.search + (t === 0 ? '#' : h));
    updateSwap();
    var pb = views[t] && views[t].querySelector('.play-unit');
    if (pb) pb.hidden = !stepRange(t, s);
    rendered = { t: t, s: s };
  }

  function renderHome() {
    var st = store();
    [].forEach.call(document.querySelectorAll('.toc-state'), function (el) {
      var t = +el.dataset.stateT;
      el.className = 'toc-state';
      if (st['d' + t] === 1) { el.classList.add('done'); el.textContent = '✓︎ 読んだ'; }
      else if (st.last && st.last.t === t && st.last.s > 0) {
        el.classList.add('doing'); el.textContent = 'つづき';
      } else { el.textContent = ''; }
    });
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

  function go(t, s, dir) {
    if (typeof reading !== 'undefined' && reading.step != null) stopAudio();
    lastDir = dir || 1;
    state.t = Math.max(0, Math.min(N, t));
    state.s = Math.max(0, s || 0);
    if (state.t > 0) {
      state.s = Math.min(state.s, stepsOf(state.t).length - 1);
    } else {
      state.s = 0;
    }
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

  document.getElementById('btnNext').addEventListener('click', next);
  document.getElementById('btnPrev').addEventListener('click', prev);
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-go]');
    if (b) { go(+b.dataset.go, 0, 1); return; }
    // 重要語チェックのシャッフル: カードの並びをランダムに入れ替える
    var sh = e.target.closest('.shuffle-btn');
    if (sh) {
      var grid = sh.closest('.step').querySelector('.tgrid');
      if (grid) {
        var cards = [].slice.call(grid.querySelectorAll('.tcard'));
        for (var i = cards.length - 1; i > 0; i--) {
          var j = Math.floor(Math.random() * (i + 1));
          var tmp = cards[i]; cards[i] = cards[j]; cards[j] = tmp;
        }
        cards.forEach(function (c) { c.classList.remove('flipped'); grid.appendChild(c); });
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
    // 重要語カード: タップで表裏（両面表示中はめくらない）
    var card = e.target.closest('.tcard');
    if (card && !card.closest('.tgrid').classList.contains('both')) {
      card.classList.toggle('flipped');
    }
  });

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
      [].forEach.call(g.querySelectorAll('.tcard.flipped'), function (c) { c.classList.remove('flipped'); });
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
    var dx = e.changedTouches[0].clientX - tx;
    var dy = e.changedTouches[0].clientY - ty;
    if (Math.abs(dx) > 64 && Math.abs(dy) < 48 && state.t > 0) {
      if (dx < 0) next(); else prev();
    }
  }, { passive: true });

  // キーボード操作（PC）: ←→ でページ送り、PageUp/Down も同じ、Home で目次へ
  document.addEventListener('keydown', function (e) {
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
  window.addEventListener('hashchange', fromHash);
  fromHash();
})();
</script>
<script type="module">
// ── ページ内チャット（スタ先生）──
// 公式LINEの参考書AI（ref_ask）と知識・会話履歴・1日回数枠を共有する。
// 認証は www.chatstudy.jp の LINE Login（Firebase Auth）。marutto-study の
// SPA と同じ localStorage 永続化なので、一度 /welcome でログインすれば共有される。
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
    '/welcome?next=' + encodeURIComponent(location.pathname + location.hash);
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
  var waiting = msg('sys', 'スタ先生が考え中…');
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

onAuthStateChanged(auth, function (u) {
  user = u;
  if (panel.hidden) return;
  if (!u) { showLogin(); return; }
  loadHistory();
});
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
                    help="指定の章番号（例 04）を marutto-study/public/tsudumon/ref/ へ出力")
    args = ap.parse_args()

    if args.deploy:
        matches = [p.stem for p in REF_DIR.glob(f"{args.deploy}-*.json")]
        if not matches:
            raise SystemExit(f"章 {args.deploy} が見つかりません")
        generate(matches[0], DEPLOY_DIR)
    else:
        for jp in sorted(REF_DIR.glob("*.json")):
            generate(jp.stem, OUT_DIR)
