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
- 「🖨 印刷」で紙のワークとして印刷できる（空欄・解答欄つき・巻末解答は最後にまとめて印字）
- 参考書 Web 版と相互リンク（../../ref/{NN}/#t{i} ⇄ ../../wb/{NN}/#t{i}）

使い方:
  python -X utf8 generate_workbook_web.py            # 歴史19冊 → output/web/wb/{NN}/index.html
  python -X utf8 generate_workbook_web.py --deploy 04  # 指定章を marutto-study の公開ディレクトリへ
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

BASE = Path(__file__).parent
OUT_DIR = BASE / "output" / "web" / "wb"
ASSET_DIR = BASE / "assets"
DEPLOY_DIR = BASE.parent / "marutto-study" / "public" / "tsudumon" / "wb"
REF_DIR = BASE / "reference"

LIFF_ID_UNITS = "2009587166-LjyCza2c"


def esc(s: str) -> str:
    return html.escape(s)


RUBY_INLINE = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")


def ruby_reading(s: str) -> str:
    """ルビ記法の読み側を連結（{徳川家康|とくがわいえやす} → とくがわいえやす）。
    入力判定で「読みでも正解」にするために使う（LINE側 judgeTermAnswer と同義）。"""
    return RUBY_INLINE.sub(lambda m: m.group(2), s)


def liff_wb(topic_name: str) -> str:
    return (f"https://liff.line.me/{LIFF_ID_UNITS}/wb"
            f"?t={urllib.parse.quote(topic_name)}")


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
        # 別タブで開く（問題タブが残るので解いている問題にすぐ戻れる）。
        # 万一ポップアップ制限で同タブ遷移しても、参考書側ヘッダーの「✏️問題」切替で
        # 解いていた位置に戻れる（相手側の last を読んで着地）。
        return (f'<a class="sec-help" href="../../ref/{ch_no}/index.html'
                f'#t{ref_index[tid]}{frag}" target="_blank" rel="noopener">'
                f'📖 解説を読む（ヒント）</a>')

    images: list[str] = []

    def use_img(rel: str):
        """assets/{rel} をパッケージ img/ 配下へ（サブフォルダ名は _ に潰す）"""
        p = ASSET_DIR / rel
        if not p.exists():
            return None
        flat = rel.replace("/", "_").replace("\\", "_")
        images.append(rel + "|" + flat)
        return f"img/{flat}"

    # 応援マスコット（透過PNG）。見出しは順番に回してにぎやかに。
    char_rotate = ["char_pencil_sm.png", "manabi_think_sm.png", "char_neko_sm.png",
                   "char_owl_sm.png", "manabi_ok_sm.png", "manabi_point_sm.png"]

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
                        f'#t{ref_index[tid]}">📖 先に参考書で理解する</a>')
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
          <button class="mk mk-ok" type="button" data-v="1">⭕ できた</button>
          <button class="mk mk-ng" type="button" data-v="0">🔺 もう一度</button>
        </div>
      </div>
    </div>""")
        answer_sections.append((f"{t_i}　{topic['name']}", []))  # placeholder → 下で埋める

        # B（まとめて採点用バッチステップ）: 全問を1画面に並べ、最後に一括で答えを開いて採点する。
        # 個別ステップと同じ qid を使うので成績（st.r）は共通。通常フロー・印刷では出さない。
        batch_items = []
        for i, card in enumerate(cards, 1):
            qid = f"qa-{tid}-{i}"
            expl = (f'<div class="qa-expl">{esc(card["explanation"])}</div>'
                    if card.get("explanation") else "")
            batch_items.append(f"""
      <div class="bq-item" data-qid="{qid}" data-a="{esc(ruby_base(card['front']))}" data-r="{esc(ruby_reading(card['front']))}">
        <div class="bq-q"><span class="qa-no">({i})</span>{esc(card['back'])}</div>
        <div class="b-inrow"><input class="b-in" type="text" placeholder="こたえを入力" autocomplete="off"></div>
        <div class="hidden-until">
          <div class="b-result" aria-live="polite"></div>
          <div class="qa-a">{to_ruby(card['front'])}</div>
          {expl}
          <div class="marks">
            <button class="mk mk-ok" type="button" data-v="1">⭕ できた</button>
            <button class="mk mk-ng" type="button" data-v="0">🔺 もう一度</button>
          </div>
        </div>
      </div>""")
        steps.append(f"""
    <div class="step qa-batch-step" data-label="B 一問一答（まとめて採点）" data-sec="BB">
      <div class="sec-h"><span class="sec-tag">B</span>一問一答<span class="sec-note">全{len(cards)}問・まとめて採点</span></div>
      <div class="howto">まず全部の問題にこたえてから、下のボタンでまとめて答え合わせしよう！</div>
      {''.join(batch_items)}
      <div class="reveal-all-row">
        <button class="reveal batch-grade" type="button">こたえをまとめて表示して採点する</button>
        <button class="b-batch-judge" type="button">入力したこたえをまとめて採点する</button>
      </div>
    </div>""")

        # C 実戦4択（タップで即判定）
        n_quiz = resolve_count(spec, "nQuiz", N_QUIZ, len(topic["quiz"]["questions"]))
        quiz = rebalance_quiz(pick_quiz(topic["quiz"]["questions"], n_quiz), tid)
        for i, q in enumerate(quiz, 1):
            qid = f"qz-{tid}-{i}"
            opts = "".join(
                f'<button class="qopt" type="button" data-i="{j}">'
                f'<span class="opt-k">{KATAKANA[j]}</span><span class="opt-t">{esc(o)}</span></button>'
                for j, o in enumerate(q["options"]))
            expl = (f'<div class="expl hidden-until">💡 {esc(q["explanation"])}</div>'
                    if q.get("explanation") else "")
            help_c = ref_help(tid, q["options"][q["correctIndex"]], q["question"])
            steps.append(f"""
    <div class="step qz-step" data-label="C 実戦問題 ({i}/{len(quiz)})" data-qid="{qid}" data-kind="qz" data-c="{q['correctIndex']}" data-sec="C">
      <div class="sec-h"><span class="sec-tag">C</span>実戦問題<span class="sec-note"><span class="qnum">{i} / {len(quiz)}</span>　正しいものを選ぼう</span></div>
      <div class="q-text">{esc(q['question'])}</div>
      <div class="qopts">{opts}</div>
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
      <div class="wline print-only"></div><div class="wline print-only"></div>
      <button class="reveal" type="button">模範解答を見る</button>
      <div class="hidden-until">
        <div class="qa-a">{esc(w['a'])}</div>
        <div class="marks">
          <button class="mk mk-ok" type="button" data-v="1">⭕ 書けた</button>
          <button class="mk mk-ng" type="button" data-v="0">🔺 もう一度</button>
        </div>
        <a class="line-mini" href="{liff_wb(topic['name'])}" target="_blank" rel="noopener">🤖 自分の答えをAIに採点してもらう（LINE）</a>
      </div>
    </div>""")

        # E 資料問題（タップで答え）
        shiryo = spec.get("shiryo", {}).get(tid, [])
        shiryo_answers = []
        s_no = 0
        for item in shiryo:
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
            img_html = f'<figure class="s-img"><img src="{img}" alt="" loading="lazy">{cap}</figure>' if img else ""
            verb = spec.get("shiryoVerb", "写真")
            steps.append(f"""
    <div class="step" data-label="E 資料問題" data-sec="E">
      <div class="sec-h"><span class="sec-tag">E</span>資料問題<span class="sec-note">{verb}を見て答えよう</span></div>
      {img_html}
      {''.join(qs)}
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
                        f'<img src="{img}" alt="" loading="lazy"></figure>')
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
            steps.append(f"""
    <div class="step" data-label="F 資料の対応" data-sec="F">
      <div class="sec-h"><span class="sec-tag">F</span>資料の対応<span class="sec-note">文にあてはまる資料を選ぼう</span></div>
      <div class="m-res-row">{''.join(res_cards)}</div>
      {''.join(item_rows)}
    </div>""")

        # 結果ステップ
        ref_btn = ""
        if tid in ref_index:
            ref_btn = (f'<a class="big-btn ref-btn" href="../../ref/{ch_no}/index.html#t{ref_index[tid]}">'
                       f'📖 参考書でおさらいする</a>')
        # 他の形式に進むチップ（この単元にある形式だけ）
        type_chips = ['<button class="chip-mode" type="button" data-mode="A">🕳 穴埋め</button>',
                      '<button class="chip-mode" type="button" data-mode="B">✍️ 短答</button>',
                      '<button class="chip-mode" type="button" data-mode="C">✅ 4択</button>']
        if written:
            type_chips.append('<button class="chip-mode" type="button" data-mode="D">📝 記述</button>')
        steps.append(f"""
    <div class="step done-step" data-label="結果" data-sec="Z">
      <div class="done">{char("manabi_banzai_sm.png", "wchar done-char")}<span>🎉 「{esc(topic['name'])}」おつかれさま！</span></div>
      <div class="score-box" data-score></div>
      <button class="big-btn wrong-btn" type="button" data-mode="wrong" hidden>🔴 まちがえた問題だけやり直す<span class="btn-sub" data-wrong-sub></span></button>
      <div class="next-modes">
        <div class="nm-h">ほかの解き方でもう一度</div>
        <div class="nm-chips">{''.join(type_chips)}</div>
      </div>
      {ref_btn}
      <a class="big-btn line-btn" href="{liff_wb(topic['name'])}" target="_blank" rel="noopener">🤖 LINEでこの単元を出題してもらう<span class="btn-sub">公式LINEに問題が届く→答えるとAIがすぐ丸つけ。すきま時間の復習に</span></a>
      <button class="big-btn retry-btn" type="button" data-retry>↻ この単元を最初から</button>
      <button class="big-btn home-btn" type="button" data-go="0">🏠 目次にもどる</button>
    </div>""")

        # やり方（モード）選択: 単元の最初に出す。推奨順=従来の全ステップ。
        # 短答は「一問ずつ/まとめて採点」、短答・4択は「シャッフル」を選べる。
        flow = ["要点まとめ", "一問一答", "4択", "記述"]
        if spec.get("shiryo", {}).get(tid):
            flow.append("資料")
        flow_html = '<span class="flow-arr">→</span>'.join(f'<span class="flow-chip">{f}</span>' for f in flow)
        mode_btn_d = ""
        if written:
            mode_btn_d = (
                '<div class="mode-card"><button class="mode-btn" type="button" data-mode="D">'
                '<span class="mode-ic ic-d">📝</span>'
                f'<span class="mode-main"><span class="mode-t">記述だけ</span>'
                f'<span class="mode-sub">{len(written)}問・模範解答つき</span></span>'
                '<span class="mode-arrow">›</span></button></div>')
        mode_step = f"""
    <div class="step mode-step" data-label="やり方をえらぶ" data-sec="M">
      <div class="sec-h"><span class="sec-tag">▶</span>やり方をえらぼう<span class="sec-note">目次にもどれば何度でも変えられるよ</span></div>
      <button class="mode-btn mode-reco" type="button" data-mode="all">
        <span class="mode-ic ic-star">⭐</span>
        <span class="mode-main"><span class="mode-t">おすすめ順でぜんぶ解く</span>
          <span class="mode-flow">{flow_html}</span></span>
        <span class="mode-arrow">›</span></button>
      <div class="mode-card"><button class="mode-btn" type="button" data-mode="A">
        <span class="mode-ic ic-a">✏️</span>
        <span class="mode-main"><span class="mode-t">穴埋め（要点まとめ）だけ</span>
          <span class="mode-sub">（　）をタップして確かめる</span></span>
        <span class="mode-arrow">›</span></button></div>
      <div class="mode-card"><button class="mode-btn" type="button" data-mode="B">
        <span class="mode-ic ic-b">🔥</span>
        <span class="mode-main"><span class="mode-t">一問一答（短答）だけ</span>
          <span class="mode-sub">{len(cards)}問・入力して自動で正誤判定</span></span>
        <span class="mode-arrow">›</span></button>
        <div class="mode-opts">
          <div class="opt-row"><span class="opt-lb">解答</span><button class="opt-chip on" type="button" data-opt="ansB" data-val="0">⌨️ 入力して判定</button><button class="opt-chip" type="button" data-opt="ansB" data-val="1">入力せず答えだけ確認</button></div>
          <div class="opt-row"><span class="opt-lb">採点</span><button class="opt-chip on" type="button" data-opt="batch" data-val="0">一問ずつ</button><button class="opt-chip" type="button" data-opt="batch" data-val="1">まとめて</button></div>
          <div class="opt-row"><span class="opt-lb">順番</span><button class="opt-chip on" type="button" data-opt="shufB" data-val="0">そのまま</button><button class="opt-chip" type="button" data-opt="shufB" data-val="1">シャッフル</button></div>
        </div>
      </div>
      <div class="mode-card"><button class="mode-btn" type="button" data-mode="C">
        <span class="mode-ic ic-c">✅</span>
        <span class="mode-main"><span class="mode-t">4択（選択）だけ</span>
          <span class="mode-sub">{len(quiz)}問・タップで即判定</span></span>
        <span class="mode-arrow">›</span></button>
        <div class="mode-opts">
          <div class="opt-row"><span class="opt-lb">順番</span><button class="opt-chip on" type="button" data-opt="shufC" data-val="0">そのまま</button><button class="opt-chip" type="button" data-opt="shufC" data-val="1">シャッフル</button></div>
        </div>
      </div>
      {mode_btn_d}
    </div>"""
        steps.insert(0, mode_step)

        views.append(f"""
<section class="view" data-t="{vt}">
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
        ref_home = f'<a class="big-btn ref-btn" href="../../ref/{ch_no}/index.html">📖 参考書を開く</a>'

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
    <a class="home-link" href="../../index.html">‹ 単元一覧にもどる</a>
    <div class="badge3"><span class="b-vol">{esc(spec['volume'])}</span><span class="b-kind">問題集</span></div>
  </div>
  <header class="top hometop">
    <div class="ht-main">
      <h1 class="ht-title">{esc(spec['title'])}</h1>
      <div class="sub">{esc(spec['subtitle'])}</div>
    </div>
    <div class="ht-mascot">{char("char_manabi_sm.png", "wchar")}<span class="ht-bubble">いっしょに<br>がんばろう！</span></div>
  </header>
  <div class="howto home-howto"><span class="hint-ic">💡</span><span>タブか下のリストから単元を選ぼう！<br>やり方（おすすめ順・穴埋め・一問一答・4択・記述）は単元を開いてから選べるよ。</span></div>
  <button class="resume" id="resumeBtn" hidden>▶ つづきから解く<span id="resumeWhere"></span></button>
  <nav class="toc">
    <div class="toc-head">
      <div class="toc-h">この単元</div>
      <button class="toc-cal" data-go="1">📅 {esc(check_title)}</button>
    </div>
    {''.join(toc_items)}
  </nav>
  {ref_home}
  <button class="big-btn print-btn" type="button" onclick="window.print()">🖨 紙に印刷して解く（解答つき）</button>
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

    # 問題集のビュー番号（t0=ホーム, t1=年表, t2〜=単元）→ 参考書の単元番号
    ref_views = [0, 0] + [ref_index.get(t["topicId"], 0) for t in topics]

    tabs = ('<button class="tab tab-home" data-go="0" aria-label="目次">🏠</button>'
            '<button class="tab" data-go="1" aria-label="年表">年</button>'
            + "".join(f'<button class="tab" data-go="{i + 1}" aria-label="{esc(t["name"])}">{i}</button>'
                      for i, t in enumerate(topics, 1)))

    page = (TEMPLATE
            .replace("__TITLE__", f"{spec['volume']} {spec['title']}｜つづもん問題集")
            .replace("__HEADBAR__", f"{esc(spec['volume'])} {esc(spec['title'])}（問題集）")
            .replace("__TABS__", tabs)
            .replace("__STORAGE_KEY__", f"tzmwb-{ch_no}")
            .replace("__CH_NO__", ch_no)
            .replace("__REF_VIEWS__", json.dumps(ref_views))
            .replace("__VIEWS__", home + "".join(views) + print_answers))
    return page, images


TEMPLATE = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>__TITLE__</title>
<style>
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --cream:#fffdf8; --line:#fde68a;
          --ok:#16a34a; --ng:#dc2626; }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         font-size:16px; line-height:1.95; color:#1c1917; background:var(--cream);
         padding-bottom:86px; }
  .wrap { max-width:640px; margin:0 auto; padding:0 16px 24px; }
  ruby rt { font-size:0.5em; }
  .print-only { display:none; }

  /* ── 上部バー ── */
  .bar { position:sticky; top:0; z-index:10; background:rgba(255,253,248,.96);
         backdrop-filter:blur(6px); border-bottom:1px solid #f0e6d2; }
  .bar-in { max-width:640px; margin:0 auto; padding:5px 12px 0; }
  .bar-row { display:flex; align-items:center; gap:8px; }
  /* 問題集⇄参考書の切替（どのページからでも1タップ・相手側は読みかけの位置に着地） */
  /* どのページからでも「本の一覧（すごろく）」へ戻れる常設ボタン。
     タブ列の 🏠 は「この本の目次」なので、こちらは 🗺＋文字でトップだと分かるようにする。 */
  .tophome { flex:none; height:30px; padding:0 12px; font-size:11.5px; font-weight:bold;
             color:#fff; background:var(--deep); border-radius:15px; text-decoration:none;
             display:inline-flex; align-items:center; white-space:nowrap;
             box-shadow:0 2px 0 #5b1e0b; }
  .swap { flex:none; display:inline-flex; border:1.5px solid var(--line); border-radius:20px;
          overflow:hidden; background:#fffbeb; }
  .sw { font-size:11px; font-weight:bold; color:var(--brand); padding:3px 7px; text-decoration:none;
        white-space:nowrap; cursor:pointer; }
  .sw.on { background:var(--brand); color:#fff; }
  .sw[hidden] { display:none; }
  /* 設問ごとの「解説を見る」（その問題の根拠になる節へ直行） */
  .sec-help { display:inline-flex; align-items:center; gap:4px; font-size:11.5px; font-weight:bold;
              color:var(--brand); background:#fffbeb; border:1.5px solid var(--line);
              border-radius:14px; padding:3px 10px; text-decoration:none; margin-top:8px; }
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
  .tabs-wrap { position:relative; flex:1; min-width:0; }
  /* 端のフェード＋矢印＝「まだ右に単元がある」と一目で分かるようにする */
  .tscroll { position:absolute; top:0; bottom:0; width:20px; border:none; cursor:pointer;
             font-size:17px; font-weight:bold; color:var(--brand); line-height:1; padding:0;
             display:flex; align-items:center; justify-content:center; font-family:inherit; }
  .tscroll[hidden] { display:none; }
  .tsl { left:0; background:linear-gradient(to right, #fffdf8 62%, rgba(255,253,248,0)); }
  .tsr { right:0; background:linear-gradient(to left, #fffdf8 62%, rgba(255,253,248,0)); }
  .tabs { display:flex; gap:5px; overflow-x:auto; padding:4px 0; width:100%; scrollbar-width:none; }
  .tabs::-webkit-scrollbar { display:none; }
  .tab { flex:none; width:30px; height:30px; border-radius:50%; border:1.5px solid var(--line);
         background:#fffbeb; color:var(--brand); font-size:14px; font-weight:bold;
         display:inline-flex; align-items:center; justify-content:center; cursor:pointer; }
  .tab.done { background:#fef3c7; }
  .tab.on { background:var(--brand); border-color:var(--brand); color:#fff;
            box-shadow:0 2px 6px rgba(180,83,9,.35); }
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
  .badge3 { display:inline-flex; border-radius:18px; overflow:hidden; font-size:12px; font-weight:bold;
            box-shadow:0 2px 4px rgba(120,80,20,.2); }
  .badge3 span { padding:4px 11px; display:inline-flex; align-items:center; white-space:nowrap; }
  .b-vol { background:var(--brand); color:#fff; }
  .b-kind { background:#fff; color:var(--deep); }
  .b-web { background:var(--amber); color:#fff; }
  .ht-title { font-size:41px; color:var(--deep); margin:12px 0 0; line-height:1.12; position:relative;
              display:inline-block; padding:0 6px; letter-spacing:.01em; }
  .ht-title::before { content:"✨"; position:absolute; left:-22px; top:2px; font-size:19px; }
  .ht-title::after { content:"✨"; position:absolute; right:-20px; bottom:4px; font-size:15px; }
  .ht-mascot { flex:none; position:relative; width:100px; padding-top:22px; text-align:center; }
  .ht-mascot .wchar { height:74px; }
  .ht-bubble { position:absolute; top:0; left:50%; transform:translateX(-50%); white-space:nowrap;
               background:#fffbeb; border:1.5px solid #f0b558; border-radius:12px; padding:4px 10px;
               font-size:11px; font-weight:bold; color:#92400e; line-height:1.25; text-align:center;
               box-shadow:0 2px 4px rgba(0,0,0,.1); }
  .ht-bubble::after { content:""; position:absolute; bottom:-7px; left:50%; transform:translateX(-50%);
                      border:5px solid transparent; border-top-color:#f0b558; }
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
  .toc-h::before { content:"📖"; display:inline-flex; align-items:center; justify-content:center;
                   width:30px; height:30px; border-radius:50%; background:var(--brand); font-size:15px; }
  .toc-cal { flex:none; border:1.5px solid var(--line); background:#fff; color:var(--brand);
             font-weight:bold; border-radius:20px; padding:6px 12px; font-size:12px; cursor:pointer;
             font-family:inherit; white-space:nowrap; box-shadow:0 2px 0 #f0e2c3; }
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
  .tchar { height:38px; margin-left:auto; }
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
  .sec-note { font-size:12px; font-weight:normal; color:#a8a29e; }
  .ref-link { display:inline-block; font-size:13px; font-weight:bold; color:var(--brand);
              text-decoration:none; border:1.5px solid var(--line); background:#fffbeb;
              border-radius:16px; padding:5px 14px; margin-bottom:10px; }

  /* ── やり方（モード）選択 ── */
  /* やり方をえらぶ: 各モードを丸アイコン＋本文＋右矢印のカードに（画像デザイン） */
  .mode-card { background:#fff; border:1.5px solid #f0e2c3; border-radius:16px; margin-top:12px;
               padding:6px 6px 10px; box-shadow:0 2px 0 #ecdcbb; }
  .mode-card .mode-btn { margin-top:0; border:none; box-shadow:none; background:none; padding:8px 6px; }
  .mode-btn { display:flex; align-items:center; gap:12px; width:100%; text-align:left; margin-top:12px;
              border:none; border-radius:16px; padding:12px 10px; font-size:16px; font-weight:bold;
              color:#44403c; background:#fff; cursor:pointer; font-family:inherit; line-height:1.35;
              box-shadow:0 2px 0 #ecdcbb; border:1.5px solid #f0e2c3; }
  .mode-ic { flex:none; width:52px; height:52px; border-radius:50%; display:inline-flex;
             align-items:center; justify-content:center; font-size:24px; background:#f1ece0; }
  .ic-star { background:#fff; }
  .ic-a { background:#e3edff; } .ic-b { background:#ffe6d6; }
  .ic-c { background:#dcfce7; } .ic-d { background:#ece9fb; }
  .mode-main { flex:1; min-width:0; }
  .mode-t { display:block; }
  .mode-btn .mode-sub { display:block; font-weight:normal; font-size:12.5px; color:#a8a29e; margin-top:3px; }
  .mode-arrow { flex:none; color:var(--brand); font-size:24px; font-weight:bold; padding-right:6px; }
  /* おすすめ順（オレンジの目立つカード） */
  .mode-reco { background:linear-gradient(#f59e0b,#ea7a09); border:none; color:#fff; margin-top:0;
               box-shadow:0 4px 0 #c2620a, 0 6px 12px rgba(180,83,9,.3); border-radius:18px; padding:14px 12px; }
  .mode-reco .mode-arrow { color:#fff; }
  .mode-flow { display:flex; flex-wrap:wrap; align-items:center; gap:5px; margin-top:6px; }
  .flow-chip { background:rgba(255,255,255,.95); color:var(--brand); font-size:11.5px; font-weight:bold;
               border-radius:12px; padding:2px 9px; }
  .flow-arr { color:#fff; font-weight:bold; font-size:12px; }
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
  .b-idk { display:none; margin-top:8px; background:none; border:none; color:#a8a29e;
           font-size:12.5px; text-decoration:underline; cursor:pointer; font-family:inherit; }
  .b-batch-judge { display:none; width:100%; margin-top:14px; border:none; border-radius:12px;
                   background:var(--brand); color:#fff; font-weight:bold; font-size:15px;
                   padding:12px; cursor:pointer; font-family:inherit;
                   box-shadow:0 2px 6px rgba(180,83,9,.3); }
  .ans-type .qa-step .b-inrow, .ans-type .qa-batch-step .b-inrow { display:flex; }
  .ans-type .qa-step .b-idk { display:inline-block; }
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
  .qopt { display:flex; align-items:center; gap:10px; text-align:left; background:#fff;
          border:1.5px solid #e2d5bd; border-radius:12px; padding:10px 12px; font-size:14.5px;
          cursor:pointer; font-family:inherit; line-height:1.7; }
  .opt-k { flex:none; width:26px; height:26px; border-radius:50%; border:1.5px solid #a8a29e;
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
  .s-img figcaption { font-size:12px; color:#a8a29e; text-align:center; margin-top:4px; }
  .s-q { margin-bottom:14px; font-size:15px; line-height:1.8; }
  .s-blank { display:block; margin:6px 0 0 26px; text-align:left; }
  .s-blank .tap-hint { display:inline; font-size:11px; color:#b8b0a6; margin-left:8px; }
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
  .line-btn { background:#06c755; color:#fff; box-shadow:0 3px 8px rgba(6,199,85,.3); }
  .btn-sub { display:block; font-weight:normal; font-size:12px; opacity:.9; }
  .ref-btn { background:#fffbeb; color:var(--brand); border:1.5px solid var(--line); }
  .retry-btn { background:#fff; color:#57534e; border:1.5px solid #e2d5bd; }
  .home-btn { background:#fff; color:#57534e; border:1.5px solid #e2d5bd; }
  .print-btn { background:#fff; color:#57534e; border:1.5px solid #e2d5bd; }
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

  .foot { text-align:center; margin-top:32px; color:#a8a29e; font-size:13px; }
  .foot-note { margin-top:4px; font-size:12px; }

  /* ── 下部ナビ ── */
  .navbar { position:fixed; left:0; right:0; bottom:0; z-index:10;
            background:rgba(255,253,248,.97); border-top:1px solid #f0e6d2;
            padding:10px 16px calc(10px + env(safe-area-inset-bottom)); }
  .navbar-in { max-width:640px; margin:0 auto; display:flex; align-items:center; gap:10px; }
  .nb { border:none; border-radius:14px; padding:12px 0; font-size:15px; font-weight:bold;
        cursor:pointer; font-family:inherit; }
  .nb-prev { flex:1; background:#fff; color:var(--brand); border:1.5px solid var(--line); }
  .nb-next { flex:2; background:var(--brand); color:#fff; box-shadow:0 3px 8px rgba(180,83,9,.3); }

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
    .mk:hover, .mopt:hover, .line-mini:hover { filter: brightness(0.94); }
    /* 白・枠線ボタン／リストは薄いアンバーで下地を変えて分かりやすく */
    .toc-item:hover, .mode-btn:hover, .opt-chip:hover, .reveal-all:hover,
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
    .print-only { display:block !important; }
    .view { display:block !important; }
    .step { display:block !important; margin-bottom:14px; break-inside:avoid; }
    .hidden-until { display:none !important; }
    .blank .ba { display:none !important; }
    .blank .bl { display:inline-block !important; background:none; }
    .qopt { border:none; padding:1px 0; background:none; }
    .qopt .opt-k { width:18px; height:18px; font-size:10px; }
    .qopt.correct, .qopt.wrong { background:none; border:none; }
    .qopt.correct .opt-k, .qopt.wrong .opt-k { background:none; color:#1c1917; border-color:#a8a29e; }
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
  .credits { font-size:11px; color:#a8a29e; margin-top:20px; }
</style></head><body>
<div class="bar"><div class="bar-in">
  <div class="bar-row">
    <a class="tophome" href="../../index.html" aria-label="単元一覧へもどる">単元一覧</a>
    <div class="swap"><a class="sw" id="swRef">📖 参考書</a><span class="sw on">✏️ 問題</span></div>
    <div class="tabs-wrap">
      <nav class="tabs" id="tabs">__TABS__</nav>
      <button class="tscroll tsl" id="tabsL" type="button" hidden aria-label="単元タブを左へ">‹</button>
      <button class="tscroll tsr" id="tabsR" type="button" hidden aria-label="単元タブを右へ">›</button>
    </div>
    <div class="bar-step" id="barStep"></div>
  </div>
  <div class="bar-title" hidden>__HEADBAR__</div>
  <div class="pbar"><div class="pfill" id="pfill"></div></div>
</div></div>
<main class="wrap" id="views">
__VIEWS__
</main>
<div class="hintbar" id="hintBar" hidden></div>
<div class="navbar" id="navbar" hidden><div class="navbar-in">
  <button class="nb nb-prev" id="btnPrev">← まえへ</button>
  <button class="nb nb-next" id="btnNext">つぎへ →</button>
</div></div>
<script>
(function () {
  var KEY = '__STORAGE_KEY__';
  var CH = '__CH_NO__';
  var REF_VIEWS = __REF_VIEWS__;        // 問題集のビューt → 参考書の単元番号（0＝対応なし）
  var views = [].slice.call(document.querySelectorAll('.view'));
  var tabs = [].slice.call(document.querySelectorAll('.tab'));
  var N = views.length - 1;
  var state = { t: 0, s: 0 };
  var lastDir = 1;
  var rendered = null; // 直前に表示していた {t, s}（ページめくり演出用）

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

  // ── 操作ヒント（初回のみ）＋タブ列のホイール操作 ──
  (function () {
    var el = document.getElementById('tabs');
    if (el) el.addEventListener('wheel', function (e) {
      // PC でも横スクロールできるよう、縦ホイールを横移動に変換する
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) { el.scrollLeft += e.deltaY; e.preventDefault(); }
    }, { passive: false });

    var bar = document.getElementById('hintBar');
    if (!bar) return;
    try { if (localStorage.getItem('tzmhint') === '1') return; } catch (e) { return; }
    var canHover = window.matchMedia && window.matchMedia('(hover:hover)').matches;
    bar.textContent = canHover ? '⌨️ ← → キーでもページをめくれるよ'
                               : '👆 よこにスワイプでもページをめくれるよ';
    var shown = false;
    window.showHint = function () {
      if (shown || state.t === 0) return;
      shown = true; bar.hidden = false;
      try { localStorage.setItem('tzmhint', '1'); } catch (e) {}
      setTimeout(function () { bar.hidden = true; }, 5000);
    };
    bar.addEventListener('click', function () { bar.hidden = true; });
  })();

  // 単元タブの左右矢印: まだ隠れているタブがある側だけ出す
  function updateTabArrows() {
    var el = document.getElementById('tabs');
    var L = document.getElementById('tabsL'), R = document.getElementById('tabsR');
    if (!el || !L || !R) return;
    var max = el.scrollWidth - el.clientWidth;
    L.hidden = el.scrollLeft <= 2;
    R.hidden = el.scrollLeft >= max - 2;
  }
  (function () {
    var el = document.getElementById('tabs');
    var L = document.getElementById('tabsL'), R = document.getElementById('tabsR');
    if (!el || !L || !R) return;
    function by(d) { el.scrollBy({ left: d * Math.max(80, el.clientWidth * 0.7), behavior: 'smooth' }); }
    L.addEventListener('click', function (e) { e.stopPropagation(); by(-1); });
    R.addEventListener('click', function (e) { e.stopPropagation(); by(1); });
    el.addEventListener('scroll', updateTabArrows, { passive: true });
    window.addEventListener('resize', updateTabArrows);
    setTimeout(updateTabArrows, 0);
  })();

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
  function showJudged(scopeEl, ok) {
    var banner = scopeEl.querySelector('.b-result');
    if (banner) {
      banner.textContent = ok ? '⭕ せいかい！' : '❌ おしい！';
      banner.className = 'b-result ' + (ok ? 'ok' : 'ng');
    }
    scopeEl.classList.add('show');
  }
  function playlist(t) {
    if (plCache[t]) return plCache[t];
    var all = domSteps(t);
    var modeStep = all.filter(function (s) { return s.dataset.sec === 'M'; })[0];
    if (!modeStep) { plCache[t] = all; return all; } // 年表など（モード無し）
    function sec(k) { return all.filter(function (s) { return s.dataset.sec === k; }); }
    var cfg = modeCfg(t);
    var list = [modeStep];
    if (cfg) {
      var body = [];
      var tail = sec('Z');
      if (cfg.mode === 'all') {
        body = all.filter(function (s) {
          return s.dataset.sec !== 'M' && s.dataset.sec !== 'BB';
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
        body = cfg.batch ? sec('BB') : orderBy(sec('B'), cfg.order);
      } else if (cfg.mode === 'C') { body = orderBy(sec('C'), cfg.order); }
      else if (cfg.mode === 'D') { body = sec('D'); }
      else if (cfg.mode === 'wrong') {
        // まちがえた問題だけ（B/C/D で r===0 のもの）を集めて出し直す
        var rw = store().r || {};
        body = all.filter(function (s) {
          return ['B', 'C', 'D'].indexOf(s.dataset.sec) >= 0
            && s.dataset.qid && rw[s.dataset.qid] === 0;
        });
      }
      // 単独/やり直しモードは表示順に合わせて「n / 全」を振り直す
      if ((cfg.mode === 'B' && !cfg.batch) || cfg.mode === 'C' || cfg.mode === 'wrong') {
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
    var rows = [];
    if (qa.tried) rows.push('<div class="score-row"><span>B 一問一答</span><b>⭕ ' + qa.done + ' / ' + qa.tried + '</b></div>');
    if (qz.tried) rows.push('<div class="score-row"><span>C 実戦4択</span><b>正解 ' + qz.done + ' / ' + qz.tried + '</b></div>');
    if (wr.tried) rows.push('<div class="score-row"><span>D 記述</span><b>⭕ ' + wr.done + ' / ' + wr.tried + '</b></div>');
    box.innerHTML = rows.join('') || 'このページの問題はタップ形式だよ。';
    // 「まちがえた問題だけやり直す」ボタン: B/C/D で r===0 の数だけ表示
    var wrongBtn = view.querySelector('.wrong-btn');
    if (wrongBtn) {
      var wrongN = [].filter.call(
        view.querySelectorAll('.qa-step[data-qid], .qz-step[data-qid], .wr-step[data-qid]'),
        function (el) { return r[el.dataset.qid] === 0; }
      ).length;
      wrongBtn.hidden = wrongN === 0;
      var sub = wrongBtn.querySelector('[data-wrong-sub]');
      if (sub) sub.textContent = wrongN + '問';
    }
  }

  function render() {
    var t = state.t, s = state.s;
    views.forEach(function (v, i) { v.classList.toggle('on', i === t); });
    tabs.forEach(function (b) {
      var bt = +b.dataset.go;
      b.classList.toggle('on', bt === t);
      b.classList.toggle('done', bt > 0 && store()['d' + bt] === 1);
    });
    var tabEl = tabs[t];
    if (tabEl && tabEl.scrollIntoView) tabEl.scrollIntoView({ block: 'nearest', inline: 'center' });
    var navbar = document.getElementById('navbar');
    var barStep = document.getElementById('barStep');
    var pfill = document.getElementById('pfill');
    if (t === 0) {
      navbar.hidden = true; barStep.textContent = ''; pfill.style.width = '0';
      renderHome();
    } else {
      var steps = stepsOf(t);
      // 一問一答「入力して判定」モードのときだけ入力UIを出す（CSS は .ans-type 起点）
      var cfgB = modeCfg(t);
      views[t].classList.toggle(
        'ans-type',
        !!(cfgB && (cfgB.mode === 'B' || cfgB.mode === 'wrong') && cfgB.ans !== 'check')
      );
      // 問題の切り替えは即時（めくりアニメ無し）。リズムよく次々と解けるように。
      domSteps(t).forEach(function (el) {
        el.classList.remove('turn-out', 'turn-in', 'turn-under', 'on');
      });
      if (steps[s]) steps[s].classList.add('on');
      navbar.hidden = false;
      var onModeStep = steps[s] && steps[s].dataset.sec === 'M';
      // 「やり方をえらぼう」は本文にも大きく出るのでヘッダーには出さない（単元タブの幅を優先）
      barStep.textContent = onModeStep ? '' : (s + 1) + ' / ' + steps.length;
      pfill.style.width = (((s + 1) / steps.length) * 100) + '%';
      document.getElementById('btnPrev').textContent = s === 0 ? '🏠 目次' : '← まえへ';
      var next = document.getElementById('btnNext');
      if (onModeStep && steps.length === 1) next.textContent = '⭐ おすすめ順で始める →';
      else if (s < steps.length - 1) next.textContent = 'つぎへ →';
      else next.textContent = t < N ? '次の単元へ →' : '🏠 目次にもどる';
      if (steps[s] && steps[s].classList.contains('done-step')) renderScore(views[t]);
      var st = store();
      st.last = { t: t, s: s };
      if (steps.length > 1 && s === steps.length - 1) st['d' + t] = 1;
      save(st);
    }
    window.scrollTo(0, 0);
    // 短答「入力して判定」モードは、毎回クリックしなくて済むよう答え入力欄へ自動フォーカス
    if (t > 0 && steps[s] && !steps[s].classList.contains('show')
        && views[t].classList.contains('ans-type')) {
      var focusIn = steps[s].querySelector('.b-inrow .b-in');
      if (focusIn) {
        try { focusIn.focus({ preventScroll: true }); } catch (err) { focusIn.focus(); }
      }
    }
    var h = '#t' + t + (t > 0 && s > 0 ? 's' + s : '');
    // クエリが付いていても落とさない（URL共有時の情報を保つ）
    if (location.hash !== h) history.replaceState(null, '', location.search + (t === 0 ? '#' : h));
    updateSwap();
    rendered = { t: t, s: s };
  }

  function renderHome() {
    var st = store();
    [].forEach.call(document.querySelectorAll('.toc-state'), function (el) {
      var t = +el.dataset.stateT;
      el.className = 'toc-state';
      if (st['d' + t] === 1) { el.classList.add('done'); el.textContent = '✓ といた'; }
      else if (st.last && st.last.t === t && st.last.s > 0) {
        el.classList.add('doing'); el.textContent = 'つづき';
      } else { el.textContent = ''; }
    });
    var btn = document.getElementById('resumeBtn');
    if (st.last && st.last.t > 0) {
      btn.hidden = false;
      var name = views[st.last.t].querySelector('.tband h2').textContent;
      document.getElementById('resumeWhere').textContent =
        name + '（' + (st.last.s + 1) + '問目）';
      btn.onclick = function () { go(st.last.t, st.last.s, 1); };
    } else { btn.hidden = true; }
  }

  function go(t, s, dir) {
    lastDir = dir || 1;
    state.t = Math.max(0, Math.min(N, t));
    state.s = Math.max(0, s || 0);
    if (state.t > 0) state.s = Math.min(state.s, stepsOf(state.t).length - 1);
    else state.s = 0;
    render();
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
    if (s < pl.length - 1) go(t, s + 1, 1);
    else if (t < N) go(t + 1, 0, 1);
    else go(0, 0, 1);
  }
  function prev() {
    var t = state.t, s = state.s;
    if (t === 0) return;
    if (s > 0) go(t, s - 1, -1);
    else go(0, 0, -1);
  }

  document.getElementById('btnNext').addEventListener('click', next);
  document.getElementById('btnPrev').addEventListener('click', prev);

  document.addEventListener('click', function (e) {
    var go_ = e.target.closest('[data-go]');
    if (go_) { go(+go_.dataset.go, 0, 1); return; }

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
      if (rm === 'B') { rcfg.ans = 'type'; rcfg.batch = false; rcfg.shuf = false; rcfg.order = null; }
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
        cfg.batch = chip('batch') === 1;
        cfg.shuf = chip('shufB') === 1;
      }
      if (cfg.mode === 'C') { cfg.shuf = chip('shufC') === 1; }
      if ((cfg.mode === 'B' && !cfg.batch) || cfg.mode === 'C') {
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
      if (bn) { bn.textContent = '👇 こたえはこちら。次はきっと書けるよ！'; bn.className = 'b-result ng'; }
      var stI = store(); stI.r = stI.r || {};
      stI.r[istep.dataset.qid] = 0;
      save(stI);
      return;
    }
    // 一問一答: 入力して判定（まとめて）
    var bbj = e.target.closest('.b-batch-judge');
    if (bbj) {
      var bstep = bbj.closest('.step');
      var stB = store(); stB.r = stB.r || {};
      [].forEach.call(bstep.querySelectorAll('.bq-item'), function (it) {
        var ok2 = judgeTerm(it.querySelector('.b-in').value, it.dataset.a, it.dataset.r);
        showJudged(it, ok2);
        stB.r[it.dataset.qid] = ok2 ? 1 : 0;
      });
      bstep.classList.add('show');
      save(stB);
      window.scrollTo(0, 0);  // 上から答え合わせを見返せるように
      return;
    }

    var rev = e.target.closest('.reveal');
    if (rev) { rev.closest('.step').classList.add('show'); return; }

    var mk = e.target.closest('.mk');
    if (mk) {
      var st = store(); st.r = st.r || {};
      // まとめて採点（バッチ）内の○△: 記録して選択表示するだけで、進まない
      var bq = mk.closest('.bq-item');
      if (bq) {
        st.r[bq.dataset.qid] = +mk.dataset.v;
        save(st);
        [].forEach.call(bq.querySelectorAll('.mk'), function (b) {
          b.classList.toggle('sel', b === mk);
        });
        return;
      }
      var stp = mk.closest('.step');
      st.r[stp.dataset.qid] = +mk.dataset.v;
      save(st);
      // 自動では進まない。選んだ印を付けて「つぎへ」ボタンか Enter で次へ。
      [].forEach.call(stp.querySelectorAll('.marks .mk'), function (b) {
        b.classList.toggle('sel', b === mk);
      });
      return;
    }

    var opt = e.target.closest('.qopt');
    if (opt) {
      var qstep = opt.closest('.qz-step');
      if (qstep.classList.contains('answered')) return;
      qstep.classList.add('answered');
      var c = +qstep.dataset.c, chosen = +opt.dataset.i;
      [].forEach.call(qstep.querySelectorAll('.qopt'), function (b, i) {
        if (i === c) b.classList.add('correct');
        else if (i === chosen) b.classList.add('wrong');
        else b.classList.add('dim');
      });
      var ex = qstep.querySelector('.expl');
      if (ex) ex.style.display = 'block';
      var st2 = store(); st2.r = st2.r || {};
      st2.r[qstep.dataset.qid] = chosen === c ? 1 : 0;
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
      item.dataset.done = '1';
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
    var dx = e.changedTouches[0].clientX - tx;
    var dy = e.changedTouches[0].clientY - ty;
    if (Math.abs(dx) > 64 && Math.abs(dy) < 48 && state.t > 0) {
      if (dx < 0) next(); else prev();
    }
  }, { passive: true });

  function fromHash() {
    var m = /#t(\\d+)(?:s(\\d+))?/.exec(location.hash);
    if (m) go(+m[1], +(m[2] || 0), 1); else go(0, 0, 1);
  }
  window.addEventListener('hashchange', fromHash);
  fromHash();
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
                    help="指定の章番号（例 04）を marutto-study/public/tsudumon/wb/ へ出力")
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
