# -*- coding: utf-8 -*-
"""
各単元（章）ごとのPDFに、総合版と同じページ番号を振る。

総合版は章順に結合しているので、各章に「その章の総合版内での開始ページ番号」から
連番を振れば、単元PDFのページ番号＝総合版のページ番号になる（＝通し番号が一致）。

使い方:
  python -X utf8 number_per_unit.py --target workbook   # output/[0-9][0-9]-*.pdf（結合前のルート）
  python -X utf8 number_per_unit.py --target reference  # output/03_参考書/歴史/中*/*.pdf
"""
import argparse
import glob
import os
import re

import fitz

from add_page_numbers import number

BASE = os.path.dirname(os.path.abspath(__file__))


def volume_no(path: str) -> int:
    """ファイル名の丸数字（①..⑲）から巻番号を得る（総合版の結合順と同じ）。"""
    for ch in os.path.basename(path):
        code = ord(ch)
        if 0x2460 <= code <= 0x2473:
            return code - 0x2460 + 1
    return 999


def chapter_no(path: str) -> int:
    m = re.match(r"(\d{2})", os.path.basename(path))
    return int(m.group(1)) if m else 999


def stamp_with_offsets(ordered_paths):
    """並び順どおりに、前の章までの累計ページを開始番号として各章へ通し番号を振る。"""
    start = 1
    for p in ordered_paths:
        doc = fitz.open(p)
        nxt = number(doc, start=start)
        tmp = p + ".num.tmp"
        doc.save(tmp, garbage=3, deflate=True)
        doc.close()
        os.replace(tmp, p)
        print(f"  p.{start:>3}–{nxt - 1:<3}  {os.path.basename(p)}")
        start = nxt
    print(f"合計 {start - 1} ページ / {len(ordered_paths)} 冊")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True,
                    choices=["workbook", "science", "reference"])
    args = ap.parse_args()

    if args.target == "workbook":
        paths = glob.glob(os.path.join(BASE, "output", "[0-9][0-9]-*.pdf"))
        paths = sorted(paths, key=chapter_no)
    elif args.target == "science":
        # 理科は総合版の結合順（merge_pdf.collect）と完全一致させる
        from merge_pdf import collect
        paths = [str(src) for _name, src in collect("science")]
    else:
        paths = glob.glob(os.path.join(BASE, "output", "03_参考書", "歴史", "中*", "*.pdf"))
        paths = sorted(paths, key=volume_no)

    if not paths:
        print("対象PDFが見つかりません")
        return
    stamp_with_offsets(paths)


if __name__ == "__main__":
    main()
