# -*- coding: utf-8 -*-
"""
問題集に対応した「読んで楽しい」参考書を印刷用 A4 HTML に生成する。

歴史ぎらいの中学生でも読めるよう、文字を詰め込まず:
- 各トピックの冒頭に大きなヒーローイラスト（assets/reference/、Codex生成）
- ナビキャラ「ヒストリー先生」が吹き出しで語りかける（hook・まとめ）
- 重要語は蛍光ペン風マーカー、要点は付箋風、用語は絵カードのグリッド
- 節ごとに絵文字アイコン・カラーブロックで視覚的リズムをつける

データ: reference/{章}.json（hook / sections[{heading,icon?,body,point}] / terms / summary）
使い方: python -X utf8 generate_reference_book.py → output/ref-{章}.html → Edge で PDF 化。
"""
import base64
import html
import io
import json
import re
import urllib.parse
from pathlib import Path

try:
    import segno
except ImportError:
    segno = None

BASE = Path(__file__).parent
REF_DIR = BASE / "reference"
OUT_DIR = BASE / "output"
ASSET_DIR = BASE / "assets" / "reference"

# 参考書QR→公式LINEのAI先生（units の LIFF にパス /ref を連結）。
# QRを読むと LIFF が開き、その単元について「質問」か「理解度チェック」を選んで
# LINE上でAIと学習できる（webhook 側で t=章番号-topicId を受け取る）。
LIFF_ID_UNITS = "2009587166-LjyCza2c"

BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")

# 節見出しに付ける絵文字を順番に回す（データで section.icon 指定があればそれ優先）
SECTION_ICONS = ["📌", "⚔️", "🏯", "📜", "🎌", "👑", "🔍", "💡"]


def esc(s: str) -> str:
    return html.escape(s)


def rich(s: str) -> str:
    """**太字** を蛍光ペン風マーカーに変換。"""
    out, pos = [], 0
    for m in BOLD_RE.finditer(s):
        out.append(esc(s[pos:m.start()]))
        out.append(f'<span class="mark">{esc(m.group(1))}</span>')
        pos = m.end()
    out.append(esc(s[pos:]))
    return "".join(out)


def img_uri(name: str):
    p = ASSET_DIR / name
    return p.as_uri() if (name and p.exists()) else None


# 用語カードの絵文字（見た目のにぎやかさ用。意味に厳密でなくてよい）
def term_emoji(i: int) -> str:
    pool = ["📖", "🏛️", "👤", "🗺️", "⚖️", "🌸", "🏯", "📿", "🎋", "🗾", "👑", "📜"]
    return pool[i % len(pool)]


def build_ref_qr(topic_key: str) -> str:
    """この単元をLINEのAI先生と深めるQRボックス。
    QRを読むと LIFF /ref が開き、質問／理解度チェックを選んでAIと学習できる。"""
    if segno is None:
        return ""
    qr_url = (f"https://liff.line.me/{LIFF_ID_UNITS}/ref"
              f"?t={urllib.parse.quote(topic_key)}")
    buf = io.BytesIO()
    segno.make(qr_url, error="m").save(buf, kind="png", scale=6, border=2)
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return f"""
  <div class="ai-box">
    <a href="{qr_url}" target="_blank" rel="noopener"><img class="ai-qr" src="data:image/png;base64,{qr_b64}"></a>
    <div class="ai-text">
      <div class="ai-title">🤖 AI先生といっしょに、この単元を深めよう！</div>
      <div class="ai-menu">
        <span class="ai-chip">❓ わからないことを質問する</span>
        <span class="ai-chip">✅ 理解度チェックを受ける（やさしい / ふつう / むずかしい）</span>
      </div>
      <div class="ai-link">スマホでQRを読むか、PDFではこちら → <a href="{qr_url}" target="_blank" rel="noopener">LINEでAI先生に相談する</a></div>
    </div>
  </div>"""


def build(chapter: str) -> str:
    spec = json.loads((REF_DIR / f"{chapter}.json").read_text(encoding="utf-8"))
    ch_no = chapter[:2]  # "04-ancient-state" → "04"（QRの単元キー用）
    navi = img_uri("navi-teacher.webp")  # ナビキャラ（無ければ絵文字で代替）

    def navi_face(size_mm):
        if navi:
            return f'<img class="navi" style="width:{size_mm}mm;height:{size_mm}mm" src="{navi}">'
        return f'<div class="navi navi-emoji" style="width:{size_mm}mm;height:{size_mm}mm;font-size:{size_mm*0.6}mm">🦉</div>'

    body = [f"""
<header class="cover">
  <div class="cover-badge">{esc(spec['volume'])}　参考書</div>
  <h1>{esc(spec['title'])}</h1>
  <div class="cover-sub">{esc(spec['subtitle'])}</div>
  <div class="cover-navi">{navi_face(22)}
    <div class="cover-bubble">こんにちは！先生といっしょに、楽しく歴史を見ていこう！</div>
  </div>
</header>"""]

    for i, t in enumerate(spec["topics"], 1):
        hero = img_uri(t.get("image", ""))
        # ヒーロー画像はトピック冒頭の右側に小さめに回り込ませる（「わかること」と並ぶ）
        hero_html = (
            f'<figure class="hero-fig"><img src="{hero}">'
            + (f'<figcaption>{esc(t.get("imageCaption",""))}</figcaption>' if t.get("imageCaption") else "")
            + "</figure>"
        ) if hero else ""

        # 「この単元でわかること」— データにあれば使い、無ければ各section見出しから自動生成
        learn = t.get("learn") or [s["heading"] for s in t["sections"]]
        learn_html = "".join(
            f'<li><span class="ov-num">{n}</span><span class="ov-txt">{rich(x)}</span></li>'
            for n, x in enumerate(learn, 1))
        overview = f"""
  <div class="overview">
    <div class="ov-main">
      <div class="ov-h"><span class="ov-ico">🎯</span>この単元でわかること</div>
      <ul class="ov-list">{learn_html}</ul>
    </div>
    {hero_html}
  </div>"""

        secs = []
        used_terms = set()  # 補足欄に一度出した用語は繰り返さない
        for si, s in enumerate(t["sections"]):
            lead = (f'<span class="sec-lead">{esc(s["lead"])}</span>'
                    if s.get("lead") else "")
            # ここだけ覚える: 本文の下に戻す（短め）
            point = (f'<div class="point"><span class="ptag">⭐ ここだけ覚える</span>'
                     f'<span class="ptxt">{rich(s["point"])}</span></div>') \
                if s.get("point") else ""
            # 右の補足欄: この節の本文に出てくる用語の意味＋任意のポイント補足
            side_items = []
            if s.get("aside"):
                side_items.append(f'<div class="side-note side-tip">💡 {rich(s["aside"])}</div>')
            for x in t.get("terms", []):
                if x["term"] in used_terms:
                    continue
                if x["term"] in s["body"]:
                    used_terms.add(x["term"])
                    side_items.append(
                        f'<div class="side-note"><div class="side-term">{esc(x["term"])}</div>'
                        f'<div class="side-desc">{esc(x["desc"])}</div></div>')
            side = "".join(side_items)
            secs.append(f"""
    <section class="sec">
      <h3><span class="sec-no">{si + 1}</span>{esc(s['heading'])}{lead}</h3>
      <div class="sec-row">
        <div class="sec-main"><p>{rich(s['body'])}</p>{point}</div>
        <aside class="sec-side">{side}</aside>
      </div>
    </section>""")

        terms = ""
        if t.get("terms"):
            cards = "".join(
                f"""<div class="tcard">
      <div class="tc-head"><span class="tc-emoji">{term_emoji(k)}</span>
        <span class="tc-term">{esc(x['term'])}
          <span class="tc-rd">{esc(x.get('reading',''))}</span></span></div>
      <div class="tc-desc">{esc(x['desc'])}</div>
    </div>"""
                for k, x in enumerate(t["terms"]))
            terms = f"""
    <div class="terms">
      <div class="terms-h">📖 重要語チェック<span class="sub">大切な言葉をおさえよう！</span></div>
      <div class="tgrid">{cards}</div>
    </div>"""

        # 30秒まとめ（データにあれば summary30、無ければ summary を流用）
        s30 = t.get("summary30") or t.get("summary")
        summary = f"""
  <div class="sum30">
    <div class="sum30-h"><span class="sum30-ico">⏱</span>30秒まとめ<span class="sum30-tag">テスト前にここだけ！</span></div>
    <div class="sum30-body">{rich(s30)}</div>
  </div>""" if s30 else ""

        ai_qr = build_ref_qr(f"{ch_no}-{t['topicId']}")

        body.append(f"""
<article class="topic">
  <div class="topic-band"><span class="topic-no">{i}</span>
    <span class="topic-name">{esc(t['name'])}</span></div>
  {overview}
  {''.join(secs)}
  {terms}
  {summary}
  {ai_qr}
</article>""")

    return TEMPLATE.replace("__TITLE__", f"{spec['volume']} 参考書 {spec['title']}") \
                   .replace("__BODY__", "".join(body))


TEMPLATE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
  @page { size: A4; margin: 12mm 12mm; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:"Yu Gothic","Meiryo",sans-serif; font-size:11pt; line-height:2.0;
         color:#1c1917; background:#fffdf8; }

  /* 蛍光ペン風マーカー */
  .mark { background:linear-gradient(transparent 55%, #fde68a 55%); font-weight:bold; padding:0 1px; }

  /* ナビキャラ */
  .navi { border-radius:50%; object-fit:cover; flex:none; box-shadow:0 1px 3px rgba(0,0,0,.15); }
  .navi-emoji { background:#fef3c7; display:flex; align-items:center; justify-content:center; }

  /* 表紙 */
  .cover { border:3px solid #f59e0b; border-radius:5mm; padding:10mm 8mm; margin-bottom:6mm;
           text-align:center; background:linear-gradient(160deg,#fffbeb,#fff7ed); }
  .cover-badge { display:inline-block; background:#b45309; color:#fff; font-weight:bold;
                 padding:1.5mm 5mm; border-radius:10mm; font-size:11pt; }
  .cover h1 { font-size:26pt; margin-top:4mm; color:#7c2d12; }
  .cover-sub { font-size:13pt; color:#92400e; margin-top:1mm; }
  .cover-navi { display:flex; align-items:center; gap:4mm; justify-content:center; margin-top:6mm; }
  .cover-bubble { position:relative; background:#fff; border:2px solid #f59e0b; border-radius:4mm;
                  padding:3mm 5mm; font-size:11pt; font-weight:bold; color:#7c2d12; max-width:120mm; }
  .cover-bubble::before { content:""; position:absolute; left:-4mm; top:50%; transform:translateY(-50%);
                  border:2mm solid transparent; border-right-color:#f59e0b; }

  /* トピック */
  .topic { page-break-before:always; }
  .topic-band { display:flex; align-items:center; gap:3mm; margin-bottom:4mm; }
  .topic-no { background:#b45309; color:#fff; border-radius:50%; width:11mm; height:11mm;
              display:inline-flex; align-items:center; justify-content:center; font-size:15pt;
              font-weight:bold; flex:none; box-shadow:0 2px 4px rgba(180,83,9,.3); }
  .topic-name { font-size:18pt; font-weight:bold; color:#7c2d12;
                border-bottom:3px solid #fde68a; padding-bottom:1mm; flex:1; }

  /* この単元でわかること（＋右にヒーロー画像） */
  .overview { display:flex; gap:5mm; align-items:center;
              background:linear-gradient(135deg,#fffbeb,#fff3d8); position:relative;
              border:2px solid #fcd34d; border-radius:4mm; padding:4mm 5mm; margin-bottom:6mm;
              box-shadow:0 2px 6px rgba(180,83,9,.09); }
  .ov-main { flex:1; }
  .ov-h { display:inline-flex; align-items:center; gap:1.5mm; background:#b45309; color:#fff;
          font-weight:bold; font-size:11pt; padding:1mm 4mm; border-radius:10mm; margin-bottom:3mm;
          box-shadow:0 2px 4px rgba(180,83,9,.25); }
  .ov-ico { font-size:12pt; }
  .ov-list { list-style:none; display:flex; flex-direction:column; gap:2mm; }
  .ov-list li { display:flex; align-items:center; gap:2.5mm; background:#fff; border:1.5px solid #fde68a;
                border-radius:2.5mm; padding:2mm 3mm; font-size:11pt; font-weight:bold; color:#44403c;
                box-shadow:0 1px 2px rgba(0,0,0,.05); }
  .ov-num { flex:none; width:6mm; height:6mm; border-radius:50%; background:#f59e0b; color:#fff;
            display:inline-flex; align-items:center; justify-content:center; font-size:9.5pt;
            box-shadow:0 1px 2px rgba(0,0,0,.12); }
  .ov-txt { flex:1; }
  .hero-fig { flex:none; width:38mm; }
  .hero-fig img { width:36mm; height:36mm; display:block; margin:0 auto; object-fit:cover;
                  border-radius:50%; border:1.2mm solid #fff; box-shadow:0 1px 5px rgba(0,0,0,.14); }
  .hero-fig figcaption { font-size:8pt; color:#a8a29e; text-align:center; margin-top:1mm; }

  /* 本文セクション（番号バッジ＋見出し＋一言リード） */
  .sec { margin-bottom:4mm; }
  .sec h3 { font-size:13.5pt; color:#7c2d12; margin-bottom:2mm; display:flex; align-items:baseline; gap:2.5mm; flex-wrap:wrap; }
  .sec-no { background:#b45309; color:#fff; border-radius:50%; width:6mm; height:6mm; flex:none;
            display:inline-flex; align-items:center; justify-content:center; font-size:10pt; }
  .sec-lead { font-size:10pt; font-weight:normal; color:#b45309; }
  /* 左=本文＋ここだけ覚える(下)／右=補足欄(全体の約22%・縦線で区切る) */
  .sec-row { display:flex; gap:5mm; align-items:stretch; padding-left:8.5mm; }
  .sec-main { flex:1; min-width:0; }
  .sec-main p { text-align:justify; }
  .sec-side { flex:none; width:40mm; border-left:1.5px solid #e2d5bd; padding-left:4mm; }
  .side-note { margin-bottom:3mm; }
  .side-term { font-weight:bold; color:#b45309; font-size:9pt; line-height:1.4; }
  .side-desc { font-size:8pt; color:#57534e; line-height:1.55; margin-top:0.3mm; }
  .side-tip { font-size:8.5pt; color:#44403c; background:#fffbeb; border-radius:1.5mm; padding:2mm; }
  /* ここだけ覚える: 本文の下・帯状（短めに） */
  .point { background:#fff9c4; border-left:3mm solid #fbbf24; border-radius:1.5mm;
           padding:2mm 3.5mm; margin-top:2.5mm; font-size:10pt; }
  .ptag { font-weight:bold; color:#b45309; margin-right:2mm; }
  .ptxt { color:#44403c; }

  /* 用語カードのグリッド（3列） */
  .terms { margin-top:5mm; page-break-inside:avoid; }
  .terms-h { font-size:13pt; font-weight:bold; color:#7c2d12; margin-bottom:3mm; display:flex; align-items:center; gap:2mm; }
  .terms-h .sub { font-size:9.5pt; font-weight:normal; color:#a8a29e; }
  .tgrid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:3mm; }
  .tcard { background:#fff; border:1.5px solid #fde68a; border-radius:2.5mm; padding:3mm; break-inside:avoid;
           box-shadow:0 1px 2px rgba(0,0,0,.04); }
  .tc-head { display:flex; align-items:center; gap:2mm; margin-bottom:1.5mm; }
  .tc-emoji { font-size:15pt; flex:none; }
  .tc-term { font-weight:bold; font-size:11.5pt; color:#7c2d12; }
  .tc-rd { display:block; font-weight:normal; font-size:7.5pt; color:#b8b0a6; }
  .tc-desc { font-size:9pt; color:#44403c; line-height:1.65; }

  /* 30秒まとめ */
  .sum30 { margin-top:6mm; border:2px solid #f59e0b; border-radius:4mm; overflow:hidden;
           page-break-inside:avoid; box-shadow:0 2px 6px rgba(245,158,11,.14); }
  .sum30-h { background:linear-gradient(90deg,#d97706,#f59e0b); color:#fff; font-weight:bold;
             font-size:12pt; padding:2mm 4mm; display:flex; align-items:center; gap:2mm; }
  .sum30-ico { font-size:15pt; }
  .sum30-tag { margin-left:auto; font-size:8.5pt; font-weight:bold; background:rgba(255,255,255,.28);
               padding:0.6mm 3mm; border-radius:6mm; }
  .sum30-body { padding:5mm 6mm 4mm; font-size:12pt; font-weight:bold; color:#44403c; line-height:2.0;
                background:#fffdf5; position:relative;
                background-image:radial-gradient(#f6e2b8 0.7px, transparent 0.7px); background-size:4mm 4mm; }
  .sum30-body::before { content:"“"; position:absolute; top:-1mm; left:1.5mm; font-size:30pt;
                        color:#fcd34d; font-family:Georgia,serif; }
  .sum30-body { padding-left:9mm; }
  /* 30秒まとめ内は蛍光でなく「濃いオレンジ太字」で重要語を強調 */
  .sum30-body .mark { background:none; color:#c2410c; font-weight:bold; padding:0; }

  /* AI先生QR（各単元の最後・コンパクト） */
  .ai-box { display:flex; gap:3.5mm; align-items:center; margin-top:4mm; page-break-inside:avoid;
            background:#f0f9f4; border:1.5px dashed #6ab08a; border-radius:3mm; padding:2.5mm 3.5mm; }
  .ai-qr { width:20mm; height:20mm; flex:none; background:#fff; padding:0.8mm; border-radius:1.5mm; }
  .ai-text { flex:1; }
  .ai-title { font-weight:bold; color:#15803d; font-size:10.5pt; margin-bottom:1.5mm; }
  .ai-menu { display:flex; flex-direction:column; gap:1mm; margin-bottom:1.5mm; }
  .ai-chip { display:inline-block; background:#fff; border:1px solid #bbe3cc; border-radius:5mm;
             padding:0.6mm 2.5mm; font-size:8.5pt; color:#166534; font-weight:bold; }
  .ai-link { font-size:8pt; color:#57534e; }
  .ai-link a { color:#15803d; }

  @media print { * { -webkit-print-color-adjust:exact; print-color-adjust:exact; } }
</style></head><body>
__BODY__
</body></html>"""


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    for jp in sorted(REF_DIR.glob("*.json")):
        out = OUT_DIR / f"ref-{jp.stem}.html"
        out.write_text(build(jp.stem), encoding="utf-8")
        print(f"generated: {out}")
