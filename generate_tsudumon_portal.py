# -*- coding: utf-8 -*-
"""
つづもん「本一覧トップ（歴史すごろく）」を生成する。

つづもん全体（歴史 中1〜中3・全19章の全単元）を1本の道でつなぐ すごろく。
各マス＝1単元。localStorage（各章 tzmwb-{NN} / tzmref-{NN}）を読んで、
クリア種別で見た目が変わる:
  - 未着手
  - 参考書を読んだ（tzmref-{NN}.d{refView}===1）
  - 問題を一部解いた（その単元の qid の一部に回答）
  - 問題を全部解いた（B/C/D 全問に回答）
  - 全問正解（全問に回答かつ全問 r===1）

マスをタップすると、その単元の問題集ページ（wb/{NN}/#t{wbView}）へ。
各本の問題集/参考書ホームからは「🗺 すごろく（本一覧）」でここへ戻れる。

■ 見た目（2026-07-20 リニューアル）
  中学生が「もう1マス進めたい」と思える冒険マップ調。時代ごとのエリア（原始・古代／
  中世／近世／近代／現代）に分け、看板・道・キャラの吹き出し・今日のミッションを置く。
  イラストは Codex（image-2）で作る想定で、画像が無くても CSS だけで成立し、
  画像が置かれたら自動で差し変わる（img は onerror で消える＝崩れない）。
  画像の仕様は CODEX_BRIEF_PORTAL.md を参照。

出力:
  python -X utf8 generate_tsudumon_portal.py            # output/web/index.html
  python -X utf8 generate_tsudumon_portal.py --deploy   # marutto-study/public/tsudumon/index.html
"""
import argparse
import html
import json
import shutil
from pathlib import Path

from generate_history_workbook import (
    BOOKS, CONTENT_ROOT, CONTENT_DIR,
    N_ITTOITTO, N_QUIZ, resolve_count,
)

BASE = Path(__file__).parent
REF_DIR = BASE / "reference"
CHAR_DIR = BASE / "assets" / "characters"
PORTAL_IMG_DIR = BASE / "assets" / "portal"     # Codex 製イラストの置き場（無くてよい）
OUT_FILE = BASE / "output" / "web" / "index.html"
DEPLOY_FILE = BASE.parent / "marutto-study" / "public" / "tsudumon" / "index.html"

# 時代エリア（章番号 → エリア）。すごろくをこの区切りで章立てして、看板とごほうびを置く。
ERAS = [
    {"key": "ancient",  "name": "原始・古代",   "chapters": ["01", "02", "03", "04"],
     "emoji": "🏺", "hint": "人類のはじまりから、天皇中心の国づくりまで"},
    {"key": "medieval", "name": "中世",         "chapters": ["05", "06"],
     "emoji": "⚔️", "hint": "武士が力をもち、幕府が生まれた時代"},
    {"key": "earlymod", "name": "近世",         "chapters": ["07", "08", "09", "10"],
     "emoji": "🏯", "hint": "天下統一から、江戸幕府のおわりまで"},
    {"key": "modern",   "name": "近代",         "chapters": ["11", "12", "13", "14", "15", "16"],
     "emoji": "🚂", "hint": "明治の新しい国づくりと、二つの世界大戦"},
    {"key": "current",  "name": "現代",         "chapters": ["17", "18", "19"],
     "emoji": "🗼", "hint": "戦後の復興から、いまの世界へ"},
]
ERA_OF = {ch: e["key"] for e in ERAS for ch in e["chapters"]}


def esc(s: str) -> str:
    return html.escape(str(s))


def grade_of(ch_no: int) -> str:
    if ch_no <= 6:
        return "中1"
    if ch_no <= 12:
        return "中2"
    return "中3"


def chapter_units(folder: str) -> list[dict]:
    spec = BOOKS[folder]
    era_dir = (CONTENT_ROOT / spec["contentDir"]) if spec.get("contentDir") else (CONTENT_DIR / folder)
    by_topic_id = {}
    for f in era_dir.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "topicId" in d:
            by_topic_id[d["topicId"]] = d
    topics = [by_topic_id[tid] for tid in spec["topics"]]

    ref_index = {}
    ref_path = REF_DIR / f"{folder}.json"
    if ref_path.exists():
        rs = json.loads(ref_path.read_text(encoding="utf-8"))
        for i, t in enumerate(rs["topics"], 1):
            ref_index[t["topicId"]] = i

    units = []
    for i, topic in enumerate(topics, 1):
        tid = topic["topicId"]
        nB = resolve_count(spec, "nItto", N_ITTOITTO, len(topic["flashcards"]))
        nC = resolve_count(spec, "nQuiz", N_QUIZ, len(topic["quiz"]["questions"]))
        nD = len(spec.get("written", {}).get(tid, []))
        units.append({
            "tid": tid,
            "name": topic["name"],
            "wbView": i + 1,     # wb: t0=home, t1=年表, 単元は t2〜
            "refView": ref_index.get(tid),
            "nQ": nB + nC + nD,  # B/C/D の総設問数（全部解いた判定用）
        })
    return units


def build_manifest() -> list[dict]:
    """[{grade, ch, vol, title, units:[...]}] を章順で返す（歴史のみ）。"""
    out = []
    hist = sorted(f for f in BOOKS if not f.startswith("science"))
    for folder in hist:
        ch_no = int(folder[:2])
        spec = BOOKS[folder]
        out.append({
            "grade": grade_of(ch_no),
            "ch": folder[:2],
            "vol": spec.get("volume", ""),
            "title": spec.get("title", ""),
            "units": chapter_units(folder),
        })
    return out


def img_tag(name: str, cls: str, alt: str = "") -> str:
    """img/<name> を読み込む。無ければ onerror で自分を消す＝CSS だけの見た目に戻る。"""
    return (f'<img class="{cls}" src="img/{name}" alt="{esc(alt)}" loading="lazy"'
            f' onerror="this.remove()">')


def build_html() -> str:
    manifest = build_manifest()
    total_units = sum(len(c["units"]) for c in manifest)

    # マス（セル）を章順に一列に。JS がエリアごとに配置し、状態で着色する。
    cells = []
    idx = 0
    for ch in manifest:
        for u in ch["units"]:
            idx += 1
            cells.append(
                f'<button class="cell" type="button"'
                f' data-ch="{ch["ch"]}" data-tid="{esc(u["tid"])}"'
                f' data-wb="{u["wbView"]}" data-ref="{u["refView"] if u["refView"] else ""}"'
                f' data-nq="{u["nQ"]}" data-n="{idx}"'
                f' data-grade="{ch["grade"]}" data-era="{ERA_OF[ch["ch"]]}"'
                f' data-vol="{esc(ch["vol"])}"'
                f' title="{esc(ch["vol"])} {esc(u["name"])}">'
                f'<span class="tok"><span class="tok-no">{idx}</span>'
                f'<span class="tok-badge"></span></span>'
                f'<span class="tok-name">{esc(u["name"])}</span>'
                f'</button>')

    # 本の一覧（学年タブつき）。単元行から問題集/参考書の該当ページへ直行できる。
    books = []
    for c in manifest:
        rows = "".join(
            f'<li class="u-row" data-ch="{c["ch"]}" data-tid="{esc(u["tid"])}"'
            f' data-ref="{u["refView"] if u["refView"] else ""}">'
            f'<span class="u-no">{i}</span>'
            f'<span class="u-name">{esc(u["name"])}</span>'
            f'<span class="u-state"></span>'
            f'<a class="u-btn wb" href="wb/{c["ch"]}/index.html#t{u["wbView"]}">✏️ 問題</a>'
            + (f'<a class="u-btn ref" href="ref/{c["ch"]}/index.html#t{u["refView"]}">📖 参考書</a>'
               if u["refView"] else '<span class="u-btn ref off">—</span>')
            + '</li>'
            for i, u in enumerate(c["units"], 1))
        books.append(
            f'<section class="book" data-grade="{c["grade"]}">'
            f'<button class="book-h" type="button">'
            f'<span class="bk-grade">{c["grade"]}</span>'
            f'<span class="bk-vol">{esc(c["vol"])}</span>'
            f'<span class="bk-title">{esc(c["title"])}</span>'
            f'<span class="bk-prog" data-ch="{c["ch"]}"></span>'
            f'<span class="bk-arrow">›</span></button>'
            f'<ul class="u-list">{rows}</ul></section>')

    manifest_min = [{"ch": c["ch"], "grade": c["grade"], "vol": c["vol"], "title": c["title"],
                     "n": len(c["units"])} for c in manifest]

    return (TEMPLATE
            .replace("__TOTAL__", str(total_units))
            .replace("__CELLS__", "".join(cells))
            .replace("__BOOKS__", "".join(books))
            .replace("__ERAS__", json.dumps(ERAS, ensure_ascii=False))
            .replace("__HERO__", img_tag("portal-hero.webp", "hero-img", "つづもん歴史すごろく"))
            .replace("__MASCOT__", img_tag("char_manabi_sm.png", "mascot", ""))
            .replace("__OWL__", img_tag("char_owl_sm.png", "owl", ""))
            .replace("__GOAL_IMG__", img_tag("portal-goal.webp", "goal-img", "ゴールの宝箱"))
            .replace("__MANIFEST__", json.dumps(manifest_min, ensure_ascii=False)))


TEMPLATE = r"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>つづもん 歴史すごろく｜本一覧</title>
<style>
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --cream:#fffdf8; --line:#fde68a;
          --paper:#fffaf0; --ink:#1c1917;
          --s-ref:#60a5fa; --s-some:#fbbf24; --s-all:#4ade80; --s-perfect:#f59e0b;
          --era-ancient:#f6e3c5; --era-medieval:#dfeedd; --era-earlymod:#e6e2f6;
          --era-modern:#dcecf7; --era-current:#fbe4e6; }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         color:var(--ink); padding-bottom:40px;
         background:
           radial-gradient(circle at 12% 8%, rgba(255,255,255,.85) 0 22%, transparent 22%),
           radial-gradient(circle at 88% 4%, rgba(255,255,255,.7) 0 16%, transparent 16%),
           linear-gradient(#eaf6ff 0 160px, #f4fbe9 160px 420px, #fffaf0 420px); }
  .wrap { max-width:860px; margin:0 auto; padding:0 14px; }

  /* ───── ヒーロー（看板＋キャラ） ───── */
  .hero { position:relative; max-width:860px; margin:0 auto; padding:14px 14px 0; }
  .hero-in { position:relative; border-radius:22px; overflow:hidden;
             background:linear-gradient(160deg,#7dd3fc,#bbf7d0 55%,#fef3c7);
             box-shadow:0 8px 22px rgba(120,80,20,.18); }
  .hero-img { display:block; width:100%; height:auto; }
  /* 画像が無いときのための CSS 版タイトル。画像があれば .hero-in.has-img で隠す */
  /* 右下にキャラが立つので、その幅ぶん本文を左へ寄せる（文字がキャラに隠れない） */
  .hero-txt { position:relative; padding:26px 96px 22px 18px; text-align:center; }
  .hero-in.has-img .hero-txt { position:absolute; inset:auto 0 0 0; padding:12px 14px 14px;
                               background:linear-gradient(transparent,rgba(255,253,248,.92) 55%); }
  .hero-tag { display:inline-block; background:var(--brand); color:#fff; font-weight:bold;
              padding:3px 14px; border-radius:20px; font-size:12px;
              box-shadow:0 2px 0 #7c2d12; }
  .hero-h1 { font-size:34px; color:var(--deep); margin-top:8px; letter-spacing:.02em;
             text-shadow:2px 2px 0 #fff, 4px 4px 0 rgba(180,83,9,.18); }
  .hero-sub { color:#7c4a12; font-size:13.5px; font-weight:bold; margin-top:6px; }
  .mascot { position:absolute; right:6px; bottom:0; width:104px; height:auto; z-index:2;
            filter:drop-shadow(0 3px 4px rgba(0,0,0,.2)); pointer-events:none; }

  /* ───── 進み具合パネル ───── */
  .panel { background:var(--paper); border:2px solid #f0dfb8; border-radius:18px;
           padding:14px 16px; box-shadow:0 4px 0 #f0e2c3; margin-top:14px; }
  .p-h { font-size:13px; font-weight:bold; color:var(--deep); display:flex; align-items:center; gap:6px; }
  .big { text-align:center; margin:6px 0 8px; font-weight:bold; color:var(--deep); }
  .big b { font-size:38px; color:var(--brand); line-height:1; }
  .big .sm { font-size:14px; }
  .ov-bar { height:16px; background:#f1e6cf; border-radius:10px; overflow:hidden;
            border:1.5px solid #ecd9ab; position:relative; }
  .ov-fill { height:100%; width:0; border-radius:8px; transition:width .5s cubic-bezier(.22,.72,.32,1);
             background:linear-gradient(90deg,#34d399,#fbbf24 70%,#f59e0b); }
  .ov-flag { position:absolute; right:4px; top:-3px; font-size:14px; }
  .counts { display:flex; gap:6px; margin-top:10px; }
  .cnt { flex:1; text-align:center; background:#fff; border:1.5px solid #f0e2c3; border-radius:12px;
         padding:6px 2px 5px; }
  .cnt b { display:block; font-size:19px; color:var(--deep); line-height:1.2; }
  .cnt span { font-size:10px; color:#8a7b62; }

  /* 凡例 */
  .legend { display:flex; flex-wrap:wrap; gap:6px 12px; justify-content:center;
            margin:10px auto 0; font-size:11.5px; color:#6b6154; }
  .lg { display:inline-flex; align-items:center; gap:4px; }
  .dot { width:13px; height:13px; border-radius:50%; border:2px solid rgba(0,0,0,.1); background:#fff; }
  .dot.d-ref { background:var(--s-ref); } .dot.d-some { background:var(--s-some); }
  .dot.d-all { background:var(--s-all); } .dot.d-perfect { background:var(--s-perfect); }

  /* ───── 今日のミッション ───── */
  .mission { display:flex; align-items:center; gap:12px; margin-top:12px;
             background:linear-gradient(#fff7ed,#fff);
             border:2px dashed var(--amber); border-radius:18px; padding:12px 14px; }
  .mission .owl { width:52px; height:auto; flex:none; filter:drop-shadow(0 2px 3px rgba(0,0,0,.18)); }
  .ms-body { flex:1; min-width:0; }
  .ms-h { font-size:12px; font-weight:bold; color:#b45309; }
  .ms-txt { font-size:14px; font-weight:bold; color:var(--deep); margin-top:2px; }
  .ms-steps { display:flex; gap:6px; margin-top:7px; }
  .ms-step { width:26px; height:26px; border-radius:50%; background:#fff; border:2px solid #f0dfb8;
             display:inline-flex; align-items:center; justify-content:center; font-size:13px; }
  .ms-step.on { background:var(--amber); border-color:var(--brand); color:#fff; }

  /* ───── すごろく盤 ───── */
  .board { margin-top:18px; }
  .era { position:relative; border-radius:22px; padding:14px 12px 16px; margin-bottom:16px;
         border:2px solid rgba(124,45,18,.10); }
  .era.e-ancient  { background:linear-gradient(var(--era-ancient),#fffdf6); }
  .era.e-medieval { background:linear-gradient(var(--era-medieval),#fffdf6); }
  .era.e-earlymod { background:linear-gradient(var(--era-earlymod),#fffdf6); }
  .era.e-modern   { background:linear-gradient(var(--era-modern),#fffdf6); }
  .era.e-current  { background:linear-gradient(var(--era-current),#fffdf6); }
  /* エリア看板（木の札風） */
  .sign { display:inline-flex; align-items:center; gap:8px; background:linear-gradient(#c89a5b,#a97b3f);
          color:#fff8ec; font-weight:bold; border-radius:12px; padding:6px 16px;
          box-shadow:0 4px 0 #7d5a2b, 0 6px 10px rgba(90,60,20,.25); font-size:15px;
          border:2px solid #8a6431; }
  .sign .s-emoji { font-size:17px; }
  .sign .s-range { font-size:11px; background:rgba(255,255,255,.25); border-radius:8px; padding:1px 7px; }
  .era-hint { font-size:11.5px; color:#7c5a2a; margin:7px 2px 10px; font-weight:bold; }

  /* 1行目は「つぎはここ！」の旗が見出しに重ならないよう上に余白 */
  .row { display:flex; gap:8px; align-items:flex-start; position:relative; margin:18px 0 12px; }
  .row.rev { flex-direction:row-reverse; }
  /* マスをつなぐ点線の道。--span＝実際にマスがある幅の割合（端数の行で線が余らない） */
  .row::before { content:""; position:absolute; left:6%; top:31px; height:6px; z-index:0;
                 width:calc(var(--span,100%) - 12%);
                 background:repeating-linear-gradient(90deg,#e8d6ae 0 12px, transparent 12px 22px);
                 border-radius:3px; }
  .row.rev::before { left:auto; right:6%; }
  .cell { position:relative; z-index:1; flex:0 0 calc((100% - (var(--row,4) - 1) * 8px) / var(--row,4));
          min-width:0; border:none; background:none;
          cursor:pointer; font-family:inherit; padding:0; display:flex; flex-direction:column;
          align-items:center; gap:4px; }
  .tok { position:relative; width:56px; height:56px; border-radius:50%; background:#fff;
         border:3px solid #e2cfa4; display:flex; flex-direction:column; align-items:center;
         justify-content:center;
         box-shadow:0 5px 0 #e2cfa4, 0 7px 10px rgba(120,80,20,.18);
         transition:transform .12s, box-shadow .12s, background-color .2s, border-color .2s; }
  .tok-no { font-weight:bold; font-size:17px; color:#8a7b62; line-height:1; }
  .tok-badge { position:absolute; right:-4px; top:-6px; font-size:15px; line-height:1;
               filter:drop-shadow(0 1px 1px rgba(0,0,0,.2)); }
  .tok-name { font-size:9.5px; color:#6b6154; line-height:1.25; text-align:center;
              max-height:2.6em; overflow:hidden; }

  .cell.s-ref  .tok { background:#eff6ff; border-color:var(--s-ref); box-shadow:0 5px 0 #93c5fd,0 7px 10px rgba(59,130,246,.22); }
  .cell.s-some .tok { background:#fffbeb; border-color:var(--s-some); box-shadow:0 5px 0 #f6d264,0 7px 10px rgba(245,158,11,.24); }
  .cell.s-all  .tok { background:#f0fdf4; border-color:var(--s-all); box-shadow:0 5px 0 #86efac,0 7px 10px rgba(22,163,74,.22); }
  .cell.s-perfect .tok { background:linear-gradient(#fffbe6,#fde68a); border-color:var(--amber);
                         box-shadow:0 5px 0 #eab308,0 8px 12px rgba(234,179,8,.4); }
  .cell.s-ref .tok-no, .cell.s-some .tok-no, .cell.s-all .tok-no, .cell.s-perfect .tok-no { color:var(--deep); }
  .cell.s-perfect .tok::after { content:""; position:absolute; inset:-7px; border-radius:50%;
                                border:2px dashed rgba(245,158,11,.55); animation:spin 9s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }

  /* いま挑戦中のマス＝旗つきで光る */
  .cell.current .tok { border-color:var(--brand); background:#fff;
                       box-shadow:0 5px 0 var(--brand), 0 0 0 4px rgba(180,83,9,.18), 0 10px 14px rgba(180,83,9,.3);
                       animation:pulse 1.8s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-3px); } }
  .cell.current::before { content:"つぎはここ！"; position:absolute; top:-17px; left:50%;
                          transform:translateX(-50%); background:var(--brand); color:#fff;
                          font-size:9.5px; font-weight:bold; padding:2px 8px; border-radius:9px;
                          white-space:nowrap; box-shadow:0 2px 4px rgba(0,0,0,.2); z-index:3; }
  .cell.here .tok::before { content:"🧑‍🎓"; position:absolute; top:-22px; left:50%;
                            transform:translateX(-50%); font-size:21px;
                            filter:drop-shadow(0 2px 2px rgba(0,0,0,.25)); }

  @media (hover:hover) { .cell:hover .tok { transform:translateY(-3px); } }
  .cell:active .tok { transform:translateY(3px); box-shadow:0 2px 0 #e2cfa4,0 3px 5px rgba(120,80,20,.18); }

  /* スタート／ゴール */
  .flagpost { display:flex; align-items:center; justify-content:center; gap:10px; margin:2px 0 12px; }
  .flagpost .fp { background:linear-gradient(#f97316,#ea580c); color:#fff; font-weight:bold;
                  border-radius:12px; padding:6px 20px; font-size:15px;
                  box-shadow:0 4px 0 #9a3412; letter-spacing:.08em; }
  .goal { text-align:center; margin:6px 0 0; }
  .goal-img { width:120px; height:auto; }
  .goal .g-box { display:inline-flex; flex-direction:column; align-items:center; gap:4px;
                 background:linear-gradient(#fff7ed,#fef3c7); border:2px solid var(--amber);
                 border-radius:18px; padding:12px 26px; box-shadow:0 5px 0 #eab308; }
  .goal .g-t { font-weight:bold; color:var(--deep); font-size:16px; }
  .goal .g-s { font-size:11.5px; color:#92400e; }

  /* ───── 本の一覧 ───── */
  .books { margin-top:26px; }
  .books-h { display:flex; align-items:center; gap:8px; justify-content:center; margin-bottom:10px; }
  .books-h h2 { font-size:17px; color:var(--deep); }
  .tabs { display:flex; gap:6px; justify-content:center; margin-bottom:12px; }
  .tab { border:2px solid #f0dfb8; background:#fff; color:var(--brand); font-weight:bold;
         border-radius:20px; padding:5px 16px; font-size:13px; cursor:pointer; font-family:inherit;
         box-shadow:0 3px 0 #f0e2c3; }
  .tab.on { background:var(--brand); color:#fff; border-color:var(--brand); box-shadow:0 3px 0 #7c2d12; }
  .book { background:var(--paper); border:2px solid #f0dfb8; border-radius:16px; margin-bottom:9px;
          overflow:hidden; box-shadow:0 3px 0 #f0e2c3; }
  .book-h { width:100%; display:flex; align-items:center; gap:8px; padding:10px 12px; cursor:pointer;
            background:none; border:none; font-family:inherit; text-align:left; }
  .bk-grade { flex:none; background:#fff3d6; color:var(--brand); font-weight:bold; font-size:11px;
              border-radius:8px; padding:2px 8px; border:1.5px solid var(--line); }
  .bk-vol { flex:none; font-weight:bold; color:var(--brand); font-size:12.5px; }
  .bk-title { flex:1; font-size:14px; font-weight:bold; color:#44403c; min-width:0; }
  .bk-prog { flex:none; font-size:11px; color:#8a7b62; font-weight:bold; }
  .bk-arrow { flex:none; color:var(--brand); font-size:20px; transition:transform .2s; }
  .book.open .bk-arrow { transform:rotate(90deg); }
  .u-list { display:none; padding:0 10px 10px; list-style:none; }
  .book.open .u-list { display:block; }
  .u-row { display:flex; align-items:center; gap:7px; padding:7px 4px; border-top:1px dashed #f0dfb8; }
  .u-no { flex:none; width:20px; height:20px; border-radius:6px; background:#fff; border:1.5px solid var(--line);
          color:var(--brand); font-weight:bold; font-size:11px; display:inline-flex;
          align-items:center; justify-content:center; }
  .u-name { flex:1; font-size:13px; min-width:0; }
  .u-state { flex:none; font-size:13px; width:16px; text-align:center; }
  .u-btn { flex:none; text-decoration:none; font-size:11.5px; font-weight:bold; border-radius:9px;
           padding:4px 9px; white-space:nowrap; }
  .u-btn.wb { background:var(--brand); color:#fff; box-shadow:0 2px 0 #7c2d12; }
  .u-btn.ref { background:#fff; color:var(--brand); border:1.5px solid var(--line); }
  .u-btn.off { color:#d6d3d1; border-color:#eee; box-shadow:none; }

  footer { text-align:center; margin-top:26px; color:#a8a29e; font-size:12px; }

  /* 画面が広いときはマスを大きめに */
  @media (min-width:640px) {
    .tok { width:66px; height:66px; }
    .tok-no { font-size:19px; }
    .tok-name { font-size:11px; }
    .row::before { top:36px; }
  }
</style></head><body>

<div class="hero">
  <div class="hero-in" id="heroIn">
    __HERO__
    <div class="hero-txt">
      <span class="hero-tag">つづもん 歴史</span>
      <h1 class="hero-h1">歴史すごろく</h1>
      <div class="hero-sub">マスを進めて、日本の歴史を制覇しよう！</div>
    </div>
    __MASCOT__
  </div>
</div>

<div class="wrap">
  <div class="panel">
    <div class="p-h">🏁 きみの進み具合</div>
    <div class="big"><b id="ovNum">0</b><span class="sm"> / __TOTAL__ マス</span>
      <span class="sm" id="ovPct">（0%）</span></div>
    <div class="ov-bar"><div class="ov-fill" id="ovFill"></div><span class="ov-flag">🚩</span></div>
    <div class="counts">
      <div class="cnt"><b id="cNone">0</b><span>まだ</span></div>
      <div class="cnt"><b id="cRef">0</b><span>📖 読んだ</span></div>
      <div class="cnt"><b id="cSome">0</b><span>✏️ 一部</span></div>
      <div class="cnt"><b id="cAll">0</b><span>✅ 全部</span></div>
      <div class="cnt"><b id="cPerfect">0</b><span>👑 全問正解</span></div>
    </div>
    <div class="legend">
      <span class="lg"><span class="dot"></span>まだ</span>
      <span class="lg"><span class="dot d-ref"></span>参考書を読んだ</span>
      <span class="lg"><span class="dot d-some"></span>一部を解いた</span>
      <span class="lg"><span class="dot d-all"></span>全部解いた</span>
      <span class="lg"><span class="dot d-perfect"></span>全問正解</span>
    </div>
  </div>

  <div class="mission">
    __OWL__
    <div class="ms-body">
      <div class="ms-h">🎯 今日のミッション</div>
      <div class="ms-txt" id="msTxt">今日は 3マス すすめよう！</div>
      <div class="ms-steps" id="msSteps"></div>
    </div>
  </div>

  <div class="board" id="board">
    <div class="flagpost"><span class="fp">🏁 スタート</span></div>
    <div id="cells" hidden>__CELLS__</div>
    <div class="goal">
      <div class="g-box">__GOAL_IMG__
        <div class="g-t">🏆 ゴール：歴史マスター</div>
        <div class="g-s">全__TOTAL__マスを制覇せよ！</div>
      </div>
    </div>
  </div>

  <div class="books">
    <div class="books-h"><h2>📚 本の一覧</h2></div>
    <div class="tabs" id="tabs">
      <button class="tab on" data-g="all">すべて</button>
      <button class="tab" data-g="中1">中1</button>
      <button class="tab" data-g="中2">中2</button>
      <button class="tab" data-g="中3">中3</button>
    </div>
    <div id="bookList">__BOOKS__</div>
  </div>
</div>
<footer>つづもん 歴史すごろく　｜　全__TOTAL__単元</footer>

<script>
(function () {
  var MANIFEST = __MANIFEST__;
  var ERAS = __ERAS__;
  var ROW = window.matchMedia('(min-width:640px)').matches ? 6 : 4;   // 1行のマス数（snake配置）

  function ls(key) { try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) { return {}; } }

  // 単元ごとのクリア種別を求める（保存形式は問題集/参考書 Web版と共通）
  function stateOf(ch, tid, nq, refV) {
    var wb = ls('tzmwb-' + ch), r = wb.r || {};
    var done = 0, correct = 0;
    var pref = ['qa-' + tid + '-', 'qz-' + tid + '-', 'wr-' + tid + '-'];
    Object.keys(r).forEach(function (k) {
      for (var i = 0; i < pref.length; i++) {
        if (k.indexOf(pref[i]) === 0) { done++; if (r[k] === 1) correct++; break; }
      }
    });
    var refRead = refV && ls('tzmref-' + ch)['d' + refV] === 1;
    if (nq > 0 && done >= nq && correct >= nq) return 'perfect';
    if (nq > 0 && done >= nq) return 'all';
    if (done > 0) return 'some';
    if (refRead) return 'ref';
    return 'none';
  }
  function cellState(c) {
    return stateOf(c.dataset.ch, c.dataset.tid, +c.dataset.nq || 0, c.dataset.ref);
  }

  // 時代エリアごとに看板を立て、snake（うねうね）配置で道をつくる
  function layout() {
    var board = document.getElementById('board');
    var goal = board.querySelector('.goal');
    var all = [].slice.call(document.querySelectorAll('#cells .cell'));
    [].forEach.call(board.querySelectorAll('.era'), function (el) { el.remove(); });

    ERAS.forEach(function (era) {
      var list = all.filter(function (c) { return c.dataset.era === era.key; });
      if (!list.length) return;
      var box = document.createElement('div');
      box.className = 'era e-' + era.key;
      var first = list[0].dataset.n, last = list[list.length - 1].dataset.n;
      box.innerHTML = '<div><span class="sign"><span class="s-emoji">' + era.emoji + '</span>'
        + era.name + '<span class="s-range">' + first + '〜' + last + '</span></span></div>'
        + '<div class="era-hint">' + era.hint + '</div>';
      for (var i = 0; i < list.length; i += ROW) {
        var row = document.createElement('div');
        row.className = 'row' + ((i / ROW) % 2 === 1 ? ' rev' : '');
        var slice = list.slice(i, i + ROW);
        slice.forEach(function (c) { row.appendChild(c); });
        // マスの幅は常に1行ぶんで割る（端数の行でもマスが大きくならない）。
        // 道の点線も実際にマスがあるぶんだけ伸ばす。
        row.style.setProperty('--row', ROW);
        row.style.setProperty('--span', (slice.length / ROW * 100) + '%');
        box.appendChild(row);
      }
      board.insertBefore(box, goal);
    });
  }

  function paint() {
    var cells = [].slice.call(document.querySelectorAll('.cell[data-tid]'));
    var n = { none: 0, ref: 0, some: 0, all: 0, perfect: 0 };
    var cleared = 0, lastCleared = -1;
    var byCh = {};
    cells.forEach(function (c, i) {
      c.classList.remove('s-ref', 's-some', 's-all', 's-perfect', 'here', 'current');
      var s = cellState(c);
      n[s]++;
      var badge = c.querySelector('.tok-badge');
      if (s !== 'none') {
        c.classList.add('s-' + s);
        badge.textContent = s === 'perfect' ? '👑' : s === 'all' ? '✅' : s === 'some' ? '✏️' : '📖';
        cleared++; lastCleared = i;
      } else { badge.textContent = ''; }
      byCh[c.dataset.ch] = byCh[c.dataset.ch] || { done: 0, all: 0 };
      byCh[c.dataset.ch].all++;
      if (s !== 'none') byCh[c.dataset.ch].done++;
    });
    if (lastCleared >= 0) cells[lastCleared].classList.add('here');
    var nextIdx = lastCleared + 1;
    while (nextIdx < cells.length && cells[nextIdx].classList.contains('s-perfect')) nextIdx++;
    if (nextIdx < cells.length) cells[nextIdx].classList.add('current');
    else if (lastCleared < 0 && cells[0]) cells[0].classList.add('current');

    var pct = cells.length ? Math.round((cleared / cells.length) * 100) : 0;
    document.getElementById('ovFill').style.width = pct + '%';
    document.getElementById('ovNum').textContent = cleared;
    document.getElementById('ovPct').textContent = '（' + pct + '%）';
    document.getElementById('cNone').textContent = n.none;
    document.getElementById('cRef').textContent = n.ref;
    document.getElementById('cSome').textContent = n.some;
    document.getElementById('cAll').textContent = n.all;
    document.getElementById('cPerfect').textContent = n.perfect;

    // 本の一覧: 章ごとの進み具合と、単元行の状態マーク
    [].forEach.call(document.querySelectorAll('.bk-prog'), function (el) {
      var b = byCh[el.dataset.ch] || { done: 0, all: 0 };
      el.textContent = b.done + '/' + b.all;
    });
    [].forEach.call(document.querySelectorAll('.u-row'), function (el) {
      var m = { perfect: '👑', all: '✅', some: '✏️', ref: '📖', none: '' };
      var nq = 0;
      var cell = document.querySelector('.cell[data-ch="' + el.dataset.ch + '"][data-tid="' + el.dataset.tid + '"]');
      if (cell) nq = +cell.dataset.nq || 0;
      el.querySelector('.u-state').textContent = m[stateOf(el.dataset.ch, el.dataset.tid, nq, el.dataset.ref)];
    });

    mission(cleared);
  }

  // 今日のミッション: その日はじめてのアクセス時のクリア数を基準に、今日進めたマス数を数える
  function mission(cleared) {
    var GOAL = 3, today = new Date().toISOString().slice(0, 10), key = 'tzmportal';
    var st = ls(key);
    if (st.date !== today) { st = { date: today, base: cleared }; localStorage.setItem(key, JSON.stringify(st)); }
    if (cleared < st.base) { st.base = cleared; localStorage.setItem(key, JSON.stringify(st)); }
    var got = Math.max(0, cleared - st.base);
    var steps = document.getElementById('msSteps');
    steps.innerHTML = '';
    for (var i = 0; i < GOAL; i++) {
      var s = document.createElement('span');
      s.className = 'ms-step' + (i < got ? ' on' : '');
      s.textContent = i < got ? '★' : (i + 1);
      steps.appendChild(s);
    }
    document.getElementById('msTxt').textContent = got >= GOAL
      ? '今日のミッション達成！ すごい！'
      : '今日は あと ' + (GOAL - got) + 'マス すすめよう！';
  }

  // マスをタップ → その単元の問題集へ
  document.addEventListener('click', function (e) {
    var cell = e.target.closest ? e.target.closest('.cell[data-tid]') : null;
    if (cell) { location.href = 'wb/' + cell.dataset.ch + '/index.html#t' + cell.dataset.wb; return; }
    var bh = e.target.closest ? e.target.closest('.book-h') : null;
    if (bh) { bh.parentNode.classList.toggle('open'); return; }
    var tab = e.target.closest ? e.target.closest('.tab') : null;
    if (tab) {
      [].forEach.call(document.querySelectorAll('.tab'), function (t) { t.classList.toggle('on', t === tab); });
      var g = tab.dataset.g;
      [].forEach.call(document.querySelectorAll('.book'), function (b) {
        b.style.display = (g === 'all' || b.dataset.grade === g) ? '' : 'none';
      });
    }
  });

  // ヒーロー画像が実際に表示できたときだけ、CSS版タイトルを画像の上へ重ねる
  var heroImg = document.querySelector('.hero-img');
  if (heroImg) heroImg.addEventListener('load', function () {
    document.getElementById('heroIn').classList.add('has-img');
  });

  document.getElementById('cells').hidden = false;
  layout();
  paint();
  window.addEventListener('focus', paint);
  window.addEventListener('pageshow', paint);
})();
</script>
</body></html>"""


def copy_assets(dest_root: Path) -> None:
    """キャラ画像と（あれば）Codex 製のポータル用イラストを img/ へ配る。"""
    img_dir = dest_root / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    for name in ("char_manabi_sm.png", "char_owl_sm.png"):
        src = CHAR_DIR / name
        if src.exists():
            shutil.copyfile(src, img_dir / name)
    if PORTAL_IMG_DIR.exists():
        for src in PORTAL_IMG_DIR.glob("portal-*"):
            shutil.copyfile(src, img_dir / src.name)


def generate(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(build_html(), encoding="utf-8")
    copy_assets(dest.parent)
    print(f"generated: {dest}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true",
                    help="marutto-study/public/tsudumon/index.html へ出力")
    args = ap.parse_args()
    generate(DEPLOY_FILE if args.deploy else OUT_FILE)
