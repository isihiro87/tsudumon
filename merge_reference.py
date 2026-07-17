# -*- coding: utf-8 -*-
"""
参考書19冊を1つのPDFに結合した「参考書 総合版」を作る（各章の先頭にしおり）。

使い方:
  python -X utf8 merge_reference.py   # output/ref-*.pdf 19冊 → output/_歴史参考書_総合版.pdf
"""
import json
import re
from pathlib import Path

import fitz

BASE = Path(__file__).parent
OUT = BASE / "output"
REF = BASE / "reference"


def main() -> None:
    items = []
    for pdf in OUT.glob("ref-*.pdf"):
        m = re.match(r"ref-(\d{2})-", pdf.stem)
        if not m:
            continue
        chapter = pdf.stem[len("ref-"):]
        j = json.loads((REF / f"{chapter}.json").read_text(encoding="utf-8"))
        title = f"{j.get('volume', '')} {j.get('title', '')}".strip()
        items.append((int(m.group(1)), title, pdf))
    items.sort(key=lambda x: x[0])

    if not items:
        print("対象PDF（output/ref-*.pdf）が見つかりません")
        return

    merged = fitz.open()
    toc = []
    for _, title, pdf in items:
        start = merged.page_count
        with fitz.open(pdf) as d:
            merged.insert_pdf(d)
        toc.append([1, title, start + 1])
    merged.set_toc(toc)

    out = OUT / "_歴史参考書_総合版.pdf"
    merged.save(out, garbage=4, deflate=True)
    print(f"{len(items)}冊を結合 → {out}（全{merged.page_count}ページ・しおり{len(toc)}件）")
    merged.close()


if __name__ == "__main__":
    main()
