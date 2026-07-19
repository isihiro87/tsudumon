# -*- coding: utf-8 -*-
"""
資料図の空欄化に合わせ、books/*.json の shiryo キャプション・設問を穴埋め型へ更新。
- キャプションから答えの語句を除く
- 画像と食い違う設問（日清戦争図など）を作り直す
- 一部の設問に丸数字（①②）参照を補う
画像は image 名で突き合わせる。
"""
import glob
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# image名 -> 新キャプション
CAPTIONS = {
    "era-scale-diagram.webp": "年の数え方",
    "ritsuryo-central-org.webp": "朝廷の中央のしくみ",
    "handen-shuju-cycle.webp": "6歳以上に土地を分けあたえるしくみ",
    "goon-hoko-relation.webp": "将軍と御家人の関係",
    "kango-trade-system.webp": "日本と明の正式な貿易のしくみ",
    "land-tax-reform.webp": "土地の税のしくみの変化",
    "manchuria-war-route.webp": "1930年代の日本の大陸進出",
    "land-reform-bar.webp": "自作地と小作地の割合の変化",
    "high-growth-gnp-chart.webp": "実質GNP成長率の推移（1955〜1973年）",
    "bubble-economy-graph.webp": "株価と地価の推移",
    "sino-japanese-war-caricature-diagram.webp": "日本と清が朝鮮をめぐって対立した構図",
}

# image名 -> 差し替える questions（[(q,a)...]）
QUESTIONS = {
    # 生成図が風刺画ではないため、図に合う設問へ作り直し
    "sino-japanese-war-caricature-diagram.webp": [
        ("図中の①の、日本と清が勢力をめぐって争った、二国の間にある地域（国）はどこか。", "朝鮮"),
        ("図のように、朝鮮をめぐって対立した日本と清が、1894年に始めた戦争を何というか。", "日清戦争"),
    ],
    # 壱岐が図に残るため「朝鮮半島に最も近い島」に限定
    "genko-route-map.webp": [
        ("地図中で、朝鮮半島に最も近く、元軍が最初に攻めた島を何というか。", "対馬"),
        ("地図中で、元軍が二度にわたって上陸をめざした九州北部の湾を何というか。", "博多湾"),
    ],
    # ②参照を補う
    "handen-shuju-cycle.webp": [
        ("図のように、戸籍に登録された6歳以上の人々に口分田を与え、死ぬと国に返させた土地の制度を何というか。", "班田収授法"),
        ("図中の②の、口分田を与えられた人々が国に納めた、稲による税を何というか。", "租"),
    ],
    "goon-hoko-relation.webp": [
        ("図中の①の、将軍が御家人の領地を守ったり与えたりすることを何というか。", "御恩"),
        ("図中の②の、御家人が将軍のために戦いや警備に参加することを何というか。", "奉公"),
    ],
    "bubble-economy-graph.webp": [
        ("グラフの①が示す、1980年代後半に株価と地価が実際の価値以上に高騰した好景気を何というか。", "バブル経済"),
        ("グラフの②の、1990年代初めに株価と地価が急落したできごとを何というか。", "バブル崩壊"),
    ],
}


def main():
    ncap = nq = 0
    for f in sorted(glob.glob("books/*.json")):
        d = json.load(open(f, encoding="utf-8"))
        changed = False
        for tid, items in d.get("shiryo", {}).items():
            lst = items if isinstance(items, list) else [items]
            for e in lst:
                img = e.get("image")
                if img in CAPTIONS and e.get("caption") != CAPTIONS[img]:
                    e["caption"] = CAPTIONS[img]
                    ncap += 1
                    changed = True
                if img in QUESTIONS:
                    e["questions"] = [{"q": q, "a": a} for q, a in QUESTIONS[img]]
                    nq += 1
                    changed = True
            d["shiryo"][tid] = lst
        if changed:
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print("updated", os.path.basename(f))
    print(f"caption {ncap}件 / questions {nq}図 を更新")
    # 検証
    for f in glob.glob("books/*.json"):
        json.load(open(f, encoding="utf-8"))
    print("全JSON OK")


if __name__ == "__main__":
    main()
