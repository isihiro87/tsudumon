# -*- coding: utf-8 -*-
"""assets/quest/ の Codex 生成 PNG を、配信用の WebP に変換する。

image_generation が出す PNG はそのままだと 1枚 1〜3MB あり、スマホには重すぎる。
用途ごとに長辺を詰めてから WebP 化する（透過は維持）。変換後は .webp だけを
generate_tsudumon_portal.py が配る（PNG は原本として残す）。

    python -X utf8 tools/quest_assets_to_webp.py
"""
from pathlib import Path

from PIL import Image

QUEST = Path(__file__).resolve().parent.parent / "assets" / "quest"

# ファイル名の接頭辞 → (長辺の上限, 品質)
RULES = [
    ("quest-bg",     (1080, 78)),
    ("quest-island", (900, 76)),
    ("quest-title",  (760, 88)),
    ("quest-badge",  (128, 90)),
    ("quest-",       (420, 88)),   # explorer / bird / chest などのキャラ
]


def rule_for(name: str) -> tuple[int, int]:
    for prefix, spec in RULES:
        if name.startswith(prefix):
            return spec
    return (900, 82)


def main() -> None:
    total_in = total_out = 0
    for src in sorted(QUEST.glob("quest-*.png")):
        if src.stem.startswith("quest-top-"):
            continue                      # カンプ画像そのものは配信しない
        limit, quality = rule_for(src.stem)
        im = Image.open(src).convert("RGBA")
        if max(im.size) > limit:
            scale = limit / max(im.size)
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        dst = src.with_suffix(".webp")
        im.save(dst, "WEBP", quality=quality, method=6)
        total_in += src.stat().st_size
        total_out += dst.stat().st_size
        print(f"{src.name:32} {src.stat().st_size/1024:8.0f}KB -> "
              f"{dst.name:33} {dst.stat().st_size/1024:7.0f}KB  {im.width}x{im.height}")
    print(f"\ntotal: {total_in/1024/1024:.1f}MB -> {total_out/1024/1024:.2f}MB")


if __name__ == "__main__":
    main()
