# -*- coding: utf-8 -*-
"""A4版トピック表紙（covers/out/topics/*.png）を Web埋め込み用 webp に変換する。

使い方: python -X utf8 covers/convert_web_covers.py
出力: covers/out/webtopics/{章}-{topicId}.webp（幅1000px・quality82・平均約90KB）

フロー: gen_topic_covers.py（表紙再生成）→ 本スクリプト → generate_reference_web.py
（Web版参考書の「この単元でわかること」画面がこの webp を埋め込む）
"""
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parent
SRC = BASE / "out" / "topics"
DST = BASE / "out" / "webtopics"


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for png in sorted(SRC.glob("*.png")):
        im = Image.open(png).convert("RGB")
        im.thumbnail((1000, 10000))
        im.save(DST / f"{png.stem}.webp", "WEBP", quality=82)
        count += 1
    print(f"converted: {count} → {DST}")


if __name__ == "__main__":
    main()
