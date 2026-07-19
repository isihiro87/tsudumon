# -*- coding: utf-8 -*-
"""
【非推奨】参考書の配布フォルダに添える「★はじめにお読みください（参考書）.pdf」を作る。

※ 2026-07-18 以降は make_intro_pdf.py がプラン別（中1/中2/中3/3学年セット）の
   統合版「はじめにお読みください」（問題集＋参考書の使い方を1枚に集約）を生成するため、
   このスクリプトは通常使わない。参考書を単体販売する場合のみ利用。
- 参考書の使い方（読んで理解 → 各単元QR → 公式LINEのAI先生に質問／理解度チェック）
- AI先生の2つの使い方（質問モード・理解度チェック＝難易度選択）の説明
- 収録内容の目次（参考書 全19冊）
- 友だち追加QR
Edge ヘッドレスで HTML → PDF 化する（他ジェネレーターと同じ方式）。
"""
import base64
import io
import json
from pathlib import Path

import segno

BASE = Path(__file__).parent
REF_DIR = BASE / "reference"
OUT_HTML = BASE / "output" / "_参考書はじめにお読みください.html"

FRIEND_URL = "https://lin.ee/wxDOngU"

GRADE_HISTORY = {**{f"{i:02d}": "中1" for i in range(1, 7)},
                 **{f"{i:02d}": "中2" for i in range(7, 13)},
                 **{f"{i:02d}": "中3" for i in range(13, 20)}}


def qr_data_uri(url: str, scale: int = 8) -> str:
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=scale, border=2)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def toc_rows():
    rows = []
    for bp in sorted(REF_DIR.glob("*.json")):
        grade = GRADE_HISTORY.get(bp.stem[:2], "")
        d = json.loads(bp.read_text(encoding="utf-8"))
        rows.append((grade, d.get("volume", ""), d["title"], d.get("subtitle", "")))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def build_html() -> str:
    qr = qr_data_uri(FRIEND_URL)
    rows = toc_rows()
    rows_html = "".join(
        f"<tr><td class='g'>{g}</td><td class='v'>{v}</td>"
        f"<td class='t'>{t}</td><td class='s'>{s}</td></tr>"
        for g, v, t, s in rows
    )

    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>はじめにお読みください（参考書）</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"Yu Gothic","Meiryo",sans-serif; font-size:10.5pt; line-height:1.8; color:#1c1917; }}
  .hero {{ border:2.5px solid #b45309; border-radius:3mm; padding:6mm; margin-bottom:6mm; text-align:center;
           background:linear-gradient(160deg,#fffbeb,#fff7ed); }}
  .hero h1 {{ font-size:20pt; color:#b45309; }}
  .hero .sub {{ font-size:11pt; color:#57534e; margin-top:2mm; }}
  h2 {{ font-size:13pt; background:#b45309; color:#fff; padding:1mm 3mm; border-radius:1.5mm; margin:6mm 0 3mm; }}
  .steps {{ display:flex; gap:4mm; margin-bottom:3mm; }}
  .step {{ flex:1; border:1.5px solid #e7e5e4; border-radius:2mm; padding:3mm; text-align:center; }}
  .step .n {{ display:inline-block; width:8mm; height:8mm; line-height:8mm; border-radius:50%; background:#f59e0b; color:#fff; font-weight:bold; }}
  .step .h {{ font-weight:bold; margin:1.5mm 0; }}
  .step .d {{ font-size:9pt; color:#57534e; }}
  /* AI先生の2つの使い方 */
  .ai2 {{ display:flex; gap:4mm; margin-bottom:3mm; }}
  .ai-card {{ flex:1; border:1.5px solid #6ab08a; border-radius:2.5mm; background:#f0f9f4; padding:3.5mm 4mm; }}
  .ai-card .h {{ font-weight:bold; color:#15803d; font-size:11.5pt; margin-bottom:1.5mm; }}
  .ai-card .d {{ font-size:9.5pt; color:#166534; }}
  .ai-card .lv {{ margin-top:2mm; font-size:8.5pt; }}
  .ai-card .lv b {{ display:inline-block; background:#fff; border:1px solid #bbe3cc; border-radius:5mm;
                   padding:0.4mm 2.5mm; margin-right:1.5mm; color:#166534; }}
  .qrbox {{ display:flex; gap:5mm; align-items:center; border:1.5px dashed #b45309; background:#fffbeb; border-radius:2mm; padding:4mm; }}
  .qrbox img {{ width:30mm; height:30mm; }}
  .qrbox .txt .h {{ font-weight:bold; color:#b45309; font-size:11pt; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:4mm; }}
  th,td {{ border:1px solid #d6d3d1; padding:0.8mm 2mm; font-size:9.5pt; }}
  th {{ background:#f5f5f4; }}
  td.g {{ text-align:center; width:12mm; white-space:nowrap; }}
  td.v {{ width:16mm; white-space:nowrap; color:#b45309; font-weight:bold; }}
  td.t {{ font-weight:bold; }}
  td.s {{ color:#78716c; font-size:8.5pt; }}
  .note {{ font-size:9pt; color:#78716c; margin-top:4mm; border-top:1px solid #e7e5e4; padding-top:2mm; }}
</style></head><body>

<div class="hero">
  <h1>チャットでスタディ 参考書</h1>
  <div class="sub">中学 歴史 ｜ 読んで理解して、公式LINEのAI先生と深める</div>
</div>

<h2>この参考書の使い方</h2>
<div class="steps">
  <div class="step"><div class="n">1</div><div class="h">読んで理解する</div><div class="d">イラスト・「わかること」・要点・30秒まとめで、楽しくインプット。</div></div>
  <div class="step"><div class="n">2</div><div class="h">単元のQRを読む</div><div class="d">各単元の最後にあるQRをスマホで読むと、公式LINEのAI先生につながるよ。</div></div>
  <div class="step"><div class="n">3</div><div class="h">AI先生と深める</div><div class="d">「質問」か「理解度チェック」を選んで、LINEでAIと対話しながら理解を深めよう。</div></div>
</div>

<h2>AI先生の2つの使い方</h2>
<div class="ai2">
  <div class="ai-card">
    <div class="h">❓ わからないことを質問する</div>
    <div class="d">その単元について、わからないことを何でも質問できます。AI先生が参考書の内容にそって、やさしく解説してくれます。</div>
  </div>
  <div class="ai-card">
    <div class="h">✅ 理解度チェックを受ける</div>
    <div class="d">AI先生がその単元の質問を出題。答えると採点・解説してくれます。むずかしさは3段階から選べます。</div>
    <div class="lv"><b>やさしい</b><b>ふつう</b><b>むずかしい</b></div>
  </div>
</div>

<div class="qrbox">
  <img src="{qr}">
  <div class="txt">
    <div class="h">📱 まずは公式LINEを友だち追加</div>
    <div>QRコードを読み取って「チャットでスタディ」を友だち追加してね。
    各単元のQRから、いつでもAI先生に質問・理解度チェックができるようになります。</div>
  </div>
</div>

<h2>収録内容（参考書 歴史 全19冊）</h2>
<table><tr><th>学年</th><th>巻</th><th>タイトル</th><th>内容</th></tr>{rows_html}</table>

<div class="note">
  ※ このPDFはご購入者様専用です。無断での複製・再配布・共有はご遠慮ください。<br>
  ※ AI先生との学習記録は、最初にご登録いただいたLINEアカウントに紐づきます。
</div>

</body></html>"""


def main() -> None:
    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print(f"HTML: {OUT_HTML}")
    print("→ Edge で PDF 化してください")


if __name__ == "__main__":
    main()
