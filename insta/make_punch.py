# -*- coding: utf-8 -*-
"""夏休みの中学生を引きつけるストーリー（1回3枚 × 3回）。

⚠️ **`--set 1` `2` `3` `5` が作る s1-*/s2-*/s3-*/d-* は不使用（2026-07-29 決定）。**
   ビビッドな地＋極太ゴシックの路線は、story-1〜3 の水彩の連作を見てきた人には
   別アカウントの投稿に見えるため破棄した。実際に投稿するのは水彩イラスト連作で、
   画像生成AI（codex）の指示書 `insta/_p-*.txt` から作り `insta/out/<MMDD>/` に置いてある。
   このファイルは**文言の控え**として残す。正本は
   `docs/つづもん-公開告知プラン-20260728.md` §5。

   ただし `--set line`（`line-0801-src`）だけは、LINE配信の添付画像を
   HTML→PNG で正確に作るために生きている。**価格・日付を画像生成AIに書かせない**
   という原則のためで、ここは消さないこと。

つづもんの説明はしない。中学生の「あるある」で笑わせ、参加させ、
最後に日付だけ置いて次を待たせる。商品の中身はLPに任せる。

見た目の方針（旧路線・s系の設計思想として残す）:
  - おしゃれさより「指が止まること」。ビビッドな地に極太ゴシック。
  - 1枚に1メッセージ。キーワードだけ巨大にする。
  - 上下250pxはInstagramのUIに隠れるので何も置かない。

使い方:
  python -X utf8 insta/make_punch.py             # 全セット（s系は不使用なので通常不要）
  python -X utf8 insta/make_punch.py --set line  # LINE配信の添付画像だけ
"""
import argparse
import html
import subprocess
import tempfile
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "out"
EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
W, H = 1080, 1920

# ── 3枚 × 3回 ────────────────────────────────────────────────
# 1枚目=笑わせて引く / 2枚目=畳みかける / 3枚目=参加させる・待たせる
SETS = {
    "1": [
        {
            # 1枚目はおわび。公式LINEが止まっていることを先に謝ってから本題へ。
            # ここだけ煽らないトーンにする（地は白・文字は小さめ）。
            # 配信はこの時点で「まだ止まったまま」なので、過去形にしない（現在形で書く）。
            "name": "s1-0", "theme": "white",
            "blocks": [
                ("【おわび】", 46, False),
                ("いま、公式LINEの", 68, False),
                ("配信が止まっています。", 68, False),
                ("ひと月に送れる通数の上限に", 44, False),
                ("達してしまったためです。", 44, False),
                ("8月から、また届けます。", 74, True),
            ],
            "sub": "楽しみに待ってくれていた人、ごめんなさい。",
        },
        {
            "name": "s1-1", "theme": "yellow",
            "blocks": [
                ("宿題やろうと思って、", 72, False),
                ("スマホ見て", 72, False),
                ("2時間。", 190, True),
            ],
            "sub": "↓ 心当たりある人",
        },
        {
            "name": "s1-2", "theme": "yellow",
            "blocks": [
                ("「明日から本気出す」", 72, False),
                ("——7月に入ってから、", 60, False),
                ("5回言った。", 150, True),
            ],
            "sub": "↓ もっと言ってる人",
        },
        {
            "name": "s1-3", "theme": "black",
            "blocks": [
                ("そんなきみに、", 72, False),
                ("8月5日（水）", 130, True),
                ("なにか始まります。", 72, False),
            ],
            "sub": "まだ言えません。",
        },
    ],
    # 2回目: 親。中学生の最大のストレス源であり、いちばん欲しいのは
    # 「親に何も言わせない方法」。商品の説明はせず、そこだけを差し出す。
    "2": [
        {
            "name": "s2-1", "theme": "yellow",
            "blocks": [
                ("「勉強しなさい」って", 68, False),
                ("言われた瞬間、やる気が", 68, False),
                ("消える。", 175, True),
            ],
            "sub": "↓ わかる人",
        },
        {
            "name": "s2-2", "theme": "yellow",
            "blocks": [
                ("さっきまで", 68, False),
                ("やろうと思ってたのに。", 68, False),
                ("言われたら、負け。", 95, True),
            ],
            "sub": "この気持ち、伝わらない。",
        },
        {
            "name": "s2-3", "theme": "black",
            "blocks": [
                ("親に何も", 68, False),
                ("言わせない方法、", 68, False),
                ("8月5日（水）", 128, True),
                ("から。", 68, False),
            ],
            "sub": "まだ言えません。",
        },
    ],
    # 3回目: 夏休み後半の焦りが出はじめる時期に、未来の自分から刺す。
    "3": [
        {
            "name": "s3-1", "theme": "yellow",
            "blocks": [
                ("8月31日の自分から", 68, False),
                ("メッセージが", 68, False),
                ("届いています。", 100, True),
            ],
            "sub": "↓ 読む",
        },
        {
            "name": "s3-2", "theme": "yellow",
            "blocks": [
                ("「なんで7月のじぶん、", 62, False),
                ("なんもしなかったの？」", 80, True),
            ],
            "sub": "毎年おなじことを言っている。",
        },
        {
            "name": "s3-3", "theme": "black",
            "blocks": [
                ("まだ間に合う。", 68, False),
                ("8月5日（水）", 128, True),
                ("ぜんぶ見せます。", 72, False),
            ],
            "sub": "もう、かくしません。",
        },
    ],
    # 8/5 当日。ここで初めて名前を出す。中身の説明はせず、ボタンを押させることだけを狙う。
    "5": [
        {
            "name": "d-1", "theme": "black",
            "blocks": [
                ("かくしてたこと、", 68, False),
                ("今日、話します。", 110, True),
            ],
            "sub": "8月5日（水）",
        },
        {
            "name": "d-2", "theme": "yellow",
            "blocks": [
                ("中学歴史、ぜんぶ。", 68, False),
                ("名前は、", 68, False),
                ("つづもん。", 190, True),
            ],
            "sub": "きょうから、はじまります。",
        },
        {
            # 下半分はリンクスタンプ（公式LINEのボタン）用に空ける。矢印でそこを指す。
            "name": "d-3", "theme": "yellow", "align": "top",
            "blocks": [
                ("まずは3日間、", 68, False),
                ("ぜんぶ無料。", 165, True),
                ("お支払いの登録はいりません。", 42, False),
                ("↓", 130, False),
            ],
            "sub": "",
        },
    ],
    # 公式LINE（一問一答）に添付する画像。ストーリーと違い単体で読まれるので、
    # 前の面を受ける言い回し（「そんなきみに、」など）は使わない。
    # 出力後に 1080×1350（4:5）へ切って使う。
    "line": [
        {
            "name": "line-0801-src", "theme": "black",
            "blocks": [
                ("8月5日（水）", 128, True),
                ("なにか始まります。", 72, False),
            ],
            "sub": "まだ言えません。",
        },
    ],
}

PAGE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { background:#888; }
  .s { position:absolute; top:0; left:0; width:%dpx; height:%dpx; overflow:hidden;
       font-family:"Meiryo","Yu Gothic",sans-serif; }
  .s.yellow { background:#ffd900; color:#141414; }
  .s.black  { background:#141414; color:#ffffff; }
  /* おわび・お知らせ。煽らないので地は白、文字は小さめ */
  .s.white  { background:#f6f6f4; color:#141414; }
  /* セーフエリア（上下250pxはUIに隠れる） */
  .in { position:absolute; inset:280px 78px 300px; display:flex; flex-direction:column;
        justify-content:center; align-items:flex-start; }
  /* リンクスタンプ（公式LINEのボタン）を下半分に置く面は、上詰めにして下を空ける */
  .in.top { justify-content:flex-start; }
  .b { font-weight:bold; line-height:1.32; letter-spacing:-.02em; white-space:nowrap; }
  /* 強調は「地の色を反転させた帯」。蛍光ペンより強く出る */
  .s.yellow .b.hl { background:#141414; color:#ffd900; padding:2px 18px 10px; }
  .s.black  .b.hl { background:#ffe000; color:#141414; padding:2px 18px 10px; }
  .s.white  .b.hl { background:#141414; color:#ffffff; padding:2px 18px 10px; }
  /* 小さい行は行間を広げないと読みにくい */
  .b.sm { line-height:1.55; letter-spacing:0; }
  .sub { font-weight:bold; font-size:36px; margin-top:52px; letter-spacing:.02em; }
  .s.yellow .sub { color:#7a6500; }
  .s.black  .sub { color:#9a9a9a; }
  .s.white  .sub { color:#6b6b6b; }
</style></head><body>
<div class="s %s"><div class="in %s">
%s
  <div class="sub">%s</div>
</div></div></body></html>"""


def esc(s: str) -> str:
    return html.escape(s)


def render(item: dict) -> str:
    rows = []
    for text, size, hl in item["blocks"]:
        cls = "b hl" if hl else "b"
        if size < 56:
            cls += " sm"
        rows.append(f'  <div class="{cls}" style="font-size:{size}px">{esc(text)}</div>')
    align = "top" if item.get("align") == "top" else ""
    return PAGE % (W, H, item["theme"], align,
                   "\n".join(rows), esc(item.get("sub", "")))


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
    ap.add_argument("--set", default=None)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    keys = [args.set] if args.set else list(SETS)
    for k in keys:
        for item in SETS[k]:
            dest = OUT / f"{item['name']}.png"
            shoot(render(item), dest)
            print(f"wrote {dest}")


if __name__ == "__main__":
    main()
