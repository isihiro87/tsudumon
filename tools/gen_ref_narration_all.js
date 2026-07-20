/* =====================================================================
   つづもん 参考書Web版：全単元の読み上げ音声をまとめて生成
   ---------------------------------------------------------------------
   gen_ref_narration.js を単元ごとに順番に呼ぶだけのバッチ。
   ・キャッシュ（output/web/tts/<NN-topicId>/_tmp）が効くので、途中で止めても
     もう一度実行すれば続きから（生成済みの文は API を叩かない）。
   ・進捗は output/web/tts/_batch-log.txt に追記。

   実行:  node tools/gen_ref_narration_all.js            （全19冊・④を先頭に）
          node tools/gen_ref_narration_all.js 04 05      （章を指定）
   ===================================================================== */
"use strict";
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const BASE = path.resolve(__dirname, "..");
const REF_DIR = path.join(BASE, "reference");
const OUT_ROOT = path.join(BASE, "output", "web", "tts");
const LOG = path.join(OUT_ROOT, "_batch-log.txt");
fs.mkdirSync(OUT_ROOT, { recursive: true });

const files = fs.readdirSync(REF_DIR).filter((f) => f.endsWith(".json")).sort();
const only = process.argv.slice(2).filter((a) => /^\d{2}$/.test(a));
// ④（無料体験単元がある巻）を先頭に、あとは章番号順
const chapters = files
  .map((f) => f.replace(/\.json$/, ""))
  .filter((c) => !only.length || only.includes(c.slice(0, 2)))
  .sort((a, b) => (a.startsWith("04") ? -1 : b.startsWith("04") ? 1 : a.localeCompare(b)));

function log(line) {
  const s = new Date().toISOString().slice(11, 19) + " " + line;
  console.log(s);
  fs.appendFileSync(LOG, s + "\n");
}

let done = 0, failed = 0;
const total = chapters.reduce((n, c) =>
  n + JSON.parse(fs.readFileSync(path.join(REF_DIR, c + ".json"), "utf8")).topics.length, 0);
log(`=== バッチ開始: ${chapters.length}冊 / ${total}単元 ===`);

for (const chapter of chapters) {
  const spec = JSON.parse(fs.readFileSync(path.join(REF_DIR, chapter + ".json"), "utf8"));
  for (let i = 1; i <= spec.topics.length; i++) {
    const t = spec.topics[i - 1];
    const label = `${chapter} #${i} ${t.name}`;
    const r = spawnSync(process.execPath, [path.join(__dirname, "gen_ref_narration.js"), chapter, String(i)],
      { cwd: BASE, encoding: "utf8", maxBuffer: 1 << 26 });
    const out = (r.stdout || "") + (r.stderr || "");
    const wrote = (out.match(/narration\.mp3 \(([\d.]+)s \/ (\d+)文\)/) || []);
    const fixes = (out.match(/読み落とし/g) || []).length;
    const cost = (out.match(/COST 概算: 約([\d.]+)円/) || [])[1] || "?";
    if (r.status === 0 && wrote[1]) {
      done++;
      log(`✓ ${label} — ${wrote[1]}s / ${wrote[2]}文 / 作り直し${fixes}件 / 約${cost}円 [${done}/${total}]`);
    } else {
      failed++;
      log(`✗ ${label} — 失敗: ${(out.match(/ERROR:.*/) || ["(不明)"])[0].slice(0, 160)}`);
    }
  }
}
log(`=== バッチ終了: 成功 ${done} / 失敗 ${failed} ===`);
