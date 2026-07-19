# -*- coding: utf-8 -*-
"""
納品フォルダの先頭に添える「★はじめにお読みください.pdf」を購入プラン別に4種類作る。
  - 中1 / 中2 / 中3（学年別プラン用: その学年の冊子だけを目次に載せる）
  - 3学年セット（全19冊）

1枚のPDFに問題集と参考書の両方の使い方をまとめる（購入者はどのプランでも
「★はじめに → 1_問題集 → 2_参考書」の同じ構成を受け取るため、案内も1枚に統合）。

内容:
  - つづもんの進め方（LINEファースト: 友だち追加 → 参考書で理解 → 問題集をLINEで解く）
  - AIの2つの使い方（問題集=AI採点 / 参考書=AI先生に質問・理解度チェック）
  - 友だち追加QR
  - 収録内容の目次（購入プラン分のみ・問題集/参考書とも）
  - 利用期間（期間ライセンス制）・ご利用ルールの注記

使い方:
  python -X utf8 make_intro_pdf.py     # output/_はじめにお読みください_{中1|中2|中3|3学年セット}.html を生成
  → Edge ヘッドレスで PDF 化 → python -X utf8 organize_output.py で 01_はじめに/ へ
"""
import base64
import io
import json
from pathlib import Path

import segno

BASE = Path(__file__).parent
BOOKS_DIR = BASE / "books"
REF_DIR = BASE / "reference"
OUT_DIR = BASE / "output"

FRIEND_URL = "https://lin.ee/wxDOngU"

GRADE_HISTORY = {**{f"{i:02d}": "中1" for i in range(1, 7)},
                 **{f"{i:02d}": "中2" for i in range(7, 13)},
                 **{f"{i:02d}": "中3" for i in range(13, 20)}}

PLANS = ["中1", "中2", "中3", "3学年セット"]


def qr_data_uri(url: str, scale: int = 8) -> str:
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=scale, border=2)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def toc_rows(src_dir: Path, grade_filter: str):
    """歴史の冊子JSON → (学年, 巻, タイトル, サブタイトル)。grade_filter='3学年セット'なら全部。"""
    rows = []
    for bp in sorted(src_dir.glob("*.json")):
        grade = GRADE_HISTORY.get(bp.stem[:2])
        if grade is None:  # 理科などは載せない（現在の販売は歴史のみ）
            continue
        if grade_filter != "3学年セット" and grade != grade_filter:
            continue
        d = json.loads(bp.read_text(encoding="utf-8"))
        rows.append((grade, d.get("volume", ""), d["title"], d.get("subtitle", "")))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def rows_html(rows):
    return "".join(
        f"<tr><td class='g'>{g}</td><td class='v'>{v}</td>"
        f"<td class='t'>{t}</td><td class='s'>{s}</td></tr>"
        for g, v, t, s in rows
    )


def build_html(plan: str) -> str:
    qr = qr_data_uri(FRIEND_URL)
    wb = toc_rows(BOOKS_DIR, plan)
    ref = toc_rows(REF_DIR, plan)
    plan_label = plan if plan == "3学年セット" else f"{plan}セット"

    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>はじめにお読みください（{plan}）</title>
<style>
  @page {{ size: A4; margin: 14mm 14mm; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"Yu Gothic","Meiryo",sans-serif; font-size:10.5pt; line-height:1.8; color:#1c1917; }}
  .hero {{ border:2.5px solid #b45309; border-radius:3mm; padding:5mm; margin-bottom:5mm; text-align:center;
           background:linear-gradient(160deg,#fffbeb,#fff7ed); }}
  .hero h1 {{ font-size:20pt; color:#b45309; }}
  .hero .sub {{ font-size:10.5pt; color:#57534e; margin-top:1.5mm; }}
  .hero .plan {{ display:inline-block; margin-top:2mm; background:#b45309; color:#fff; font-weight:bold;
                 border-radius:5mm; padding:0.5mm 5mm; font-size:10.5pt; }}
  h2 {{ font-size:13pt; background:#b45309; color:#fff; padding:1mm 3mm; border-radius:1.5mm; margin:5mm 0 3mm; }}
  .steps {{ display:flex; gap:4mm; margin-bottom:3mm; }}
  .step {{ flex:1; border:1.5px solid #e7e5e4; border-radius:2mm; padding:3mm; text-align:center; }}
  .step .n {{ display:inline-block; width:8mm; height:8mm; line-height:8mm; border-radius:50%; background:#f59e0b; color:#fff; font-weight:bold; }}
  .step .h {{ font-weight:bold; margin:1.5mm 0; }}
  .step .d {{ font-size:9pt; color:#57534e; text-align:left; }}
  .ai2 {{ display:flex; gap:4mm; margin-bottom:3mm; }}
  .ai-card {{ flex:1; border:1.5px solid #6ab08a; border-radius:2.5mm; background:#f0f9f4; padding:3.5mm 4mm; }}
  .ai-card .h {{ font-weight:bold; color:#15803d; font-size:11pt; margin-bottom:1.5mm; }}
  .ai-card .d {{ font-size:9.5pt; color:#166534; }}
  .ai-card .lv {{ margin-top:2mm; font-size:8.5pt; }}
  .ai-card .lv b {{ display:inline-block; background:#fff; border:1px solid #bbe3cc; border-radius:5mm;
                   padding:0.4mm 2.5mm; margin-right:1.5mm; color:#166534; }}
  .paper {{ border:1.5px solid #e7e5e4; background:#fafaf9; border-radius:2mm; padding:2.5mm 4mm; font-size:9.5pt; color:#57534e; margin-bottom:3mm; }}
  .paper b {{ color:#1c1917; }}
  .qrbox {{ display:flex; gap:5mm; align-items:center; border:1.5px dashed #b45309; background:#fffbeb; border-radius:2mm; padding:4mm; }}
  .qrbox img {{ width:28mm; height:28mm; }}
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
  <h1>つづもん</h1>
  <div class="sub">中学歴史 問題集＋参考書 ｜ LINEで解いて、AIがすぐ採点。“日本一つづけやすい”を目指す問題集</div>
  <div class="plan">{plan_label}</div>
</div>

<h2>つづもんの進め方（3ステップ）</h2>
<div class="steps">
  <div class="step"><div class="n">1</div><div class="h">公式LINEを友だち追加</div><div class="d">下のQRコードから友だち追加。AI採点・AI先生・学習記録は、すべてこのLINEの中で動きます。</div></div>
  <div class="step"><div class="n">2</div><div class="h">参考書で理解する</div><div class="d">「2_参考書」フォルダの参考書をイラストと要点で読むだけ。わからないことは、単元末のQRからAI先生に質問できます。</div></div>
  <div class="step"><div class="n">3</div><div class="h">問題集をLINEで解く</div><div class="d">「1_問題集」フォルダの各単元のQRを読むと、その単元の問題がLINEに届きます。解けばその場でAIが丸つけ。</div></div>
</div>
<div class="paper"><b>✏️ 紙でじっくり派も大歓迎。</b>問題集をA4で印刷して書き込めば、巻末解答で丸つけできます。
「紙で解いてから、LINEで復習」の合わせ技もおすすめです。</div>

<h2>AIの2つの使い方</h2>
<div class="ai2">
  <div class="ai-card">
    <div class="h">⭕ 問題集 × AI採点</div>
    <div class="d">4択・入力・記述問題をLINEで解くと、AIがその場で採点・解説。レベル・正答率・ニガテを記録し、まちがえた問題は自動で再出題されます。</div>
  </div>
  <div class="ai-card">
    <div class="h">❓ 参考書 × AI先生</div>
    <div class="d">単元のことを何でも質問できるほか、「理解度チェック」ではAI先生が出題→採点・解説してくれます。</div>
    <div class="lv"><b>やさしい</b><b>ふつう</b><b>むずかしい</b></div>
  </div>
</div>

<div class="qrbox">
  <img src="{qr}">
  <div class="txt">
    <div class="h">📱 まずはここから ｜ 公式LINEを友だち追加</div>
    <div>QRコードを読み取って「チャットでスタディ」（つづもんの採点アカウント）を友だち追加してください。
    追加できたら、あとは各冊子のQRを読むだけで学習を始められます。</div>
  </div>
</div>

<h2>収録内容 ｜ 問題集（{plan}・全{len(wb)}冊）</h2>
<table><tr><th>学年</th><th>巻</th><th>タイトル</th><th>内容</th></tr>{rows_html(wb)}</table>

<h2>収録内容 ｜ 参考書（{plan}・全{len(ref)}冊）</h2>
<table><tr><th>学年</th><th>巻</th><th>タイトル</th><th>内容</th></tr>{rows_html(ref)}</table>

<div class="note">
  ※ このPDFはご購入者様専用です。各ページに購入者名が記載されています。
  ご家庭内での印刷・きょうだいでのご利用はOKですが、ご家庭の外への配布・共有はご遠慮ください。<br>
  ※ 公式LINEのサービス（問題演習・AI採点・AI先生・学習記録）は、ご購入プランの利用期間中お使いいただけます。
  期間終了後も、ダウンロード済みのPDFはそのままずっとご利用いただけます
  （LINEのサービスのみ、ご希望の場合は月額で継続できます）。<br>
  ※ 公式LINEでの学習記録は、最初にご登録いただいたアカウントに紐づきます。<br>
  ※ わからないこと・困ったことがあれば、公式LINEでそのままメッセージを送ってください。
</div>

</body></html>"""


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for plan in PLANS:
        out = OUT_DIR / f"_はじめにお読みください_{plan}.html"
        out.write_text(build_html(plan), encoding="utf-8")
        print(f"HTML: {out}")
    print("→ Edge で PDF 化してください（build コマンド参照）")


if __name__ == "__main__":
    main()
