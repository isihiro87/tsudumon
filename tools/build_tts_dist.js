/* =====================================================================
   つづもん 読み上げ音声：配信用に軽量化してまとめる
   ---------------------------------------------------------------------
   output/web/tts/<NN-topicId>/narration.mp3（128kbps・合計264MB）を
   64kbps モノラルへ再エンコードして dist/tts/ に集める（合計 約130MB）。
   読み上げ音声は人の声だけなので 64kbps で聞き分けはつかず、
   生徒の通信量と配信コストが半分になる。

   出力:
     dist/tts/<NN-topicId>.mp3        … 配信する音声
     dist/tts/_manifest.json          … {key: {sec, bytes}} の一覧

   実行: node tools/build_tts_dist.js [--bitrate 64k]
   ===================================================================== */
"use strict";
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const BASE = path.resolve(__dirname, "..");
const SRC = path.join(BASE, "output", "web", "tts");
const OUT = path.join(BASE, "dist", "tts");
function resolveBin(envVal, def, exe) {
  if (envVal) {
    try { if (fs.statSync(envVal).isDirectory()) return path.join(envVal, exe); } catch (e) {}
    return envVal;
  }
  return def;
}
const FFMPEG = resolveBin(process.env.FFMPEG, "C:/ffmpeg/bin/ffmpeg.exe", "ffmpeg.exe");
const argv = process.argv.slice(2);
const BITRATE = (() => {
  const i = argv.indexOf("--bitrate");
  return i >= 0 && argv[i + 1] ? argv[i + 1] : "64k";
})();

fs.mkdirSync(OUT, { recursive: true });
const keys = fs.readdirSync(SRC).filter((d) => fs.existsSync(path.join(SRC, d, "narration.mp3")));
const manifest = {};
let srcBytes = 0, outBytes = 0;

keys.forEach((key, i) => {
  const src = path.join(SRC, key, "narration.mp3");
  const dst = path.join(OUT, key + ".mp3");
  const json = JSON.parse(fs.readFileSync(path.join(SRC, key, "narration.json"), "utf8"));
  // 元より新しければ作り直さない（再実行が速い）
  const fresh = fs.existsSync(dst) && fs.statSync(dst).mtimeMs >= fs.statSync(src).mtimeMs;
  if (!fresh) {
    execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-i", src,
      "-c:a", "libmp3lame", "-b:a", BITRATE, "-ac", "1", "-ar", "24000", dst]);
  }
  srcBytes += fs.statSync(src).size;
  outBytes += fs.statSync(dst).size;
  manifest[key] = { sec: json.total, bytes: fs.statSync(dst).size, voice: json.voice };
  process.stdout.write(`\r${i + 1}/${keys.length} ${key}${fresh ? "（再利用）" : ""}          `);
});
fs.writeFileSync(path.join(OUT, "_manifest.json"), JSON.stringify(manifest, null, 1));
console.log(`\n${keys.length}本 / ${(srcBytes / 1048576).toFixed(0)}MB → ${(outBytes / 1048576).toFixed(0)}MB（${BITRATE}）`);
console.log("wrote " + OUT);
