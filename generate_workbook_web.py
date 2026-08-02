# -*- coding: utf-8 -*-
"""
問題集の「スマホ/PC対応 インタラクティブ Web 版」を生成する
（印刷用 A4 PDF = generate_history_workbook.py の兄弟。問題の選定・並びは PDF と同一）。

構成（参考書 Web 版と同じレッスンプレイヤー型）:
- 上部タブ: 🏠（目次）／年（年表でチェック）／①〜⑧（単元）
- 単元の中身は 1 問ずつ表示: A 要点まとめ（穴埋めタップで答え）→ B 一問一答（1問ずつ・
  こたえを見る→○△セルフ採点）→ C 実戦4択（タップで即判定＋解説）→ D 記述（模範解答＋
  LINE AI採点への導線）→ E 資料問題 / F 資料の対応 → 結果（正答数・復習導線）
- 進捗・成績は localStorage に保存（目次に ✓・つづきから）
- ⚠️ 「紙に印刷して解く」ボタンは**いったん撤去**（ユーザー指示 2026-08-02・公開に間に合わないため）。
  印刷用のスタイル（@media print）と巻末解答の生成は**残してある**ので、告知とボタンを
  戻せば復活する。撤去したのは導線と告知だけで、印刷そのものを壊してはいない。
- 参考書 Web 版と相互リンク（../../ref/{NN}/#t{i} ⇄ ../../wb/{NN}/#t{i}）

使い方:
  python -X utf8 generate_workbook_web.py            # 歴史19冊 → output/web/wb/{NN}/index.html
  python -X utf8 generate_workbook_web.py --deploy 04  # 指定章を配信ビルド dist-web/wb/ へ
"""
import argparse
import html
import json
import re
import shutil
import urllib.parse
from pathlib import Path

from generate_history_workbook import (
    BOOKS, CONTENT_ROOT, CONTENT_DIR, N_ITTOITTO, N_QUIZ,
    pick_flashcards, pick_quiz, rebalance_quiz, resolve_count,
    split_blanks, ruby_base, to_ruby, c_num, KATAKANA,
)
# 記述AI採点に使う Firebase Web 設定（marutto-study/.env から読む・参考書Web版と共通）
from generate_reference_web import firebase_web_config

BASE = Path(__file__).parent
OUT_DIR = BASE / "output" / "web" / "wb"
ASSET_DIR = BASE / "assets"
DEPLOY_DIR = BASE / "dist-web" / "wb"


# ── UIラインアイコン（絵文字を使わず統一トーンに。currentColor で色を継承）──
def _svg(inner, fill=False):
    attr = ('fill="currentColor"' if fill else
            'fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round"')
    return f'<svg class="mi" viewBox="0 0 24 24" {attr} aria-hidden="true">{inner}</svg>'


IC = {
    # おすすめ順（星）
    "star": _svg('<path d="M12 3.4l2.5 5 5.5.8-4 3.9 1 5.5-4.9-2.6-5 2.6 1-5.5-4-3.9 5.5-.8z"/>', fill=True),
    # 穴埋め（（　）に線）
    "ana": _svg('<path d="M9 4.7C6.7 6.3 6.1 9 6.1 12s.6 5.7 2.9 7.3"/>'
                '<path d="M15 4.7c2.3 1.6 2.9 4.3 2.9 7.3s-.6 5.7-2.9 7.3"/>'
                '<line x1="9.4" y1="12.3" x2="14.6" y2="12.3"/>'),
    # 一問一答（Q&Aの吹き出し2つ）
    "qa": _svg('<path d="M3.9 5.4h9.2a1.5 1.5 0 0 1 1.5 1.5v3.3a1.5 1.5 0 0 1-1.5 1.5H8l-4.1 2.9z"/>'
               '<path d="M20.1 10.8v5.9a1.5 1.5 0 0 1-1.5 1.5h-4.3L10.3 21v-2.3"/>'),
    # 4択（選択肢・中央が選択済み）
    "yon": _svg('<circle cx="6" cy="7" r="1.6"/><line x1="10" y1="7" x2="19" y2="7"/>'
                '<circle cx="6" cy="12.4" r="1.6" fill="currentColor"/><line x1="10" y1="12.4" x2="19" y2="12.4"/>'
                '<circle cx="6" cy="17.8" r="1.6"/><line x1="10" y1="17.8" x2="19" y2="17.8"/>'),
    # 記述（文書＋行）
    "doc": _svg('<path d="M6.6 3.6H13l4.4 4.4V19a1.5 1.5 0 0 1-1.5 1.5H6.6A1.5 1.5 0 0 1 5.1 19V5.1A1.5 1.5 0 0 1 6.6 3.6z"/>'
                '<path d="M12.8 3.7V8.4h4.6"/><line x1="8" y1="13" x2="14.5" y2="13"/>'
                '<line x1="8" y1="16.3" x2="12.6" y2="16.3"/>'),
    # ヘッダー: 参考書（本）・問題（ペン）・目次（家）
    "book": _svg('<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v15.5H5.5A1.5 1.5 0 0 0 4 20.5z"/>'
                 '<path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H13v15.5h5.5A1.5 1.5 0 0 1 20 20.5z"/>'),
    "pen": _svg('<path d="M14.6 5.3l4.1 4.1"/>'
                '<path d="M4.6 19.4l1-4.1L15.2 5.7a1.3 1.3 0 0 1 1.9 0l1.2 1.2a1.3 1.3 0 0 1 0 1.9L8.7 18.4z"/>'),
    "home": _svg('<path d="M4 11l8-6 8 6"/><path d="M6 10.2v9h12v-9"/>'),
    # 入力して答え合わせ（キーボード）・答えを見て自己採点（目）
    "kbd": _svg('<rect x="2.8" y="6.7" width="18.4" height="10.6" rx="1.8"/>'
                '<line x1="6" y1="10" x2="6.1" y2="10"/><line x1="9.4" y1="10" x2="9.5" y2="10"/>'
                '<line x1="12.8" y1="10" x2="12.9" y2="10"/><line x1="16.2" y1="10" x2="16.3" y2="10"/>'
                '<line x1="8" y1="14" x2="16" y2="14"/>'),
    "eye": _svg('<path d="M2.6 12S6 6.6 12 6.6 21.4 12 21.4 12 18 17.4 12 17.4 2.6 12 2.6 12z"/>'
                '<circle cx="12" cy="12" r="2.6"/>'),
}

# カテゴリアイコンは codex イラスト（assets/ui-icons/ic-*.png）があれば SVG より優先。
# 各章の img/ に配置して参照（トピック毎に data URI を埋め込むとページが重くなるため）。
# ic-star.png は 2026-08-01 に描き直した。以前は星に曲がりくねった道がつながっていて
# （試作の指示書が「星、または旗の立った小道」と2案を並べたため codex が両方描いた）、
# 52px では何の記号か伝わらなかった。いまは星ひとつだけ。
# 指示書は assets/ui-icons/CODEX_BRIEF_ICON_STAR.md。
UI_ICON_KEYS = ("star", "ana", "qa", "yon", "doc")
for _k in UI_ICON_KEYS:
    if (ASSET_DIR / "ui-icons" / f"ic-{_k}.png").exists():
        IC[_k] = f'<img class="mi-img" src="img/ic-{_k}.png" alt="" aria-hidden="true">'
REF_DIR = BASE / "reference"

LIFF_ID_UNITS = "2009587166-LjyCza2c"
# 記述AI採点 Cloud Function（referenceChat と同じ関数群・購入者ゲートつき）
GRADE_API = "https://asia-northeast1-chatstudy-63477.cloudfunctions.net/gradeWritten"


def esc(s: str) -> str:
    return html.escape(s)


RUBY_INLINE = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")


def ruby_reading(s: str) -> str:
    """ルビ記法の読み側を連結（{徳川家康|とくがわいえやす} → とくがわいえやす）。
    入力判定で「読みでも正解」にするために使う（LINE側 judgeTermAnswer と同義）。"""
    return RUBY_INLINE.sub(lambda m: m.group(2), s)


# つづもん公式LINEのベーシックID。`oaMessage` はトークを開いて**本文を下書き**する。
# 生徒は送信を押すだけ＝Botは reply で返せる（**配信枠を消費しない**）。
# 旧 LIFF（line.chatstudy.jp 側）はつづもんから切り離したので使わない。
TSUDUMON_OA_ID = "@215uijik"


def line_ask_url(ch_no: str, topic_name: str) -> str:
    """
    解いた単元について LINE で質問・復習するためのリンク。
    トークを開いて**本文を下書き**するだけなので、Botは reply で返せる
    ＝**配信枠を消費しない**。本文の **第N章** から単元を特定する。
    """
    text = f"「{topic_name}」（第{int(ch_no)}章）の問題を解いたよ"
    return (f"https://line.me/R/oaMessage/{TSUDUMON_OA_ID}/"
            f"?{urllib.parse.quote(text)}")


def blanks_html(text: str, start: int = 0) -> tuple[str, list[str]]:
    """[[答え]] → タップで開く空欄チップ。(html, answers)"""
    segs, answers = split_blanks(text)
    out, i = [], start
    for kind, s in segs:
        if kind == "text":
            out.append(esc(s))
        else:
            w = max(3, min(10, len(ruby_base(s)))) * 0.9
            out.append(
                f'<button class="blank" type="button">'
                f'<span class="bno">{c_num(i)}</span>'
                f'<span class="ba">{esc(s)}</span>'
                f'<span class="bl" style="width:{w}em"></span></button>')
            i += 1
    return "".join(out), answers


# 教材ゲート（中間案・ゆるめ「頭出しは見せる」）。無料単元は tsudumonCore と一致。
FREE_WORKBOOK_TOPICS = {"律令国家と奈良時代"}
# 頭出し = やり方をえらぶ＋要点まとめ＋短答の最初の数問まで。step>=5 で購入者判定。
# （2→5 に緩和: 「1問も解けないまま鍵」では、体験する前に判断させることになるため。
#   おすすめ順では M・A・短答のやり方・短答1・短答2 まで無料で解ける）
WB_LOCK_FROM = 5


def grade_of_ch(ch_no: str) -> str:
    n = int(ch_no)
    return "中1" if n <= 6 else "中2" if n <= 12 else "中3"


def build(folder: str) -> tuple[str, list[str]]:
    spec = BOOKS[folder]
    ch_no = folder[:2]
    era_dir = (CONTENT_ROOT / spec["contentDir"]) if spec.get("contentDir") else (CONTENT_DIR / folder)
    by_topic_id = {}
    for f in era_dir.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "topicId" in d:
            by_topic_id[d["topicId"]] = d
    topics = [by_topic_id[tid] for tid in spec["topics"]]

    # 参考書 Web 版の単元 index（topicId → #t番号）: 相互リンク用
    ref_index = {}
    ref_image = {}        # topicId → 単元挿絵（目次サムネ用）
    ref_sections = {}     # topicId → [節の本文（見出し＋本文）]（設問→節の対応づけ用）
    # 「解説を読む」をその場で開くための節データ（ページ内シートに出す）。
    # 参考書ページへ飛ばずに読めるので、1問ごとの往復が要らなくなる。
    ref_help_text = {}    # "topicId:節番号" → {h:見出し, b:本文, p:ここだけ覚える}
    ref_path = REF_DIR / f"{folder}.json"
    if ref_path.exists():
        ref_spec = json.loads(ref_path.read_text(encoding="utf-8"))
        for i, t in enumerate(ref_spec["topics"], 1):
            ref_index[t["topicId"]] = i
            if t.get("image"):
                ref_image[t["topicId"]] = t["image"]
            ref_sections[t["topicId"]] = [
                (sec.get("heading", "") + sec.get("lead", "") + sec.get("body", "")
                 + sec.get("point", "")).replace("**", "")
                for sec in t.get("sections", [])]
            for si, sec in enumerate(t.get("sections", []), 1):
                ref_help_text[f"{t['topicId']}:{si}"] = {
                    "h": sec.get("heading", "").replace("**", ""),
                    "b": sec.get("body", "").replace("**", ""),
                    "p": (sec.get("point") or "").replace("**", ""),
                }

    def ref_help(tid: str, *hints: str) -> str:
        """設問の答え（用語）が最もよく出てくる節へのリンク。
        参考書のページ構成は step0=単元表紙 / step1..n=節 なので、節の番号がそのまま s になる。
        当てられないときは単元の先頭へ（それでも「探しに戻る」より速い）。"""
        if tid not in ref_index:
            return ""
        secs = ref_sections.get(tid) or []
        # 答えそのもの（強い手がかり）＋設問文から拾った漢字2文字以上の語（弱い手がかり）で
        # 節ごとに点数をつけ、いちばん高い節を選ぶ。
        strong = [h for h in hints if h and len(h) >= 2]
        weak = []
        for h in hints:
            weak += [w for w in re.findall(r"[一-鿿]{2,}", h or "") if w not in strong]
        best, best_hits = 0, 0
        for si, body in enumerate(secs, 1):
            hits = sum(body.count(h) * 3 for h in strong) + sum(body.count(w) for w in weak)
            if hits > best_hits:
                best, best_hits = si, hits
        frag = f"s{best}" if best else ""
        # まずはページ内シートで開く（JS が data-sec を見て、その節をその場に出す）。
        # シートの中の「参考書でくわしく読む」を押したときだけ、参考書ページへ移動する。
        sec_key = f' data-sec-key="{esc(tid)}:{best}"' if best else ""
        return (f'<a class="sec-help"{sec_key} href="../../ref/{ch_no}/index.html'
                f'#t{ref_index[tid]}{frag}">'
                f'<svg class="sh-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6.5C10.5 5.3 8.4 4.8 6 4.8c-1 0-2 .1-2.8.3v13c.8-.2 1.8-.3 2.8-.3 2.4 0 4.5.5 6 1.7 1.5-1.2 3.6-1.7 6-1.7 1 0 2 .1 2.8.3v-13C20 4.9 19 4.8 18 4.8c-2.4 0-4.5.5-6 1.7z"/></svg>'
                f'解説を読む（ヒント）</a>')

    images: list[str] = []
    # カテゴリアイコン（codexイラスト）を img/ic-*.png として各章にコピー
    for _k in UI_ICON_KEYS:
        if (ASSET_DIR / "ui-icons" / f"ic-{_k}.png").exists():
            images.append(f"ui-icons/ic-{_k}.png|ic-{_k}.png")

    def use_img(rel: str):
        """assets/{rel} をパッケージ img/ 配下へ（サブフォルダ名は _ に潰す）"""
        p = ASSET_DIR / rel
        if not p.exists():
            return None
        flat = rel.replace("/", "_").replace("\\", "_")
        images.append(rel + "|" + flat)
        return f"img/{flat}"

    # 応援マスコット（透過PNG）。見出しは順番に回してにぎやかに。
    char_rotate = ["sensei_f_think_sm.png", "sensei_f_ok_sm.png",
                   "sensei_f_point_sm.png", "sensei_f_banzai_sm.png"]

    def char(name: str, cls: str = "wchar"):
        u = use_img("characters/" + name)
        return f'<img class="{cls}" src="{u}" alt="">' if u else ""

    views = []
    answer_sections = []  # 印刷用 巻末解答
    used_credit_imgs = set()

    # ---------- 年表でチェック（タブ「年」= t1） ----------
    check_title = spec.get("checkTitle", "年表でチェック")
    check_cols = spec.get("checkCols", ["年代", "できごと"])
    tl_rows, tl_answers = [], []
    idx = 0
    for year, ev in spec["timeline"]:
        ev_html, ans = blanks_html(ev, idx)
        idx += len(ans)
        tl_answers.extend(ans)
        tl_rows.append(f"<tr><td class='tl-year'>{esc(year)}</td><td>{ev_html}</td></tr>")
    answer_sections.append((check_title, [("", tl_answers, None)]))
    views.append(f"""
<section class="view" data-t="1">
  <div class="tband"><span class="ttag">年</span><h2>{esc(check_title)}</h2></div>
  <div class="step" data-label="{esc(check_title)}">
    <div class="howto">（　）をタップすると答えが出るよ。まずは自分で言ってから確かめよう！</div>
    <div class="reveal-all-row"><button class="reveal-all" type="button">すべての答えを表示</button></div>
    <table class="tl-table"><tr><th class="tl-year">{esc(check_cols[0])}</th><th>{esc(check_cols[1])}</th></tr>{''.join(tl_rows)}</table>
  </div>
</section>""")

    # ---------- 各単元（t2〜） ----------
    credits_map = {}
    credits_path = ASSET_DIR / "credits.json"
    if credits_path.exists():
        credits_map = {c["file"]: c for c in json.loads(credits_path.read_text(encoding="utf-8"))}

    for t_i, topic in enumerate(topics, 1):
        tid = topic["topicId"]
        vt = t_i + 1  # view index（t1=年表）
        steps = []

        # A 要点まとめ
        summary_html, summary_ans = blanks_html(spec["summaries"][tid])
        ref_link = ""
        if tid in ref_index:
            ref_link = (f'<a class="ref-link" href="../../ref/{ch_no}/index.html'
                        f'#t{ref_index[tid]}">先に参考書で理解する</a>')
        steps.append(f"""
    <div class="step" data-label="A 要点まとめ" data-sec="A">
      <div class="sec-h"><span class="sec-tag">A</span>要点まとめ<span class="sec-note">（　）をタップして確かめよう</span></div>
      {ref_link}
      <div class="summary">{summary_html}</div>
      <div class="reveal-all-row"><button class="reveal-all" type="button">すべての答えを表示</button></div>
    </div>""")

        # B 一問一答（1問1ステップ・セルフ採点）
        n_itto = resolve_count(spec, "nItto", N_ITTOITTO, len(topic["flashcards"]))
        cards = pick_flashcards(topic["flashcards"], n_itto)
        # おすすめ順で「短答」に入る手前で、答え合わせのやり方を選ぶステップ（mode=all のときだけ流れに入る）
        if cards:
            steps.append(f"""
    <div class="step mb-step" data-label="短答のやり方" data-sec="MB">
      <div class="sec-h"><span class="sec-tag">▶</span>ここからは一問一答<span class="sec-note">答え合わせのやり方をえらぼう</span></div>
      <button class="mode-btn mb-pick" type="button" data-ansall="type">
        <span class="mode-ic">{IC['kbd']}</span>
        <span class="mode-main"><span class="mode-t">入力して答え合わせ</span>
          <span class="mode-sub">こたえを打つと自動で正誤判定</span></span>
        <span class="mode-arrow">›</span></button>
      <button class="mode-btn mb-pick" type="button" data-ansall="check">
        <span class="mode-ic">{IC['eye']}</span>
        <span class="mode-main"><span class="mode-t">答えを見て自己採点</span>
          <span class="mode-sub">こたえを見て ○ △ をタップ</span></span>
        <span class="mode-arrow">›</span></button>
    </div>""")
        for i, card in enumerate(cards, 1):
            qid = f"qa-{tid}-{i}"
            expl = (f'<div class="qa-expl">{esc(card["explanation"])}</div>'
                    if card.get("explanation") else "")
            help_b = ref_help(tid, ruby_base(card["front"]), card["back"])
            steps.append(f"""
    <div class="step qa-step" data-label="B 一問一答 ({i}/{len(cards)})" data-qid="{qid}" data-kind="qa" data-sec="B" data-a="{esc(ruby_base(card['front']))}" data-r="{esc(ruby_reading(card['front']))}">
      <div class="sec-h"><span class="sec-tag">B</span>一問一答<span class="sec-note"><span class="qnum">{i} / {len(cards)}</span></span></div>
      <div class="q-text">{esc(card['back'])}</div>
      <div class="wline print-only"></div>
      <div class="b-inrow"><input class="b-in" type="text" placeholder="こたえを入力（ひらがなでもOK）" autocomplete="off" enterkeyhint="done"><button class="b-judge" type="button">判定</button></div>
      <button class="b-idk" type="button">わからない…こたえを見る</button>
      <button class="reveal" type="button">こたえを見る</button>
      {help_b}
      <div class="hidden-until">
        <div class="b-result" aria-live="polite"></div>
        <div class="qa-a">{to_ruby(card['front'])}</div>
        {expl}
        <div class="marks">
          <button class="mk mk-ok" type="button" data-v="1">できた</button>
          <button class="mk mk-ng" type="button" data-v="0">もう一度</button>
        </div>
      </div>
    </div>""")
        answer_sections.append((f"{t_i}　{topic['name']}", []))  # placeholder → 下で埋める

        # C 実戦4択（タップで即判定）
        n_quiz = resolve_count(spec, "nQuiz", N_QUIZ, len(topic["quiz"]["questions"]))
        quiz = rebalance_quiz(pick_quiz(topic["quiz"]["questions"], n_quiz), tid)
        for i, q in enumerate(quiz, 1):
            qid = f"qz-{tid}-{i}"
            opts = "".join(
                f'<button class="qopt" type="button" data-i="{j}">'
                f'<span class="opt-k">{j + 1}</span><span class="opt-t">{esc(o)}</span></button>'
                for j, o in enumerate(q["options"]))
            expl = (f'<div class="expl hidden-until">{esc(q["explanation"])}</div>'
                    if q.get("explanation") else "")
            help_c = ref_help(tid, q["options"][q["correctIndex"]], q["question"])
            steps.append(f"""
    <div class="step qz-step" data-label="C 実戦問題 ({i}/{len(quiz)})" data-qid="{qid}" data-kind="qz" data-c="{q['correctIndex']}" data-sec="C">
      <div class="sec-h"><span class="sec-tag">C</span>実戦問題<span class="sec-note"><span class="qnum">{i} / {len(quiz)}</span>　正しいものを選ぼう</span></div>
      <div class="q-text">{esc(q['question'])}</div>
      <div class="qopts">{opts}</div>
      <button class="retry-q print-hide" type="button">おしい！ もう一度考える（えらび直す）</button>
      {expl}
      {help_c}
    </div>""")

        # D 記述
        written = spec.get("written", {}).get(tid, [])
        for i, w in enumerate(written, 1):
            qid = f"wr-{tid}-{i}"
            kw = ""
            if w.get("keywords"):
                chips = "".join(f'<span class="kw-chip">{esc(k)}</span>' for k in w["keywords"])
                kw = f'<div class="kw-note">指定語句 {chips}</div>'
            steps.append(f"""
    <div class="step wr-step" data-label="D 記述問題 ({i}/{len(written)})" data-qid="{qid}" data-kind="qa" data-sec="D">
      <div class="sec-h"><span class="sec-tag">D</span>記述問題<span class="sec-note"><span class="qnum">{i} / {len(written)}</span>　文章で説明しよう</span></div>
      <div class="q-text">{esc(w['q'])}</div>
      {kw}
      {ref_help(tid, *(w.get("keywords") or []), w.get("a", ""))}
      <textarea class="w-input print-hide" rows="3" placeholder="ここに書いてみよう（書かずに頭の中で説明してもOK）"></textarea>
      <div class="w-count print-hide" data-target="{max(20, round(len(w['a']) / 10) * 10)}">0字（目安 {max(20, round(len(w['a']) / 10) * 10)}字）</div>
      <div class="wline print-only"></div><div class="wline print-only"></div>
      <div class="wr-actions">
        <button class="ai-grade print-hide" type="button" data-bankid="q-wbw-history-{ch_no}-{tid}-{i}" disabled>AI採点</button>
        <button class="reveal" type="button">わからない</button>
      </div>
      <div class="ai-result" hidden></div>
      <div class="hidden-until">
        <div class="qa-a">{esc(w['a'])}</div>
      </div>
    </div>""")

        # E 資料問題（タップで答え）
        shiryo = spec.get("shiryo", {}).get(tid, [])
        shiryo_answers = []
        s_no = 0
        for si_item, item in enumerate(shiryo, 1):
            img = use_img(item["image"])
            used_credit_imgs.add(item["image"])
            qs = []
            for w in item["questions"]:
                s_no += 1
                shiryo_answers.append(w["a"])
                qs.append(
                    f'<div class="s-q"><span class="qa-no">({s_no})</span>{esc(w["q"])}'
                    f'<button class="blank s-blank" type="button">'
                    f'<span class="ba">{esc(w["a"])}</span><span class="bl" style="width:8em"></span>'
                    f'<span class="tap-hint">タップで答え</span></button></div>')
            cap = f'<figcaption>{esc(item["caption"])}</figcaption>' if item.get("caption") else ""
            img_html = (f'<figure class="s-img"><img class="zoomable" src="{img}" alt="" loading="lazy">'
                        f'{cap}<span class="zoom-tag">画像をタップで大きく見られるよ</span></figure>') if img else ""
            verb = spec.get("shiryoVerb", "写真")
            # 資料問題も採点対象にする（data-qid が無く、結果にもまちがい直しにも出ていなかった）。
            # 答えをタップで確かめる形式なので、○×は自己申告（できた／もう一度）で受ける。
            qid = f"sh-{tid}-{si_item}"
            steps.append(f"""
    <div class="step" data-label="E 資料問題" data-sec="E" data-qid="{qid}" data-kind="self">
      <div class="sec-h"><span class="sec-tag">E</span>資料問題<span class="sec-note">{verb}を見て答えよう</span></div>
      {img_html}
      {''.join(qs)}
      <div class="marks print-hide">
        <button class="mk mk-ok" type="button" data-v="1">ぜんぶ答えられた</button>
        <button class="mk mk-ng" type="button" data-v="0">あやしい</button>
      </div>
    </div>""")

        # F 資料の対応
        match = spec.get("shiryoMatch", {}).get(tid)
        match_answers = []
        if match:
            res_cards = []
            for r in match["resources"]:
                img = use_img(r["image"])
                used_credit_imgs.add(r["image"])
                if img:
                    res_cards.append(
                        f'<figure class="m-res"><span class="m-lab">{esc(r["label"])}</span>'
                        f'<img class="zoomable" src="{img}" alt="" loading="lazy"></figure>')
            labels = [r["label"] for r in match["resources"]]
            item_rows = []
            for i, it in enumerate(match["items"], 1):
                match_answers.append(it["answer"])
                btns = "".join(
                    f'<button class="mopt" type="button" data-l="{esc(l)}">{esc(l)}</button>'
                    for l in labels)
                item_rows.append(
                    f'<div class="m-item" data-a="{esc(it["answer"])}">'
                    f'<div class="m-text"><span class="qa-no">({i})</span>{esc(it["text"])}</div>'
                    f'<div class="m-btns">{btns}</div></div>')
            # 資料の対応も採点対象に（全問正解なら1・1つでも外したら0を自動で記録する）
            steps.append(f"""
    <div class="step" data-label="F 資料の対応" data-sec="F" data-qid="mt-{tid}" data-kind="match"
         data-n="{len(match['items'])}">
      <div class="sec-h"><span class="sec-tag">F</span>資料の対応<span class="sec-note">文にあてはまる資料を選ぼう</span></div>
      <div class="m-res-row">{''.join(res_cards)}</div>
      {''.join(item_rows)}
    </div>""")

        # 結果ステップ（絵文字は使わない・ボタンは用途で色分け）
        ref_btn = ""
        if tid in ref_index:
            ref_btn = (f'<a class="big-btn ref-btn" href="../../ref/{ch_no}/index.html#t{ref_index[tid]}">'
                       f'参考書でおさらい</a>')
        # 他の形式に進むチップ（この単元にある形式だけ）
        type_chips = ['<button class="chip-mode" type="button" data-mode="A">穴埋め</button>',
                      '<button class="chip-mode" type="button" data-mode="B">短答</button>',
                      '<button class="chip-mode" type="button" data-mode="C">4択</button>']
        if written:
            type_chips.append('<button class="chip-mode" type="button" data-mode="D">記述</button>')
        steps.append(f"""
    <div class="step done-step" data-label="結果" data-sec="Z">
      <div class="done">{char("sensei_f_banzai_sm.png", "wchar done-char")}<span>「{esc(topic['name'])}」おつかれさま！</span></div>
      <div class="score-box" data-score></div>
      <button class="big-btn wrong-btn" type="button" data-mode="wrong" hidden>まちがえた問題だけやり直す<span class="btn-sub" data-wrong-sub></span></button>
      <button class="big-btn primary-next" type="button" data-primary hidden></button>
      <details class="more-actions">
        <summary>ほかにもできること</summary>
        <div class="next-modes">
          <div class="nm-h">ほかの解き方でもう一度</div>
          <div class="nm-chips">{''.join(type_chips)}</div>
        </div>
        <div class="end-btns">
          {ref_btn}
          <a class="big-btn line-btn" href="{line_ask_url(ch_no, topic['name'])}" target="_blank" rel="noopener">LINEで報告</a>
          <button class="big-btn retry-btn" type="button" data-retry>最初から</button>
          <a class="big-btn home-btn" href="../../map/index.html">単元一覧</a>
        </div>
        <p class="line-note">「LINEで報告」は、開いたらそのまま送信を押すだけ。AIに伝わって、まちがえた問題の解き直しや質問もできます。</p>
      </details>
    </div>""")

        # やり方（モード）選択: 単元の最初に出す。推奨順=従来の全ステップ。
        # 短答は「一問ずつ/まとめて採点」、短答・4択は「シャッフル」を選べる。
        mode_btn_d = ""
        if written:
            mode_btn_d = (
                '<div class="mode-card"><button class="mode-btn" type="button" data-mode="D">'
                f'<span class="mode-ic">{IC["doc"]}</span>'
                f'<span class="mode-main"><span class="mode-t">記述</span>'
                f'<span class="mode-sub">{len(written)}問</span></span>'
                '<span class="mode-arrow">›</span></button></div>')
        # 2回目以降は前回の解き方をそのまま使えるよう、いちばん上に「続きから」を出す
        # （毎回えらび直させると、単元を開くたびに2回タップが増えるだけだった）。
        # 細かいオプション（解答の仕方・順番）は既定でたたみ、必要な人だけ開く。
        mode_step = f"""
    <div class="step mode-step" data-label="やり方をえらぶ" data-sec="M">
      <div class="sec-h"><span class="sec-tag">▶</span>やり方をえらぼう<span class="sec-note">あとから何度でも変えられるよ</span></div>
      <button class="mode-btn mode-again" type="button" data-again hidden>
        <span class="mode-ic ic-star">{IC['star']}</span>
        <span class="mode-main"><span class="mode-t">前回のつづき</span>
          <span class="mode-sub" data-again-sub></span></span>
        <span class="mode-arrow">›</span></button>
      <button class="mode-btn mode-reco" type="button" data-mode="all">
        <span class="mode-ic ic-star">{IC['star']}</span>
        <span class="mode-main"><span class="mode-t">おすすめ順で解く</span>
          <span class="mode-sub">穴埋め → 短答{len(cards)}問 → 4択{len(quiz)}問{'  → 記述' if written else ''}</span></span>
        <span class="mode-arrow">›</span></button>
      <div class="mode-card"><button class="mode-btn" type="button" data-mode="A">
        <span class="mode-ic">{IC['ana']}</span>
        <span class="mode-main"><span class="mode-t">穴埋め（要点まとめ）</span>
          <span class="mode-sub">（　）をタップして確かめる</span></span>
        <span class="mode-arrow">›</span></button></div>
      <div class="mode-card"><button class="mode-btn" type="button" data-mode="B">
        <span class="mode-ic">{IC['qa']}</span>
        <span class="mode-main"><span class="mode-t">一問一答（入力）</span>
          <span class="mode-sub">{len(cards)}問・入力して自動で正誤判定</span></span>
        <span class="mode-arrow">›</span></button>
        <details class="mode-opts-wrap"><summary>解き方をこまかく決める</summary>
        <div class="mode-opts">
          <div class="opt-row"><span class="opt-lb">解答</span><button class="opt-chip on" type="button" data-opt="ansB" data-val="0">答えを入力</button><button class="opt-chip" type="button" data-opt="ansB" data-val="1">見て確認</button></div>
          <div class="opt-row"><span class="opt-lb">順番</span><button class="opt-chip on" type="button" data-opt="shufB" data-val="0">そのまま</button><button class="opt-chip" type="button" data-opt="shufB" data-val="1">シャッフル</button></div>
        </div></details>
      </div>
      <div class="mode-card"><button class="mode-btn" type="button" data-mode="C">
        <span class="mode-ic">{IC['yon']}</span>
        <span class="mode-main"><span class="mode-t">選択</span>
          <span class="mode-sub">{len(quiz)}問・タップで即判定</span></span>
        <span class="mode-arrow">›</span></button>
        <details class="mode-opts-wrap"><summary>解き方をこまかく決める</summary>
        <div class="mode-opts">
          <div class="opt-row"><span class="opt-lb">順番</span><button class="opt-chip on" type="button" data-opt="shufC" data-val="0">そのまま</button><button class="opt-chip" type="button" data-opt="shufC" data-val="1">シャッフル</button></div>
        </div></details>
      </div>
      {mode_btn_d}
    </div>"""
        steps.insert(0, mode_step)

        views.append(f"""
<section class="view" data-t="{vt}"{'' if topic['name'] in FREE_WORKBOOK_TOPICS else f' data-lock="{WB_LOCK_FROM}"'}>
  <div class="tband"><span class="tno">{t_i}</span><h2>{esc(topic['name'])}</h2>{char(char_rotate[(t_i - 1) % len(char_rotate)], "wchar tchar")}</div>
  {''.join(steps)}
</section>""")

        # 印刷用 巻末解答
        groups = [
            ("A 要点まとめ", [f"{c_num(i)} {a}" for i, a in enumerate(summary_ans)], False),
            ("B 一問一答", [f"({i+1}) {ruby_base(c['front'])}" for i, c in enumerate(cards)], False),
            ("C 実戦問題", [f"({i+1}) {KATAKANA[q['correctIndex']]}（{q['options'][q['correctIndex']]}）"
                          for i, q in enumerate(quiz)], False),
        ]
        if written:
            groups.append(("D 記述問題", [f"({i+1}) {w['a']}" for i, w in enumerate(written)], True))
        if shiryo_answers:
            groups.append(("E 資料問題", [f"({i+1}) {a}" for i, a in enumerate(shiryo_answers)], False))
        if match_answers:
            groups.append(("F 資料の対応", [f"({i+1}) {a}" for i, a in enumerate(match_answers)], False))
        answer_sections[-1] = (f"{t_i}　{topic['name']}", groups)

    # ---------- ホーム ----------
    def toc_thumb(tid):
        img = ref_image.get(tid)
        u = use_img("reference/" + img) if img else None
        return f'<img class="toc-thumb" src="{u}" alt="" loading="lazy">' if u else '<span class="toc-thumb ph"></span>'
    toc_items = []
    for i, t in enumerate(topics, 1):
        toc_items.append(
            f'<button class="toc-item" data-go="{i + 1}">{toc_thumb(t["topicId"])}'
            f'<span class="toc-no">{i}</span>'
            f'<span class="toc-name">{esc(t["name"])}</span>'
            f'<span class="toc-state" data-state-t="{i + 1}"></span>'
            f'<span class="toc-arrow">›</span></button>')

    ref_home = ""
    if ref_index:
        ref_home = f'<a class="big-btn ref-btn" href="../../ref/{ch_no}/index.html">参考書を開く</a>'

    credits_html = ""
    lines = []
    for f in sorted(used_credit_imgs):
        c = credits_map.get(f)
        if c:
            lines.append(f"{esc(c['source'])}（{esc(c['artist'])} / {esc(c['license'])} / Wikimedia Commons）")
    if lines:
        credits_html = '<div class="credits">画像出典: ' + "　".join(lines) + "</div>"

    home = f"""
<section class="view home" data-t="0">
  <div class="home-topline">
    <div class="badge3"><span class="b-vol">{esc(spec['volume'])}</span><span class="b-kind">問題集</span></div>
  </div>
  <header class="top hometop">
    <div class="ht-main">
      <h1 class="ht-title">{esc(spec['title'])}</h1>
      <div class="sub">{esc(spec['subtitle'])}</div>
    </div>
    <div class="ht-mascot">{char("char_sensei_f_sm.png", "wchar")}<span class="ht-bubble">いっしょに<br>がんばろう！</span></div>
  </header>
  <div class="bookprog"><div class="bp-txt" id="bookTxt">解き終えた単元 0 / 0</div>
    <div class="bp-bar"><div class="bp-fill" id="bookFill"></div></div></div>
  <button class="resume" id="resumeBtn" hidden>▶ つづきから解く<span id="resumeWhere"></span></button>
  <button class="big-btn review-btn" id="reviewBtn" type="button" hidden>まちがえた問題だけ解き直す<span class="btn-sub" id="reviewSub"></span></button>
  <nav class="toc">
    <div class="toc-head">
      <div class="toc-h">単元を選択</div>
      <button class="toc-cal" data-go="1">{esc(check_title)}<span class="cal-go">›</span></button>
    </div>
    {''.join(toc_items)}
  </nav>
  {ref_home}
  {credits_html}
  <footer class="foot">
    <div>つづもん 問題集</div>
    <div class="foot-note">ダウンロード済みのA4版PDF（書き込みレイアウト）もあわせてどうぞ。</div>
  </footer>
</section>"""

    # ---------- 印刷用 巻末解答 ----------
    ans_blocks = []
    for title, groups in answer_sections:
        parts = []
        for label, items, block in groups:
            label_html = f'<span class="a-label">{esc(label)}</span>' if label else ""
            if block:
                cells = "".join(f'<div class="a-written">{esc(x)}</div>' for x in items)
            else:
                cells = "　".join(f'<span class="a-item">{esc(x)}</span>' for x in items)
            parts.append(f'<div class="a-group">{label_html}{cells}</div>')
        ans_blocks.append(f'<div class="a-topic"><div class="a-title">{esc(title)}</div>{"".join(parts)}</div>')
    print_answers = f"""
<section class="print-answers print-only">
  <h2 class="ans-band">解答</h2>
  {''.join(ans_blocks)}
</section>"""

    # ── まちがい直し（この本の全単元をまたぐ復習ビュー）──
    #   これまで「まちがえた問題だけやり直す」は単元の中でしか使えなかった。
    #   目次から押すと、章ぜんぶの誤答をここに集めて（JSが複製して）順に出す。
    review_view = f"""
<section class="view review-view" data-t="{len(topics) + 2}">
  <div class="tband"><span class="ttag">R</span><h2>まちがえた問題だけ</h2></div>
  <div class="step" data-label="まちがい直し" data-sec="RH">
    <div class="sec-h"><span class="sec-tag">R</span>まちがい直し<span class="sec-note" id="revNote"></span></div>
    <div class="howto">この本のなかで、まちがえた問題・あやしかった問題を集めたよ。<br>
      正解できた問題は、この一覧から消えていくよ。</div>
  </div>
  <div id="revSlot"></div>
  <div class="step done-step" data-label="結果" data-sec="Z">
    <div class="done"><span>まちがい直し おつかれさま！</span></div>
    <div class="score-box" data-score></div>
    <button class="big-btn retry-btn" type="button" data-go="0">目次にもどる</button>
  </div>
</section>"""

    # 問題集のビュー番号（t0=ホーム, t1=年表, t2〜=単元）→ 参考書の単元番号
    ref_views = [0, 0] + [ref_index.get(t["topicId"], 0) for t in topics] + [0]

    # 単元の選択はドロワー（下から出る一覧）。番号の丸タブは19単元で見切れていた。
    drawer = ('<button class="dw-item" data-go="1" data-dw="1" type="button">'
              '<span class="dw-no">年表</span>'
              f'<span class="dw-name">{esc(check_title)}</span>'
              '<span class="dw-state" data-state-t="1"></span></button>'
              + "".join(
                  f'<button class="dw-item" data-go="{i + 1}" data-dw="{i + 1}" type="button">'
                  f'<span class="dw-no">{i}</span>'
                  f'<span class="dw-name">{esc(t["name"])}</span>'
                  f'<span class="dw-state" data-state-t="{i + 1}"></span></button>'
                  for i, t in enumerate(topics, 1)))

    page = (TEMPLATE
            .replace("__TITLE__", f"{spec['volume']} {spec['title']}｜つづもん問題集")
            .replace("__HEADBAR__", f"{esc(spec['volume'])} {esc(spec['title'])}（問題集）")
            .replace("__DRAWER__", drawer)
            .replace("__SECTIONS__", json.dumps(ref_help_text, ensure_ascii=False))
            .replace("__STORAGE_KEY__", f"tzmwb-{ch_no}")
            .replace("__CH_NO__", ch_no)
            .replace("__GRADE__", grade_of_ch(ch_no))
            .replace("__GRADE_API__", GRADE_API)
            .replace("__FIREBASE_WEB_CONFIG__", json.dumps(firebase_web_config()))
            .replace("__REF_VIEWS__", json.dumps(ref_views))
            .replace("__VIEWS__", home + "".join(views) + review_view + print_answers))
    return page, images


TEMPLATE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<script>if(location.hostname==='tsudumon.web.app'){location.replace('https://tsudumon.jp'+location.pathname+location.search+location.hash);}</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#fffdf8">
<link rel="manifest" href="../../manifest.webmanifest">
<title>__TITLE__</title>
<script>
// 表示設定（文字サイズ・配色）は描画前に当てる（あとから当てるとチラつくため）。
// 参考書ページと同じ localStorage['tzm-view'] を共有する。
(function () {
  var v = {};
  try { v = JSON.parse(localStorage.getItem('tzm-view') || '{}') || {}; } catch (e) {}
  var th = v.theme || 'auto';
  var dark = th === 'dark' || (th === 'auto' && window.matchMedia
             && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  if (v.fs) document.documentElement.style.setProperty('--fs', v.fs);
  if (v.ruby === 0) document.documentElement.classList.add('noruby');
  window.__tzmView = v;
})();
</script>
<style>
  /* 配色は変数だけで切り替える（下の [data-theme="dark"] が夜モード）。
     --fs は文字サイズ設定（小/ふつう/大/特大）の倍率。参考書ページと共通。 */
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --cream:#fffdf8; --line:#fde68a;
          --ok:#16a34a; --ng:#dc2626;
          --ink:#1c1917; --ink2:#44403c; --ink3:#6f675e; --card:#fff; --card2:#fff9ef;
          --edge:#f0e6d2; --edge2:#e2d5bd; --tint:#fffbeb; --shadow:rgba(120,80,20,.14);
          --fs:1; }
  :root[data-theme="dark"] {
    --brand:#f0a355; --deep:#ffd9a8; --amber:#f59e0b; --cream:#17140f; --line:#5c4a1e;
    --ok:#4ade80; --ng:#f87171;
    --ink:#f2ece2; --ink2:#ded5c7; --ink3:#a89d8c; --card:#221d16; --card2:#1e1a14;
    --edge:#3a3128; --edge2:#453a2d; --tint:#2a2318; --shadow:rgba(0,0,0,.5); }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         font-size:calc(16px * var(--fs)); line-height:1.95; color:var(--ink);
         background:var(--cream);
         padding-bottom:86px; }
  .wrap { max-width:640px; margin:0 auto; padding:0 16px 24px; }
  ruby rt { font-size:0.5em; color:var(--ink3); }
  :root.noruby rt { display:none; }
  .print-only { display:none; }
  /* キーボード操作の現在地を必ず見せる */
  :focus-visible { outline:3px solid var(--amber); outline-offset:2px; border-radius:6px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.001ms !important; animation-iteration-count:1 !important;
                             transition-duration:.001ms !important; scroll-behavior:auto !important; }
  }
  .sr-only { position:absolute; width:1px; height:1px; margin:-1px; padding:0; overflow:hidden;
             clip:rect(0 0 0 0); white-space:nowrap; border:0; }

  /* ── 上部バー ── */
  /* 下へ進んでいる間は隠す（LINE内ブラウザは上下にLINEのUIが入り、本文が狭いため） */
  .bar { position:sticky; top:0; z-index:10; background:var(--cream);
         backdrop-filter:blur(6px); border-bottom:1px solid var(--edge);
         transition:transform .22s ease; }
  body.hidebar .bar { transform:translateY(-100%); }
  .bar-in { max-width:640px; margin:0 auto; padding:5px 12px 0; }
  .bar-row { display:flex; align-items:center; gap:8px; }
  /* 問題集⇄参考書の切替（どのページからでも1タップ・相手側は読みかけの位置に着地） */
  /* どのページからでも「本の一覧（すごろく）」へ戻れる常設ボタン。
     タブ列の 🏠 は「この本の目次」なので、こちらは 🗺＋文字でトップだと分かるようにする。 */
  .tophome { flex:none; height:30px; padding:0 12px; font-size:11.5px; font-weight:bold;
             color:#fff; background:var(--deep); border-radius:15px; text-decoration:none;
             display:inline-flex; align-items:center; gap:5px; white-space:nowrap;
             box-shadow:0 2px 0 #5b1e0b; transition:filter .12s; }
  .th-ic { width:14px; height:14px; fill:currentColor; flex:none; }
  @media (hover:hover) { .tophome:hover { filter:brightness(1.12); } }
  /* 参考書⇄問題の切りかえタブ。押せると分かるよう、非選択側は白ボタン風＋ホバー反応 */
  .swap { flex:none; display:inline-flex; gap:3px; padding:2px; border-radius:16px;
          background:#f0e2c3; }
  .sw { font-size:11.5px; font-weight:bold; color:var(--brand); padding:4px 12px; text-decoration:none;
        white-space:nowrap; cursor:pointer; border-radius:13px; background:#fff;
        transition:filter .12s, background-color .12s; }
  .sw.on { background:var(--brand); color:#fff; cursor:default; box-shadow:0 1px 2px rgba(180,83,9,.3); }
  @media (hover:hover) { .sw:not(.on):hover { background:#fff8ec; filter:brightness(0.98); } }
  .sw[hidden] { display:none; }
  /* 設問ごとの「解説を見る」（その問題の根拠になる節へ直行） */
  .sec-help { display:inline-flex; align-items:center; gap:5px; font-size:11.5px; font-weight:bold;
              color:var(--brand); background:#fffbeb; border:1.5px solid var(--line);
              border-radius:14px; padding:4px 12px; text-decoration:none; margin-top:8px; cursor:pointer; }
  .sh-ic { width:14px; height:14px; fill:currentColor; flex:none; }
  .bar-title { font-weight:bold; color:var(--deep); font-size:14px; flex:1;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bar-step { flex:none; font-size:11px; font-weight:bold; color:var(--brand); }
  /* 初回だけ出す操作ヒント（PCはキー、スマホはスワイプ） */
  .hintbar { position:fixed; left:50%; transform:translateX(-50%); bottom:132px; z-index:35;
             background:rgba(28,25,23,.88); color:#fff; font-size:12.5px; font-weight:bold;
             border-radius:20px; padding:8px 16px; box-shadow:0 4px 14px rgba(0,0,0,.3);
             animation:hintIn .3s ease; }
  .hintbar[hidden] { display:none; }
  @keyframes hintIn { from { opacity:0; transform:translate(-50%,10px); }
                      to { opacity:1; transform:translate(-50%,0); } }
  /* 単元の選択はドロワー（下から出る一覧）。丸タブ横スクロールは19単元では
     見切れて番号も読めず、上部バーの幅も食っていたためやめた。 */
  .unitbtn { flex:1; min-width:0; height:30px; padding:0 8px 0 11px; border:1.5px solid var(--line);
             background:var(--tint); color:var(--brand); border-radius:15px; cursor:pointer;
             font-family:inherit; font-size:12px; font-weight:bold; display:inline-flex;
             align-items:center; gap:6px; overflow:hidden; }
  .ub-name { flex:1; min-width:0; text-align:left; white-space:nowrap; overflow:hidden;
             text-overflow:ellipsis; }
  .ub-caret { flex:none; opacity:.7; }
  @media (hover:hover) { .unitbtn:hover { background:#fff2d6; } }
  .cfgbtn { flex:none; width:30px; height:30px; border-radius:50%; border:1.5px solid var(--line);
            background:var(--tint); color:var(--brand); cursor:pointer; font-size:14px;
            display:inline-flex; align-items:center; justify-content:center; font-family:inherit; }
  .cfg-ic { width:16px; height:16px; fill:currentColor; }
  .drawer { position:fixed; inset:0; z-index:60; display:flex; align-items:flex-end;
            justify-content:center; }
  .drawer[hidden] { display:none; }
  .dw-back { position:absolute; inset:0; background:rgba(40,26,10,.5); border:none; width:100%; }
  .dw-panel { position:relative; width:100%; max-width:640px; max-height:82vh; display:flex;
              flex-direction:column; background:var(--cream);
              border-radius:20px 20px 0 0; padding-bottom:env(safe-area-inset-bottom);
              box-shadow:0 -8px 30px rgba(0,0,0,.3); animation:dwUp .22s ease; }
  @keyframes dwUp { from { transform:translateY(18px); opacity:.6; } to { transform:none; opacity:1; } }
  .dw-head { display:flex; align-items:center; gap:8px; padding:14px 16px 10px;
             font-size:16px; font-weight:bold; color:var(--deep); border-bottom:1px solid var(--edge); }
  .dw-close { margin-left:auto; border:none; background:none; color:var(--ink3); font-size:26px;
              line-height:1; cursor:pointer; padding:0 6px; font-family:inherit; }
  .dw-list { overflow-y:auto; padding:8px 12px 16px; -webkit-overflow-scrolling:touch; }
  .dw-item { display:flex; align-items:center; gap:10px; width:100%; text-align:left;
             background:var(--card); border:1.5px solid var(--edge); border-radius:12px;
             padding:11px 12px; margin-bottom:7px; font-family:inherit; font-size:14.5px;
             font-weight:bold; color:var(--ink2); cursor:pointer; line-height:1.4; }
  .dw-item.on { border-color:var(--brand); background:var(--tint); }
  .dw-no { flex:none; min-width:26px; height:26px; padding:0 6px; border-radius:13px;
           background:var(--amber); color:#fff;
           display:inline-flex; align-items:center; justify-content:center; font-size:13px; }
  .dw-item.on .dw-no { background:var(--brand); }
  .dw-name { flex:1; min-width:0; }
  .dw-state { flex:none; font-size:11px; font-weight:bold; color:var(--ok); }
  .dw-state.doing { color:var(--brand); }
  .dw-home { justify-content:center; background:var(--tint); }
  @media (hover:hover) { .dw-item:hover { background:#fff8ec; } }
  .cfg-row { display:flex; align-items:center; gap:10px; padding:10px 4px; flex-wrap:wrap; }
  .cfg-lb { flex:none; font-size:13.5px; font-weight:bold; color:var(--ink2); min-width:5.5em; }
  .cfg-chip { border:1.5px solid var(--edge2); background:var(--card); color:var(--ink2);
              border-radius:16px; padding:7px 16px; font-size:13.5px; font-weight:bold;
              cursor:pointer; font-family:inherit; }
  .cfg-chip.on { background:var(--brand); border-color:var(--brand); color:#fff; }
  .pbar { height:3px; background:#f5ecd8; border-radius:2px; overflow:hidden; }
  .pfill { height:100%; width:0; background:linear-gradient(90deg,var(--amber),#fbbf24);
           transition:width .25s ease; }

  .view { display:none; }
  .view.on { display:block; position:relative; animation:vfade .18s ease; }
  @keyframes vfade { from { opacity:.6; } to { opacity:1; } }
  .step { display:none; }
  .step.on { display:block; }
  /* 本物っぽいページめくり（2枚重ね・参考書Web版と共通）:
     進む = 今のページ自体が左とじに沿って手前にめくれて去り、下から次のページが現れる。
     戻る = 前のページが手前からめくり戻されて上に着地する。 */
  /* min-height:100% = 下に敷かれた新ページ全体を覆う（絶対配置なので view の実高さに解決される。
     これが無いと、めくれるページより新ページが長いとき下端が透けて見える） */
  .step.turn-out { display:block; position:absolute; top:0; left:0; width:100%; min-height:100%;
                   z-index:3; pointer-events:none; background:var(--cream);
                   transform-origin:left center;
                   animation:turnOut .45s cubic-bezier(.55,.06,.68,.19) forwards; }
  @keyframes turnOut {
    0%   { transform:perspective(1200px) rotateY(0); opacity:1; }
    75%  { opacity:1; }
    100% { transform:perspective(1200px) rotateY(-88deg); opacity:0; } }
  .step.turn-out::after { content:""; position:absolute; inset:0; pointer-events:none;
                          background:linear-gradient(to right, transparent 55%, rgba(124,45,18,.12)); }
  .step.on.turn-in { position:relative; z-index:3; background:var(--cream);
                     transform-origin:left center;
                     animation:turnIn .45s cubic-bezier(.22,.72,.32,1); }
  @keyframes turnIn {
    from { transform:perspective(1200px) rotateY(-88deg); }
    to   { transform:perspective(1200px) rotateY(0); } }
  .step.turn-under { display:block; position:absolute; top:0; left:0; width:100%; z-index:1;
                     pointer-events:none; max-height:100%; overflow:hidden; }

  /* ── ホーム ── */
  .top { text-align:center; padding:26px 0 6px; }
  .badge { display:inline-block; background:var(--brand); color:#fff; font-weight:bold;
           padding:4px 16px; border-radius:20px; font-size:13px; }
  .webtag { background:rgba(255,255,255,.25); border-radius:10px; padding:1px 8px; font-size:11px; margin-left:4px; }
  .top h1 { font-size:29px; color:var(--deep); margin-top:12px; line-height:1.4; }
  .sub { color:#92400e; font-size:14px; margin-top:4px; }
  /* 目次ページのヘッダー（画像デザイン：3分割バッジ＋左寄せタイトル＋右にマスコット） */
  .home-topline { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:2px; }
  .hometop { display:flex; align-items:flex-start; gap:6px; padding:8px 2px 2px; text-align:left; }
  .ht-main { flex:1; min-width:0; text-align:center; }
  /* 本のラベル（押せない表示）: トグルに見えないようフラットな1トーンのタグに */
  .badge3 { display:inline-flex; align-items:center; gap:6px; border-radius:8px;
            background:#f4ecdb; padding:3px 10px; font-size:11.5px; font-weight:bold; }
  .badge3 span { padding:0; display:inline-flex; align-items:center; white-space:nowrap; }
  .b-vol { color:var(--brand); }
  .b-kind { color:#9a7b4f; }
  .b-web { background:var(--amber); color:#fff; }
  .ht-title { font-size:41px; color:var(--deep); margin:12px 0 0; line-height:1.12; position:relative;
              display:inline-block; padding:0 6px; letter-spacing:.01em; }
  .ht-title::before, .ht-title::after { content:none; }
  .ht-mascot { flex:none; display:flex; align-items:center; flex-direction:row-reverse; gap:9px; }
  .ht-mascot .wchar { height:84px; }
  .ht-bubble { position:relative; white-space:nowrap;
               background:#fffbeb; border:1.5px solid #f0b558; border-radius:12px; padding:6px 11px;
               font-size:11px; font-weight:bold; color:#92400e; line-height:1.3; text-align:center;
               box-shadow:0 2px 4px rgba(0,0,0,.1); }
  .ht-bubble::after { content:""; position:absolute; right:-8px; top:50%; transform:translateY(-50%);
                      border:5px solid transparent; border-left-color:#f0b558; }
  .howto { font-size:13.5px; color:#57534e; }
  .home-howto { display:flex; align-items:flex-start; gap:10px; margin-top:14px; background:#fffbeb;
                border:1.5px dashed var(--line); border-radius:14px; padding:11px 13px; text-align:left; }
  .hint-ic { flex:none; width:30px; height:30px; border-radius:50%; background:var(--amber);
             display:inline-flex; align-items:center; justify-content:center; font-size:15px; }
  .resume { display:block; width:100%; margin:16px 0 0; background:var(--brand); color:#fff;
            border:none; border-radius:14px; padding:13px; font-size:15px; font-weight:bold;
            cursor:pointer; box-shadow:0 3px 8px rgba(180,83,9,.3); font-family:inherit; }
  .resume span { font-weight:normal; font-size:12px; opacity:.9; margin-left:8px; }
  .toc { margin:16px 0 12px; background:#fff9ef; border:2px solid #f0e2c3; border-radius:16px; padding:12px; }
  .toc-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px; }
  .toc-h { font-weight:bold; color:var(--deep); font-size:16px; display:flex; align-items:center; gap:8px; }
  .toc-h::before { content:""; flex:none; width:30px; height:30px; border-radius:50%;
                   background:var(--brand) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'%3E%3Cpath d='M12 6.6C10.5 5.4 8.4 4.9 6 4.9c-1 0-2 .1-2.8.3v12.9c.8-.2 1.8-.3 2.8-.3 2.4 0 4.5.5 6 1.7 1.5-1.2 3.6-1.7 6-1.7 1 0 2 .1 2.8.3V5.2C20 5 19 4.9 18 4.9c-2.4 0-4.5.5-6 1.7z'/%3E%3C/svg%3E") center/17px no-repeat; }
  /* 「年表でチェック」へ飛ぶボタン。押せると気づかれるよう塗り＋矢印＋押し込み影で目立たせる */
  .toc-cal { flex:none; border:none; background:linear-gradient(#fbbf24,#f59e0b); color:#fff;
             font-weight:bold; border-radius:20px; padding:8px 8px 8px 14px; font-size:12.5px;
             cursor:pointer; font-family:inherit; white-space:nowrap;
             display:inline-flex; align-items:center; gap:6px;
             box-shadow:0 3px 0 #c2740a, 0 4px 8px rgba(217,119,6,.3);
             transition:transform .12s, box-shadow .12s, filter .12s; }
  @media (hover:hover) {
    .toc-cal:hover { transform:translateY(-2px); filter:brightness(1.06);
                     box-shadow:0 5px 0 #c2740a, 0 7px 12px rgba(217,119,6,.38); }
    .toc-cal:hover .cal-go { background:rgba(255,255,255,.55); }
  }
  .toc-cal:active { transform:translateY(2px); box-shadow:0 1px 0 #c2740a; }
  .cal-go { display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px;
            border-radius:50%; background:rgba(255,255,255,.35); font-size:14px; line-height:1; }
  /* 単元カード（大きめサムネ＋番号＋名前＋右矢印） */
  .toc-item { display:flex; align-items:center; width:100%; margin-bottom:8px; padding:0;
              background:#fff; border:1.5px solid #f0e2c3; border-radius:12px; overflow:hidden;
              box-shadow:0 2px 0 #ecdcbb; cursor:pointer; color:#44403c; font-weight:bold;
              font-size:15px; text-align:left; font-family:inherit; line-height:1.35; min-height:62px; }
  .toc-item:last-child { margin-bottom:0; }
  .toc-thumb { flex:none; width:80px; align-self:stretch; object-fit:cover; border:none; background:#fff7e6; }
  .toc-thumb.ph { background:linear-gradient(135deg,#fef3c7,#fde68a); align-self:stretch; }
  .toc-no { flex:none; margin-left:12px; min-width:26px; height:26px; border-radius:50%; background:var(--amber);
            color:#fff; display:inline-flex; align-items:center; justify-content:center;
            font-size:13px; padding:0 5px; }
  .toc-name { flex:1; padding:10px 6px 10px 10px; }
  .toc-arrow { flex:none; color:var(--brand); font-size:22px; font-weight:bold; padding:0 12px 0 4px; }
  /* 高さ固定: ✓ が絵文字グリフで描画される環境でも行高が揺れないように */
  .toc-state { flex:none; font-size:11px; font-weight:bold; line-height:1;
               display:inline-flex; align-items:center; height:20px; }
  .toc-state.done { color:var(--ok); }
  .toc-state.doing { color:var(--brand); background:#fffbeb; border:1px solid var(--line);
                     border-radius:10px; padding:1px 8px; }

  /* ── マスコット ── */
  .wchar { flex:none; object-fit:contain; }
  .home-cheer { display:flex; align-items:center; justify-content:center; gap:8px; margin-top:12px; }
  .home-cheer .wchar { height:58px; }
  .sp-bubble { position:relative; display:inline-block; background:#fffbeb; border:1.5px solid #f0b558;
               border-radius:12px; padding:5px 12px; font-size:13px; font-weight:bold; color:#92400e; }
  .sp-bubble.sp-taill::before { content:""; position:absolute; left:-7px; top:50%; transform:translateY(-50%);
               border:5px solid transparent; border-right-color:#f0b558; }
  .tchar { height:84px; margin-left:auto; }
  .done-char { height:52px; vertical-align:middle; margin-right:6px; }

  /* ── 単元 ── */
  .tband { display:flex; align-items:center; gap:10px; margin:18px 0 14px; }
  .tno, .ttag { flex:none; min-width:34px; height:34px; border-radius:50%; background:var(--brand); color:#fff;
         display:inline-flex; align-items:center; justify-content:center; font-size:16px;
         font-weight:bold; box-shadow:0 2px 4px rgba(180,83,9,.3); padding:0 6px; }
  .tband h2 { font-size:20px; color:var(--deep); border-bottom:3px solid var(--line);
              padding-bottom:2px; flex:1; line-height:1.4; }
  .sec-h { display:flex; align-items:center; gap:8px; font-size:16px; font-weight:bold;
           color:var(--deep); margin-bottom:10px; }
  .sec-tag { flex:none; background:var(--brand); color:#fff; border-radius:8px; width:26px; height:26px;
             display:inline-flex; align-items:center; justify-content:center; font-size:14px; }
  .sec-note { font-size:12px; font-weight:normal; color:var(--ink3); }
  .ref-link { display:inline-block; font-size:13px; font-weight:bold; color:var(--brand);
              text-decoration:none; border:1.5px solid var(--line); background:#fffbeb;
              border-radius:16px; padding:5px 14px; margin-bottom:10px; }

  /* ── やり方（モード）選択 ── */
  /* やり方をえらぶ: 各モードを丸アイコン＋本文＋右矢印のカードに（画像デザイン） */
  .mode-card { background:#fff; border:1.5px solid #f0e2c3; border-radius:16px; margin-top:12px;
               padding:6px 6px 10px; box-shadow:0 2px 0 #ecdcbb; }
  .mode-card .mode-btn { margin-top:0; border:none; box-shadow:none; background:none; padding:8px 6px; }
  /* ⚠️ display を指定する要素には [hidden] の打ち消しを必ず添える。
     UA の [hidden]{display:none} は .mode-btn の display:flex に負けるので、
     これが無いと「前回のつづき」が**解き方を保存していない人にも出てしまい**、
     押しても行き先が無い（＝押しても何も起きない）状態になる。 */
  .mode-btn[hidden] { display:none; }
  .mode-btn { display:flex; align-items:center; gap:12px; width:100%; text-align:left; margin-top:12px;
              border:none; border-radius:16px; padding:12px 10px; font-size:16px; font-weight:bold;
              color:#44403c; background:#fff; cursor:pointer; font-family:inherit; line-height:1.35;
              box-shadow:0 2px 0 #ecdcbb; border:1.5px solid #f0e2c3; }
  /* アイコン: 絵文字をやめ、ブランド色の統一ラインアイコンに（丸背景も1トーンに揃える） */
  .mode-ic { flex:none; width:52px; height:52px; border-radius:50%; display:inline-flex;
             align-items:center; justify-content:center; background:#f7e8cf; color:var(--brand); }
  .mode-ic .mi { width:27px; height:27px; display:block; }
  /* codexイラストのカテゴリアイコン（丸背景は消して、アイコン自身のバッジを見せる） */
  .mode-ic .mi-img { width:52px; height:52px; object-fit:contain; display:block; }
  .mode-ic:has(.mi-img) { background:transparent; }
  /* 星アイコン。地の色が違う2箇所で使うので、それぞれ見えるように分ける
     （オレンジのカードでは白抜き、白いカードではブランド色）。 */
  .mode-reco .ic-star { background:rgba(255,255,255,.22); color:#fff; }
  .mode-again .ic-star { background:#f7e8cf; color:var(--brand); }
  .mode-main { flex:1; min-width:0; }
  .mode-t { display:block; }
  .mode-btn .mode-sub { display:block; font-weight:normal; font-size:12.5px; color:var(--ink3); margin-top:3px; }
  .mode-arrow { flex:none; color:var(--brand); font-size:24px; font-weight:bold; padding-right:6px; }
  /* おすすめ順（オレンジの目立つカード） */
  /* 「前回のつづき」の直下に来るので、くっつかないよう間を空ける
     （2つは別の選択肢。詰めると1枚のカードに見える） */
  .mode-reco { background:linear-gradient(#f59e0b,#ea7a09); border:none; color:#fff; margin-top:14px;
               box-shadow:0 4px 0 #c2620a, 0 6px 12px rgba(180,83,9,.3); border-radius:18px; padding:14px 12px; }
  .mode-reco .mode-arrow { color:#fff; }
  .mode-flow { display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-top:7px; }
  .flow-unit { display:inline-flex; align-items:center; gap:6px; }  /* 「→ 記述」を一体で折り返す */
  .flow-chip { background:rgba(255,255,255,.95); color:var(--brand); font-size:11.5px; font-weight:bold;
               border-radius:12px; padding:3px 10px; white-space:nowrap; }
  .flow-arr { color:rgba(255,255,255,.9); font-weight:bold; font-size:12px; }
  /* オプション（一問一答・4択の中） */
  .mode-opts { margin:2px 8px 4px 70px; display:flex; flex-direction:column; gap:7px; }
  .opt-row { font-size:12.5px; font-weight:bold; color:#78716c; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .opt-lb { flex:none; color:#57534e; }
  .opt-chip { border:1.5px solid #e2d5bd; background:#fff; color:#78716c; border-radius:16px;
              padding:5px 14px; font-size:12.5px; font-weight:bold; cursor:pointer; font-family:inherit; }
  .opt-chip.on { background:var(--brand); border-color:var(--brand); color:#fff; }

  /* ── 一問一答 まとめて採点 ── */
  .bq-item { border-top:1px dashed #e2d5bd; padding:10px 0; }
  .bq-item:first-of-type { border-top:none; }
  .bq-q { font-weight:bold; }
  .bq-item .marks { margin-top:8px; }
  .mk.sel { background:#fffbeb; box-shadow:inset 0 0 0 2px currentColor; }

  /* ── 一問一答 入力して判定（.view.ans-type のときだけ入力UIを出す）── */
  .b-inrow { display:none; gap:8px; margin-top:10px; }
  .b-in { flex:1; min-width:0; border:1.5px solid #e2d5bd; border-radius:12px; padding:10px 12px;
          font-size:16px; font-family:inherit; background:#fff; }
  .b-in:focus { outline:none; border-color:var(--amber); }
  .b-judge { flex:none; border:none; border-radius:12px; background:var(--brand); color:#fff;
             font-weight:bold; font-size:14px; padding:0 18px; cursor:pointer; font-family:inherit; }
  .b-idk { display:none; margin-top:8px; background:none; border:none; color:var(--ink3);
           font-size:12.5px; text-decoration:underline; cursor:pointer; font-family:inherit; }
  .b-batch-judge { display:none; width:100%; margin-top:14px; border:none; border-radius:12px;
                   background:var(--brand); color:#fff; font-weight:bold; font-size:15px;
                   padding:12px; cursor:pointer; font-family:inherit;
                   box-shadow:0 2px 6px rgba(180,83,9,.3); }
  .ans-type .qa-step .b-inrow, .ans-type .qa-batch-step .b-inrow { display:flex; }
  .ans-type .qa-step .b-idk { display:inline-block; }
  /* 判定が済んだら「わからない…こたえを見る」は消す（答えが出たあとに残っていた） */
  .ans-type .qa-step.show .b-idk, .qa-step.show .b-idk { display:none; }
  .ans-type .qa-step .reveal, .ans-type .batch-grade { display:none; }
  .ans-type .qa-step .marks, .ans-type .qa-batch-step .marks { display:none; }
  .ans-type .b-batch-judge { display:block; }
  .show .b-batch-judge, .show .b-inrow .b-judge { display:none; }
  .show .b-in { pointer-events:none; background:#faf8f2; }
  .b-result { font-weight:bold; font-size:16px; margin-bottom:4px; }
  .b-result:empty { display:none; }
  .b-result.ok { color:var(--ok); }
  .b-result.ng { color:var(--ng); }

  /* 穴埋めチップ */
  .summary { background:#fff; border:1.5px solid #e2d5bd; border-radius:12px; padding:12px 14px;
             text-align:justify; }
  .blank { display:inline; border:none; background:none; font:inherit; cursor:pointer; padding:0; }
  .blank .bno { color:var(--brand); font-weight:bold; }
  .blank .ba { display:none; font-weight:bold; color:var(--brand);
               background:linear-gradient(transparent 55%, var(--line) 55%); padding:0 2px; }
  .blank .bl { display:inline-block; border-bottom:2px solid #a8a29e; height:1em;
               vertical-align:-2px; max-width:9em; background:#fffbeb; }
  .blank.open .ba { display:inline; }
  .blank.open .bl { display:none; }
  .tap-hint { display:none; }
  .reveal-all-row { margin-top:10px; text-align:right; }
  .reveal-all { border:1.5px solid var(--line); background:#fffbeb; color:var(--brand);
                font-weight:bold; font-size:13px; border-radius:16px; padding:6px 14px;
                cursor:pointer; font-family:inherit; }

  /* 年表 */
  .tl-table { width:100%; border-collapse:collapse; background:#fff; font-size:14px; }
  .tl-table th, .tl-table td { border:1px solid #d6cbb2; padding:6px 10px; }
  .tl-table th { background:#faf5eb; font-size:13px; }
  .tl-year { width:74px; text-align:center; white-space:nowrap; }

  /* 問題共通 */
  .q-text { font-size:16.5px; font-weight:bold; line-height:1.9; }
  .qa-no { font-weight:bold; margin-right:6px; color:var(--brand); }
  .reveal { display:block; width:100%; margin-top:14px; border:none; border-radius:12px;
            background:var(--amber); color:#fff; font-weight:bold; font-size:15px;
            padding:12px; cursor:pointer; font-family:inherit; box-shadow:0 2px 6px rgba(245,158,11,.3); }
  .hidden-until { display:none; }
  .show .hidden-until { display:block; }
  .show .reveal { display:none; }
  /* 記述: 「AI採点」と「わからない」を横並びに */
  .wr-actions { display:flex; gap:10px; margin-top:12px; }
  .wr-actions .ai-grade, .wr-actions .reveal { margin-top:0; width:auto; flex:1; }

  /* 記述のAIその場採点 */
  .ai-grade { display:block; width:100%; margin-top:12px; border:none; border-radius:12px;
              background:linear-gradient(#b45309,#8a3f07); color:#fff8ec; font-weight:bold;
              font-size:15px; padding:12px; cursor:pointer; font-family:inherit;
              box-shadow:0 2px 6px rgba(180,83,9,.3); }
  .ai-grade:disabled { opacity:.6; cursor:default; }
  @media (hover:hover) { .ai-grade:hover:not(:disabled) { filter:brightness(1.07); } }
  .ai-result { margin-top:12px; border-radius:14px; padding:12px 14px; border:2px solid var(--line);
               background:#fff; }
  .ai-result[hidden] { display:none; }
  .ai-result.v-correct { border-color:#bbe3cc; background:#f0fdf4; }
  .ai-result.v-partial { border-color:#fde68a; background:#fffbeb; }
  .ai-result.v-incorrect { border-color:#fecaca; background:#fef2f2; }
  .ai-result.v-info { border-color:var(--line); background:#fffbeb; }
  .air-head { display:flex; align-items:center; gap:8px; font-weight:bold; font-size:16px; }
  .air-badge { flex:none; width:30px; height:30px; border-radius:50%; display:inline-flex;
               align-items:center; justify-content:center; color:#fff; font-size:17px; }
  .v-correct .air-badge { background:var(--ok); }
  .v-partial .air-badge { background:var(--amber); }
  .v-incorrect .air-badge { background:var(--ng); }
  .air-line { margin-top:8px; font-size:13.5px; line-height:1.7; color:#44403c; }
  .air-line b { color:var(--deep); }
  .air-login { display:inline-block; margin-top:6px; color:var(--brand); font-weight:bold;
               text-decoration:underline; cursor:pointer; }
  .air-spin { display:inline-block; width:16px; height:16px; border:2px solid #e2d5bd;
              border-top-color:var(--brand); border-radius:50%; animation:airspin .7s linear infinite;
              vertical-align:-3px; margin-right:6px; }
  @keyframes airspin { to { transform:rotate(360deg); } }
  .qa-a { margin-top:12px; background:#fff; border:2px solid var(--amber); border-radius:12px;
          padding:10px 14px; font-size:18px; font-weight:bold; color:var(--deep); text-align:center; }
  .qa-expl { font-size:13.5px; color:#57534e; background:#fffbeb; border-radius:10px;
             padding:8px 12px; margin-top:8px; line-height:1.8; }
  .marks { display:flex; gap:10px; margin-top:12px; }
  .mk { flex:1; border:2px solid; border-radius:12px; background:#fff; font-weight:bold;
        font-size:15px; padding:10px; cursor:pointer; font-family:inherit; }
  .mk-ok { border-color:#bbe3cc; color:var(--ok); }
  .mk-ng { border-color:#fecaca; color:var(--ng); }

  /* 4択 */
  .qopts { display:flex; flex-direction:column; gap:8px; margin-top:12px; }
  /* color を明示（iOS Safari は button のテキストを既定で青にするため） */
  .qopt { display:flex; align-items:center; gap:10px; text-align:left; background:#fff; color:#1c1917;
          border:1.5px solid #e2d5bd; border-radius:12px; padding:10px 12px; font-size:14.5px;
          cursor:pointer; font-family:inherit; line-height:1.7; }
  .opt-t { color:#1c1917; }
  .opt-k { flex:none; width:26px; height:26px; border-radius:50%; border:1.5px solid #a8a29e;
           color:#44403c; background:#fff;
           display:inline-flex; align-items:center; justify-content:center; font-size:13px; font-weight:bold; }
  .qz-step.answered .qopt { cursor:default; }
  .qopt.correct { border-color:var(--ok); background:#f0fdf4; }
  .qopt.correct .opt-k { background:var(--ok); border-color:var(--ok); color:#fff; }
  .qopt.wrong { border-color:var(--ng); background:#fef2f2; }
  .qopt.wrong .opt-k { background:var(--ng); border-color:var(--ng); color:#fff; }
  .qopt.dim { opacity:.55; }
  .expl { margin-top:10px; font-size:13.5px; color:#57534e; background:#fffbeb;
          border-radius:10px; padding:8px 12px; line-height:1.8; }
  .qz-step.answered .expl { display:block; }

  /* 記述 */
  .kw-note { font-size:13px; color:#57534e; margin-top:6px; }
  .kw-chip { display:inline-block; border:1px solid var(--brand); color:var(--brand);
             border-radius:6px; padding:0 8px; margin-left:6px; font-size:12.5px; }
  .w-input { width:100%; margin-top:12px; border:1.5px solid #e2d5bd; border-radius:12px;
             padding:10px 12px; font:inherit; font-size:14.5px; background:#fff; resize:vertical; }
  .line-mini { display:block; margin-top:10px; text-align:center; font-size:13px; font-weight:bold;
               color:#06c755; text-decoration:none; border:1.5px solid #bbe3cc; border-radius:12px;
               padding:8px; background:#f0fdf4; }

  /* 資料 */
  .s-img { margin-bottom:12px; }
  .s-img img { width:100%; border-radius:12px; border:1px solid #e2d5bd; display:block; }
  .s-img figcaption { font-size:12px; color:var(--ink3); text-align:center; margin-top:4px; }
  .s-q { margin-bottom:14px; font-size:15px; line-height:1.8; }
  .s-blank { display:block; margin:6px 0 0 26px; text-align:left; }
  .s-blank .tap-hint { display:inline; font-size:11px; color:var(--ink3); margin-left:8px; }
  .s-blank.open .tap-hint { display:none; }
  .m-res-row { display:flex; gap:8px; margin-bottom:14px; }
  .m-res { flex:1; text-align:center; }
  .m-res img { width:100%; border-radius:10px; border:1px solid #e2d5bd; }
  .m-lab { display:block; font-weight:bold; color:var(--brand); font-size:14px; }
  .m-item { background:#fff; border:1.5px solid #e2d5bd; border-radius:12px; padding:10px 12px;
            margin-bottom:10px; }
  .m-text { font-size:14.5px; line-height:1.8; }
  .m-btns { display:flex; gap:8px; margin-top:8px; }
  .mopt { flex:1; border:1.5px solid #e2d5bd; background:#fffbeb; border-radius:10px;
          font-weight:bold; font-size:15px; padding:8px; cursor:pointer; font-family:inherit; }
  .mopt.correct { border-color:var(--ok); background:#f0fdf4; color:var(--ok); }
  .mopt.wrong { border-color:var(--ng); background:#fef2f2; color:var(--ng); }

  /* 結果 */
  .done { text-align:center; font-size:17px; font-weight:bold; color:var(--deep); margin:14px 0; }
  .score-box { background:#fff; border:2px solid var(--line); border-radius:14px; padding:14px;
               margin-bottom:12px; font-size:14.5px; }
  .score-row { display:flex; justify-content:space-between; padding:4px 2px; }
  .score-row b { color:var(--brand); }
  .big-btn { display:block; width:100%; text-align:center; margin-top:10px; border:none;
             border-radius:14px; padding:13px 16px; font-size:15px; font-weight:bold;
             cursor:pointer; font-family:inherit; text-decoration:none; }
  /* 単元の終わりのボタンは **1行に2つ**。狭い画面では1列に折る。 */
  .end-btns { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:10px; }
  @media (max-width:360px) { .end-btns { grid-template-columns:1fr; } }
  .end-btns .big-btn { margin-top:0; padding:11px 8px; font-size:14px; border-radius:12px; }
  /* LINEボタン: シンプルに。補足はボタンの下へ */
  .line-block { margin-top:10px; }
  .line-btn { margin-top:0; background:#06c755; color:#fff; box-shadow:0 3px 0 #05a648; }
  .line-note { font-size:11.5px; color:var(--ink3); text-align:center; margin:6px 4px 0; line-height:1.6; }
  .btn-sub { display:block; font-weight:normal; font-size:12px; opacity:.9; }
  .ref-btn { background:#fffbeb; color:var(--brand); border:1.5px solid var(--line); }
  .retry-btn { background:#fff; color:#57534e; border:1.5px solid #e2d5bd; }
  .home-btn { background:#fff; color:#57534e; border:1.5px solid #e2d5bd; }
  /* すごろく（本一覧）へ戻るリンク */
  .home-link { display:inline-block; margin:10px 0 0; font-size:13px; font-weight:bold;
               color:var(--brand); text-decoration:none; background:#fffbeb;
               border:1.5px solid var(--line); border-radius:16px; padding:6px 14px; }
  /* まちがえた問題だけやり直す */
  .wrong-btn { background:#fef2f2; color:var(--ng); border:1.5px solid #fecaca; }
  .wrong-btn[hidden] { display:none; }
  /* ほかの解き方でもう一度（形式チップ） */
  .next-modes { margin-top:14px; background:#fff; border:1.5px solid var(--line); border-radius:14px;
                padding:12px 14px; }
  .nm-h { font-size:13px; font-weight:bold; color:var(--deep); margin-bottom:8px; }
  .nm-chips { display:flex; flex-wrap:wrap; gap:8px; }
  .chip-mode { flex:1 1 auto; min-width:calc(50% - 4px); border:1.5px solid #e2d5bd; background:#fffbeb;
               color:var(--brand); border-radius:12px; padding:10px 8px; font-size:14px; font-weight:bold;
               cursor:pointer; font-family:inherit; }

  .foot { text-align:center; margin-top:32px; color:var(--ink3); font-size:13px; }
  .foot-note { margin-top:4px; font-size:12px; }

  /* ── 下部ナビ ── */
  /* 教材ゲートのロック案内（頭出しの先） */
  .lock-ov { position:fixed; inset:0; z-index:40; background:rgba(60,40,15,.5);
             display:flex; align-items:center; justify-content:center; padding:20px; }
  .lock-ov[hidden] { display:none; }
  .lock-card { width:100%; max-width:360px; background:#fff; border-radius:18px; padding:24px 20px 18px;
               text-align:center; box-shadow:0 10px 30px rgba(0,0,0,.3); }
  .lock-ic svg { width:34px; height:34px; }
  .lock-ic { font-size:40px; }
  .lock-t { font-size:18px; font-weight:bold; color:var(--deep); margin:6px 0 6px; }
  .lock-d { font-size:13px; color:#78716c; line-height:1.8; margin-bottom:16px; }
  .lock-btn { display:block; width:100%; margin-top:10px; border:none; border-radius:13px; padding:13px;
              font-size:15px; font-weight:bold; text-decoration:none; cursor:pointer; font-family:inherit;
              transition:transform .12s ease, box-shadow .12s ease, filter .12s ease, background .12s ease; }
  .lb-trial { background:linear-gradient(135deg,#f59e0b,#d97706); color:#fff; font-size:16px;
              box-shadow:0 4px 12px rgba(217,119,6,.42); }
  .lb-trial:disabled { opacity:.6; cursor:default; box-shadow:none; }
  .lb-line { background:#06c755; color:#fff; box-shadow:0 3px 8px rgba(6,199,85,.3); }
  .lb-buy { background:#fff; color:var(--brand); border:1.5px solid var(--line); }
  .lock-btn[hidden] { display:none; }
  .lock-btn:active:not(:disabled) { transform:translateY(0); }
  @media (hover:hover) {
    .lb-trial:hover:not(:disabled) { filter:brightness(1.07); transform:translateY(-1px);
                                     box-shadow:0 6px 16px rgba(217,119,6,.5); }
    .lb-line:hover { filter:brightness(1.07); transform:translateY(-1px);
                     box-shadow:0 5px 12px rgba(6,199,85,.4); }
    .lb-buy:hover { background:#fffbeb; border-color:var(--brand); transform:translateY(-1px); }
    .lock-sublink:hover:not(:disabled) { color:var(--deep); }
    .lock-close:hover { color:#78716c; }
  }
  .lock-msg { margin-top:13px; padding:10px 12px; border-radius:11px; font-size:13px; line-height:1.7;
              background:#fffbeb; color:#92400e; border:1px solid #fde68a; }
  .lock-msg.ok { background:#ecfdf5; color:#047857; border-color:#a7f3d0; }
  .lock-msg.warn { background:#fef2f2; color:#b91c1c; border-color:#fecaca; }
  .lock-msg[hidden] { display:none; }
  .lock-sublink { display:block; width:100%; margin-top:14px; background:none; border:none; cursor:pointer;
                  color:#92400e; font-size:13px; font-family:inherit; text-decoration:underline; padding:4px; }
  .lock-sublink:disabled { opacity:.6; cursor:default; }
  .lock-sublink[hidden] { display:none; }
  .lock-close { display:block; width:100%; margin-top:12px; background:none; border:none; cursor:pointer;
                color:var(--ink3); font-size:12.5px; font-family:inherit; text-decoration:underline; }

  .navbar { position:fixed; left:0; right:0; bottom:0; z-index:10;
            background:rgba(255,253,248,.97); border-top:1px solid #f0e6d2;
            padding:10px 16px calc(10px + env(safe-area-inset-bottom)); }
  .navbar-in { max-width:640px; margin:0 auto; display:flex; align-items:center; gap:10px; }
  .nb { border:none; border-radius:14px; padding:12px 0; font-size:15px; font-weight:bold;
        cursor:pointer; font-family:inherit; }
  .nb-prev { flex:1; background:#fff; color:var(--brand); border:1.5px solid var(--line); }
  .nb-next { flex:2; background:var(--brand); color:#fff; box-shadow:0 3px 8px rgba(180,83,9,.3); }
  /* 未回答で先に進めないときは、押せないことが分かるグレーに */
  .nb-next.locked, .nb-next:disabled { background:#e7ddc9; color:#b0a488; box-shadow:none; cursor:not-allowed; }

  /* ── ホバー: マウスを乗せると「押せる」ことが分かる（タッチ端末では固着しないよう hover 端末限定）── */
  @media (hover: hover) {
    .tab, .toc-item, .reveal, .reveal-all, .batch-grade, .mk, .mopt, .blank,
    .big-btn, .nb, .resume, .mode-btn, .opt-chip, .b-judge, .b-idk, .b-batch-judge,
    .ref-link, .line-mini, .b-in, .reveal-all,
    .qz-step:not(.answered) .qopt {
      transition: filter .12s ease, background-color .12s ease; }
    /* 色つき（塗り）ボタンは少し濃くして「押せる」感を出す */
    .tab:hover, .reveal:hover, .batch-grade:hover, .big-btn:hover, .nb:hover,
    .resume:hover, .mode-reco:hover, .b-judge:hover, .b-batch-judge:hover,
    .mk:hover, .mopt:hover, .line-mini:hover,
    .opt-chip.on:hover { filter: brightness(0.94); }
    /* 白・枠線ボタン／リストは薄いアンバーで下地を変える（塗りボタンは上の brightness 側）。
       選択中(.on)チップや mode-reco は塗りなので、この背景変更から除外して文字が埋もれないように */
    .toc-item:hover, .mode-btn:not(.mode-reco):hover, .opt-chip:not(.on):hover, .reveal-all:hover,
    .ref-link:hover, .b-idk:hover, .blank:hover, .chip-mode:hover, .sec-help:hover,
    .qz-step:not(.answered) .qopt:hover { background-color: #fff8ec; }
    .b-in:hover { border-color: var(--amber); }
    /* 回答済みの4択・対応は押せないのでカーソルも通常に */
    .qz-step.answered .qopt, .m-item[data-done] .mopt { cursor: default; }
  }

  /* ── 印刷（紙のワークとして使える） ── */
  @media print {
    body { background:#fff; padding-bottom:0; font-size:10.5pt; line-height:1.8; }
    .bar, .navbar, .resume, .reveal, .marks, .reveal-all-row, .w-input, .line-mini,
    .big-btn, .qa-expl, .expl, .tap-hint, .toc-state, .home-howto, .howto, .m-btns { display:none !important; }
    .mode-step, .qa-batch-step, .b-inrow, .b-idk, .b-batch-judge, .b-result { display:none !important; }
    /* 問題選択・短答のやり方・結果などの操作用ページは紙に出さない（問題と解答だけ印刷） */
    .drawer, .sheet, .lightbox, .whynext, .review-view, .bookprog, .review-btn,
    .w-count, .retry-q, .zoom-tag, .unitbtn, .cfgbtn, .more-actions,
    .mode-step, .mb-step, .done-step, .next-modes, .chip-mode,
    .retry-btn, .home-btn, .wrong-btn, .ai-grade, .ai-result, .print-hide { display:none !important; }
    .print-only { display:block !important; }
    .view { display:block !important; }
    .step { display:block !important; margin-bottom:14px; break-inside:avoid; }
    .hidden-until { display:none !important; }
    .blank .ba { display:none !important; }
    .blank .bl { display:inline-block !important; background:none; }
    .qopt { border:none; padding:1px 0; background:none; }
    .qopt .opt-k { width:18px; height:18px; font-size:10px; }
    .qopt.correct, .qopt.wrong { background:none; border:none; }
    .qopt.correct .opt-k, .qopt.wrong .opt-k { background:none; color:#1c1917; border-color:var(--ink3); }
    .qopts { gap:2px; margin-top:4px; }
    .wline { border-bottom:1px solid #78716c; height:9mm; margin-top:2mm; }
    .toc-item, .tab { cursor:default; }
    .top { padding-top:0; }
    .tband { margin-top:8mm; break-after:avoid; }
    .m-item { break-inside:avoid; }
    .m-item::after { content:"〔　　〕"; color:#44403c; }
    .print-answers { page-break-before:always; font-size:9pt; line-height:1.9; }
    .ans-band { background:#44403c; color:#fff; text-align:center; padding:2px 0; border-radius:4px;
                margin-bottom:8px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    .a-topic { border-bottom:1px dashed #a8a29e; padding:4px 0; }
    .a-title { font-weight:bold; background:#f5f5f4; padding:0 6px; border-left:8px solid var(--brand);
               -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    .a-label { font-weight:bold; color:var(--brand); margin-right:6px; }
    .a-item { display:inline-block; margin-right:4px; }
    .a-written { padding-left:6px; }
    .credits { font-size:7.5pt; color:#78716c; border-top:1px solid #d6d3d1; margin-top:8px; }
  }
  .credits { font-size:11px; color:var(--ink3); margin-top:20px; }

  /* ── 画像タップで拡大（資料問題・資料の対応。参考書ページと同じ操作）── */
  .lightbox { position:fixed; inset:0; z-index:200; background:rgba(20,14,8,.88);
              display:flex; align-items:center; justify-content:center; padding:20px;
              -webkit-tap-highlight-color:transparent; cursor:zoom-out; }
  .lightbox[hidden] { display:none; }
  .lightbox img { max-width:96vw; max-height:90vh; border-radius:10px; background:#fffdf8;
                  box-shadow:0 8px 40px rgba(0,0,0,.55); }
  .lb-close { position:fixed; top:14px; right:16px; width:42px; height:42px; border:none;
              border-radius:50%; background:rgba(255,255,255,.92); color:#7c2d12; font-size:24px;
              line-height:1; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.3); }
  .lb-hint { position:fixed; bottom:20px; left:0; right:0; text-align:center; color:#fff;
             font-size:12px; opacity:.7; pointer-events:none; }
  .s-img img, .m-res img { cursor:zoom-in; }
  .zoom-tag { display:block; text-align:center; font-size:11px; color:var(--ink3); margin-top:3px; }

  /* ── 解説シート（参考書へ飛ばずに、その場で根拠の節を読む）── */
  .sheet { position:fixed; inset:0; z-index:70; display:flex; align-items:flex-end;
           justify-content:center; }
  .sheet[hidden] { display:none; }
  .sh-back { position:absolute; inset:0; background:rgba(40,26,10,.5); border:none; width:100%; }
  .sh-panel { position:relative; width:100%; max-width:640px; max-height:76vh; display:flex;
              flex-direction:column; background:var(--cream); border-radius:20px 20px 0 0;
              padding-bottom:env(safe-area-inset-bottom);
              box-shadow:0 -8px 30px rgba(0,0,0,.3); animation:dwUp .22s ease; }
  .sh-head { display:flex; align-items:center; gap:8px; padding:14px 16px 10px; font-size:15.5px;
             font-weight:bold; color:var(--deep); border-bottom:1px solid var(--edge); }
  .sh-body { overflow-y:auto; padding:14px 16px; font-size:14.5px; line-height:1.95;
             color:var(--ink2); -webkit-overflow-scrolling:touch; }
  .sh-body .sh-h { font-size:16px; font-weight:bold; color:var(--deep); margin-bottom:6px; }
  .sh-body .sh-point { margin-top:12px; background:#fff9c4; border-left:6px solid #fbbf24;
                       border-radius:8px; padding:10px 12px; color:#44403c; }
  .sh-more { display:block; margin:0 16px 14px; text-align:center; text-decoration:none;
             background:var(--tint); border:1.5px solid var(--line); color:var(--brand);
             font-weight:bold; font-size:14px; border-radius:12px; padding:11px; }

  /* ── 4択・記述・短答まわりの追加UI ── */
  /* 正誤は色だけで示さない（色が見分けにくい人にも伝わるよう記号を添える） */
  .opt-k::after { content:""; }
  .qopt.correct .opt-k::after { content:"○"; }
  .qopt.wrong .opt-k::after { content:"×"; }
  .qopt.correct .opt-k, .qopt.wrong .opt-k { font-size:0; }
  .qopt.correct .opt-k::after, .qopt.wrong .opt-k::after { font-size:14px; }
  /* もう一度考える（1回だけ、間違えた選択肢を消して選び直せる） */
  .retry-q { display:none; width:100%; margin-top:10px; border:1.5px solid var(--line);
             background:var(--tint); color:var(--brand); font-weight:bold; font-size:14px;
             border-radius:12px; padding:10px; cursor:pointer; font-family:inherit; }
  .qz-step.answered.can-retry .retry-q { display:block; }
  .qz-step.answered.can-retry .expl { display:none; }
  .qopt.gone { display:none; }
  /* 惜しい（1文字違い）の再入力 */
  .b-result.near { color:#b45309; }
  /* 記述の字数カウンタ */
  .w-count { text-align:right; font-size:12px; color:var(--ink3); margin-top:4px; }
  .w-count.over { color:var(--ng); font-weight:bold; }
  /* 「つぎへ」が押せない理由 */
  .whynext { position:fixed; left:50%; transform:translateX(-50%);
             bottom:calc(76px + env(safe-area-inset-bottom)); z-index:35;
             background:rgba(28,25,23,.9); color:#fff; font-size:12.5px; font-weight:bold;
             border-radius:20px; padding:8px 16px; box-shadow:0 4px 14px rgba(0,0,0,.3); }
  .whynext[hidden] { display:none; }
  /* 目次: この本の到達率／復習キュー */
  .bookprog { margin-top:14px; background:var(--card2); border:1.5px solid var(--edge);
              border-radius:14px; padding:10px 14px; }
  .bp-txt { font-size:12.5px; font-weight:bold; color:var(--brand); margin-bottom:6px; }
  .bp-bar { height:8px; background:#f0e2c3; border-radius:5px; overflow:hidden; }
  .bp-fill { height:100%; width:0; border-radius:5px;
             background:linear-gradient(90deg,var(--amber),#fbbf24); transition:width .3s ease; }
  .review-btn { background:#fef2f2; color:var(--ng); border:1.5px solid #fecaca; }
  .review-btn[hidden] { display:none; }
  .toc-state.again { color:#b45309; background:#fff7ed; border:1px solid #fdba74;
                     border-radius:10px; padding:1px 8px; }

  /* ── よるモード（配色設定 = dark）──
     個別に直書きしている白背景・薄い枠だけをまとめて上書きする。 */
  :root[data-theme="dark"] { color-scheme: dark; }
  :root[data-theme="dark"] .toc, :root[data-theme="dark"] .toc-item,
  :root[data-theme="dark"] .summary, :root[data-theme="dark"] .qopt,
  :root[data-theme="dark"] .mode-btn, :root[data-theme="dark"] .mode-card,
  :root[data-theme="dark"] .m-item, :root[data-theme="dark"] .score-box,
  :root[data-theme="dark"] .qa-a, :root[data-theme="dark"] .w-input,
  :root[data-theme="dark"] .b-in, :root[data-theme="dark"] .ai-result,
  :root[data-theme="dark"] .next-modes, :root[data-theme="dark"] .chip-mode,
  :root[data-theme="dark"] .mk, :root[data-theme="dark"] .mopt,
  :root[data-theme="dark"] .opt-chip, :root[data-theme="dark"] .cfg-chip,
  :root[data-theme="dark"] .dw-item, :root[data-theme="dark"] .sw,
  :root[data-theme="dark"] .nb-prev, :root[data-theme="dark"] .lock-card,
  :root[data-theme="dark"] .ref-link, :root[data-theme="dark"] .sec-help,
  :root[data-theme="dark"] .tl-table, :root[data-theme="dark"] .unitbtn,
  :root[data-theme="dark"] .cfgbtn, :root[data-theme="dark"] .bookprog,
  :root[data-theme="dark"] .retry-btn, :root[data-theme="dark"] .home-btn,
  :root[data-theme="dark"] .ref-btn,
  :root[data-theme="dark"] .ht-bubble, :root[data-theme="dark"] .qa-expl,
  :root[data-theme="dark"] .expl, :root[data-theme="dark"] .sp-bubble {
    background:var(--card); color:var(--ink); border-color:var(--edge); }
  :root[data-theme="dark"] .opt-t, :root[data-theme="dark"] .m-text,
  :root[data-theme="dark"] .q-text, :root[data-theme="dark"] .summary { color:var(--ink); }
  :root[data-theme="dark"] .toc-item { box-shadow:none; }
  :root[data-theme="dark"] .pbar, :root[data-theme="dark"] .bp-bar { background:#3a3128; }
  :root[data-theme="dark"] .swap { background:#2f281e; }
  :root[data-theme="dark"] .navbar, :root[data-theme="dark"] .bar { background:var(--cream); }
  :root[data-theme="dark"] .tl-table th { background:#2a2318; }
  :root[data-theme="dark"] .tl-table th, :root[data-theme="dark"] .tl-table td { border-color:var(--edge2); }
  :root[data-theme="dark"] .blank .bl { background:#2a2318; border-bottom-color:var(--ink3); }
  :root[data-theme="dark"] .qopt.correct { background:#12291b; }
  :root[data-theme="dark"] .qopt.wrong { background:#2c1616; }
  :root[data-theme="dark"] .s-img img, :root[data-theme="dark"] .m-res img,
  :root[data-theme="dark"] .toc-thumb { filter:brightness(.88); }
</style></head><body>
<div class="bar"><div class="bar-in">
  <div class="bar-row">
    <a class="tophome" href="../../map/index.html" aria-label="単元一覧へもどる"><svg class="th-ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/></svg>単元一覧</a>
    <div class="swap" role="tablist" aria-label="参考書と問題の切りかえ"><a class="sw" id="swRef" role="tab">参考書</a><span class="sw on">問題</span></div>
    <button class="unitbtn" id="unitBtn" type="button" aria-haspopup="dialog" aria-label="単元をえらぶ">
      <span class="ub-name" id="unitBtnName">目次</span><span class="ub-caret" aria-hidden="true">▾</span></button>
    <button class="cfgbtn" id="cfgBtn" type="button" aria-label="文字サイズ・配色の設定">
      <svg class="cfg-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18h7v2H4zm0-7h10v2H4zm0-7h16v2H4zm13.5 9L20 18l-2.5 4L15 18z"/></svg></button>
    <div class="bar-step" id="barStep"></div>
  </div>
  <div class="bar-title" hidden>__HEADBAR__</div>
  <div class="pbar"><div class="pfill" id="pfill"></div></div>
</div></div>
<div class="drawer" id="drawer" hidden>
  <button class="dw-back" id="dwBack" type="button" aria-label="閉じる"></button>
  <div class="dw-panel" role="dialog" aria-modal="true" aria-label="単元をえらぶ">
    <div class="dw-head"><span id="dwTitle">単元をえらぶ</span>
      <button class="dw-close" id="dwClose" type="button" aria-label="閉じる">×</button></div>
    <div class="dw-list" id="dwList">
      <button class="dw-item dw-home" data-go="0" type="button">目次（この本のトップ）</button>
      __DRAWER__
    </div>
    <div class="dw-list" id="cfgList" hidden>
      <div class="cfg-row"><span class="cfg-lb">文字サイズ</span>
        <button class="cfg-chip" type="button" data-fs="0.9">小</button>
        <button class="cfg-chip on" type="button" data-fs="1">ふつう</button>
        <button class="cfg-chip" type="button" data-fs="1.15">大</button>
        <button class="cfg-chip" type="button" data-fs="1.3">特大</button></div>
      <div class="cfg-row"><span class="cfg-lb">配色</span>
        <button class="cfg-chip on" type="button" data-theme="light">あかるい</button>
        <button class="cfg-chip" type="button" data-theme="dark">よる</button>
        <button class="cfg-chip" type="button" data-theme="auto">端末にあわせる</button></div>
      <div class="cfg-row"><span class="cfg-lb">ルビ</span>
        <button class="cfg-chip on" type="button" data-ruby="1">表示する</button>
        <button class="cfg-chip" type="button" data-ruby="0">消す</button></div>
    </div>
  </div>
</div>
<main class="wrap" id="views">
__VIEWS__
</main>
<div class="sr-only" id="liveMsg" aria-live="polite" role="status"></div>
<div class="lightbox" id="lightbox" hidden>
  <img id="lightboxImg" alt="">
  <button class="lb-close" id="lbClose" type="button" aria-label="閉じる">×</button>
  <div class="lb-hint">タップで閉じる</div>
</div>
<div class="sheet" id="expSheet" hidden>
  <button class="sh-back" id="shBack" type="button" aria-label="閉じる"></button>
  <div class="sh-panel" role="dialog" aria-modal="true" aria-label="解説">
    <div class="sh-head"><span id="shTitle">解説</span>
      <button class="dw-close" id="shClose" type="button" aria-label="閉じる">×</button></div>
    <div class="sh-body" id="shBody"></div>
    <a class="sh-more" id="shMore" href="#">参考書でくわしく読む →</a>
  </div>
</div>
<div class="hintbar" id="hintBar" hidden></div>
<div class="whynext" id="whyNext" hidden></div>
<div class="navbar" id="navbar" hidden><div class="navbar-in">
  <button class="nb nb-prev" id="btnPrev">← まえへ</button>
  <button class="nb nb-next" id="btnNext">つぎへ →</button>
</div></div>
<div class="lock-ov" id="lockOv" hidden><div class="lock-card">
  <div class="lock-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></div>
  <div class="lock-t" id="lockT">つづきも、無料でためせます</div>
  <div class="lock-d" id="lockD">3日間は、ぜんぶの単元がつかえます。<br>気に入ったら、そのまま続けられます。</div>
  <button class="lock-btn lb-trial" id="lockTrial">🎁 3日間無料でためす</button>
  <button class="lock-btn lb-trial" id="lockSubMain" hidden>月額プランに登録（1,280円／月）</button>
  <button class="lock-btn lb-buy" id="lockParent">おうちの人にお願いする</button>
  <a class="lock-btn lb-buy" href="../../index.html">つづもんって？ くわしく見る →</a>
  <button class="lock-btn lb-line" id="lockLogin">LINEでログイン（登録ずみの方）</button>
  <div class="lock-msg" id="lockMsg" hidden></div>
  <button class="lock-sublink" id="lockSub">ためさずに月額プランに登録（1,280円／月）</button>
  <button class="lock-close" id="lockClose">とじる</button>
</div></div>

<script type="module">
// 記述AI採点のログイン（tsudumon.jp/login/ の LINE Login＝Firebase Auth。参考書ページと同じ）。
// 通常のスクリプトからは window.__tzmAuth 経由で使う（module は個別スコープのため）。
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import {
  initializeAuth, browserLocalPersistence, browserSessionPersistence,
  inMemoryPersistence, onAuthStateChanged,
} from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';
try {
  var app = initializeApp(__FIREBASE_WEB_CONFIG__);
  var auth = initializeAuth(app, {
    persistence: [browserLocalPersistence, browserSessionPersistence, inMemoryPersistence],
  });
  window.__tzmAuth = {
    ready: false,
    user: null,
    idToken: function () { return this.user ? this.user.getIdToken() : Promise.resolve(null); },
    login: function () {
      location.href = '/login/?next=' + encodeURIComponent(location.pathname + location.hash);
    },
  };
  var ENTITLEMENT_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonEntitlement';
  async function refreshEntitlement(u) {
    try {
      var idToken = await u.getIdToken();
      var res = await fetch(ENTITLEMENT_API, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: idToken }),
      });
      if (!res.ok) return;
      var data = await res.json();
      var grades = (data && data.grades) || [];
      try {
        if (grades.length === 0) {
          localStorage.removeItem('tzm-lic');
        } else {
          var exp = Math.min(Number(data.expiresAtMs) || (Date.now() + 30 * 24 * 3600 * 1000), Date.now() + 30 * 24 * 3600 * 1000);
          localStorage.setItem('tzm-lic', JSON.stringify({ g: grades, exp: exp }));
        }
      } catch (e) {}
      if (window.tzmRefreshGate) window.tzmRefreshGate();
      if (window.tzmApplyLockState) {
        window.tzmApplyLockState({ result: data && data.result, trialUsed: !!(data && data.trialUsed) });
      }
    } catch (e) { /* localStorage フォールバックのまま */ }
  }

  // ── 3日間無料体験（ロックカードの主ボタン）──
  //   1 uid 1回。サーバ（tsudumonTrialStart）で判定→成功なら refreshEntitlement で解錠。
  var TRIAL_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonTrialStart';
  var TRIAL_LABEL = '🎁 3日間無料でためす';
  function tzmTrialMsg(text, kind) {
    var el = document.getElementById('lockMsg');
    if (!el) return;
    el.textContent = text;
    el.className = 'lock-msg' + (kind ? ' ' + kind : '');
    el.hidden = false;
  }
  function tzmTrialBtn(disabled, label) {
    var b = document.getElementById('lockTrial');
    if (!b) return;
    b.disabled = disabled;
    if (label != null) b.textContent = label;
  }
  async function tzmDoTrial() {
    var u = auth.currentUser;
    if (!u) return;
    tzmTrialBtn(true, '開始しています…');   // 連打防止
    try {
      var idToken = await u.getIdToken();
      var res = await fetch(TRIAL_API, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: idToken }),
      });
      var data = {};
      try { data = await res.json(); } catch (e) {}
      if (res.ok && data && data.ok) {
        tzmTrialBtn(true, '✓ 体験を開始しました');
        tzmTrialMsg('体験開始！' + (data.expiresLabel || '3日後') + 'まで全単元つかえます 🎉', 'ok');
        setTimeout(function () { refreshEntitlement(u); }, 1600);   // 解錠＋ロックを閉じる
        return;
      }
      var reason = data && data.reason;
      if (reason === 'already_licensed') {
        tzmTrialBtn(true, '✓ ご利用いただけます');
        tzmTrialMsg(data.message || 'すでにご利用いただけます。解錠します。', 'ok');
        setTimeout(function () { refreshEntitlement(u); }, 1200);
        return;
      }
      if (reason === 'trial_used') {
        tzmTrialBtn(true, '体験は利用ずみです');
        tzmTrialMsg(data.message || '無料体験はご利用ずみです。購入すると続きが解けます。', 'warn');
        return;
      }
      tzmTrialBtn(false, TRIAL_LABEL);
      tzmTrialMsg((data && data.message) || '体験を開始できませんでした。もう一度お試しください。', 'warn');
    } catch (e) {
      tzmTrialBtn(false, TRIAL_LABEL);
      tzmTrialMsg('通信エラー。電波の良いところでもう一度お試しください', 'warn');
    }
  }
  // 通常script のクリックハンドラから呼ばれる。ログイン済みなら即実行、未ログインなら
  // pending を立ててログインへ（LINE内は無操作／外部はボタン式。戻ってきたら下で継続）。
  window.tzmStartTrial = function (next) {
    if (auth.currentUser) { tzmDoTrial(); return; }
    try { localStorage.setItem('tzm-trial-pending', '1'); } catch (e) {}
    var here = next || (location.pathname + location.hash);
    location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
  };

  // ── 月額サブスク登録（ロックカードの「月額プランに登録」ボタン）──
  //   Stripe Checkout 直付け。tzmStartCheckout はログイン往復（trial と同型）→
  //   tsudumonCreateCheckout POST → 成功で Checkout URL へ遷移。
  var CHECKOUT_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonCreateCheckout';
  var SUB_LABEL = 'ためさずに月額プランに登録（1,280円／月）';
  var SUB_MAIN_LABEL = '月額プランに登録（1,280円／月）';
  // 体験ずみの人には主ボタン（lockSubMain）が出ているので、いま見えているほうを操作する。
  function tzmSubEl() {
    var main = document.getElementById('lockSubMain');
    if (main && !main.hidden) return { el: main, label: SUB_MAIN_LABEL };
    var sub = document.getElementById('lockSub');
    return sub ? { el: sub, label: SUB_LABEL } : null;
  }
  function tzmSubBtn(disabled, label) {
    var t = tzmSubEl();
    if (!t) return;
    t.el.disabled = disabled;
    if (label != null) t.el.textContent = label === SUB_LABEL ? t.label : label;
  }
  async function tzmDoCheckout() {
    var u = auth.currentUser;
    if (!u) return;
    tzmSubBtn(true, '準備しています…');   // 連打防止（成功時はそのまま遷移）
    try {
      var idToken = await u.getIdToken();
      var res = await fetch(CHECKOUT_API, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: idToken }),
      });
      var data = {};
      try { data = await res.json(); } catch (e) {}
      if (res.ok && data && data.ok && data.url) {
        location.href = data.url;   // Stripe Checkout へ
        return;
      }
      var reason = data && data.reason;
      if (reason === 'already_subscribed') {
        tzmSubBtn(true, '✓ 登録ずみです');
        tzmTrialMsg(data.message || 'すでに月額プランにご登録いただいています。解錠します。', 'ok');
        setTimeout(function () { refreshEntitlement(u); }, 1200);
        return;
      }
      // not_configured / stripe_error / 通信失敗 はいずれも準備中として案内
      tzmSubBtn(false, SUB_LABEL);
      tzmTrialMsg('決済の準備中です。公式LINEでお知らせします。', 'warn');
    } catch (e) {
      tzmSubBtn(false, SUB_LABEL);
      tzmTrialMsg('決済の準備中です。公式LINEでお知らせします。', 'warn');
    }
  }
  // ログイン済みなら即実行、未ログインなら pending を立ててログインへ（戻ってきたら下で継続）。
  window.tzmStartCheckout = function (next) {
    if (auth.currentUser) { tzmDoCheckout(); return; }
    try { localStorage.setItem('tzm-sub-pending', '1'); } catch (e) {}
    var here = next || (location.pathname + location.hash);
    location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
  };

  // ── おうちの人にわたすカード（ロックカードの「おうちの人にお願いする」）──
  //   中学生本人は決済できない。カードを発行して「見せる画面」（QR＋台本）へ送る。
  //   設計: pdf-workbook/.steering/20260727-parent-handoff/design.md
  var INVITE_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonInviteCreate';
  function tzmParentBtn(disabled, label) {
    var el = document.getElementById('lockParent');
    if (!el) return;
    el.disabled = disabled;
    if (label != null) el.textContent = label;
  }
  async function tzmDoParentCard() {
    var u = auth.currentUser;
    if (!u) return;
    tzmParentBtn(true, '準備しています…');
    try {
      var idToken = await u.getIdToken();
      var res = await fetch(INVITE_API, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: idToken }),
      });
      var data = {};
      try { data = await res.json(); } catch (e) {}
      if (res.ok && data && data.ok && data.handoffUrl) {
        location.href = data.handoffUrl;
        return;
      }
    } catch (e) {}
    tzmParentBtn(false, 'おうちの人にお願いする');
    tzmTrialMsg('いま準備できませんでした。公式LINEの「おうちの人に見せたい」からも出せます。', 'warn');
  }
  window.tzmStartParentCard = function (next) {
    if (auth.currentUser) { tzmDoParentCard(); return; }
    try { localStorage.setItem('tzm-parent-pending', '1'); } catch (e) {}
    var here = next || (location.pathname + location.hash);
    location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
  };

  onAuthStateChanged(auth, function (u) {
    window.__tzmAuth.user = u;
    window.__tzmAuth.ready = true;
    window.tzmAuthUser = u || null;   // 通常script のゲート自動ログイン判定用
    if (u) refreshEntitlement(u);
    // 体験／登録ボタン→ログイン往復から戻ってきた継続: pending が立っていれば自動で続行
    if (u) {
      try {
        if (localStorage.getItem('tzm-trial-pending')) {
          localStorage.removeItem('tzm-trial-pending');
          tzmDoTrial();
        } else if (localStorage.getItem('tzm-sub-pending')) {
          localStorage.removeItem('tzm-sub-pending');
          tzmDoCheckout();
        } else if (localStorage.getItem('tzm-parent-pending')) {
          localStorage.removeItem('tzm-parent-pending');
          tzmDoParentCard();
        }
      } catch (e) {}
    }
    document.dispatchEvent(new CustomEvent('tzm-auth'));
  });
} catch (e) { /* 設定が無ければ採点はフォールバック（自己採点）に倒れる */ }
</script>

<script>
(function () {
  var KEY = '__STORAGE_KEY__';
  var CH = '__CH_NO__';
  var GRADE = '__GRADE__';        // この本の学年（中1/中2/中3）
  var GRADE_API = '__GRADE_API__';      // 記述AI採点 Cloud Function
  var REF_VIEWS = __REF_VIEWS__;        // 問題集のビューt → 参考書の単元番号（0＝対応なし）
  var views = [].slice.call(document.querySelectorAll('.view'));
  var tabs = [].slice.call(document.querySelectorAll('.dw-item[data-dw]'));
  // 最後のビューは「まちがい直し（章ぜんぶ）」。通常のページ送りの対象からは外す。
  var REVIEW_T = views.length - 1;
  var N = views.length - 2;
  var state = { t: 0, s: 0 };
  var lastDir = 1;
  var rendered = null; // 直前に表示していた {t, s}（ページめくり演出用）
  var navigating = false;  // popstate 由来の移動中は履歴を積まない

  // ── 問題集 ⇄ 参考書の行き来（相手側の読みかけページに着地） ──
  function refHref(t) {
    var base = '../../ref/' + CH + '/index.html';
    var v = REF_VIEWS[t] || 0;
    if (!v) return base;
    var s = 0;
    try {
      var st = JSON.parse(localStorage.getItem('tzmref-' + CH) || '{}');
      if (st.last && st.last.t === v && st.last.s > 0) s = st.last.s;
    } catch (e) {}
    return base + '#t' + v + (s ? 's' + s : '');
  }
  function updateSwap() {
    var a = document.getElementById('swRef');
    a.href = refHref(state.t);
  }

  // ── 表示設定（文字サイズ・配色・ルビ）＝参考書ページと共通の localStorage['tzm-view'] ──
  var VIEWCFG = window.__tzmView || {};
  function saveViewCfg() {
    try { localStorage.setItem('tzm-view', JSON.stringify(VIEWCFG)); } catch (e) {}
  }
  function applyViewCfg() {
    var root = document.documentElement;
    var th = VIEWCFG.theme || 'auto';
    var dark = th === 'dark' || (th === 'auto' && window.matchMedia
               && window.matchMedia('(prefers-color-scheme: dark)').matches);
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    root.style.setProperty('--fs', VIEWCFG.fs || 1);
    root.classList.toggle('noruby', VIEWCFG.ruby === 0);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', dark ? '#17140f' : '#fffdf8');
    [].forEach.call(document.querySelectorAll('#cfgList .cfg-chip'), function (b) {
      if (b.dataset.fs) b.classList.toggle('on', String(VIEWCFG.fs || 1) === b.dataset.fs);
      if (b.dataset.theme) b.classList.toggle('on', th === b.dataset.theme);
      if (b.dataset.ruby) b.classList.toggle('on', String(VIEWCFG.ruby == null ? 1 : VIEWCFG.ruby) === b.dataset.ruby);
    });
  }
  applyViewCfg();
  if (window.matchMedia) {
    try {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
        if ((VIEWCFG.theme || 'auto') === 'auto') applyViewCfg();
      });
    } catch (e) {}
  }

  // ── 単元ドロワー（一覧シート）＋表示設定シート ──
  var drawerEl = document.getElementById('drawer');
  var dwListEl = document.getElementById('dwList');
  var cfgListEl = document.getElementById('cfgList');
  var lastFocus = null;
  function setInert(on) {
    [].forEach.call(document.querySelectorAll('body > *:not(#drawer):not(#expSheet)'), function (el) {
      try { el.inert = on; } catch (e) {}
    });
  }
  function openDrawer(mode) {
    lastFocus = document.activeElement;
    var cfg = mode === 'cfg';
    dwListEl.hidden = cfg;
    cfgListEl.hidden = !cfg;
    document.getElementById('dwTitle').textContent = cfg ? '表示の設定' : '単元をえらぶ';
    drawerEl.hidden = false;
    document.body.style.overflow = 'hidden';
    setInert(true);
    var cur = drawerEl.querySelector('.dw-item.on');
    if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: 'center' });
    var f = drawerEl.querySelector('.dw-close');
    if (f) f.focus();
  }
  function closeDrawer() {
    if (drawerEl.hidden) return;
    drawerEl.hidden = true;
    document.body.style.overflow = '';
    setInert(false);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  document.getElementById('unitBtn').addEventListener('click', function () { openDrawer('units'); });
  document.getElementById('cfgBtn').addEventListener('click', function () { openDrawer('cfg'); });
  document.getElementById('dwClose').addEventListener('click', closeDrawer);
  document.getElementById('dwBack').addEventListener('click', closeDrawer);
  cfgListEl.addEventListener('click', function (e) {
    var b = e.target.closest('.cfg-chip');
    if (!b) return;
    if (b.dataset.fs) VIEWCFG.fs = parseFloat(b.dataset.fs);
    if (b.dataset.theme) VIEWCFG.theme = b.dataset.theme;
    if (b.dataset.ruby) VIEWCFG.ruby = +b.dataset.ruby;
    saveViewCfg();
    applyViewCfg();
  });

  // ── 解説シート（参考書へ飛ばずに、根拠の節をその場で読む）──
  var SECTIONS = __SECTIONS__;
  var sheetEl = document.getElementById('expSheet');
  function openSheet(key, href) {
    var d = SECTIONS[key];
    if (!d) { location.href = href; return; }          // 節が特定できないときは従来どおり参考書へ
    document.getElementById('shTitle').textContent = d.h || '解説';
    document.getElementById('shBody').innerHTML =
      '<div class="sh-h">' + escHtml(d.h || '') + '</div>'
      + '<div>' + escHtml(d.b || '') + '</div>'
      + (d.p ? '<div class="sh-point"><b>ここだけ覚える</b><br>' + escHtml(d.p) + '</div>' : '');
    var more = document.getElementById('shMore');
    more.href = href;
    sheetEl.hidden = false;
    document.body.style.overflow = 'hidden';
    setInert(true);
    document.getElementById('shClose').focus();
  }
  function closeSheet() {
    if (sheetEl.hidden) return;
    sheetEl.hidden = true;
    document.body.style.overflow = '';
    setInert(false);
  }
  document.getElementById('shClose').addEventListener('click', closeSheet);
  document.getElementById('shBack').addEventListener('click', closeSheet);
  // シートの「参考書でくわしく読む」は、いまの問題位置を back= に付けて移動する
  document.getElementById('shMore').addEventListener('click', function (e) {
    e.preventDefault();
    var href = this.getAttribute('href') || '';
    var hi = href.indexOf('#');
    var base = hi >= 0 ? href.slice(0, hi) : href;
    var frag = hi >= 0 ? href.slice(hi) : '';
    var back = encodeURIComponent(location.pathname + location.hash);
    location.href = base + (base.indexOf('?') >= 0 ? '&' : '?') + 'back=' + back + frag;
  });

  // ── 操作ヒント（初回のみ）──
  (function () {
    var bar = document.getElementById('hintBar');
    if (!bar) return;
    // ヒントのキーは参考書／問題集で分ける（操作が違うのに片方で消費されていた）
    try { if (localStorage.getItem('tzmhint-wb') === '1') return; } catch (e) { return; }
    var canHover = window.matchMedia && window.matchMedia('(hover:hover)').matches;
    bar.textContent = canHover ? '⌨️ ← → キーでもページをめくれるよ'
                               : 'よこにスワイプでもページをめくれるよ';
    var shown = false;
    window.showHint = function () {
      if (shown || state.t === 0) return;
      shown = true; bar.hidden = false;
      try { localStorage.setItem('tzmhint-wb', '1'); } catch (e) {}
      setTimeout(function () { bar.hidden = true; }, 5000);
    };
    bar.addEventListener('click', function () { bar.hidden = true; });
  })();

  // ───── 記述問題のAIその場採点 ─────
  function escHtml(s) {
    return String(s || '').replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function setAiResult(step, cls, html) {
    var box = step.querySelector('.ai-result');
    if (!box) return;
    box.className = 'ai-result ' + cls;
    box.innerHTML = html;
    box.hidden = false;
  }
  function aiFallback(step, msg) {
    setAiResult(step, 'v-info', '<div class="air-line">' + escHtml(msg) + '</div>');
    step.classList.add('show');   // 模範解答＋自己採点(○△)を出してフォロー
  }
  function renderGradeCard(step, r) {
    var v = r.verdict;
    var mark = v === 'correct' ? '○' : v === 'partial' ? '△' : '×';
    var head = v === 'correct' ? 'よくできました！'
             : v === 'partial' ? 'おしい！あと少し' : 'もう一度チャレンジ';
    var h = '<div class="air-head"><span class="air-badge">' + mark + '</span>' + head + '</div>';
    if (r.good) h += '<div class="air-line"><b>よかった点</b>：' + escHtml(r.good) + '</div>';
    if (r.missing) h += '<div class="air-line"><b>足りない点</b>：' + escHtml(r.missing) + '</div>';
    if (r.hint) h += '<div class="air-line"><b>つぎのヒント</b>：' + escHtml(r.hint) + '</div>';
    setAiResult(step, 'v-' + v, h);
  }
  function loginPrompt(step) {
    setAiResult(step, 'v-info',
      '<div class="air-line">AI採点は、購入者ログインで使えます。</div>'
      + '<span class="air-login" data-ai-login>ログインする</span>');
  }
  function gradeWritten(step, btn) {
    if (!step || !btn) return;
    var ta = step.querySelector('.w-input');
    var answer = ta ? ta.value.trim() : '';
    if (answer.length < 2) {
      setAiResult(step, 'v-info', '<div class="air-line">まず自分の言葉で書いてみよう。書けたら採点するよ。</div>');
      return;
    }
    var auth = window.__tzmAuth;
    if (!auth) { aiFallback(step, 'いまAI採点を準備中です。模範解答を見て自己採点もできます。'); return; }
    if (!auth.ready) {
      setAiResult(step, 'v-info', '<span class="air-spin"></span>ログイン状態を確認中…');
      document.addEventListener('tzm-auth', function once() {
        document.removeEventListener('tzm-auth', once);
        gradeWritten(step, btn);
      });
      return;
    }
    if (!auth.user) { loginPrompt(step); return; }
    var bankid = btn.dataset.bankid;
    btn.disabled = true;
    setAiResult(step, 'v-info', '<span class="air-spin"></span>AIが採点しています…');
    auth.idToken().then(function (token) {
      if (!token) throw new Error('no token');
      return fetch(GRADE_API, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: token, id: bankid, answer: answer.slice(0, 500) }),
      });
    }).then(function (res) {
      return res.json().catch(function () { return {}; })
        .then(function (data) { return { status: res.status, data: data }; });
    }).then(function (r) {
      btn.disabled = false;
      if (r.status === 200 && r.data && r.data.result) {
        var result = r.data.result;
        renderGradeCard(step, result);
        // 進捗保存: correct のみ 1（＝全問正解=perfect の対象）。
        //          partial/incorrect は 0（解答済みだが正解ではない＝some/all には数える）。
        var st = store(); st.r = st.r || {}; st.g = st.g || {};
        st.r[step.dataset.qid] = result.verdict === 'correct' ? 1 : 0;
        st.g[step.dataset.qid] = result;
        save(st);
        refreshNextLock();
        return;
      }
      if (r.status === 402) {
        setAiResult(step, 'v-info', '<div class="air-line">'
          + escHtml((r.data && r.data.message) || 'この単元は購入者向けです。') + '</div>');
        return;
      }
      if (r.status === 401 || r.status === 403) { loginPrompt(step); return; }
      if (r.status === 429) {
        setAiResult(step, 'v-info', '<div class="air-line">'
          + escHtml((r.data && r.data.message) || 'きょうのAI利用が上限に達しました。また明日どうぞ。') + '</div>');
        return;
      }
      aiFallback(step, 'いまAI採点に失敗しました。模範解答を見て自己採点してね。');
    }).catch(function () {
      btn.disabled = false;
      aiFallback(step, '通信に失敗しました。模範解答を見て自己採点してね。');
    });
  }
  // 再訪時に、保存済みの採点結果カードを復元する
  function restoreGradeCards() {
    var g = (store() || {}).g || {};
    [].forEach.call(document.querySelectorAll('.wr-step'), function (step) {
      var r = g[step.dataset.qid];
      if (r) renderGradeCard(step, r);
    });
  }

  // 記述: 空欄のあいだは「AI採点」を押せないようにする（入力があれば有効化）
  function syncAiBtn(step) {
    if (!step) return;
    var ta = step.querySelector('.w-input'), b = step.querySelector('.ai-grade');
    if (ta && b) b.disabled = !ta.value.trim();
  }
  [].forEach.call(document.querySelectorAll('.wr-step'), function (s) { syncAiBtn(s); syncCount(s); });
  document.addEventListener('input', function (e) {
    if (e.target.classList && e.target.classList.contains('w-input')) {
      var st = e.target.closest('.wr-step');
      syncAiBtn(st);
      syncCount(st);
      // 書いた内容は保存する（再訪時に「採点結果はあるのに自分の答案が消えている」を防ぐ）
      if (st && st.dataset.qid) {
        var s2 = store(); s2.wtxt = s2.wtxt || {};
        s2.wtxt[st.dataset.qid] = e.target.value.slice(0, 600);
        save(s2);
      }
    }
  });
  // 保存してある答案を書き戻す
  (function () {
    var w = (store() || {}).wtxt || {};
    [].forEach.call(document.querySelectorAll('.wr-step'), function (step) {
      var ta = step.querySelector('.w-input');
      if (ta && w[step.dataset.qid]) { ta.value = w[step.dataset.qid]; syncAiBtn(step); syncCount(step); }
    });
  })();

  // 記述: 字数カウンタ（入試の記述は字数が要件そのもの。目安に対する今の字数を出す）
  function syncCount(step) {
    if (!step) return;
    var ta = step.querySelector('.w-input'), c = step.querySelector('.w-count');
    if (!ta || !c) return;
    var n = ta.value.trim().length;
    var target = +c.dataset.target || 0;
    c.textContent = n + '字（目安 ' + target + '字）';
    c.classList.toggle('over', target > 0 && n > target * 1.6);
  }

  function store() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
  }
  function save(obj) { try { localStorage.setItem(KEY, JSON.stringify(obj)); } catch (e) {} }
  function domSteps(t) { return [].slice.call(views[t].querySelectorAll('.step')); }
  function modeCfg(t) { return store()['m' + t] || null; }

  // ── プレイリスト（選んだ「やり方」に応じたステップ列）──
  // mode: 'all'=おすすめ順（従来の全ステップ）/ 'A'=穴埋め / 'B'=一問一答 /
  //       'C'=4択 / 'D'=記述。B は batch（まとめて採点）と shuf、C は shuf を持つ。
  // シャッフル順（order）は保存するので、つづきから再開しても順番は変わらない。
  var plCache = {};
  function orderBy(arr, order) {
    if (!order || order.length !== arr.length) return arr;
    return order.map(function (i) { return arr[i]; });
  }
  function shuffledOrder(n) {
    var a = []; for (var i = 0; i < n; i++) a.push(i);
    for (var j = n - 1; j > 0; j--) {
      var k = Math.floor(Math.random() * (j + 1));
      var tmp = a[j]; a[j] = a[k]; a[k] = tmp;
    }
    return a;
  }

  // ── 一問一答の入力採点（LINE 側 workbookTopic.judgeTermAnswer と同じ規則）──
  // 表記（漢字）でも読み（ひらがな/カタカナ）でも正解。かっこ書き「絹（シルク）」は
  // 全体・かっこ前・かっこ内のどれでも正解。NFKC・空白/記号除去で表記ゆれを吸収。
  function normTerm(s) {
    var t = (s || '').normalize('NFKC').trim().toLowerCase();
    t = t.replace(/[ァ-ヶ]/g, function (ch) {
      return String.fromCharCode(ch.charCodeAt(0) - 0x60);
    });
    return t.replace(/[\\s・･「」『』()（）。、.,ー?？!！]/g, '');
  }
  function stripParen(s) { return (s || '').replace(/[（(][^（）()]*[）)]/g, ''); }
  function parenIn(s) {
    var out = [], re = /[（(]([^（）()]*)[）)]/g, m;
    while ((m = re.exec(s || '')) !== null) { if (m[1]) out.push(m[1]); }
    return out;
  }
  function judgeTerm(input, a, r) {
    var targets = {};
    [a, r].forEach(function (raw) {
      if (!raw) return;
      [raw, stripParen(raw)].concat(parenIn(raw)).forEach(function (v) {
        var n = normTerm(v); if (n) targets[n] = 1;
      });
    });
    return [input, stripParen(input)].map(normTerm).some(function (x) {
      return x && targets[x];
    });
  }
  // 1文字だけ違う（＝惜しい）かどうか。編集距離1までを「惜しい」とみなす。
  function editDist1(a, b) {
    if (a === b) return false;
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > 1) return false;
    var i = 0, j = 0, diff = 0;
    while (i < la && j < lb) {
      if (a[i] === b[j]) { i++; j++; continue; }
      if (++diff > 1) return false;
      if (la > lb) i++; else if (lb > la) j++; else { i++; j++; }
    }
    return true;
  }
  function nearMiss(input, a, r) {
    var x = normTerm(input);
    if (!x) return false;
    return [a, r].some(function (raw) {
      if (!raw) return false;
      return [raw, stripParen(raw)].concat(parenIn(raw)).some(function (v) {
        var n = normTerm(v);
        return n && editDist1(x, n);
      });
    });
  }
  function showJudged(scopeEl, ok) {
    var banner = scopeEl.querySelector('.b-result');
    if (banner) {
      banner.textContent = ok ? 'せいかい！' : 'おしい！';
      banner.className = 'b-result ' + (ok ? 'ok' : 'ng');
    }
    scopeEl.classList.add('show');
  }
  function playlist(t) {
    if (plCache[t]) return plCache[t];
    var all = domSteps(t);
    var modeStep = all.filter(function (s) { return s.dataset.sec === 'M'; })[0];
    if (!modeStep) { plCache[t] = all; return all; } // 年表・まちがい直し（モード無し）
    function sec(k) { return all.filter(function (s) { return s.dataset.sec === k; }); }
    var cfg = modeCfg(t);
    var list = [modeStep];
    if (cfg) {
      var body = [];
      var tail = sec('Z');
      if (cfg.mode === 'all') {
        body = all.filter(function (s) {
          return s.dataset.sec !== 'M';
        });
        tail = [];
        // 以前のシャッフルで振り直した番号を元に戻す
        ['B', 'C'].forEach(function (k) {
          var arr = sec(k);
          arr.forEach(function (el, i) {
            var q = el.querySelector('.qnum');
            if (q) q.textContent = (i + 1) + ' / ' + arr.length;
          });
        });
      } else if (cfg.mode === 'A') { body = sec('A'); }
      else if (cfg.mode === 'B') {
        body = orderBy(sec('B'), cfg.order);
      } else if (cfg.mode === 'C') { body = orderBy(sec('C'), cfg.order); }
      else if (cfg.mode === 'D') { body = sec('D'); }
      else if (cfg.mode === 'wrong') {
        // まちがえた問題だけ（B/C/D/E/F で r===0 のもの）を集めて出し直す
        var rw = store().r || {};
        body = all.filter(function (s) {
          return ['B', 'C', 'D', 'E', 'F'].indexOf(s.dataset.sec) >= 0
            && s.dataset.qid && rw[s.dataset.qid] === 0;
        });
      }
      // 単独/やり直しモードは表示順に合わせて「n / 全」を振り直す
      if (cfg.mode === 'B' || cfg.mode === 'C' || cfg.mode === 'wrong') {
        body.forEach(function (el, i) {
          var q = el.querySelector('.qnum');
          if (q) q.textContent = (i + 1) + ' / ' + body.length;
        });
      }
      list = [modeStep].concat(body, tail);
    }
    plCache[t] = list;
    return list;
  }
  function stepsOf(t) { return playlist(t); }
  function applyMode(t, cfg) {
    var st = store(); st['m' + t] = cfg; save(st);
    delete plCache[t];
    go(t, 1, 1);
  }

  // 指定形式(secs)の該当ステップを再挑戦できる状態に戻す（見た目リセット、必要ならスコアも）
  function resetTypeSteps(view, secs, pred, clearR, st) {
    [].forEach.call(view.querySelectorAll('.step'), function (el) {
      if (secs.indexOf(el.dataset.sec) < 0 || !pred(el)) return;
      el.classList.remove('show', 'answered');
      [].forEach.call(el.querySelectorAll('.qopt'), function (b) { b.classList.remove('correct', 'wrong', 'dim'); });
      [].forEach.call(el.querySelectorAll('.b-in'), function (i) { i.value = ''; });
      [].forEach.call(el.querySelectorAll('.b-result'), function (b) { b.textContent = ''; b.className = 'b-result'; });
      [].forEach.call(el.querySelectorAll('.mk.sel'), function (b) { b.classList.remove('sel'); });
      [].forEach.call(el.querySelectorAll('.blank.open'), function (b) { b.classList.remove('open'); });
      if (clearR && el.dataset.qid) delete st.r[el.dataset.qid];
    });
  }

  // 4択の選択肢の表示順を毎回シャッフルする（ラベル1,2,3,4は位置固定・中身だけ入れ替え）。
  // data-i（元の選択肢番号）は各ボタンに保持したままなので、正誤判定はそのまま動く。
  function shuffleQopts(step) {
    if (!step || step.classList.contains('answered')) return;   // 回答済みは並びを保つ
    var box = step.querySelector('.qopts');
    if (!box) return;
    var opts = [].slice.call(box.querySelectorAll('.qopt'));
    if (opts.length < 2) return;
    for (var i = opts.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = opts[i]; opts[i] = opts[j]; opts[j] = tmp;
    }
    opts.forEach(function (el, i) {
      box.appendChild(el);                       // 新しい順で並べ直す
      var k = el.querySelector('.opt-k');
      if (k) k.textContent = (i + 1);            // ラベルは上から 1,2,3,4
    });
  }

  function renderScore(view) {
    var st = store(), r = st.r || {};
    var box = view.querySelector('[data-score]');
    if (!box) return;
    function count(sel) {
      var ids = [].map.call(view.querySelectorAll(sel), function (el) { return el.dataset.qid; });
      var done = ids.filter(function (id) { return r[id] === 1; }).length;
      var tried = ids.filter(function (id) { return id in r; }).length;
      return { total: ids.length, done: done, tried: tried };
    }
    var qa = count('.qa-step'), qz = count('.qz-step'), wr = count('.wr-step');
    var sh = count('.step[data-sec="E"][data-qid]'), mt = count('.step[data-sec="F"][data-qid]');
    var rows = [];
    if (qa.tried) rows.push('<div class="score-row"><span>B 一問一答</span><b>正解 ' + qa.done + ' / ' + qa.tried + '</b></div>');
    if (qz.tried) rows.push('<div class="score-row"><span>C 実戦4択</span><b>正解 ' + qz.done + ' / ' + qz.tried + '</b></div>');
    if (wr.tried) rows.push('<div class="score-row"><span>D 記述</span><b>正解 ' + wr.done + ' / ' + wr.tried + '</b></div>');
    if (sh.tried) rows.push('<div class="score-row"><span>E 資料問題</span><b>できた ' + sh.done + ' / ' + sh.tried + '</b></div>');
    if (mt.tried) rows.push('<div class="score-row"><span>F 資料の対応</span><b>全問正解 ' + mt.done + ' / ' + mt.tried + '</b></div>');
    // 穴埋め（A）だけを解いたときも「やった手ごたえ」を出す。
    // 以前はここが「このページの問題はタップ形式だよ。」だけで、達成感がゼロだった。
    var blanks = view.querySelectorAll('.step[data-sec="A"] .blank');
    var opened = view.querySelectorAll('.step[data-sec="A"] .blank.open');
    if (!rows.length && blanks.length) {
      rows.push('<div class="score-row"><span>A 要点まとめ</span><b>確かめた空欄 '
        + opened.length + ' / ' + blanks.length + '</b></div>');
    }
    box.innerHTML = rows.join('') || 'この単元はタップして確かめる形式だよ。おつかれさま！';
    // 「まちがえた問題だけやり直す」ボタン: B/C/D/E/F で r===0 の数だけ表示
    var wrongN = [].filter.call(
      view.querySelectorAll('[data-qid]'),
      function (el) { return r[el.dataset.qid] === 0; }
    ).length;
    var wrongBtn = view.querySelector('.wrong-btn');
    if (wrongBtn) {
      wrongBtn.hidden = wrongN === 0;
      var sub = wrongBtn.querySelector('[data-wrong-sub]');
      if (sub) sub.textContent = wrongN + '問';
    }
    // 「次にやること」を1つだけ大きく出す（ボタンが7つ並んで主導線が埋もれていた）。
    //   まちがいがある → まちがい直し／無ければ → 次の単元へ
    var pn = view.querySelector('[data-primary]');
    if (pn) {
      if (wrongN > 0) { pn.hidden = true; }        // まちがい直しボタンが主役になる
      else if (state.t > 0 && state.t < N) {
        pn.hidden = false;
        pn.textContent = '次の単元へすすむ →';
        pn.dataset.goNext = '1';
      } else { pn.hidden = true; }
    }
  }

  function render() {
    var t = state.t, s = state.s;
    views.forEach(function (v, i) {
      v.classList.toggle('on', i === t);
      // 表示していないビューは支援技術からも隠す
      if (i === t) v.removeAttribute('aria-hidden'); else v.setAttribute('aria-hidden', 'true');
    });
    var st0 = store();
    tabs.forEach(function (b) {
      var bt = +b.dataset.go;
      b.classList.toggle('on', bt === t);
      var stt = b.querySelector('.dw-state');
      if (stt) {
        var doing = st0.last && st0.last.t === bt && st0.last.s > 0;
        stt.className = 'dw-state' + (st0['d' + bt] === 1 ? '' : doing ? ' doing' : '');
        stt.textContent = st0['d' + bt] === 1 ? '✓ といた' : doing ? 'つづき' : '';
      }
    });
    var ubn = document.getElementById('unitBtnName');
    if (ubn) {
      var h2 = t > 0 && views[t] && views[t].querySelector('.tband h2');
      ubn.textContent = t === 0 ? '目次' : (h2 ? h2.textContent : '');
    }
    var navbar = document.getElementById('navbar');
    var barStep = document.getElementById('barStep');
    var pfill = document.getElementById('pfill');
    if (t === 0) {
      navbar.hidden = true; barStep.textContent = ''; pfill.style.width = '0';
      renderHome();
    } else {
      var steps = stepsOf(t);
      // 一問一答「入力して判定」モードのときだけ入力UIを出す（CSS は .ans-type 起点）
      // おすすめ順（all）は、短答手前の MB ステップで選んだ ansAll に従う。
      var cfgB = modeCfg(t);
      views[t].classList.toggle(
        'ans-type',
        t === REVIEW_T || !!(cfgB && (      // まちがい直しは常に「入力して判定」
          ((cfgB.mode === 'B' || cfgB.mode === 'wrong') && cfgB.ans !== 'check')
          || (cfgB.mode === 'all' && cfgB.ansAll === 'type')
        ))
      );
      // 問題の切り替えは即時（めくりアニメ無し）。リズムよく次々と解けるように。
      domSteps(t).forEach(function (el) {
        el.classList.remove('turn-out', 'turn-in', 'turn-under', 'on');
      });
      if (steps[s]) steps[s].classList.add('on');
      // 4択は表示のたびに選択肢の並びをシャッフル（未回答のときだけ）
      if (steps[s] && steps[s].classList.contains('qz-step')) shuffleQopts(steps[s]);
      navbar.hidden = false;
      var onModeStep = steps[s] && steps[s].dataset.sec === 'M';
      // 「やり方をえらぼう」は本文にも大きく出るのでヘッダーには出さない（単元タブの幅を優先）
      barStep.textContent = onModeStep ? '' : (s + 1) + ' / ' + steps.length;
      pfill.style.width = (((s + 1) / steps.length) * 100) + '%';
      document.getElementById('btnPrev').textContent = s === 0 ? '目次へ' : '← まえへ';
      var next = document.getElementById('btnNext');
      if (onModeStep && steps.length === 1) next.textContent = 'おすすめ順で始める →';
      else if (s < steps.length - 1) next.textContent = 'つぎへ →';
      else next.textContent = (t < N && t !== REVIEW_T) ? '次の単元へ →' : '目次にもどる';
      if (steps[s] && steps[s].classList.contains('done-step')) renderScore(views[t]);
      // 「前回のつづき」（やり方をえらぶ画面の先頭）。2回目以降は選び直さずに再開できる。
      if (onModeStep) {
        var again = steps[s].querySelector('[data-again]');
        var cfgPrev = modeCfg(t);
        if (again) {
          var LABEL = { all: 'おすすめ順', A: '穴埋め', B: '一問一答', C: '4択', D: '記述', wrong: 'まちがい直し' };
          // 「解き方が保存されているか」だけで出してはいけない（ユーザー指摘 2026-08-01）。
          // それだと次の2つで**押しても何も起きないボタン**が出る:
          //   ① 保存された解き方に該当する問題がこの単元に無い（例: 記述を選んだ
          //      あと、記述の無い単元を開く）→ playlist が「やり方をえらぶ」1枚だけ
          //      になり、飛び先の step が存在しない
          //   ② まだ1問も進んでいない（p{t} が無い）→ 「つづき」が実在しない
          // 反応しないボタンは、壊れているのか自分の操作が悪いのか判断できないので、
          // **出さない**のが正しい。押せるときだけ出す。
          var pAg = store()['p' + t] || 0;
          var canResume = !!cfgPrev && pAg >= 1 && stepsOf(t).length > 1;
          again.hidden = !canResume;
          var asub = again.querySelector('[data-again-sub]');
          if (canResume && asub) {
            // どこから始まるかを出す。「つづきから」だけだと、押した先が
            // 前回やめた場所なのか最初なのか分からない。
            asub.textContent = (LABEL[cfgPrev.mode] || '')
              + (pAg > 1 ? '・' + pAg + 'つめから' : 'を最初から');
          }
        }
      }
      var st = store();
      // まちがい直し（復習ビュー）は「つづきから」や✓の対象にしない
      if (t !== REVIEW_T) {
        st.last = { t: t, s: s };
        // 「前回のつづき」用に、単元ごとの**中身のステップ**を控える。
        // st.last は単元を開くたび s=0（やり方をえらぶ画面）で上書きされるので、
        // これだけを見ていると再開位置が毎回消えてしまう（実際そうなっていた）。
        if (s > 0) st['p' + t] = s;
        st['ts' + t] = Date.now();      // 復習おすすめ（最終学習日）に使う
        if (steps.length > 1 && s === steps.length - 1) st['d' + t] = 1;
        save(st);
      }
    }
    window.scrollTo(0, 0);
    // 短答の入力欄には自動でフォーカスしない。
    //   スマホでキーボードが立ち上がって問題文が隠れてしまうため（実機で確認）。
    //   入力したい人は入力欄をタップすればよい。
    var h = '#t' + t + (t > 0 && s > 0 ? 's' + s : '');
    // ページ送りを履歴に積む（replaceState だけだと戻る操作でサイトから出てしまう）
    if (location.hash !== h) {
      var url = location.pathname + location.search + (t === 0 ? '#' : h);
      if (navigating) history.replaceState({ t: t, s: s }, '', url);
      else history.pushState({ t: t, s: s }, '', url);
    }
    updateSwap();
    refreshNextLock();
    announce();
    rendered = { t: t, s: s };
  }

  // いま何問目かを読み上げソフトへ知らせる（画面には出さない）
  function announce() {
    var live = document.getElementById('liveMsg');
    if (!live) return;
    var steps = state.t > 0 ? stepsOf(state.t) : null;
    var lab = steps && steps[state.s] ? (steps[state.s].dataset.label || '') : '目次';
    live.textContent = lab + (steps ? '（' + (state.s + 1) + ' / ' + steps.length + '）' : '');
  }

  function renderHome() {
    var st = store();
    var doneN = 0, unitN = 0;
    [].forEach.call(document.querySelectorAll('.toc-state'), function (el) {
      var t = +el.dataset.stateT;
      unitN++;
      el.className = 'toc-state';
      if (st['d' + t] === 1) {
        doneN++;
        // 解いてから日が経った単元は「復習しよう」に変える（忘れたころに出す）
        var days = st['ts' + t] ? Math.floor((Date.now() - st['ts' + t]) / 86400000) : 0;
        if (days >= 7) { el.classList.add('again'); el.textContent = '復習しよう'; }
        else { el.classList.add('done'); el.textContent = '✓ といた'; }
      } else if (st.last && st.last.t === t && st.last.s > 0) {
        el.classList.add('doing'); el.textContent = 'つづき';
      } else { el.textContent = ''; }
    });
    var pw = document.getElementById('bookFill'), pt = document.getElementById('bookTxt');
    if (pw && pt) {
      pw.style.width = (unitN ? Math.round(doneN / unitN * 100) : 0) + '%';
      pt.textContent = '解き終えた単元 ' + doneN + ' / ' + unitN
        + (unitN && doneN >= unitN ? '　ぜんぶ解いた！ 🎉' : '');
    }
    var btn = document.getElementById('resumeBtn');
    if (st.last && st.last.t > 0 && views[st.last.t]) {
      btn.hidden = false;
      var name = views[st.last.t].querySelector('.tband h2').textContent;
      document.getElementById('resumeWhere').textContent =
        name + '（' + (st.last.s + 1) + '問目）';
      btn.onclick = function () { go(st.last.t, st.last.s, 1); };
    } else { btn.hidden = true; }
    // まちがい直し（章ぜんぶ）: 誤答が1問でもあれば目次に出す
    var rb = document.getElementById('reviewBtn');
    if (rb) {
      var n = wrongIds().length;
      rb.hidden = n === 0;
      var sub = document.getElementById('reviewSub');
      if (sub) sub.textContent = n + '問';
    }
  }

  // ── まちがい直し（この本の全単元をまたぐ復習）──
  //   誤答（r===0）の設問を複製して復習ビューに並べる。イベントは document 委譲＆
  //   保存キーは data-qid なので、複製でもそのまま採点・保存が動く。
  function wrongIds() {
    var r = (store() || {}).r || {};
    return [].filter.call(
      document.querySelectorAll('.view:not(.review-view) [data-qid]'),
      function (el) { return r[el.dataset.qid] === 0; }
    ).map(function (el) { return el.dataset.qid; });
  }
  function buildReview() {
    var slot = document.getElementById('revSlot');
    if (!slot) return 0;
    slot.innerHTML = '';
    var r = (store() || {}).r || {};
    var src = [].filter.call(
      document.querySelectorAll('.view:not(.review-view) .step[data-qid]'),
      function (el) { return r[el.dataset.qid] === 0; }
    );
    src.forEach(function (el, i) {
      var c = el.cloneNode(true);
      c.classList.remove('show', 'answered', 'on', 'can-retry');
      c.dataset.clone = '1';
      [].forEach.call(c.querySelectorAll('.qopt'), function (b) { b.classList.remove('correct', 'wrong', 'dim', 'gone'); });
      [].forEach.call(c.querySelectorAll('.b-in'), function (x) { x.value = ''; });
      [].forEach.call(c.querySelectorAll('.b-result'), function (x) { x.textContent = ''; x.className = 'b-result'; });
      [].forEach.call(c.querySelectorAll('.mk.sel'), function (x) { x.classList.remove('sel'); });
      [].forEach.call(c.querySelectorAll('.blank.open'), function (x) { x.classList.remove('open'); });
      [].forEach.call(c.querySelectorAll('.m-item'), function (x) {
        delete x.dataset.done;
        [].forEach.call(x.querySelectorAll('.mopt'), function (b) { b.classList.remove('correct', 'wrong'); });
      });
      var q = c.querySelector('.qnum');
      if (q) q.textContent = (i + 1) + ' / ' + src.length;
      c.dataset.label = 'まちがい直し (' + (i + 1) + '/' + src.length + ')';
      slot.appendChild(c);
    });
    var note = document.getElementById('revNote');
    if (note) note.textContent = src.length + '問';
    // 入力して判定するかどうかは、直近の解き方に合わせる
    var v = views[REVIEW_T];
    v.classList.toggle('ans-type', true);
    delete plCache[REVIEW_T];
    return src.length;
  }

  // ── 教材ゲート（中間案・ゆるめ「頭出しは見せる」）──
  //   有料単元はやり方えらぶ＋要点まとめまで誰でも試せる。その先は購入者（この学年）だけ。
  function isLicensed() {
    try {
      var raw = localStorage.getItem('tzm-lic');
      if (!raw) return false;
      var obj = JSON.parse(raw);
      if (Array.isArray(obj)) { localStorage.removeItem('tzm-lic'); return false; }
      if (!obj || !obj.exp || Date.now() >= obj.exp) { localStorage.removeItem('tzm-lic'); return false; }
      return (obj.g || []).indexOf(GRADE) >= 0;
    } catch (e) { return false; }
  }
  function lockFrom(t) { var v = views[t]; return v ? +(v.getAttribute('data-lock') || 0) : 0; }
  function gateBlocks(t, s) { var lk = lockFrom(t); return lk > 0 && !isLicensed() && s >= lk; }
  // ロックカードを出す前に、LINE内ブラウザで未ログインなら一度だけ無操作ログインを試みる。
  //   ログイン状態は module script が公開する window.tzmAuthUser で判定（module はスコープが別）。
  //   sessionStorage['tzm-auto-login'] で「タブ内1回だけ」に制限（失敗しても2度目は普通にロック表示）。
  function tzmMaybeAutoLogin() {
    if (window.tzmAuthUser) return false;
    if (!/ Line\\//.test(navigator.userAgent)) return false;
    try {
      if (sessionStorage.getItem('tzm-auto-login')) return false;
      sessionStorage.setItem('tzm-auto-login', '1');
    } catch (e) { return false; }
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    location.href = '../../login/?auto=1&next=' + encodeURIComponent(here);
    return true;
  }
  function showLock() { if (tzmMaybeAutoLogin()) return; var ov = document.getElementById('lockOv'); if (ov) ov.hidden = false; }
  function hideLock() { var ov = document.getElementById('lockOv'); if (ov) ov.hidden = true; }
  window.tzmRefreshGate = function () { if (isLicensed()) hideLock(); };
  // entitlement 反映後に呼ばれ、ロックカードの主ボタンを状況に合わせて入れ替える
  //   （体験ずみ／期限切れの人に、必ず失敗する体験ボタンを主役で見せない）。
  //   参考書ジェネレータ generate_reference_web.py と同じ仕様。
  window.tzmApplyLockState = function (st) {
    var used = !!(st && (st.trialUsed || st.result === 'expired'));
    var t = document.getElementById('lockT'), d = document.getElementById('lockD');
    var trial = document.getElementById('lockTrial'), subMain = document.getElementById('lockSubMain');
    var sub = document.getElementById('lockSub'), login = document.getElementById('lockLogin');
    if (!t || !d || !trial || !subMain || !sub) return;
    trial.hidden = used;
    subMain.hidden = !used;
    sub.hidden = used;
    if (login) login.hidden = true;   // ここに来る時点でログイン済み
    if (used) {
      t.textContent = 'つづきは、月額プランで';
      d.innerHTML = '無料体験は終了しました。<br>月額1,280円（税込）で、中学歴史ぜんぶ（全19単元）が使えます。いつでも解約できます。';
    }
  };

  function go(t, s, dir) {
    lastDir = dir || 1;
    // REVIEW_T（まちがい直し）は N の外側にあるので、上限は REVIEW_T まで許す
    state.t = Math.max(0, Math.min(REVIEW_T, t));
    state.s = Math.max(0, s || 0);
    if (state.t > 0) {
      state.s = Math.min(state.s, stepsOf(state.t).length - 1);
      if (gateBlocks(state.t, state.s)) {
        state.s = Math.max(0, lockFrom(state.t) - 1);
        render();
        showLock();
        return;
      }
    } else state.s = 0;
    hideLock();
    render();
  }
  // ── 未回答ガード: 問題(一問一答/4択/記述)に答えるまで「つぎへ」で先に進めない ──
  function isGatedStep(step) {
    return !!step && /(^| )(qa-step|qa-batch-step|qz-step|wr-step)( |$)/.test(step.className);
  }
  function stepAnswered(step) {
    if (!step) return true;
    if (step.classList.contains('show') || step.classList.contains('answered')) return true;
    var qid = step.dataset.qid;
    if (qid) { var r = (store() || {}).r || {}; if (r[qid] !== undefined) return true; }
    return false;
  }
  function refreshNextLock() {
    var b = document.getElementById('btnNext');
    if (!b) return;
    var steps = state.t > 0 ? stepsOf(state.t) : null;
    var stp = steps ? steps[state.s] : null;
    var locked = !!(stp && isGatedStep(stp) && !stepAnswered(stp));
    b.classList.toggle('locked', locked);
    b.disabled = locked;
    if (!locked) hideWhy();
  }
  // 押せない理由を伝える（グレーで止まるだけでは「壊れた」と思われる）
  var whyTimer = 0;
  function showWhy(step) {
    var el = document.getElementById('whyNext');
    if (!el) return;
    var kind = step && step.classList.contains('qz-step') ? '選択肢をえらぶと進めるよ'
             : step && step.classList.contains('wr-step') ? '書けたら「AI採点」、むずかしければ「わからない」で進めるよ'
             : 'こたえを入力するか「こたえを見る」を押すと進めるよ';
    el.textContent = kind;
    el.hidden = false;
    clearTimeout(whyTimer);
    whyTimer = setTimeout(function () { el.hidden = true; }, 3200);
  }
  function hideWhy() {
    var el = document.getElementById('whyNext');
    if (el) el.hidden = true;
  }
  function next() {
    var t = state.t, s = state.s;
    if (t === 0) return;
    var pl = stepsOf(t);
    // モード未選択のまま「つぎへ」= おすすめ順で開始
    if (s === 0 && pl.length === 1 && pl[0].dataset.sec === 'M') {
      applyMode(t, { mode: 'all' });
      return;
    }
    if (isGatedStep(pl[s]) && !stepAnswered(pl[s])) { showWhy(pl[s]); return; }  // 未回答は進めない
    if (s < pl.length - 1) go(t, s + 1, 1);
    else if (t === REVIEW_T) go(0, 0, 1);
    else if (t < N) go(t + 1, 0, 1);
    else go(0, 0, 1);
  }
  function prev() {
    var t = state.t, s = state.s;
    if (t === 0) return;
    if (s > 0) go(t, s - 1, -1);
    else go(0, 0, -1);
  }

  // 体験開始の実処理は module script の window.tzmStartTrial（Firebase Auth が要る）。
  document.getElementById('lockTrial').addEventListener('click', function () {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    if (window.tzmStartTrial) window.tzmStartTrial(here);
  });
  // 月額プラン登録: 体験ボタンと同型のログイン往復 → Stripe Checkout へ遷移
  function tzmGoCheckout() {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    if (window.tzmStartCheckout) window.tzmStartCheckout(here);
  }
  document.getElementById('lockSub').addEventListener('click', tzmGoCheckout);
  document.getElementById('lockSubMain').addEventListener('click', tzmGoCheckout);
  // おうちの人にお願いする: 中学生本人は決済できないので、ここが実際の出口になる。
  // カードを発行して「見せる画面」（QR＋台本）へ遷移する。
  document.getElementById('lockParent').addEventListener('click', function () {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    if (window.tzmStartParentCard) window.tzmStartParentCard(here);
  });
  document.getElementById('lockLogin').addEventListener('click', function () {
    var here = location.pathname + '#t' + state.t + (state.s > 0 ? 's' + state.s : '');
    location.href = '../../login/?next=' + encodeURIComponent(here);
  });
  document.getElementById('lockClose').addEventListener('click', hideLock);
  document.getElementById('btnNext').addEventListener('click', next);
  document.getElementById('btnPrev').addEventListener('click', prev);
  // disabled のボタンは click が出ないので、その周りのタップで理由を出す
  document.getElementById('navbar').addEventListener('click', function (e) {
    var b = document.getElementById('btnNext');
    if (b && b.disabled && !e.target.closest('#btnPrev')) {
      var pl = state.t > 0 ? stepsOf(state.t) : null;
      showWhy(pl ? pl[state.s] : null);
    }
  });
  // 目次の「まちがえた問題だけ解き直す」（この本の全単元をまたぐ）
  (function () {
    var rb = document.getElementById('reviewBtn');
    if (rb) rb.addEventListener('click', function () {
      if (buildReview() > 0) go(REVIEW_T, 0, 1);
    });
  })();
  // 回答するとロックを解除（回答処理の後に評価するため click は次tickで）
  document.addEventListener('click', function () { setTimeout(refreshNextLock, 0); });
  document.addEventListener('input', refreshNextLock);

  document.addEventListener('click', function (e) {
    // 「解説を読む」= その場でシートを開く（参考書ページへの往復をやめた）。
    // 節が特定できないときだけ、従来どおり参考書へ移動する。
    var sh = e.target.closest('.sec-help');
    if (sh) {
      e.preventDefault();
      openSheet(sh.dataset.secKey || '', sh.getAttribute('href'));
      return;
    }
    var go_ = e.target.closest('[data-go]');
    if (go_) { closeDrawer(); go(+go_.dataset.go, 0, 1); return; }
    // 結果画面の主導線（次の単元へ）
    var pnext = e.target.closest('[data-primary]');
    if (pnext) { if (state.t < N) go(state.t + 1, 0, 1); return; }
    // 「前回のつづき」= 保存済みの解き方で、**やめたところから**再開
    var again = e.target.closest('[data-again]');
    if (again) {
      var stAg = store();
      var plAg = stepsOf(state.t);
      // 保存された解き方に該当する問題がこの単元に無いと、飛び先の step が
      // 存在せず「押しても何も起きない」ボタンになる。表示側でも弾いているが、
      // ここでも塞ぐ（無反応は、壊れているのか操作ミスなのか本人に区別できない）。
      if (plAg.length <= 1) { again.hidden = true; return; }
      // 控えた位置に戻す。無ければ先頭（1）。playlist が短くなっていても外さない
      var sAg = stAg['p' + state.t] || 1;
      if (sAg > plAg.length - 1) sAg = plAg.length - 1;
      if (sAg < 1) sAg = 1;
      go(state.t, sAg, 1);
      return;
    }

    // 結果画面: 「ほかの解き方」チップ /「まちがえた問題だけやり直す」
    var rchip = e.target.closest('.chip-mode, .wrong-btn');
    if (rchip) {
      var rm = rchip.dataset.mode;
      var vw = views[state.t];
      var stR = store(); stR.r = stR.r || {};
      if (rm === 'wrong') {
        // まちがい(r===0)の問題を再挑戦できるよう見た目だけ戻す（rは維持＝集合を保つ）
        resetTypeSteps(vw, ['B', 'C', 'D'], function (el) {
          return el.dataset.qid && stR.r[el.dataset.qid] === 0;
        }, false, stR);
      } else {
        // その形式を最初からやり直せるよう見た目とスコアを戻す
        resetTypeSteps(vw, [rm], function () { return true; }, true, stR);
      }
      save(stR);
      var rcfg = { mode: rm };
      // まちがい直しは、直前の解き方（入力/確認）を引き継ぐ（既定は入力）
      if (rm === 'wrong') { rcfg.ans = (modeCfg(state.t) || {}).ans || 'type'; }
      if (rm === 'B') { rcfg.ans = 'type'; rcfg.shuf = false; rcfg.order = null; }
      if (rm === 'C') { rcfg.shuf = false; rcfg.order = null; }
      applyMode(state.t, rcfg);
      return;
    }

    // やり方（モード）選択
    var chipBtn = e.target.closest('.opt-chip');
    if (chipBtn) {
      [].forEach.call(chipBtn.parentElement.querySelectorAll('.opt-chip'), function (b) {
        b.classList.toggle('on', b === chipBtn);
      });
      return;
    }
    // おすすめ順の「短答のやり方」選択（.mb-pick は .mode-btn でもあるので先に処理）
    var pick = e.target.closest('.mb-pick');
    if (pick) {
      var pt = state.t;
      var pcfg = modeCfg(pt) || { mode: 'all' };
      pcfg.ansAll = pick.dataset.ansall;   // 'type'=入力して判定 / 'check'=見て自己採点
      var pst = store(); pst['m' + pt] = pcfg; save(pst);
      go(pt, state.s + 1, 1);              // 次（最初の一問一答）へ。render() で入力/確認が切り替わる
      return;
    }
    var mb = e.target.closest('.mode-btn');
    if (mb) {
      var mstep = mb.closest('.mode-step');
      var mt = state.t;
      function chip(name) {
        var c = mstep.querySelector('.opt-chip.on[data-opt="' + name + '"]');
        return c ? +c.dataset.val : 0;
      }
      var cfg = { mode: mb.dataset.mode };
      if (cfg.mode === 'B') {
        cfg.ans = chip('ansB') === 1 ? 'check' : 'type';
        cfg.shuf = chip('shufB') === 1;
      }
      if (cfg.mode === 'C') { cfg.shuf = chip('shufC') === 1; }
      if (cfg.mode === 'B' || cfg.mode === 'C') {
        var cnt = views[mt].querySelectorAll('.step[data-sec="' + cfg.mode + '"]').length;
        cfg.order = cfg.shuf ? shuffledOrder(cnt) : null;
      }
      applyMode(mt, cfg);
      return;
    }

    var blank = e.target.closest('.blank');
    if (blank) { blank.classList.toggle('open'); return; }

    var rall = e.target.closest('.reveal-all');
    if (rall) {
      var step = rall.closest('.step');
      var opened = step.querySelectorAll('.blank.open').length;
      var all = step.querySelectorAll('.blank');
      var open = opened < all.length;
      [].forEach.call(all, function (b) { b.classList.toggle('open', open); });
      rall.textContent = open ? 'すべての答えを隠す' : 'すべての答えを表示';
      return;
    }

    // 一問一答: 入力して判定（一問ずつ）
    var bj = e.target.closest('.b-judge');
    if (bj) {
      var jstep = bj.closest('.qa-step');
      if (jstep.classList.contains('show')) return;  // 判定済みは無視
      var jin = jstep.querySelector('.b-in');
      if (!jin.value.trim()) { jin.focus(); return; }  // 未入力なら何もしない
      var ok = judgeTerm(jin.value, jstep.dataset.a, jstep.dataset.r);
      // 「1文字ちがい」は即×にせず、もう一度だけ入力させる（送りがな・変換ミスの救済）。
      if (!ok && !jstep.dataset.near && nearMiss(jin.value, jstep.dataset.a, jstep.dataset.r)) {
        jstep.dataset.near = '1';
        var nb = jstep.querySelector('.b-result');
        if (nb) { nb.textContent = 'おしい！ 1文字ちがうかも。もう一度どうぞ'; nb.className = 'b-result near'; }
        jin.select();
        return;
      }
      // 判定したらキーボードを閉じる（開いたままだと、答えも解説もキーボードに隠れる）
      try { jin.blur(); } catch (err) {}
      showJudged(jstep, ok);
      var stJ = store(); stJ.r = stJ.r || {};
      stJ.r[jstep.dataset.qid] = ok ? 1 : 0;
      save(stJ);
      // 自動では進まない。「つぎへ」ボタンか Enter で次の問題へ。
      return;
    }
    var idk = e.target.closest('.b-idk');
    if (idk) {
      var istep = idk.closest('.qa-step');
      showJudged(istep, false);
      var bn = istep.querySelector('.b-result');
      if (bn) { bn.textContent = 'こたえはこちら。次はきっと書けるよ！'; bn.className = 'b-result ng'; }
      var stI = store(); stI.r = stI.r || {};
      stI.r[istep.dataset.qid] = 0;
      save(stI);
      return;
    }
    var rev = e.target.closest('.reveal');
    if (rev) { rev.closest('.step').classList.add('show'); return; }

    var ag = e.target.closest('.ai-grade');
    if (ag) { gradeWritten(ag.closest('.wr-step'), ag); return; }
    var aiLogin = e.target.closest('[data-ai-login]');
    if (aiLogin) { if (window.__tzmAuth) window.__tzmAuth.login(); return; }

    var mk = e.target.closest('.mk');
    if (mk) {
      var st = store(); st.r = st.r || {};
      var stp = mk.closest('.step');
      st.r[stp.dataset.qid] = +mk.dataset.v;
      save(st);
      // 自動では進まない。選んだ印を付けて「つぎへ」ボタンか Enter で次へ。
      [].forEach.call(stp.querySelectorAll('.marks .mk'), function (b) {
        b.classList.toggle('sel', b === mk);
      });
      return;
    }

    // 4択「もう一度考える」: 間違えた選択肢を1つ消して、選び直せるようにする
    var rq = e.target.closest('.retry-q');
    if (rq) {
      var rstep = rq.closest('.qz-step');
      rstep.classList.remove('answered', 'can-retry');
      [].forEach.call(rstep.querySelectorAll('.qopt'), function (b) {
        b.classList.remove('correct', 'dim');
        if (b.classList.contains('wrong')) { b.classList.remove('wrong'); b.classList.add('gone'); }
      });
      rstep.dataset.retried = '1';
      var st6 = store(); st6.r = st6.r || {};
      delete st6.r[rstep.dataset.qid];      // 選び直す間は未回答に戻す（結果は次の選択で決まる）
      save(st6);
      refreshNextLock();
      return;
    }
    var opt = e.target.closest('.qopt');
    if (opt) {
      var qstep = opt.closest('.qz-step');
      if (qstep.classList.contains('answered')) return;
      qstep.classList.add('answered');
      var c = +qstep.dataset.c, chosen = +opt.dataset.i;
      [].forEach.call(qstep.querySelectorAll('.qopt'), function (b) {
        var bi = +b.dataset.i;
        if (bi === c) b.classList.add('correct');
        else if (bi === chosen) b.classList.add('wrong');
        else b.classList.add('dim');
      });
      var ok4 = chosen === c;
      // 1回だけ「もう一度考える」を出す（一発勝負だと、考え直す機会を捨てていた）
      var canRetry = !ok4 && !qstep.dataset.retried
                     && qstep.querySelectorAll('.qopt:not(.gone)').length > 2;
      qstep.classList.toggle('can-retry', canRetry);
      var ex = qstep.querySelector('.expl');
      if (ex && !canRetry) ex.style.display = 'block';
      var st2 = store(); st2.r = st2.r || {};
      st2.r[qstep.dataset.qid] = ok4 ? 1 : 0;
      save(st2);
      return;
    }

    var mopt = e.target.closest('.mopt');
    if (mopt) {
      var item = mopt.closest('.m-item');
      if (item.dataset.done) return;
      var ok = mopt.dataset.l === item.dataset.a;
      mopt.classList.add(ok ? 'correct' : 'wrong');
      if (!ok) {
        [].forEach.call(item.querySelectorAll('.mopt'), function (b) {
          if (b.dataset.l === item.dataset.a) b.classList.add('correct');
        });
      }
      item.dataset.done = ok ? 'ok' : 'ng';
      // 資料の対応も採点対象（ぜんぶ答え終わったら、全問正解かどうかを記録する）
      var fstep = item.closest('.step[data-qid]');
      if (fstep) {
        var items = [].slice.call(fstep.querySelectorAll('.m-item'));
        var answered = items.filter(function (x) { return x.dataset.done; });
        if (answered.length === items.length) {
          var allOk = items.every(function (x) { return x.dataset.done === 'ok'; });
          var st7 = store(); st7.r = st7.r || {};
          st7.r[fstep.dataset.qid] = allOk ? 1 : 0;
          save(st7);
        }
      }
      return;
    }

    var retry = e.target.closest('[data-retry]');
    if (retry) {
      var view = retry.closest('.view');
      var st3 = store(); st3.r = st3.r || {};
      [].forEach.call(view.querySelectorAll('[data-qid]'), function (el) {
        delete st3.r[el.dataset.qid];
      });
      delete st3['d' + state.t];
      delete st3['m' + state.t];  // やり方選択からやり直す
      delete plCache[state.t];
      [].forEach.call(view.querySelectorAll('.mk.sel'), function (b) {
        b.classList.remove('sel');
      });
      [].forEach.call(view.querySelectorAll('.bq-item.show'), function (it) {
        it.classList.remove('show');
      });
      [].forEach.call(view.querySelectorAll('.b-in'), function (inp) { inp.value = ''; });
      [].forEach.call(view.querySelectorAll('.b-result'), function (b) {
        b.textContent = ''; b.className = 'b-result';
      });
      save(st3);
      [].forEach.call(view.querySelectorAll('.step'), function (el) {
        el.classList.remove('show', 'answered');
      });
      [].forEach.call(view.querySelectorAll('.qopt'), function (b) {
        b.classList.remove('correct', 'wrong', 'dim');
      });
      [].forEach.call(view.querySelectorAll('.m-item'), function (it) {
        delete it.dataset.done;
        [].forEach.call(it.querySelectorAll('.mopt'), function (b) {
          b.classList.remove('correct', 'wrong');
        });
      });
      [].forEach.call(view.querySelectorAll('.blank.open'), function (b) {
        b.classList.remove('open');
      });
      go(state.t, 0, -1);
      return;
    }
  });

  document.addEventListener('keydown', function (e) {
    var tag = e.target && e.target.tagName;
    var inField = tag === 'INPUT' || tag === 'TEXTAREA';
    // 日本語入力の変換確定 Enter を判定に使わない。
    //   「かまくらばくふ」→漢字に変換した瞬間の Enter で採点され、
    //   正しく書けているのに不正解になっていた（実機で確認）。
    if (e.isComposing || e.keyCode === 229) return;
    if (e.key === 'Escape') {
      if (!document.getElementById('expSheet').hidden) { closeSheet(); return; }
      if (!drawerEl.hidden) { closeDrawer(); return; }
      if (!document.getElementById('lightbox').hidden) { closeLb(); return; }
    }
    if (!drawerEl.hidden || !document.getElementById('expSheet').hidden) return;
    if (e.key === 'Enter') {
      // 一問一答の短答入力欄: 未判定＆入力あり=判定 / 判定済み=次へ / 未入力=何もしない
      if (inField && e.target.classList.contains('b-in')) {
        var stp = e.target.closest('.qa-step');
        if (stp && stp.classList.contains('show')) next();
        else if (e.target.value.trim() && stp) stp.querySelector('.b-judge').click();
        // 未入力のときは何もしない（誤操作で先に進めない）
        e.preventDefault();
        return;
      }
      // 記述の textarea 内 Enter は改行のまま（次へにしない）
      if (inField) return;
      // それ以外は Enter で次へ
      next();
      e.preventDefault();
      return;
    }
    if (inField) return;  // 入力中の矢印キーではページ送りしない
    if (e.key === 'ArrowRight' || e.key === 'PageDown') { next(); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { prev(); e.preventDefault(); }
    else if (e.key === 'Home') { go(0, 0, -1); e.preventDefault(); }
  });
  var tx = 0, ty = 0;
  document.addEventListener('touchstart', function (e) {
    tx = e.changedTouches[0].clientX; ty = e.changedTouches[0].clientY;
  }, { passive: true });
  document.addEventListener('touchend', function (e) {
    // 画像拡大中・シート表示中はページ送りしない
    if (!document.getElementById('lightbox').hidden || !drawerEl.hidden
        || !document.getElementById('expSheet').hidden) return;
    var dx = e.changedTouches[0].clientX - tx;
    var dy = e.changedTouches[0].clientY - ty;
    if (Math.abs(dx) > 64 && Math.abs(dy) < 48 && state.t > 0) {
      if (dx < 0) next(); else prev();
    }
  }, { passive: true });

  // 資料の画像はタップで拡大（参考書ページと同じ操作。細部が見えないと解けない）
  var lb = document.getElementById('lightbox');
  var lbImg = document.getElementById('lightboxImg');
  function openLb(src) { lbImg.src = src; lb.hidden = false; document.body.style.overflow = 'hidden'; }
  function closeLb() { lb.hidden = true; lbImg.removeAttribute('src'); document.body.style.overflow = ''; }
  document.addEventListener('click', function (e) {
    var z = e.target.closest('img.zoomable');
    if (z) { e.preventDefault(); e.stopPropagation(); openLb(z.currentSrc || z.src); }
  });
  lb.addEventListener('click', closeLb);
  document.getElementById('lbClose').addEventListener('click', function (e) { e.stopPropagation(); closeLb(); });

  // ── 上部バーの自動しまい込み（LINE内ブラウザで本文が狭いため）──
  (function () {
    var lastY = 0;
    window.addEventListener('scroll', function () {
      var y = Math.max(0, window.scrollY || 0);
      if (y > lastY + 6 && y > 80) document.body.classList.add('hidebar');
      else if (y < lastY - 6 || y < 40) document.body.classList.remove('hidebar');
      lastY = y;
    }, { passive: true });
  })();

  function fromHash() {
    var m = /#t(\\d+)(?:s(\\d+))?/.exec(location.hash);
    if (m) {
      var ht = +m[1];
      if (ht === REVIEW_T) buildReview();     // 復習ビューへの直リンクでも中身を作る
      go(ht, +(m[2] || 0), 1);
    } else go(0, 0, 1);
  }
  // 戻る／進む: 履歴に積んだページへ移動する（サイトから出てしまわないように）
  window.addEventListener('popstate', function () {
    navigating = true;
    fromHash();
    navigating = false;
  });
  fromHash();
  restoreGradeCards();   // 再訪時に保存済みのAI採点カードを復元

  // オフラインでも開けるように Service Worker を登録（通学中・電波の悪い所むけ）
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('../../sw.js', { scope: '../../' }).catch(function () {});
    });
  }
})();
</script>

<!-- ── 学習ログの同期（進み具合・時間・正誤をサーバへ）──
     つづもんの進捗はもともと端末の localStorage にしか無く、サーバ側に「どこまで
     進んだか」「何を間違えたか」が一切無かった。AIが個別に対応できるよう、ここで
     まとめてサーバへ送る。
       - 進捗は localStorage 全体（tzmwb-* / tzmref-*）から作る**フル・スナップショット**。
         初回の送信が、そのまま**これまでの学習の吸い上げ**になる。
       - 時間は「このページを見ていた時間」の増分だけを足して送る（送信後に0へ戻す）。
     ログインしていないと送れない（idToken が要る）ので、その間は貯めておく。 -->
<script>
(function () {
  var PROGRESS_API = 'https://asia-northeast1-chatstudy-63477.cloudfunctions.net/recordTsudumonProgress';
  var PART = 'wb';               // 'wb'（問題集）or 'ref'（参考書）
  var CH = '__CH_NO__';
  var SIG_KEY = 'tzm-sync-sig';            // 前回送った進捗の指紋（無駄な送信を避ける）
  var MS_KEY = 'tzm-sync-ms-' + PART + CH; // 未送信の滞在時間（タブを閉じても消えない）
  var TICK_MS = 15000;                     // 15秒ごとに可視時間を積む
  var SEND_MS = 60000;                     // 60秒ぶん貯まったら送る
  var IDLE_MAX = 5 * 60 * 1000;            // 5分以上の間隔は「放置」とみなし捨てる

  var pendingMs = 0;
  var lastTick = Date.now();
  var sending = false;
  try { pendingMs = parseInt(localStorage.getItem(MS_KEY) || '0', 10) || 0; } catch (e) {}

  function savePendingMs() { try { localStorage.setItem(MS_KEY, String(pendingMs)); } catch (e) {} }

  function tick() {
    var now = Date.now();
    var d = now - lastTick;
    lastTick = now;
    if (document.visibilityState !== 'visible') return;
    if (d <= 0 || d > IDLE_MAX) return;    // スリープ・放置は学習時間に数えない
    pendingMs += d;
    savePendingMs();
  }

  /** localStorage の生データ（tzm*）をそのまま集める。端末復元用の控え。 */
  function rawSnapshot() {
    var out = {};
    var n = 0;
    try { n = localStorage.length; } catch (e) { return out; }
    for (var i = 0; i < n; i++) {
      var k = null;
      try { k = localStorage.key(i); } catch (e) { continue; }
      if (!/^tzm(wb|ref)-\d{2}$/.test(k || '')) continue;
      try { out[k] = localStorage.getItem(k); } catch (e) {}
    }
    return out;
  }

  /**
   * 端末をまたいだ進捗の取り込み（マージ）。
   * 以前は「ローカルが空のときだけ」復元していたため、新しい端末で1問でも
   * 解くと、それ以降サーバの控えが二度と戻らなかった。
   * いまはサーバの控えを土台にして、ローカルの記録を上書きで重ねる。
   */
  function mergeUnit(remote, local) {
    var out = {};
    var k;
    for (k in remote) out[k] = remote[k];
    for (k in local) {
      var lv = local[k], rv = out[k];
      if (lv && rv && typeof lv === 'object' && typeof rv === 'object') {
        var m = {}, j;
        for (j in rv) m[j] = rv[j];
        for (j in lv) m[j] = lv[j];        // 同じ設問はローカル（新しい端末での結果）を優先
        out[k] = m;
      } else if (/^d\d+$/.test(k)) {
        out[k] = (lv === 1 || rv === 1) ? 1 : lv;   // 解いた✓は消さない
      } else {
        out[k] = lv;
      }
    }
    return out;
  }
  function restoreFromServer() {
    var u = window.tzmAuthUser;
    if (!u) return;
    try {
      if (sessionStorage.getItem('tzm-restored') === '1') return;
      sessionStorage.setItem('tzm-restored', '1');   // 何度も往復しない
    } catch (e) { return; }
    u.getIdToken().then(function (idToken) {
      return fetch(PROGRESS_API, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify({ idToken: idToken, restore: true }),
      });
    }).then(function (res) { return res && res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data || !data.ok || !data.raw) return;
        var changed = 0;
        for (var k in data.raw) {
          if (!/^tzm(wb|ref)-\d{2}$/.test(k)) continue;
          try {
            var remote = JSON.parse(data.raw[k] || '{}');
            var local = JSON.parse(localStorage.getItem(k) || '{}');
            if (!remote || typeof remote !== 'object') continue;
            var merged = mergeUnit(remote, local && typeof local === 'object' ? local : {});
            var next = JSON.stringify(merged);
            if (next !== JSON.stringify(local)) { localStorage.setItem(k, next); changed++; }
          } catch (e) {}
        }
        if (changed > 0) location.reload();   // 取り込んだ進捗で描き直す
      })
      .catch(function () {});
  }

  /** localStorage 全体から全章の進捗を作る（＝過去ぶんも含む）。 */
  function snapshot() {
    var units = {};
    var n = 0;
    try { n = localStorage.length; } catch (e) { return units; }
    for (var i = 0; i < n; i++) {
      var k = null;
      try { k = localStorage.key(i); } catch (e) { continue; }
      var m = /^tzm(wb|ref)-(\d{2})$/.exec(k || '');
      if (!m) continue;
      var st = null;
      try { st = JSON.parse(localStorage.getItem(k) || '{}'); } catch (e) { continue; }
      if (!st || typeof st !== 'object') continue;
      var u = units[m[2]] || (units[m[2]] = {});
      var steps = 0;
      for (var key in st) { if (/^d\d+$/.test(key) && st[key] === 1) steps++; }
      if (m[1] === 'ref') { u.refSteps = steps; }
      else { u.wbSteps = steps; if (st.r && typeof st.r === 'object') u.r = st.r; }
    }
    // このページの章については、総数（全節数・全設問数）も送る。
    // サーバは「読んだ節 ÷ 全節」「解いた問題 ÷ 全問」で “やり切ったか” を判定する
    // （総数は教材ページにしか無い情報。8割で「やり切った」とみなす）。
    try {
      var here = units[CH] || (units[CH] = {});
      var viewCount = document.querySelectorAll('.view').length - 1;  // 表紙を除く
      if (viewCount > 0) {
        if (PART === 'ref') here.refTotal = viewCount;
        else here.wbTotal = viewCount;
      }
      if (PART === 'wb') {
        here.qTotal = document.querySelectorAll('.view:not(.review-view) [data-qid]').length;
      }
    } catch (e) {}
    return units;
  }

  function signature(units) {
    try { return JSON.stringify(units); } catch (e) { return ''; }
  }

  /** @param useBeacon ページ離脱時は sendBeacon（非同期fetchは間に合わない） */
  function send(useBeacon) {
    var u = window.tzmAuthUser;
    if (!u || sending) return;
    tick();
    var units = snapshot();
    var sig = signature(units);
    var lastSig = '';
    try { lastSig = localStorage.getItem(SIG_KEY) || ''; } catch (e) {}
    // 進捗に変化が無く、時間も貯まっていなければ送らない（無駄な書き込みをしない）
    if (sig === lastSig && pendingMs < SEND_MS) return;
    if (pendingMs > 0) {
      units[CH] = units[CH] || {};
      units[CH][PART === 'ref' ? 'msRef' : 'msWb'] = pendingMs;
    }
    var sentMs = pendingMs;

    sending = true;
    u.getIdToken().then(function (idToken) {
      var body = JSON.stringify({
        idToken: idToken,
        units: units,
        raw: rawSnapshot(),   // 端末を変えたときの復元用（サーバに控える）
      });
      var done = function () {
        // 送れたぶんの時間は消す（次回に二重計上しない）
        pendingMs = Math.max(0, pendingMs - sentMs);
        savePendingMs();
        try { localStorage.setItem(SIG_KEY, sig); } catch (e) {}
        sending = false;
      };
      if (useBeacon && navigator.sendBeacon) {
        // Content-Type を application/json にすると preflight が必要になり
        // sendBeacon では送れない。text/plain で送り、サーバ側で JSON.parse する。
        var ok = navigator.sendBeacon(PROGRESS_API, new Blob([body], { type: 'text/plain' }));
        if (ok) done(); else sending = false;
        return;
      }
      fetch(PROGRESS_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body,
        keepalive: true,
      }).then(function (res) {
        if (res.ok) done(); else sending = false;
      }).catch(function () { sending = false; });
    }).catch(function () { sending = false; });
  }

  // ログインが確定してから復元を試す（未ログインでは何もしない）。
  restoreFromServer();
  setTimeout(restoreFromServer, 2500);   // 認証が遅れて確定する場合の保険

  setInterval(tick, TICK_MS);
  setInterval(function () { send(false); }, SEND_MS);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') send(true);
    else lastTick = Date.now();   // 戻ってきた時点から数え直す
  });
  window.addEventListener('pagehide', function () { send(true); });
  // ログイン直後（体験開始・購入の往復から戻ったとき等）に、過去ぶんをまとめて送る
  setTimeout(function () { send(false); }, 4000);
})();
</script>
</body></html>"""


def generate(folder: str, dest_root: Path) -> None:
    page, images = build(folder)
    ch_no = folder[:2]
    dest = dest_root / ch_no
    (dest / "img").mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(page, encoding="utf-8")
    for pair in sorted(set(images)):
        rel, flat = pair.split("|")
        shutil.copy2(ASSET_DIR / rel, dest / "img" / flat)
    print(f"generated: {dest / 'index.html'}（画像{len(set(images))}枚）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", metavar="NN",
                    help="指定の章番号（例 04）を dist-web/wb/ へ出力")
    args = ap.parse_args()

    if args.deploy:
        matches = [f for f in BOOKS if f.startswith(args.deploy) and not f.startswith("science")]
        if not matches:
            raise SystemExit(f"章 {args.deploy} が見つかりません")
        generate(matches[0], DEPLOY_DIR)
    else:
        for folder in BOOKS:
            if folder.startswith("science"):
                continue  # 現在の販売は歴史のみ
            generate(folder, OUT_DIR)
