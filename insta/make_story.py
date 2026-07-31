# -*- coding: utf-8 -*-
"""
Instagram ストーリー用の縦長画像（1080×1920）を作る。

文字が主役の面は画像生成AIに描かせず HTML→PNG にする。
  - 日本語が絶対に崩れない
  - シリーズでトーンが揃う
  - あとから文言だけ差し替えて作り直せる
背景のイラストが要る面だけ、別途 Codex(image-2) の絵を敷く想定（img= で指定）。

使い方:
  python -X utf8 insta/make_story.py            # insta/out/*.png を生成
  python -X utf8 insta/make_story.py --set teaser

セーフエリア: 上下 250px 前後は Instagram の UI（アイコン・返信欄）に隠れるので、
文字はその内側にしか置かない。
"""
import argparse
import html
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "out"
EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
CHAR_DIR = BASE.parent / "assets" / "characters"     # マスコット（透過PNG）
BAND_DIR = BASE.parent / "covers" / "img"            # 歴史イラストの帯など

W, H = 1080, 1920

# ── 文言セット ────────────────────────────────────────────────
# 「まだ何も明かさない予告」。商品名も機能も出さず、気持ちだけを置く。
SETS = {
    "teaser": [
        {
            "kicker": "",
            "lines": ["テスト前に、", "いちど覚えて、", "終わったら、忘れる。"],
            "mark": 2,                      # 何行目に蛍光マーカーを引くか（0始まり）
            "note": "",
            "tail": "",
            "theme": "cream",
            "char": "manabi_think.png",     # 上に大きく置くマスコット
            "charSize": 460,
        },
        {
            "kicker": "",
            "lines": ["それが、ずっと", "もったいない。"],
            "mark": 1,
            "note": "",
            "tail": "いま、つくっています。",
            "theme": "cream",
            "char": "char_owl.png",
            "charSize": 430,
            "band": "cover-history-band.png",   # 下に敷く歴史イラストの帯
            "bandFade": True,
        },
        {
            "kicker": "中学歴史のための",
            "lines": ["あたらしいものを", "つくっています。"],
            "mark": None,
            "note": "くわしいことは、また今度。",
            "tail": "つづく",
            "theme": "brand",
            "char": "manabi_banzai.png",
            "charSize": 300,
            "band": "cover-history-band.png",
        },
    ],
}

# ── 実画面チラ見せの面 ────────────────────────────────────────
# 価格・日付・アプリ画面など「1文字でも崩れたら困るもの」は画像生成AIに描かせず、
# LP の実スクリーンショット（lp/img/）を敷いてここで組む。
SHOT_DIR = BASE.parent / "lp" / "img"
TMP_DIR = BASE / "assets"

SHOT_SETS = {
    "reveal": [
        {
            # 質問スタンプを上に乗せる面。下半分は意図的に空けておく。
            "name": "ask",
            "lines": ["つづもんって、", "どんな教材だと思う？"],
            "mark": 1,
            "note": "↓ 下のスタンプから、なんでも聞いてください",
            "align": "top",
        },
        {
            "name": "line",
            "lines": ["今日やることが、", "LINEに届く。"],
            "mark": 1,
            "shot": "screen-app-line.webp",
            "shotCropTop": 130,      # 「チャットでスタディ」のヘッダーを切る
            "shotCropBottom": 1240,  # 会話の下の空白を切る
            "note": "選んだ時刻に、その日の1単元が。",
        },
        {
            "name": "write",
            "lines": ["記述も、", "AIがその場で採点。"],
            "mark": 1,
            "shot": "screen-app-write.webp",
            "note": "「この答えで合ってる？」が、もう起きない。",
        },
        {
            "name": "qa",
            "lines": ["基礎用語は、", "一問一答で何周でも。"],
            "mark": 1,
            "shot": "screen-app-qa.webp",
            "shotCropBottom": 1180,   # 下の空白を切る
            "note": "まちがえた問題は、ニガテとして後日もう一度。",
        },
        {
            # AI先生はLPの公式キャラ（3D）。連作の水彩とはトーンが違うので、
            # 周囲を溶かして地に馴染ませ、文字を主役にする。
            "name": "ai",
            "lines": ["わからないことは、", "質問し放題。"],
            "mark": 1,
            "shot": "ai-teacher-card.webp",
            "shotW": 600,
            "shotBlend": True,
            "note": "24時間、何度聞いても嫌な顔をしません。",
        },
    ],
    # 8/1(土) — 保護者に見せてもらうための1枚。
    # 価格・解約・安全性という「1文字も崩せない情報」なので、必ずこちら（HTML→PNG）で作る。
    "parent": [
        {
            "name": "price",
            "lines": ["おうちの人に、", "見せてください。"],
            "mark": 1,
            "card": [
                ("料金", "月額 1,280円", True),
                ("おためし", "3日間 無料。お支払いの登録はいりません", False),
                ("解約", "いつでもできます。違約金はありません", False),
                ("安全", "AIとのやり取りは、運営が定期的に確認しています", False),
            ],
            "note": "↑ くわしくは、上のリンクから（保護者の方へのページ）",
        },
    ],
}

PAGE_SHOT = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { background:#888; }
  .story { position:absolute; top:0; left:0; width:%dpx; height:%dpx; overflow:hidden;
           font-family:"Yu Mincho","YuMincho","Hiragino Mincho ProN","MS PMincho",serif;
           background:
             radial-gradient(circle at 20%% 12%%, rgba(255,255,255,.92) 0 32%%, transparent 64%%),
             radial-gradient(circle at 84%% 84%%, rgba(253,230,138,.22) 0 26%%, transparent 58%%),
             linear-gradient(160deg,#fffdf8,#fdf6e8); color:#3b2415; }
  /* セーフエリア（上下250pxはUIに隠れる） */
  .inner { position:absolute; inset:280px 90px 300px; display:flex; flex-direction:column;
           align-items:flex-start; justify-content:center; }
  .inner.top { justify-content:flex-start; }
  .line { font-size:72px; font-weight:bold; line-height:1.55; letter-spacing:.03em;
          white-space:nowrap; }
  .line .mk { background:linear-gradient(transparent 62%%, rgba(245,158,11,.55) 62%%);
              padding:0 6px; }
  /* 実画面。角丸＋影で「スマホの中身」に見せる */
  .shotwrap { align-self:center; margin-top:44px; border-radius:26px; overflow:hidden;
              box-shadow:0 18px 40px rgba(120,80,20,.28); border:3px solid rgba(124,45,18,.14);
              background:#fff; }
  .shotwrap img { display:block; width:%dpx; height:auto; }
  /* 背景が紙色の素材（AI先生など）は、枠に入れず周囲を溶かして地に馴染ませる */
  .shotwrap.blend { border:none; box-shadow:none; background:transparent; border-radius:0;
                    margin-top:24px; }
  .shotwrap.blend img { -webkit-mask-image:radial-gradient(ellipse at 50%% 48%%,
                          #000 52%%, transparent 76%%);
                        mask-image:radial-gradient(ellipse at 50%% 48%%,
                          #000 52%%, transparent 76%%); }
  .note { font-family:"Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif;
          font-size:32px; line-height:1.75; margin-top:38px; color:#7c5a3a; }
  /* 価格・解約などの「崩せない情報」を並べるカード */
  .card { align-self:stretch; margin-top:46px; background:rgba(255,255,255,.88);
          border:2px solid rgba(124,45,18,.13); border-radius:30px; padding:20px 44px;
          box-shadow:0 14px 34px rgba(120,80,20,.15); }
  .card .row { display:flex; align-items:baseline; gap:22px; padding:26px 0;
               border-bottom:1px solid rgba(124,45,18,.10); }
  .card .row:last-child { border-bottom:none; }
  .card .k { font-family:"Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif;
             font-size:27px; font-weight:bold; color:#b45309; white-space:nowrap;
             min-width:150px; letter-spacing:.08em; }
  .card .v { font-family:"Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif;
             font-size:33px; line-height:1.5; color:#3b2415; }
  .card .v.big { font-size:62px; font-weight:bold; letter-spacing:.01em; }
  .card .tax { font-family:"Yu Gothic",sans-serif; font-size:28px; color:#7c5a3a;
               margin-left:10px; }
  .no { position:absolute; right:90px; bottom:250px; font-family:"Yu Gothic",sans-serif;
        font-size:28px; letter-spacing:.2em; color:rgba(124,45,18,.35); }
</style></head><body>
<div class="story">
  <div class="inner %s">
    <div>%s</div>
    %s
    %s
  </div>
  <div class="no">%s</div>
</div></body></html>"""

SHOT_W = 520   # 実画面の表示幅


def prep_shot(item: dict) -> str:
    """スクショを必要なら上部トリミングして、HTMLから参照できるURIを返す。"""
    from PIL import Image
    src = SHOT_DIR / item["shot"]
    crop = item.get("shotCropTop", 0)
    dest = TMP_DIR / f"_shot-{item['name']}.png"
    im = Image.open(src)
    bottom = item.get("shotCropBottom") or im.height
    if crop or bottom != im.height:
        im = im.crop((0, crop, im.width, bottom))
    im.save(dest)
    return dest.as_uri()


def render_shot(item: dict, no: str) -> str:
    lines = []
    for i, ln in enumerate(item["lines"]):
        body = esc(ln)
        if item.get("mark") == i:
            body = f'<span class="mk">{body}</span>'
        lines.append(f'<div class="line">{body}</div>')
    shot = ""
    if item.get("shot"):
        cls = "shotwrap blend" if item.get("shotBlend") else "shotwrap"
        shot = f'<div class="{cls}"><img src="{prep_shot(item)}" alt=""></div>'
    elif item.get("card"):
        rows = []
        for key, val, big in item["card"]:
            v = f'<span class="v big">{esc(val)}</span><span class="tax">（税込）</span>' \
                if big else f'<span class="v">{esc(val)}</span>'
            rows.append(f'<div class="row"><span class="k">{esc(key)}</span>{v}</div>')
        shot = f'<div class="card">{"".join(rows)}</div>'
    note = f'<div class="note">{esc(item["note"])}</div>' if item.get("note") else ""
    align = "top" if item.get("align") == "top" else ""
    return PAGE_SHOT % (W, H, item.get("shotW", SHOT_W),
                        align, "".join(lines), shot, note, no)


PAGE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { background:#888; }
  .story { position:absolute; top:0; left:0; width:%dpx; height:%dpx; overflow:hidden;
           font-family:"Yu Mincho","YuMincho","Hiragino Mincho ProN","MS PMincho",serif;
           display:flex; flex-direction:column; }
  /* 紙の質感（淡いグラデ＋にじみ） */
  .story.cream { background:
      radial-gradient(circle at 22%% 18%%, rgba(255,255,255,.9) 0 30%%, transparent 62%%),
      radial-gradient(circle at 82%% 88%%, rgba(253,230,138,.35) 0 28%%, transparent 60%%),
      linear-gradient(160deg,#fffdf8,#fdf3e2); color:#3b2415; }
  .story.brand { background:
      radial-gradient(circle at 78%% 16%%, rgba(255,255,255,.18) 0 26%%, transparent 58%%),
      linear-gradient(165deg,#8a3c0c,#7c2d12 60%%,#5b1e0b); color:#fff8ec; }
  /* セーフエリア（上下 250px はUIに隠れるので文字を置かない） */
  .inner { flex:1; padding:290px 96px 300px; display:flex; flex-direction:column;
           justify-content:center; position:relative; z-index:2; }
  /* マスコット（透過PNG）。文字の上に大きく置く */
  .char { display:block; height:auto; margin:0 0 54px -14px;
          filter:drop-shadow(0 10px 16px rgba(120,80,20,.22)); }
  /* 歴史イラストの帯。下端いっぱいに敷いて世界観だけ伝える（中身は明かさない） */
  .band { position:absolute; left:0; right:0; bottom:170px; width:100%%; z-index:1;
          border-radius:18px; }
  /* 帯があるときは、その高さぶん本文を上へ逃がす（文字と絵を重ねない） */
  .story.has-band .inner { padding-bottom:560px; }
  .band.fade { -webkit-mask-image:linear-gradient(to bottom, transparent, #000 45%%);
               mask-image:linear-gradient(to bottom, transparent, #000 45%%); opacity:.85; }
  /* 濃い面では、貼った紙のように見せる（背景がクリームの絵をそのまま活かす） */
  .story.brand .band { opacity:.97; filter:sepia(.22);
                       box-shadow:0 8px 30px rgba(0,0,0,.28); }
  .kicker { font-family:"Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif;
            font-size:36px; font-weight:bold; letter-spacing:.14em; margin-bottom:34px;
            color:#b45309; }
  .story.brand .kicker { color:#fcd34d; }
  .line { font-size:78px; font-weight:bold; line-height:1.62; letter-spacing:.04em;
          white-space:nowrap; }   /* 折り返しは禁止＝改行は lines で明示的に決める */
  .line .mk { background:linear-gradient(transparent 62%%, rgba(245,158,11,.55) 62%%);
              padding:0 6px; }
  .story.brand .line .mk { background:linear-gradient(transparent 62%%, rgba(252,211,77,.45) 62%%); }
  .note { font-family:"Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif;
          font-size:34px; line-height:1.9; margin-top:56px; color:#7c5a3a; }
  .story.brand .note { color:#f5d9bd; }
  .tail { font-family:"Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif;
          font-size:34px; font-weight:bold; margin-top:64px; letter-spacing:.1em;
          color:#b45309; }
  .story.brand .tail { color:#fcd34d; }
  /* 右下の小さな余韻（連番） */
  .no { position:absolute; right:96px; bottom:250px; font-family:"Yu Gothic",sans-serif;
        font-size:28px; letter-spacing:.2em; color:rgba(124,45,18,.35); }
  .story.brand .no { color:rgba(255,248,236,.45); }
</style></head><body>
<div class="story %s">
  %s
  <div class="inner">
    %s
    %s
    <div>%s</div>
    %s
    %s
  </div>
  <div class="no">%s</div>
</div></body></html>"""


def esc(s: str) -> str:
    return html.escape(s)


def render(item: dict, no: str) -> str:
    lines = []
    for i, ln in enumerate(item["lines"]):
        body = esc(ln)
        if item.get("mark") == i:
            body = f'<span class="mk">{body}</span>'
        lines.append(f'<div class="line">{body}</div>')
    kicker = f'<div class="kicker">{esc(item["kicker"])}</div>' if item.get("kicker") else ""
    note = f'<div class="note">{esc(item["note"])}</div>' if item.get("note") else ""
    tail = f'<div class="tail">{esc(item["tail"])}</div>' if item.get("tail") else ""
    char = ""
    if item.get("char"):
        src = (CHAR_DIR / item["char"])
        if src.exists():
            char = (f'<img class="char" src="{src.as_uri()}"'
                    f' style="width:{item.get("charSize", 400)}px" alt="">')
    band = ""
    if item.get("band"):
        src = BAND_DIR / item["band"]
        if src.exists():
            cls = "band fade" if item.get("bandFade") else "band"
            band = f'<img class="{cls}" src="{src.as_uri()}" alt="">'
    theme = item.get("theme", "cream") + (" has-band" if band else "")
    return PAGE % (W, H, theme, band, char, kicker,
                   "".join(lines), note, tail, no)


def shoot(html_text: str, dest: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "s.html"
        src.write_text(html_text, encoding="utf-8")
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={W},{H}", "--virtual-time-budget=2000",
                        f"--screenshot={dest}", src.as_uri()],
                       capture_output=True, check=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="teaser")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # 実画面を敷く面（SHOT_SETS）は連番ではなくファイル名で出す
    if args.set in SHOT_SETS:
        items = SHOT_SETS[args.set]
        for item in items:
            dest = OUT / f"{args.set}-{item['name']}.png"
            shoot(render_shot(item, ""), dest)
            print(f"wrote {dest}")
        return

    items = SETS[args.set]
    for i, item in enumerate(items, 1):
        dest = OUT / f"{args.set}-{i}.png"
        shoot(render(item, f"{i} / {len(items)}"), dest)
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
