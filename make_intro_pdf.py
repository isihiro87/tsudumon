# -*- coding: utf-8 -*-
"""
配布フォルダの先頭に添える「★はじめにお読みください.pdf」を作る。
- 教材の使い方（紙で解く → QRで公式LINE → AI採点・成績管理）
- 収録内容の目次（歴史/理科の一覧）
- 友だち追加QR
Edge ヘッドレスで HTML → PDF 化する（他ジェネレーターと同じ方式）。
"""
import base64
import io
import json
import os
from pathlib import Path

import segno

BASE = Path(__file__).parent
BOOKS_DIR = BASE / "books"
OUT_HTML = BASE / "output" / "_はじめにお読みください.html"

FRIEND_URL = "https://lin.ee/wxDOngU"


def qr_data_uri(url: str, scale: int = 8) -> str:
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=scale, border=2)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def toc_rows(subject_prefix, is_science):
    from watermark_pdf import book_meta
    rows = []
    for bp in sorted(BOOKS_DIR.glob("*.json")):
        stem = bp.stem
        if is_science and not stem.startswith("science"):
            continue
        if not is_science and stem.startswith("science"):
            continue
        subj, grade, name = book_meta(stem)
        d = json.loads(bp.read_text(encoding="utf-8"))
        rows.append((grade, d.get("volume", ""), d["title"], d.get("subtitle", "")))
    # 学年順
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def build_html() -> str:
    qr = qr_data_uri(FRIEND_URL)
    hist = toc_rows("", False)
    sci = toc_rows("", True)

    def rows_html(rows):
        out = []
        for grade, vol, title, sub in rows:
            out.append(
                f"<tr><td class='g'>{grade}</td><td class='v'>{vol}</td>"
                f"<td class='t'>{title}</td><td class='s'>{sub}</td></tr>"
            )
        return "".join(out)

    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>はじめにお読みください</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"Yu Gothic","Meiryo",sans-serif; font-size:10.5pt; line-height:1.8; color:#1c1917; }}
  .hero {{ border:2.5px solid #b45309; border-radius:3mm; padding:6mm; margin-bottom:6mm; text-align:center; }}
  .hero h1 {{ font-size:20pt; color:#b45309; }}
  .hero .sub {{ font-size:11pt; color:#57534e; margin-top:2mm; }}
  h2 {{ font-size:13pt; background:#b45309; color:#fff; padding:1mm 3mm; border-radius:1.5mm; margin:6mm 0 3mm; }}
  .steps {{ display:flex; gap:4mm; margin-bottom:3mm; }}
  .step {{ flex:1; border:1.5px solid #e7e5e4; border-radius:2mm; padding:3mm; text-align:center; }}
  .step .n {{ display:inline-block; width:8mm; height:8mm; line-height:8mm; border-radius:50%; background:#f59e0b; color:#fff; font-weight:bold; }}
  .step .h {{ font-weight:bold; margin:1.5mm 0; }}
  .step .d {{ font-size:9pt; color:#57534e; }}
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
  <h1>チャットでスタディ 問題集</h1>
  <div class="sub">中学 歴史・理科 ｜ 紙で解いて、公式LINEでAI採点・成績管理</div>
</div>

<h2>この問題集の使い方</h2>
<div class="steps">
  <div class="step"><div class="n">1</div><div class="h">紙で解く</div><div class="d">要点まとめ・一問一答・4択・記述・資料問題を書き込んで解こう。</div></div>
  <div class="step"><div class="n">2</div><div class="h">QRを読む</div><div class="d">各単元のQRコードをスマホで読むと、公式LINEにその単元の問題が届くよ。</div></div>
  <div class="step"><div class="n">3</div><div class="h">LINEで復習</div><div class="d">4択・入力・記述に挑戦。AIが採点し、レベル・正答率・ニガテを記録します。</div></div>
</div>

<div class="qrbox">
  <img src="{qr}">
  <div class="txt">
    <div class="h">📱 まずは公式LINEを友だち追加</div>
    <div>QRコードを読み取って「チャットでスタディ」を友だち追加してね。
    問題集のQRから、いつでも問題演習・成績確認ができるようになります。</div>
  </div>
</div>

<h2>収録内容（歴史 全19冊）</h2>
<table><tr><th>学年</th><th>巻</th><th>タイトル</th><th>内容</th></tr>{rows_html(hist)}</table>

<h2>収録内容（理科 全12冊）</h2>
<table><tr><th>学年</th><th>巻</th><th>タイトル</th><th>内容</th></tr>{rows_html(sci)}</table>

<div class="note">
  ※ このPDFはご購入者様専用です。各ページに購入者名が記載されています。
  無断での複製・再配布・共有はご遠慮ください。<br>
  ※ 公式LINEでの学習記録は、最初にご登録いただいたアカウントに紐づきます。
</div>

</body></html>"""


def main() -> None:
    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print(f"HTML: {OUT_HTML}")
    print("→ Edge で PDF 化してください（build コマンド参照）")


if __name__ == "__main__":
    main()
