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
    items = SETS[args.set]
    OUT.mkdir(parents=True, exist_ok=True)
    for i, item in enumerate(items, 1):
        dest = OUT / f"{args.set}-{i}.png"
        shoot(render(item, f"{i} / {len(items)}"), dest)
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
