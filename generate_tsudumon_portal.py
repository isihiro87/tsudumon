# -*- coding: utf-8 -*-
"""
つづもん「本一覧トップ（3Dすごろく）」を生成する。

つづもん全体（歴史 中1〜中3・全19章の全単元）を1本の道でつなぐ 3D すごろく。
各マス＝1単元。localStorage（各章 tzmwb-{NN} / tzmref-{NN}）を読んで、
クリア種別で見た目が変わる:
  - 未着手
  - 参考書を読んだ（tzmref-{NN}.d{refView}===1）
  - 問題を一部解いた（その単元の qid の一部に回答）
  - 問題を全部解いた（B/C/D 全問に回答）
  - 全問正解（全問に回答かつ全問 r===1）

マスをタップすると、その単元の問題集ページ（wb/{NN}/#t{wbView}）へ。
各本の問題集/参考書ホームからは「🗺 すごろく（本一覧）」でここへ戻れる。

出力:
  python -X utf8 generate_tsudumon_portal.py            # output/web/index.html
  python -X utf8 generate_tsudumon_portal.py --deploy   # marutto-study/public/tsudumon/index.html
"""
import argparse
import html
import json
from pathlib import Path

from generate_history_workbook import (
    BOOKS, CONTENT_ROOT, CONTENT_DIR,
    N_ITTOITTO, N_QUIZ, resolve_count,
)

BASE = Path(__file__).parent
REF_DIR = BASE / "reference"
OUT_FILE = BASE / "output" / "web" / "index.html"
DEPLOY_FILE = BASE.parent / "marutto-study" / "public" / "tsudumon" / "index.html"


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


def build_html() -> str:
    manifest = build_manifest()
    total_units = sum(len(c["units"]) for c in manifest)

    # マス（セル）を「学年 → 章 → 単元」の順に一列に並べる。JS が snake 配置＋状態着色する。
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
                f' data-grade="{ch["grade"]}" data-vol="{esc(ch["vol"])}"'
                f' title="{esc(ch["vol"])} {esc(u["name"])}">'
                f'<span class="cell-face">'
                f'<span class="cell-no">{idx}</span>'
                f'<span class="cell-badge"></span>'
                f'</span>'
                f'<span class="cell-name">{esc(u["name"])}</span>'
                f'</button>')

    # 学年の境目（各学年の最初の単元の通し番号）を JS に渡す
    grade_starts = {}
    n = 0
    for ch in manifest:
        for _ in ch["units"]:
            n += 1
            grade_starts.setdefault(ch["grade"], n)

    manifest_min = [
        {"ch": c["ch"], "grade": c["grade"], "vol": c["vol"], "title": c["title"],
         "units": [{"n": None} for _ in c["units"]]}
        for c in manifest
    ]
    # units の通し番号を振る
    k = 0
    for c in manifest_min:
        for u in c["units"]:
            k += 1
            u["n"] = k

    return (TEMPLATE
            .replace("__TOTAL__", str(total_units))
            .replace("__CELLS__", "".join(cells))
            .replace("__GRADE_STARTS__", json.dumps(grade_starts, ensure_ascii=False))
            .replace("__MANIFEST__", json.dumps(manifest_min, ensure_ascii=False)))


TEMPLATE = r"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>つづもん 歴史すごろく｜本一覧</title>
<style>
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --cream:#fffdf8; --line:#fde68a;
          --ok:#16a34a; --ng:#dc2626;
          --s-ref:#93c5fd; --s-some:#fcd34d; --s-all:#86efac; --s-perfect:#fbbf24; }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         color:#1c1917; background:linear-gradient(#fffdf8,#fef6e4); padding-bottom:40px; }
  .wrap { max-width:720px; margin:0 auto; padding:0 14px; }

  header.top { text-align:center; padding:22px 0 8px; }
  .badge { display:inline-block; background:var(--brand); color:#fff; font-weight:bold;
           padding:4px 16px; border-radius:20px; font-size:13px; }
  header.top h1 { font-size:26px; color:var(--deep); margin-top:10px; }
  header.top .sub { color:#92400e; font-size:13.5px; margin-top:4px; }

  /* 全体の進み具合 */
  .overall { max-width:720px; margin:12px auto 4px; padding:0 14px; }
  .ov-bar { height:12px; background:#f1e6cf; border-radius:8px; overflow:hidden; border:1px solid #f0deb0; }
  .ov-fill { height:100%; width:0; background:linear-gradient(90deg,var(--amber),#fbbf24); transition:width .4s; }
  .ov-txt { text-align:center; font-size:12.5px; font-weight:bold; color:#92400e; margin-top:5px; }

  /* 凡例 */
  .legend { display:flex; flex-wrap:wrap; gap:8px 14px; justify-content:center;
            margin:10px auto 6px; font-size:12px; color:#57534e; }
  .lg { display:inline-flex; align-items:center; gap:5px; }
  .dot { width:14px; height:14px; border-radius:4px; border:1.5px solid rgba(0,0,0,.12); }
  .dot.d-ref { background:var(--s-ref); } .dot.d-some { background:var(--s-some); }
  .dot.d-all { background:var(--s-all); } .dot.d-perfect { background:var(--s-perfect); }
  .dot.d-none { background:#fff; }

  /* 3D すごろく盤 */
  .board-wrap { perspective:1400px; margin:8px 0 4px; overflow-x:hidden; }
  .board { transform:rotateX(16deg); transform-origin:top center; transform-style:preserve-3d;
           padding:6px 2px 30px; }
  .grade-band { display:flex; align-items:center; gap:8px; margin:16px 0 8px;
                transform:translateZ(1px); }
  .grade-tag { flex:none; background:var(--deep); color:#fff; font-weight:bold; font-size:14px;
               border-radius:10px; padding:4px 14px; box-shadow:0 3px 0 #5b1e0b; }
  .grade-line { flex:1; height:3px; background:repeating-linear-gradient(90deg,#e7d3ad 0 10px,transparent 10px 18px); }

  .row { display:flex; gap:10px; margin-bottom:10px; align-items:stretch; }
  .row.rev { flex-direction:row-reverse; }

  .cell { position:relative; flex:1 1 0; min-width:0; border:none; background:none; cursor:pointer;
          font-family:inherit; padding:0; }
  /* マス＝立体ブロック（上面＋下の厚み） */
  .cell-face { display:flex; flex-direction:column; align-items:center; justify-content:center;
               background:#fff; border:2px solid #e7d3ad; border-radius:12px; padding:8px 4px 7px;
               box-shadow:0 6px 0 #e2cfa4, 0 8px 10px rgba(120,80,20,.18);
               transition:transform .12s, box-shadow .12s, background-color .2s, border-color .2s; }
  .cell-no { font-weight:bold; font-size:15px; color:#78716c; line-height:1; }
  .cell-badge { font-size:15px; line-height:1; margin-top:3px; min-height:16px; }
  .cell-name { display:block; font-size:9.5px; color:#78716c; margin-top:4px; line-height:1.25;
               max-height:2.5em; overflow:hidden; text-align:center; }

  /* 状態別の色 */
  .cell.s-ref  .cell-face { background:#eff6ff; border-color:#bfdbfe; box-shadow:0 6px 0 #bfdbfe,0 8px 10px rgba(59,130,246,.2); }
  .cell.s-some .cell-face { background:#fffbeb; border-color:#fcd34d; box-shadow:0 6px 0 #f6d264,0 8px 10px rgba(245,158,11,.22); }
  .cell.s-all  .cell-face { background:#f0fdf4; border-color:#86efac; box-shadow:0 6px 0 #86efac,0 8px 10px rgba(22,163,74,.2); }
  .cell.s-perfect .cell-face { background:linear-gradient(#fffbe6,#fef3c7); border-color:var(--amber);
                     box-shadow:0 6px 0 #eab308,0 9px 12px rgba(234,179,8,.35); }
  .cell.s-ref .cell-no, .cell.s-some .cell-no, .cell.s-all .cell-no, .cell.s-perfect .cell-no { color:var(--deep); }
  /* いま挑戦中（つぎのマス）を光らせる */
  .cell.current .cell-face { border-color:var(--brand); box-shadow:0 6px 0 var(--brand),0 0 0 3px rgba(180,83,9,.25),0 10px 14px rgba(180,83,9,.3); }
  .cell.current::after { content:"つぎはここ"; position:absolute; top:-16px; left:50%; transform:translateX(-50%);
                         background:var(--brand); color:#fff; font-size:10px; font-weight:bold;
                         padding:2px 7px; border-radius:8px; white-space:nowrap; }
  /* プレイヤーの駒 */
  .cell.here .cell-face::before { content:"🧑‍🎓"; position:absolute; top:-20px; left:50%;
                         transform:translateX(-50%); font-size:22px; filter:drop-shadow(0 2px 2px rgba(0,0,0,.25)); }

  .start-flag, .goal-flag { text-align:center; font-size:22px; margin:4px 0; transform:translateZ(1px); }
  .goal-flag .g-txt, .start-flag .s-txt { display:block; font-size:12px; font-weight:bold; color:var(--brand); }

  @media (hover:hover) {
    .cell:hover .cell-face { transform:translateY(-2px); }
    .home-link:hover, .book-link:hover { filter:brightness(0.96); }
  }
  .cell:active .cell-face { transform:translateY(3px); box-shadow:0 3px 0 #e2cfa4,0 4px 6px rgba(120,80,20,.18); }

  /* 章一覧（テキストリンク・すごろくが苦手な人向けの直リンク） */
  .books { margin:18px 0 0; }
  .books h2 { font-size:15px; color:var(--deep); text-align:center; margin-bottom:8px; }
  .book-row { display:flex; align-items:center; gap:8px; background:#fff; border:1.5px solid var(--line);
              border-radius:12px; padding:8px 12px; margin-bottom:7px; }
  .book-row .bk-vol { flex:none; font-weight:bold; color:var(--brand); font-size:13px; min-width:52px; }
  .book-row .bk-title { flex:1; font-size:14px; font-weight:bold; color:#44403c; }
  .book-link { flex:none; text-decoration:none; font-size:12px; font-weight:bold; border-radius:10px;
               padding:5px 10px; }
  .book-link.wb { background:var(--brand); color:#fff; }
  .book-link.ref { background:#fffbeb; color:var(--brand); border:1.5px solid var(--line); }
  .grade-head { font-size:13px; font-weight:bold; color:var(--deep); margin:12px 0 6px; padding-left:2px; }

  footer { text-align:center; margin-top:26px; color:#a8a29e; font-size:12px; }
</style></head><body>
<header class="top wrap">
  <div class="badge">つづもん 歴史</div>
  <h1>🗺 歴史すごろく</h1>
  <div class="sub">マスを進めて日本の歴史を制覇しよう！ 解いたところがどんどんクリアに変わるよ。</div>
</header>
<div class="overall"><div class="ov-bar"><div class="ov-fill" id="ovFill"></div></div>
  <div class="ov-txt" id="ovTxt"></div></div>
<div class="legend">
  <span class="lg"><span class="dot d-none"></span>まだ</span>
  <span class="lg"><span class="dot d-ref"></span>📖 参考書を読んだ</span>
  <span class="lg"><span class="dot d-some"></span>✏️ 一部を解いた</span>
  <span class="lg"><span class="dot d-all"></span>✅ 全部解いた</span>
  <span class="lg"><span class="dot d-perfect"></span>👑 全問正解</span>
</div>
<div class="board-wrap"><div class="wrap"><div class="board" id="board">
  <div class="start-flag">🏁<span class="s-txt">スタート</span></div>
  <div id="cells" style="display:none">__CELLS__</div>
  <div class="goal-flag">🏆<span class="g-txt">ゴール（歴史マスター）</span></div>
</div></div></div>

<div class="wrap books" id="books"></div>
<footer>つづもん 歴史すごろく　｜　全__TOTAL__単元</footer>

<script>
(function () {
  var MANIFEST = __MANIFEST__;
  var GRADE_STARTS = __GRADE_STARTS__;
  var ROW = 4; // 1行のマス数（snake配置）

  function ls(key) { try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) { return {}; } }

  // 単元ごとのクリア種別を求める
  function stateOf(cell) {
    var ch = cell.dataset.ch, tid = cell.dataset.tid;
    var nq = +cell.dataset.nq || 0;
    var wb = ls('tzmwb-' + ch), r = wb.r || {};
    var done = 0, correct = 0;
    var pref = ['qa-' + tid + '-', 'qz-' + tid + '-', 'wr-' + tid + '-'];
    Object.keys(r).forEach(function (k) {
      for (var i = 0; i < pref.length; i++) {
        if (k.indexOf(pref[i]) === 0) { done++; if (r[k] === 1) correct++; break; }
      }
    });
    var refV = cell.dataset.ref;
    var refRead = refV && ls('tzmref-' + ch)['d' + refV] === 1;
    if (nq > 0 && done >= nq && correct >= nq) return 'perfect';
    if (nq > 0 && done >= nq) return 'all';
    if (done > 0) return 'some';
    if (refRead) return 'ref';
    return 'none';
  }

  // snake（うねうね）配置で盤を組む。学年の変わり目に見出しを入れる。
  function layout() {
    var board = document.getElementById('board');
    var all = [].slice.call(document.querySelectorAll('#cells .cell'));
    var goal = board.querySelector('.goal-flag');
    // 既存の行を消す（再描画対応）
    [].forEach.call(board.querySelectorAll('.row, .grade-band'), function (el) { el.remove(); });

    var byGrade = {};
    all.forEach(function (c) { (byGrade[c.dataset.grade] = byGrade[c.dataset.grade] || []).push(c); });
    var order = ['中1', '中2', '中3'];
    order.forEach(function (g) {
      var list = byGrade[g]; if (!list || !list.length) return;
      var band = document.createElement('div');
      band.className = 'grade-band';
      band.innerHTML = '<span class="grade-tag">' + g + '</span><span class="grade-line"></span>';
      board.insertBefore(band, goal);
      for (var i = 0; i < list.length; i += ROW) {
        var row = document.createElement('div');
        row.className = 'row' + ((i / ROW) % 2 === 1 ? ' rev' : '');
        var slice = list.slice(i, i + ROW);
        slice.forEach(function (c) { row.appendChild(c); });
        // 端数は空マスで埋めて幅をそろえる
        for (var f = slice.length; f < ROW; f++) {
          var sp = document.createElement('span'); sp.className = 'cell'; sp.style.visibility = 'hidden';
          row.appendChild(sp);
        }
        board.insertBefore(row, goal);
      }
    });
  }

  function paint() {
    var cells = [].slice.call(document.querySelectorAll('.cell[data-tid]'));
    var cleared = 0, lastCleared = -1;
    cells.forEach(function (c, i) {
      c.classList.remove('s-ref', 's-some', 's-all', 's-perfect', 'here', 'current');
      var s = stateOf(c);
      var badge = c.querySelector('.cell-badge');
      if (s !== 'none') {
        c.classList.add('s-' + s);
        badge.textContent = s === 'perfect' ? '👑' : s === 'all' ? '✅' : s === 'some' ? '✏️' : '📖';
        cleared++; lastCleared = i;
      } else { badge.textContent = ''; }
    });
    // 駒＝最後にクリアしたマス、つぎ＝その次の未クリアマス
    if (lastCleared >= 0) cells[lastCleared].classList.add('here');
    var nextIdx = lastCleared + 1;
    while (nextIdx < cells.length && cells[nextIdx].classList.contains('s-perfect')) nextIdx++;
    if (nextIdx < cells.length) cells[nextIdx].classList.add('current');
    else if (lastCleared < 0 && cells[0]) cells[0].classList.add('current');
    // 全体進捗
    var pct = cells.length ? Math.round((cleared / cells.length) * 100) : 0;
    document.getElementById('ovFill').style.width = pct + '%';
    document.getElementById('ovTxt').textContent =
      'クリア ' + cleared + ' / ' + cells.length + ' マス（' + pct + '%）';
  }

  // 章一覧（直リンク）
  function books() {
    var box = document.getElementById('books');
    var html = '<h2>📚 本の一覧（直接ひらく）</h2>';
    var curGrade = '';
    MANIFEST.forEach(function (c) {
      if (c.grade !== curGrade) { curGrade = c.grade; html += '<div class="grade-head">' + c.grade + '</div>'; }
      html += '<div class="book-row"><span class="bk-vol">' + c.vol + '</span>'
        + '<span class="bk-title">' + c.title + '</span>'
        + '<a class="book-link wb" href="wb/' + c.ch + '/index.html">✏️ 問題</a>'
        + '<a class="book-link ref" href="ref/' + c.ch + '/index.html">📖 参考書</a></div>';
    });
    box.innerHTML = html;
  }

  // マスをタップ → その単元の問題集へ
  document.addEventListener('click', function (e) {
    var cell = e.target.closest('.cell[data-tid]');
    if (!cell) return;
    location.href = 'wb/' + cell.dataset.ch + '/index.html#t' + cell.dataset.wb;
  });

  document.getElementById('cells').style.display = '';
  layout();
  paint();
  books();
  // 別タブで進めて戻ってきたら再集計
  window.addEventListener('focus', paint);
  window.addEventListener('pageshow', paint);
})();
</script>
</body></html>"""


def generate(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(build_html(), encoding="utf-8")
    print(f"generated: {dest}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true",
                    help="marutto-study/public/tsudumon/index.html へ出力")
    args = ap.parse_args()
    generate(DEPLOY_FILE if args.deploy else OUT_FILE)
