# 整理後の参考書PDF（output/03_参考書/歴史/中*/）を巻順にマージして総合版を作り直す。
# 通常は merge_reference.py（flat ref-*.pdf 前提）を使うが、organize 済みで flat が無いとき用。
import glob
import re
import os
import fitz

from add_page_numbers import number

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = glob.glob(os.path.join(BASE, "output", "03_参考書", "歴史", "中*", "*.pdf"))


def volume_no(path: str) -> int:
    """ファイル名の丸数字（①..⑲）から巻番号を得る。"""
    name = os.path.basename(path)
    for ch in name:
        code = ord(ch)
        if 0x2460 <= code <= 0x2473:  # ①(1)..⑳(20)
            return code - 0x2460 + 1
    return 999


items = sorted(SRC, key=volume_no)
merged = fitz.open()
toc = []
for p in items:
    start = merged.page_count
    with fitz.open(p) as d:
        merged.insert_pdf(d)
    # しおり = 「歴史① 年代の表し方」（（参考書）と拡張子を除く）
    title = os.path.splitext(os.path.basename(p))[0].replace("（参考書）", "").strip()
    toc.append([1, title, start + 1])

merged.set_toc(toc)
number(merged)  # 全体の通し番号（フッター中央）
out = os.path.join(BASE, "output", "04_総合版", "歴史参考書_総合版.pdf")
merged.save(out, deflate=True, garbage=3)
print(f"結合完了 {len(items)}冊 / 全{merged.page_count}ページ / しおり{len(toc)}件")
print("出力:", out, os.path.getsize(out), "bytes")
