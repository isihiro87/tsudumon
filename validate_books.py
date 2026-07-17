# -*- coding: utf-8 -*-
"""books/*.json の整合性チェック。
- 必須キーの有無 / topics が実フォルダの全JSONと一致・order順
- summaries が全 topicId をカバー / 空欄数・文字数が基準内
- timeline 行数 / 空欄の有無
- [[ ]] にルビ記法が混入していないか
"""
import json
import re
import sys
from pathlib import Path

CONTENT_ROOT = Path(r"C:\Users\user\projects\education-apps\marutto-study\data\content")
CONTENT_DIR = CONTENT_ROOT / "history"
BOOKS_DIR = Path(__file__).parent / "books"
BLANK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

ok = True
for spec_path in sorted(BOOKS_DIR.glob("*.json")):
    folder = spec_path.stem
    errors, warns = [], []
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[NG] {folder}: JSONパース失敗 {e}")
        ok = False
        continue

    for key in ("volume", "title", "subtitle", "topics", "timeline", "summaries"):
        if key not in spec:
            errors.append(f"キー欠落: {key}")
    if errors:
        print(f"[NG] {folder}: " + " / ".join(errors))
        ok = False
        continue

    # 理科等は spec["contentDir"] で章フォルダを指す
    era_dir = (CONTENT_ROOT / spec["contentDir"]) if spec.get("contentDir") else (CONTENT_DIR / folder)
    actual = {}
    for f in era_dir.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        actual[d["topicId"]] = d["order"]
    expected = [t for t, _ in sorted(actual.items(), key=lambda kv: kv[1])]

    if set(spec["topics"]) != set(actual):
        missing = set(actual) - set(spec["topics"])
        extra = set(spec["topics"]) - set(actual)
        errors.append(f"topics不一致 欠落={sorted(missing)} 余分={sorted(extra)}")
    elif spec["topics"] != expected:
        warns.append(f"topicsがorder順でない（期待: {expected}）")

    if not (10 <= len(spec["timeline"]) <= 20):
        warns.append(f"timeline行数={len(spec['timeline'])}")
    for row in spec["timeline"]:
        if not (isinstance(row, list) and len(row) == 2):
            errors.append(f"timeline行の形式不正: {row}")
            break
    tl_blanks = sum(len(BLANK_RE.findall(ev)) for _, ev in spec["timeline"])
    if tl_blanks < len(spec["timeline"]) * 0.7:
        warns.append(f"timelineの空欄が少ない({tl_blanks})")

    for tid in spec["topics"]:
        s = spec["summaries"].get(tid)
        if not s:
            errors.append(f"summary欠落: {tid}")
            continue
        blanks = BLANK_RE.findall(s)
        plain = BLANK_RE.sub(lambda m: m.group(1), s)
        if not (4 <= len(blanks) <= 12):
            warns.append(f"{tid}: 空欄{len(blanks)}個")
        if not (180 <= len(plain) <= 550):
            warns.append(f"{tid}: {len(plain)}字")
        if "{" in s or "}" in s:
            errors.append(f"{tid}: ルビ記法混入")
        dup = [b for b in set(blanks) if blanks.count(b) > 1]
        if dup:
            warns.append(f"{tid}: 空欄重複 {dup}")

    written = spec.get("written")
    if written is None:
        warns.append("written 未追加")
    else:
        for tid in spec["topics"]:
            items = written.get(tid)
            if not items:
                errors.append(f"written欠落: {tid}")
                continue
            if len(items) != 2:
                warns.append(f"{tid}: written {len(items)}問")
            for j, w in enumerate(items, 1):
                if not w.get("q") or not w.get("a"):
                    errors.append(f"{tid} written({j}): q/a欠落")
                    continue
                if not (30 <= len(w["a"]) <= 130):
                    warns.append(f"{tid} written({j}): 模範解答{len(w['a'])}字")
                for k in w.get("keywords", []):
                    if k not in w["a"]:
                        warns.append(f"{tid} written({j}): 指定語句「{k}」が模範解答にない")

    if errors:
        print(f"[NG] {folder}: " + " / ".join(errors))
        ok = False
    elif warns:
        print(f"[warn] {folder}: " + " / ".join(warns))
    else:
        print(f"[OK] {folder}")

sys.exit(0 if ok else 1)
