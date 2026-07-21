# -*- coding: utf-8 -*-
"""
つづもん「本一覧トップ（歴史クエスト）」を生成する。

歴史 中1〜中3・全19章の全単元を、**学年ごとに独立した冒険マップ**として並べる。
各マス＝1単元。localStorage（各章 tzmwb-{NN} / tzmref-{NN}）を読んで、
クリア種別で見た目が変わる:
  - 未着手
  - 参考書を読んだ（tzmref-{NN}.d{refView}===1）
  - 問題を一部解いた（その単元の qid の一部に回答）
  - 問題を全部解いた（B/C/D 全問に回答）
  - 全問正解（全問に回答かつ全問 r===1）

マスをタップすると、その単元の問題集ページ（wb/{NN}/#t{wbView}）へ。
各本の問題集/参考書ホームからは「🗺 歴史クエスト（本一覧）」でここへ戻れる。

■ 学年（2026-07-20）
  マップも本の一覧も「いま選んでいる学年」ぶんだけを表示する。
  どの学年を持っているかは **配布URLのパラメータ** で渡す:

      index.html?g=1,2      … 中1・中2 を登録
      index.html?g=中1      … 中1 だけ
      index.html?g=all      … 全学年

  受け取った時点で localStorage['tzmgrades'] に保存するので、2回目以降は
  パラメータなしのURLでも同じ学年が出る。**2学年以上のときだけ**上部に
  学年タブが出て切り替えられる（1学年ならタブは出さない）。
  パラメータも保存もない場合は全学年（体験・確認用）。

■ 見た目（2026-07-20 リニューアル）
  古地図・羊皮紙調の縦長カンプ `assets/quest/quest-top-mobile.png` を再現。
  イラストは Codex（image_generation）で作る想定で、画像が無くても CSS だけで
  成立し、画像が置かれたら自動で差し変わる（img は onerror で消える＝崩れない）。
  画像の仕様は CODEX_BRIEF_QUEST_MOBILE.md を参照。

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
QUEST_IMG_DIR = BASE / "assets" / "quest"       # 同上（歴史クエスト用）
OUT_FILE = BASE / "output" / "web" / "index.html"
DEPLOY_FILE = BASE.parent / "marutto-study" / "public" / "tsudumon" / "index.html"

GRADES = ["中1", "中2", "中3"]

# 時代エリア（章番号 → エリア）。マップをこの区切りで島に分けて、看板を立てる。
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
    """[{grade, ch, no, vol, title, units:[...]}] を章順で返す（歴史のみ）。"""
    out = []
    hist = sorted(f for f in BOOKS if not f.startswith("science"))
    for folder in hist:
        ch_no = int(folder[:2])
        spec = BOOKS[folder]
        out.append({
            "grade": grade_of(ch_no),
            "ch": folder[:2],
            "no": ch_no,          # 「冒険N」の N（全学年通し）
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
    # 学年ごとのマス数（進捗の分母は「その学年の中で」数える）
    grade_total = {g: sum(len(c["units"]) for c in manifest if c["grade"] == g) for g in GRADES}

    # マス（セル）。JS が「いま選んでいる学年」ぶんだけを島に並べる。
    # data-n は全学年通し、data-gn は学年内の通し番号（マスに出る数字）。
    cells = []
    idx = 0
    gidx = {g: 0 for g in GRADES}
    for ch in manifest:
        for u in ch["units"]:
            idx += 1
            gidx[ch["grade"]] += 1
            cells.append(
                f'<button class="cell" type="button"'
                f' data-ch="{ch["ch"]}" data-tid="{esc(u["tid"])}"'
                f' data-wb="{u["wbView"]}" data-ref="{u["refView"] if u["refView"] else ""}"'
                f' data-nq="{u["nQ"]}" data-n="{idx}" data-gn="{gidx[ch["grade"]]}"'
                f' data-grade="{ch["grade"]}" data-era="{ERA_OF[ch["ch"]]}"'
                f' data-vol="{esc(ch["vol"])}"'
                f' title="{esc(ch["vol"])} {esc(u["name"])}">'
                f'<span class="tok"><span class="tok-no">{gidx[ch["grade"]]}</span>'
                f'<span class="tok-badge"></span></span>'
                f'<span class="tok-name">{esc(u["name"])}</span>'
                f'</button>')

    # 単元一覧。学年で絞り込み、章の帯＋単元行をそのまま並べる（開閉なし＝カンプと同じ密度）。
    books = []
    for c in manifest:
        rows = "".join(
            f'<li class="u-row" data-ch="{c["ch"]}" data-tid="{esc(u["tid"])}"'
            f' data-ref="{u["refView"] if u["refView"] else ""}">'
            f'<span class="u-no">{i}</span>'
            f'<span class="u-name">{esc(u["name"])}</span>'
            f'<span class="u-state"></span>'
            f'<a class="u-btn wb" href="wb/{c["ch"]}/index.html#t{u["wbView"]}">問題</a>'
            + (f'<a class="u-btn ref" href="ref/{c["ch"]}/index.html#t{u["refView"]}">参考書</a>'
               if u["refView"] else '<span class="u-btn ref off">—</span>')
            + '</li>'
            for i, u in enumerate(c["units"], 1))
        books.append(
            f'<section class="book" data-grade="{c["grade"]}">'
            f'<div class="ch-band">'
            f'<span class="cb-flag">🚩</span>'
            f'<span class="cb-no">冒険 {c["no"]}</span>'
            f'<span class="cb-title">{esc(c["title"])}</span>'
            f'<span class="bk-prog" data-ch="{c["ch"]}"></span>'
            f'</div>'
            f'<ul class="u-list">{rows}</ul></section>')

    manifest_min = [{"ch": c["ch"], "grade": c["grade"], "vol": c["vol"], "title": c["title"],
                     "n": len(c["units"])} for c in manifest]

    return (TEMPLATE
            .replace("__TOTAL__", str(total_units))
            .replace("__CELLS__", "".join(cells))
            .replace("__BOOKS__", "".join(books))
            .replace("__ERAS__", json.dumps(ERAS, ensure_ascii=False))
            .replace("__GRADES__", json.dumps(GRADES, ensure_ascii=False))
            .replace("__GRADE_TOTAL__", json.dumps(grade_total, ensure_ascii=False))
            .replace("__TITLE__", img_tag("quest-title.webp", "title-img", "歴史クエスト"))
            .replace("__CHEST__", img_tag("quest-chest.webp", "g-chest", ""))
            .replace("__EXPLORER__", img_tag("quest-explorer.webp", "ch-explorer", ""))
            .replace("__BIRD__", img_tag("quest-bird.webp", "ch-bird", ""))
            .replace("__MASCOT__", img_tag("char_manabi_sm.png", "ch-mascot", ""))
            .replace("__MANIFEST__", json.dumps(manifest_min, ensure_ascii=False)))


TEMPLATE = r"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>つづもん 歴史クエスト｜本一覧</title>
<style>
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --line:#e8d3a8;
          --paper:#fffaf0; --parch:#f5e6c8; --wood:#8b5a2b; --ink:#3b2b16;
          --s-ref:#60a5fa; --s-some:#fbbf24; --s-all:#4ade80; --s-perfect:#f59e0b;
          --era-ancient:#eadfbe; --era-medieval:#dfead9; --era-earlymod:#e3ddd0;
          --era-modern:#dfd9e6; --era-current:#e6dcd2; }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { font-family:"Kiwi Maru","Zen Maru Gothic","Hiragino Maru Gothic ProN",
                     "Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         color:var(--ink);
         padding-bottom:calc(40px + env(safe-area-inset-bottom));
         background:#efe0c0;
         /* 羊皮紙テクスチャ（img/quest-bg.webp）。無ければ下のグラデーションだけが見える */
         background-image:
           url("img/quest-bg.webp"),
           radial-gradient(circle at 18% 12%, rgba(255,255,255,.55) 0 26%, transparent 26%),
           radial-gradient(circle at 82% 68%, rgba(255,255,255,.4) 0 22%, transparent 22%),
           linear-gradient(160deg,#f7ead0,#eddcb8 60%,#e6d2ab);
         background-size:cover, auto, auto, auto;
         background-position:top center;
         background-attachment:fixed, scroll, scroll, scroll; }
  .wrap { max-width:720px; margin:0 auto; padding:0 14px;
          padding-top:calc(6px + env(safe-area-inset-top)); }

  /* ───── ヘッダー ───── */
  .head { position:relative; text-align:center; padding:8px 0 4px; }
  .head-h1 { font-size:34px; font-weight:900; color:#fcd34d; letter-spacing:.03em;
             -webkit-text-stroke:5px #6b3b12; paint-order:stroke fill;
             text-shadow:0 3px 0 rgba(107,59,18,.45); }
  /* ロゴ画像（img/quest-title.webp）が読めたら文字版と差し替える */
  .title-img { display:none; width:min(88%,400px); height:auto; margin:0 auto; }
  .head.has-logo .title-img { display:block; }
  .head.has-logo .head-h1, .head.has-logo .head-sub {
                            position:absolute; width:1px; height:1px; overflow:hidden;
                            clip-path:inset(50%); white-space:nowrap; }
  .head-sub { display:inline-block; margin-top:2px; background:linear-gradient(#5c3a17,#40260d);
              color:#fdf3d9; font-size:13px; font-weight:bold; padding:5px 20px;
              border-radius:6px; box-shadow:0 3px 0 rgba(60,34,10,.5); }
  .ch-explorer { position:absolute; left:0; bottom:-2px; width:64px; height:auto; pointer-events:none; }
  .ch-bird { position:absolute; right:0; bottom:-2px; width:64px; height:auto; pointer-events:none; }

  /* ───── 学年タブ（2学年以上のときだけ出る） ───── */
  .gtabs { display:none; gap:8px; justify-content:center; margin:6px 0 0; }
  .gtabs.show { display:flex; }
  .gtab { border:2px solid #c9a978; background:#fffaf0; color:var(--brand); font-weight:bold;
          border-radius:22px; padding:7px 22px; font-size:14px; cursor:pointer; font-family:inherit;
          box-shadow:0 3px 0 #d8bd91; }
  .gtab.on { background:linear-gradient(#b45309,#8a3f07); color:#fff8ec; border-color:#7c2d12;
             box-shadow:0 3px 0 #5c2508; }

  /* ───── 巻物パネル ───── */
  .panel { background:linear-gradient(#fffdf6,#f8eed9); border:2px solid #ddc39a;
           border-radius:16px; padding:10px 14px 11px; margin-top:10px;
           box-shadow:0 4px 0 #ddc39a, 0 6px 14px rgba(120,80,20,.14); }
  .p-h { font-size:12.5px; font-weight:bold; color:var(--deep); text-align:center; }
  .big { text-align:center; margin:2px 0 7px; font-weight:bold; color:var(--deep); }
  .big b { font-size:30px; color:var(--brand); line-height:1; }
  .big .sm { font-size:14px; }
  .ov-bar { height:18px; background:#f1e6cf; border-radius:10px; overflow:hidden;
            border:2px solid #ddc39a; position:relative; }
  .ov-fill { height:100%; width:0; border-radius:8px; transition:width .5s cubic-bezier(.22,.72,.32,1);
             background:linear-gradient(90deg,#fbbf24,#f59e0b 70%,#d97706); }

  /* 凡例（2行に折り返す） */
  .legend { display:flex; flex-wrap:wrap; gap:8px 14px; justify-content:center;
            margin-top:10px; font-size:11.5px; color:#6b5a3c; }
  .lg { display:inline-flex; align-items:center; gap:5px; }
  .dot { width:14px; height:14px; border-radius:50%; border:2px solid rgba(0,0,0,.12); background:#fff; }
  .dot.d-ref { background:var(--s-ref); } .dot.d-some { background:var(--s-some); }
  .dot.d-all { background:var(--s-all); } .dot.d-perfect { background:var(--s-perfect); }

  /* ───── 今日のミッション ───── */
  .mission { display:flex; align-items:center; gap:10px; margin-top:10px;
             background:linear-gradient(#fffdf6,#fdf3e0);
             border:2px dashed var(--amber); border-radius:14px; padding:8px 12px; }
  .ch-mascot { width:42px; height:auto; flex:none; filter:drop-shadow(0 2px 3px rgba(0,0,0,.18)); }
  .ms-body { flex:1; min-width:0; }
  .ms-h { font-size:12px; font-weight:bold; color:#b45309; }
  .ms-txt { font-size:14px; font-weight:bold; color:var(--deep); margin-top:2px; }
  .ms-steps { display:flex; gap:6px; margin-top:7px; }
  .ms-step { width:26px; height:26px; border-radius:50%; background:#fff; border:2px solid #ddc39a;
             display:inline-flex; align-items:center; justify-content:center; font-size:13px; }
  .ms-step.on { background:var(--amber); border-color:var(--brand); color:#fff; }

  /* ───── マップ（時代エリアごとに1画面・横スワイプで切替） ───── */
  .board { margin-top:12px; }
  #cells { display:none; }   /* 表示前のマスの置き場 */
  /* 横スワイプのカルーセル。1ページ＝1時代エリア */
  .era-track { display:flex; overflow-x:auto; scroll-snap-type:x mandatory; scroll-behavior:smooth;
               -webkit-overflow-scrolling:touch; scrollbar-width:none; background:#bcd6e2;
               border-radius:22px; border:3px solid rgba(124,45,18,.22);
               box-shadow:inset 0 0 0 3px rgba(255,255,255,.35), 0 6px 18px rgba(120,80,20,.2); }
  .era-track::-webkit-scrollbar { display:none; }
  /* 各エリアのページ。背景は学年の舞台画像を上/下に寄せて敷く（JSで設定） */
  .era-page { flex:0 0 100%; scroll-snap-align:start; position:relative;
              padding:10px 8px 16px; background-size:cover; background-repeat:no-repeat; }
  /* ページ送りのドット */
  .era-nav { display:flex; align-items:center; justify-content:center; gap:12px; margin:9px 0 2px; }
  .era-dots { display:flex; gap:8px; justify-content:center; }
  .era-arrow { flex:none; border:2px solid #d8bd91; background:#fffaf0; color:var(--brand);
               font-weight:bold; border-radius:16px; padding:5px 14px; font-size:12.5px;
               cursor:pointer; font-family:inherit; box-shadow:0 2px 0 #d8bd91; white-space:nowrap; }
  .era-arrow:disabled { opacity:.3; box-shadow:none; cursor:default; }
  .era-dot { width:9px; height:9px; border-radius:50%; background:#d8bd91; border:none; padding:0;
             cursor:pointer; transition:width .2s, background-color .2s; }
  .era-dot.on { background:var(--brand); width:22px; border-radius:5px; }
  /* 時代の木の看板 */
  .sign { display:inline-flex; align-items:center; gap:7px; background:linear-gradient(#c89a5b,#a97b3f);
          color:#fff8ec; font-weight:bold; border-radius:9px; padding:4px 13px;
          box-shadow:0 3px 0 #7d5a2b, 0 5px 8px rgba(90,60,20,.25); font-size:13.5px;
          border:2px solid #8a6431; }
  .sign .s-emoji { font-size:15px; }
  .sign .s-range { font-size:10.5px; background:rgba(255,255,255,.25); border-radius:8px; padding:1px 6px; }
  .era-hint { font-size:11px; color:#7c5a2a; margin:5px 2px 2px; font-weight:bold; }

  /* マスは1行4個。各マスに単元名を出す（何の内容か一目でわかる） */
  .row { display:flex; gap:6px; align-items:flex-start; position:relative; margin:10px 0 4px; }
  .row.rev { flex-direction:row-reverse; }
  /* マスをつなぐ点線の道 */
  .row::before { content:""; position:absolute; left:8%; top:23px; height:5px; z-index:0;
                 width:calc(var(--span,100%) - 16%);
                 background:repeating-linear-gradient(90deg,#c9a978 0 9px, transparent 9px 17px);
                 border-radius:3px; }
  .row.rev::before { left:auto; right:8%; }
  .cell { position:relative; z-index:1; flex:0 0 calc((100% - (var(--row,4) - 1) * 6px) / var(--row,4));
          min-width:0; border:none; background:none;
          cursor:pointer; font-family:inherit; padding:0; display:flex; flex-direction:column;
          align-items:center; gap:3px; }
  .tok { position:relative; width:min(100%,46px); aspect-ratio:1; border-radius:50%; background:#fffdf6;
         border:2.5px solid #e2cfa4; display:flex; align-items:center; justify-content:center;
         box-shadow:0 3px 0 #e2cfa4, 0 5px 7px rgba(120,80,20,.18);
         transition:transform .12s, box-shadow .12s, background-color .2s, border-color .2s; }
  .tok-no { font-weight:bold; font-size:17px; color:#7a6a4d; line-height:1; }
  .tok-badge { position:absolute; right:-3px; bottom:-3px; font-size:12px; line-height:1;
               filter:drop-shadow(0 1px 1px rgba(0,0,0,.2)); }
  /* 単元名（島の上でも読めるよう白いチップに） */
  .tok-name { font-size:9.5px; line-height:1.25; color:#3b2b16; text-align:center; max-width:100%;
              background:rgba(255,253,246,.9); border-radius:7px; padding:2px 5px;
              box-shadow:0 1px 2px rgba(120,80,20,.15);
              display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  /* バッジ画像（img/quest-badge-*.webp）が使えるときだけ絵文字と差し替える */
  .has-badges .tok-badge { font-size:0; width:16px; height:16px;
                           background:center/contain no-repeat; }
  .has-badges .cell.s-ref     .tok-badge { background-image:url("img/quest-badge-ref.webp"); }
  .has-badges .cell.s-some    .tok-badge { background-image:url("img/quest-badge-some.webp"); }
  .has-badges .cell.s-all     .tok-badge { background-image:url("img/quest-badge-all.webp"); }
  .has-badges .cell.s-perfect .tok-badge { background-image:url("img/quest-badge-perfect.webp"); }
  /* 島のイラストの上に乗るので、白いにじみで文字を浮かせる */
  .era-hint { text-shadow:0 0 4px #fffdf6, 0 0 6px #fffdf6; }

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
  .cell.current .tok { border-color:var(--brand); background:#fffdf6;
                       box-shadow:0 5px 0 var(--brand), 0 0 0 4px rgba(180,83,9,.18), 0 10px 14px rgba(180,83,9,.3);
                       animation:pulse 1.8s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-3px); } }
  /* いまいるマスの上に立つ探検者。1行8マスなので吹き出しは出さない */
  .cell.here .tok::before { content:"🧑‍🎓"; position:absolute; top:-17px; left:50%;
                            transform:translateX(-50%); font-size:16px;
                            filter:drop-shadow(0 2px 2px rgba(0,0,0,.25)); }

  @media (hover:hover) { .cell:hover .tok { transform:translateY(-3px); } }
  .cell:active .tok { transform:translateY(3px); box-shadow:0 2px 0 #e2cfa4,0 3px 5px rgba(120,80,20,.18); }

  /* ゴール：ふだんは色を抜いて「まだ先」を演出。全マスクリアで .goal.done なら点灯 */
  .goal { margin:8px 0 0; }
  .goal .g-box { display:flex; align-items:center; gap:12px;
                 background:#f3ecdd; border:2px solid #d8c9a8;
                 border-radius:16px; padding:9px 14px; box-shadow:0 4px 0 #d8c9a8;
                 filter:grayscale(.85) opacity(.72); transition:filter .4s, background-color .4s, border-color .4s; }
  .goal.done .g-box { background:linear-gradient(#fffdf6,#fdf0cf); border-color:var(--amber);
                      box-shadow:0 4px 0 #eab308; filter:none; }
  .g-chest { width:56px; height:auto; flex:none; }
  .goal .g-flag { display:inline-block; background:#a89a7c; color:#fff8ec;
                  font-weight:bold; border-radius:5px; padding:2px 12px; font-size:12px;
                  letter-spacing:.1em; box-shadow:0 2px 0 #857a5f; }
  .goal.done .g-flag { background:linear-gradient(#e0453a,#b91c1c); box-shadow:0 2px 0 #7f1d1d; }
  .goal .g-t { font-weight:bold; color:var(--deep); font-size:14.5px; margin-top:4px; }
  .goal .g-s { font-size:11px; color:#92400e; }

  /* ───── 単元一覧 ───── */
  .books { margin-top:18px; }
  .books-h { text-align:center; margin-bottom:10px; }
  .books-h h2 { display:inline-block; font-size:16px; color:var(--deep);
                background:linear-gradient(#fffdf6,#f4e7cd); border:2px solid #ddc39a;
                border-radius:11px; padding:6px 22px; box-shadow:0 3px 0 #ddc39a; }
  .book { background:var(--paper); border:2px solid #ddc39a; border-radius:12px; margin-bottom:8px;
          overflow:hidden; box-shadow:0 3px 0 #e6d3ae; }
  /* 章の帯（冒険N）。カンプの学年帯と同じ役目 */
  .ch-band { display:flex; align-items:center; gap:6px; padding:6px 10px;
             background:linear-gradient(#f0dcb4,#e7cd9c); border-bottom:2px solid #ddc39a; }
  .cb-flag { flex:none; font-size:12px; }
  .cb-no { flex:none; font-weight:bold; color:var(--deep); font-size:11.5px; white-space:nowrap; }
  .cb-title { flex:1; font-size:12.5px; font-weight:bold; color:#4a3a22; min-width:0;
              overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .bk-prog { flex:none; font-size:10.5px; color:#7c5a2a; font-weight:bold; }
  .u-list { list-style:none; }
  .u-row { display:flex; align-items:center; gap:6px; padding:5px 9px; }
  .u-row + .u-row { border-top:1px dashed #ecdcbb; }
  .u-no { flex:none; width:19px; height:19px; border-radius:6px; background:#fff; border:1.5px solid var(--line);
          color:var(--brand); font-weight:bold; font-size:10.5px; display:inline-flex;
          align-items:center; justify-content:center; }
  .u-name { flex:1; font-size:12.5px; min-width:0; overflow:hidden;
            text-overflow:ellipsis; white-space:nowrap; }
  .u-state { flex:none; font-size:12px; width:15px; text-align:center; }
  .u-btn { flex:none; text-decoration:none; font-size:10.5px; font-weight:bold; border-radius:7px;
           padding:3px 9px; white-space:nowrap; }
  .u-btn.wb { background:linear-gradient(#b45309,#8a3f07); color:#fff8ec; box-shadow:0 2px 0 #5c2508; }
  .u-btn.ref { background:#fff; color:#1d4ed8; border:1.5px solid #bfdbfe; box-shadow:0 2px 0 #e6efff; }
  .u-btn.off { color:#d6d3d1; border-color:#eee; box-shadow:none; background:#fff; }

  /* ───── 冒険のきろく ───── */
  .record { margin-top:22px; }
  .rec-h { text-align:center; margin-bottom:10px; }
  .rec-h h2 { display:inline-block; font-size:16px; color:var(--deep);
              background:linear-gradient(#fffdf6,#f4e7cd); border:2px solid #ddc39a;
              border-radius:12px; padding:6px 22px; box-shadow:0 3px 0 #ddc39a; }
  .counts { display:flex; gap:8px; }
  .cnt { flex:1; text-align:center; background:#fffdf6; border:2px solid #ddc39a; border-radius:12px;
         padding:9px 2px 7px; box-shadow:0 3px 0 #e6d3ae; }
  .cnt b { display:block; font-size:22px; color:var(--deep); line-height:1.2; }
  .cnt span { font-size:10.5px; color:#8a7b62; }

  footer { text-align:center; margin-top:26px; color:#9c8a6a; font-size:12px; }

  /* 画面が広いときはマスを大きめに（1行4個のまま） */
  @media (min-width:640px) {
    .tok { width:min(100%,60px); }
    .tok-no { font-size:22px; }
    .tok-name { font-size:11px; }
    .row { gap:10px; }
    .row::before { top:29px; }
    .cell { flex:0 0 calc((100% - (var(--row,4) - 1) * 10px) / var(--row,4)); }
    .head-h1 { font-size:42px; }
  }
</style></head><body>

<div class="wrap">
  <header class="head" id="head">
    __EXPLORER__
    __TITLE__
    <h1 class="head-h1">歴史クエスト</h1>
    <div class="head-sub">中学歴史の冒険に出発しよう！</div>
    __BIRD__
  </header>

  <div class="gtabs" id="gtabs"></div>

  <div class="panel">
    <div class="p-h">あなたの冒険の進み具合</div>
    <div class="big"><b id="ovNum">0</b><span class="sm"> / <span id="ovTotal">0</span> マス</span>
      <span class="sm" id="ovPct">（0%）</span></div>
    <div class="ov-bar"><div class="ov-fill" id="ovFill"></div></div>
    <div class="legend">
      <span class="lg"><span class="dot"></span>まだ</span>
      <span class="lg"><span class="dot d-ref"></span>参考書を読んだ</span>
      <span class="lg"><span class="dot d-some"></span>一部を解いた</span>
      <span class="lg"><span class="dot d-all"></span>全部解いた</span>
      <span class="lg"><span class="dot d-perfect"></span>全問正解</span>
    </div>
  </div>

  <div class="mission">
    __MASCOT__
    <div class="ms-body">
      <div class="ms-h">🎯 今日のミッション</div>
      <div class="ms-txt" id="msTxt">今日は 3マス すすめよう！</div>
      <div class="ms-steps" id="msSteps"></div>
    </div>
  </div>

  <div class="board" id="board">
    <div class="era-track" id="eraTrack"></div>
    <div class="era-nav" id="eraNav">
      <button class="era-arrow" id="eraPrev" type="button">‹ 前へ</button>
      <div class="era-dots" id="eraDots"></div>
      <button class="era-arrow" id="eraNext" type="button">次へ ›</button>
    </div>
    <div id="cells">__CELLS__</div>
    <div class="goal">
      <div class="g-box">
        __CHEST__
        <div>
          <span class="g-flag">ゴール！</span>
          <div class="g-t">🏆 <span id="goalGrade">中1</span> 制覇！</div>
          <div class="g-s">全<span id="goalTotal">0</span>マスを進めよう</div>
        </div>
      </div>
    </div>
  </div>

  <div class="books">
    <div class="books-h"><h2>📖 単元一覧</h2></div>
    <div id="bookList">__BOOKS__</div>
  </div>

  <div class="record">
    <div class="rec-h"><h2>冒険のきろく</h2></div>
    <div class="counts">
      <div class="cnt"><b id="cCleared">0</b><span>クリアマス数</span></div>
      <div class="cnt"><b id="cStamp">0</b><span>集めたスタンプ</span></div>
      <div class="cnt"><b id="cPerfect">0</b><span>全問正解</span></div>
    </div>
  </div>
</div>
<footer>つづもん 歴史クエスト　｜　全__TOTAL__単元</footer>

<script>
(function () {
  var MANIFEST = __MANIFEST__;
  var ERAS = __ERAS__;
  var GRADES = __GRADES__;
  var GRADE_TOTAL = __GRADE_TOTAL__;
  var ROW = 4;   // 1行のマス数（エリアごとに1画面・snake配置）

  function ls(key) { try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) { return {}; } }
  function lsRaw(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, v) { try { localStorage.setItem(key, v); } catch (e) {} }

  /* ───── 登録学年 ─────
     配布URLの ?g= で受け取り、localStorage['tzmgrades'] に保存する。
       ?g=1,2 / ?g=中1,中2 / ?g=all
     パラメータも保存もなければ全学年（体験・確認用）。 */
  function parseGrades(raw) {
    if (!raw) return null;
    if (/^all$/i.test(raw.trim())) return GRADES.slice();
    var out = [];
    raw.split(/[,\s、]+/).forEach(function (t) {
      var m = t.match(/([123])/);
      if (!m) return;
      var g = '中' + m[1];
      if (GRADES.indexOf(g) >= 0 && out.indexOf(g) < 0) out.push(g);
    });
    return out.length ? out : null;
  }
  function myGrades() {
    var q = parseGrades(new URLSearchParams(location.search).get('g'));
    if (q) { save('tzmgrades', JSON.stringify(q)); return q; }
    var saved = null;
    try { saved = JSON.parse(lsRaw('tzmgrades') || 'null'); } catch (e) {}
    if (saved && saved.length) {
      var ok = saved.filter(function (g) { return GRADES.indexOf(g) >= 0; });
      if (ok.length) return ok;
    }
    return GRADES.slice();
  }

  var MY = myGrades();
  var cur = lsRaw('tzmgrade');
  if (MY.indexOf(cur) < 0) cur = MY[0];

  function renderTabs() {
    var box = document.getElementById('gtabs');
    box.innerHTML = '';
    // 1学年しか持っていない人にはタブを出さない
    if (MY.length < 2) return;
    box.classList.add('show');
    MY.forEach(function (g) {
      var b = document.createElement('button');
      b.className = 'gtab' + (g === cur ? ' on' : '');
      b.type = 'button';
      b.dataset.g = g;
      b.textContent = g;
      box.appendChild(b);
    });
  }

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

  // いまの学年のマスを、時代エリアごとの1ページ（横スワイプ）に並べる
  function layout() {
    var track = document.getElementById('eraTrack');
    var dots = document.getElementById('eraDots');
    var pool = document.getElementById('cells');
    var all = [].slice.call(document.querySelectorAll('.cell[data-tid]'));
    all.forEach(function (c) { if (c.parentNode !== pool) pool.appendChild(c); });
    track.innerHTML = ''; dots.innerHTML = '';

    var gn = { '中1': 1, '中2': 2, '中3': 3 }[cur] || 1;
    var veil = 'linear-gradient(rgba(255,253,246,.30),rgba(255,253,246,.42))';
    var img = 'url("img/quest-stage-g' + gn + '.webp")';
    var mine = all.filter(function (c) { return c.dataset.grade === cur; });
    var page = 0;
    ERAS.forEach(function (era) {
      var list = mine.filter(function (c) { return c.dataset.era === era.key; });
      if (!list.length) return;
      var box = document.createElement('div');
      box.className = 'era-page e-' + era.key;
      // 学年の舞台画像を、1エリア目は上・2エリア目は下に寄せて見せる
      box.style.backgroundImage = veil + ', ' + img;
      box.style.backgroundPosition = (page === 0 ? 'top center' : 'bottom center');
      var first = list[0].dataset.gn, last = list[list.length - 1].dataset.gn;
      box.innerHTML = '<div><span class="sign"><span class="s-emoji">' + era.emoji + '</span>'
        + era.name + '<span class="s-range">' + first + '〜' + last + '</span></span></div>'
        + '<div class="era-hint">' + era.hint + '</div>';
      for (var i = 0; i < list.length; i += ROW) {
        var row = document.createElement('div');
        row.className = 'row' + ((i / ROW) % 2 === 1 ? ' rev' : '');
        var slice = list.slice(i, i + ROW);
        slice.forEach(function (c) { row.appendChild(c); });
        row.style.setProperty('--row', ROW);
        row.style.setProperty('--span', (slice.length / ROW * 100) + '%');
        box.appendChild(row);
      }
      track.appendChild(box);
      var dot = document.createElement('button');
      dot.className = 'era-dot' + (page === 0 ? ' on' : '');
      dot.type = 'button'; dot.dataset.page = page;
      dot.setAttribute('aria-label', era.name);
      dots.appendChild(dot);
      page++;
    });
    document.getElementById('eraNav').style.display = page > 1 ? '' : 'none';
    updateEraNav();

    [].forEach.call(document.querySelectorAll('.book'), function (b) {
      b.style.display = (b.dataset.grade === cur) ? '' : 'none';
    });
    document.getElementById('goalGrade').textContent = cur;
    document.getElementById('goalTotal').textContent = GRADE_TOTAL[cur] || 0;
    document.getElementById('ovTotal').textContent = GRADE_TOTAL[cur] || 0;
    track.scrollLeft = 0;
  }

  // いまのページ番号と、ドット・前へ/次へボタンの状態を更新
  function updateEraNav() {
    var track = document.getElementById('eraTrack');
    var dots = document.getElementById('eraDots');
    if (!track || !track.clientWidth) return;
    var pages = dots.children.length;
    var idx = Math.round(track.scrollLeft / track.clientWidth);
    [].forEach.call(dots.children, function (d, i) { d.classList.toggle('on', i === idx); });
    document.getElementById('eraPrev').disabled = idx <= 0;
    document.getElementById('eraNext').disabled = idx >= pages - 1;
  }
  // ドット・スワイプ・前へ/次へボタンの同期（一度きり設定）
  (function () {
    var track = document.getElementById('eraTrack');
    var dots = document.getElementById('eraDots');
    if (!track) return;
    function goPage(idx) {
      var pages = dots.children.length;
      idx = Math.max(0, Math.min(pages - 1, idx));
      track.scrollTo({ left: idx * track.clientWidth, behavior: 'smooth' });
    }
    var timer = null;
    track.addEventListener('scroll', function () {
      if (timer) return;
      timer = requestAnimationFrame(function () { timer = null; updateEraNav(); });
    }, { passive: true });
    dots.addEventListener('click', function (e) {
      var d = e.target.closest && e.target.closest('.era-dot');
      if (d) goPage(+d.dataset.page);
    });
    document.getElementById('eraPrev').addEventListener('click', function () {
      goPage(Math.round(track.scrollLeft / track.clientWidth) - 1);
    });
    document.getElementById('eraNext').addEventListener('click', function () {
      goPage(Math.round(track.scrollLeft / track.clientWidth) + 1);
    });
  })();

  function paint() {
    // 進捗はいまの学年の中で数える（マップに並んでいるマス＝いまの学年）
    var cells = [].slice.call(document.querySelectorAll('.era-page .cell[data-tid]'));
    var n = { none: 0, ref: 0, some: 0, all: 0, perfect: 0 };
    var cleared = 0, lastCleared = -1;
    var byCh = {};
    // 章ごとの進み具合は全学年ぶん集計する（表示は絞られていても値は正しく）
    [].forEach.call(document.querySelectorAll('.cell[data-tid]'), function (c) {
      var s = cellState(c);
      byCh[c.dataset.ch] = byCh[c.dataset.ch] || { done: 0, all: 0 };
      byCh[c.dataset.ch].all++;
      if (s !== 'none') byCh[c.dataset.ch].done++;
    });
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

    // 冒険のきろく（いまの学年ぶん）
    var goalEl = document.querySelector('.goal');
    if (goalEl) goalEl.classList.toggle('done', cells.length > 0 && cleared >= cells.length);
    document.getElementById('cCleared').textContent = cleared;
    document.getElementById('cStamp').textContent = n.all + n.perfect;
    document.getElementById('cPerfect').textContent = n.perfect;

    // 本の一覧: 章ごとの進み具合と、単元行の状態マーク
    [].forEach.call(document.querySelectorAll('.bk-prog'), function (el) {
      var b = byCh[el.dataset.ch] || { done: 0, all: 0 };
      el.textContent = 'スタンプ ' + b.done + '/' + b.all;
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
    var GOAL = 3, today = new Date().toISOString().slice(0, 10), key = 'tzmportal-' + cur;
    var st = ls(key);
    if (st.date !== today) { st = { date: today, base: cleared }; save(key, JSON.stringify(st)); }
    if (cleared < st.base) { st.base = cleared; save(key, JSON.stringify(st)); }
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

  document.addEventListener('click', function (e) {
    if (!e.target.closest) return;
    // 学年タブ
    var gtab = e.target.closest('.gtab');
    if (gtab) {
      cur = gtab.dataset.g;
      save('tzmgrade', cur);
      renderTabs(); layout(); paint();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    // マスをタップ → その単元の問題集へ
    var cell = e.target.closest('.cell[data-tid]');
    if (cell) { location.href = 'wb/' + cell.dataset.ch + '/index.html'; return; }  // まず章の目次へ
  });

  // ロゴ画像が実際に表示できたときだけ、CSS文字版のタイトルと差し替える
  var logo = document.querySelector('.title-img');
  if (logo) {
    if (logo.complete && logo.naturalWidth) document.getElementById('head').classList.add('has-logo');
    else logo.addEventListener('load', function () {
      document.getElementById('head').classList.add('has-logo');
    });
  }
  // バッジ画像が置かれていれば、絵文字のバッジを画像に切り替える
  (function () {
    var probe = new Image();
    probe.onload = function () { document.documentElement.classList.add('has-badges'); };
    probe.src = 'img/quest-badge-all.webp';
  })();

  renderTabs();
  layout();
  paint();
  window.addEventListener('focus', paint);
  window.addEventListener('pageshow', paint);
})();
</script>
</body></html>"""


def copy_assets(dest_root: Path) -> None:
    """キャラ画像と（あれば）Codex 製のイラストを img/ へ配る。"""
    img_dir = dest_root / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    for name in ("char_manabi_sm.png", "char_owl_sm.webp"):
        src = CHAR_DIR / name
        if src.exists():
            shutil.copyfile(src, img_dir / name)
    if PORTAL_IMG_DIR.exists():
        for src in PORTAL_IMG_DIR.glob("portal-*"):
            shutil.copyfile(src, img_dir / src.name)
    # 歴史クエストのイラストは WebP だけを配る（PNG は原本。tools/quest_assets_to_webp.py で変換）
    if QUEST_IMG_DIR.exists():
        for src in QUEST_IMG_DIR.glob("quest-*.webp"):
            if src.name.startswith("quest-top-"):
                continue   # カンプ画像そのものは配らない
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


