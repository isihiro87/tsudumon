/* =====================================================================
   つづもん 参考書Web版：読み上げ音声＋読み位置ハイライト（試作）
   ---------------------------------------------------------------------
   入力 : pdf-workbook/reference/<chapter>.json の 1 単元
   出力 : output/web/tts/<chapter>-<topicId>/
            narration.mp3   ... 単元まるごとの読み上げ
            narration.json  ... 文ごとの開始秒・長さ（実測）
            index.html      ... 音声プレーヤー＋読んでいる文がハイライトされるデモ

   仕組み: 文ごとに Gemini TTS で音声(PCM)生成 → wav 化して ffprobe で実測
          → 無音を足して連結 → mp3。実測秒を積み上げて文の開始時刻表を作る。
          （TTS はタイムスタンプを返さないので「文ごとに作って測る」のが確実）

   実行例:
     node tools/gen_ref_narration.js 04-ancient-state 1
     node tools/gen_ref_narration.js 04-ancient-state 1 --voice Achird
     node tools/gen_ref_narration.js 04-ancient-state 1 --samples   （声くらべ用の短い試聴も作る）

   APIキー: 環境変数 GEMINI_API_KEY か movie_study/tools/.gemini-api-key.txt
   ===================================================================== */
"use strict";
const fs = require("fs");
const path = require("path");
const https = require("https");
const { execFileSync, spawnSync } = require("child_process");

const BASE = path.resolve(__dirname, "..");                 // pdf-workbook/
const REPO = path.resolve(BASE, "..");                      // education-apps/
// FFMPEG/FFPROBE 環境変数がディレクトリを指す場合は実行ファイル名を補う
function resolveBin(envVal, def, exe) {
  if (envVal) {
    try { if (fs.statSync(envVal).isDirectory()) return path.join(envVal, exe); } catch (e) {}
    return envVal;
  }
  return def;
}
const FFMPEG = resolveBin(process.env.FFMPEG, "C:/ffmpeg/bin/ffmpeg.exe", "ffmpeg.exe");
const FFPROBE = resolveBin(process.env.FFPROBE, "C:/ffmpeg/bin/ffprobe.exe", "ffprobe.exe");

const argv = process.argv.slice(2);
const positional = argv.filter((a) => !a.startsWith("--"));
const flag = (name, def) => {
  const i = argv.indexOf("--" + name);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : def;
};
const CHAPTER = positional[0] || "04-ancient-state";
const TOPIC_NO = parseInt(positional[1] || "1", 10);          // 1 始まり
// ★やさしい男性の声。Gemini プリセット: Umbriel(おだやか)/Achird(親しみ)/Charon(落ち着き)
const VOICE = flag("voice", process.env.GEMINI_TTS_VOICE || "Umbriel");
const SPEED = parseFloat(flag("speed", "1.0"));              // ピッチ維持で速度調整
const WITH_SAMPLES = argv.includes("--samples");
// 読み落とし検査（既定ON。--no-verify で切る）。Gemini 音声理解で本文どおりか確かめ、NG は作り直す。
const VERIFY = !argv.includes("--no-verify");
const GAP_MS = parseInt(flag("gap", process.env.TTS_GAP_MS || "3000"), 10);   // TTS 1件ごとの待機ms
const SAMPLE_VOICES = ["Umbriel", "Achird", "Charon", "Iapetus"];
// モデル: ユーザー指定 gemini-3.1-flash-tts。404 のときは -preview へ自動フォールバック。
let MODEL = process.env.GEMINI_TTS_MODEL || "gemini-3.1-flash-tts";
const MODEL_FALLBACK = "gemini-3.1-flash-tts-preview";

let API_KEY = process.env.GEMINI_API_KEY;
const keyFile = path.join(REPO, "movie_study", "tools", ".gemini-api-key.txt");
if (!API_KEY && fs.existsSync(keyFile)) API_KEY = fs.readFileSync(keyFile, "utf8").trim();
if (!API_KEY) { console.error("GEMINI_API_KEY が見つかりません"); process.exit(1); }

// ── 読み修正辞書（ムビスタの蓄積を流用：歴史の固有名詞の読み間違いを音声側だけ直す）──
let READINGS = {};
const loadReadings = (p) => {
  try { const j = JSON.parse(fs.readFileSync(p, "utf8")); return j.readings || j || {}; }
  catch (e) { console.warn("readings 読み込み失敗（無視）: " + p); return {}; }
};
READINGS = Object.assign(
  loadReadings(path.join(REPO, "movie_study", "lessons", "readings.json")),   // 歴史の固有名詞
  loadReadings(path.join(__dirname, "tsudumon.readings.json")));              // つづもん固有（世紀の読み等）
delete READINGS._comment;
const READING_KEYS = Object.keys(READINGS).sort((a, b) => b.length - a.length);
const applyReadings = (t) => READING_KEYS.reduce((s, k) => s.split(k).join(READINGS[k]), t);

// ── テキスト整形 ───────────────────────────────────────────────
const stripBold = (s) => String(s).replace(/\*\*(.+?)\*\*/g, "$1");
const escHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// **強調** を .mark に（参考書Web版の rich() と同じ見た目）
const rich = (s) => String(s).split(/(\*\*.+?\*\*)/).map((p) =>
  p.startsWith("**") && p.endsWith("**") ? `<span class="mark">${escHtml(p.slice(2, -2))}</span>` : escHtml(p)).join("");

// 文分割（「」（）の中の 。！？ では切らない）。**強調**は文をまたがない前提。
function splitSentences(full) {
  const out = []; let buf = "", depth = 0;
  for (const ch of String(full)) {
    buf += ch;
    if (ch === "「" || ch === "（" || ch === "『") depth++;
    else if (ch === "」" || ch === "）" || ch === "』") depth = Math.max(0, depth - 1);
    else if (depth === 0 && (ch === "。" || ch === "！" || ch === "？")) { out.push(buf); buf = ""; }
  }
  if (buf.trim()) out.push(buf);
  return out.filter((s) => s.trim());
}

// ── 読点で「句」に分ける（ハイライトの粒度）──────────────────
//   音声は文まるごとで作る（読点で切って合成すると句ごとに文末イントネーションが付いて不自然）。
//   ハイライトだけを句単位にし、句の開始時刻は下の estimateClauseTimes で実測から割り出す。
const MIN_CLAUSE = 8;   // これより短い句は前後にくっつける（一瞬すぎる点滅を防ぐ）
function splitClauses(sentence) {
  // **強調** の内側の読点では切らない
  const raw = [];
  let buf = "", bold = false;
  const chars = [...String(sentence)];
  for (let i = 0; i < chars.length; i++) {
    const ch = chars[i];
    if (ch === "*" && chars[i + 1] === "*") { bold = !bold; buf += "**"; i++; continue; }
    buf += ch;
    if (!bold && ch === "、") { raw.push(buf); buf = ""; }
  }
  if (buf) raw.push(buf);
  // 短すぎる句をまとめる
  const out = [];
  for (const c of raw) {
    const len = [...stripBold(c)].length;
    if (out.length && (len < MIN_CLAUSE || [...stripBold(out[out.length - 1])].length < MIN_CLAUSE)) {
      out[out.length - 1] += c;
    } else out.push(c);
  }
  return out.length ? out : [sentence];
}

// 発話の重み（おおよそのモーラ数）。漢字は2モーラ前後、かなは1、小書き・記号は軽く。
function weight(text) {
  let w = 0;
  for (const ch of [...String(text)]) {
    if (/[ぁぃぅぇぉっゃゅょァィゥェォッャュョー]/.test(ch)) w += 0.5;
    else if (/[、。！？「」（）『』・]/.test(ch)) w += 0.15;      // 読点自体の間は別途ポーズで見る
    else if (/[一-鿿]/.test(ch)) w += 2;                  // 漢字
    else if (/[0-9]/.test(ch)) w += 1.5;
    else w += 1;
  }
  return w;
}

// 文の wav から無音（＝読点のポーズ）を検出して、句の開始秒を決める。
//   ①モーラ数按分でおおよその境界を出す ②その近くにある実測の無音へスナップ
// 無音が見つからない/数が合わないときは按分値のまま使う（ズレても数百msに収まる）。
function detectSilences(wav) {
  // silencedetect の結果は stderr に出る（stdout ではない）
  const r = spawnSync(FFMPEG, ["-hide_banner", "-i", wav, "-af",
    "silencedetect=noise=-38dB:d=0.09", "-f", "null", "-"], { encoding: "utf8" });
  const out = (r.stderr || "") + (r.stdout || "");
  const sil = [];
  let start = null;
  for (const line of out.split(/\r?\n/)) {
    const s = line.match(/silence_start:\s*([\d.]+)/);
    const e = line.match(/silence_end:\s*([\d.]+)/);
    if (s) start = parseFloat(s[1]);
    if (e && start !== null) { sil.push({ start, end: parseFloat(e[1]) }); start = null; }
  }
  return sil;
}

function estimateClauseTimes(wav, clauses, total) {
  const times = [0];
  if (clauses.length === 1) return times;
  const ws = clauses.map((c) => weight(stripBold(c)));
  const sum = ws.reduce((a, b) => a + b, 0);
  // ①按分（先頭の立ち上がり無音は無視できる程度なのでそのまま比例配分）
  const est = [];
  let acc = 0;
  for (let i = 0; i < clauses.length - 1; i++) { acc += ws[i]; est.push(total * acc / sum); }
  // ②実測の無音へスナップ（前後 0.9 秒以内・順序を保って1つずつ使う）
  const sil = detectSilences(wav).filter((s) => s.start > 0.15 && s.end < total - 0.15);
  let from = 0;
  for (let i = 0; i < est.length; i++) {
    let best = -1, bestGap = 0.9;
    for (let k = from; k < sil.length; k++) {
      const mid = (sil[k].start + sil[k].end) / 2;
      const gap = Math.abs(mid - est[i]);
      if (gap < bestGap) { bestGap = gap; best = k; }
    }
    // 無音の「終わり」＝次の句の話し始め
    times.push(+(best >= 0 ? sil[best].end : est[i]).toFixed(3));
    if (best >= 0) from = best + 1;
  }
  // 単調増加を保証
  for (let i = 1; i < times.length; i++) if (times[i] <= times[i - 1]) times[i] = +(times[i - 1] + 0.15).toFixed(3);
  return times;
}

// ── 単元 → 読み上げブロック ────────────────────────────────────
const spec = JSON.parse(fs.readFileSync(path.join(BASE, "reference", CHAPTER + ".json"), "utf8"));
const topic = spec.topics[TOPIC_NO - 1];
if (!topic) { console.error("単元が見つかりません: " + TOPIC_NO); process.exit(1); }
const CH_NO = CHAPTER.slice(0, 2);

const blocks = [];   // { kind, secNo, heading, sentences:[raw] }
const push = (kind, text, extra = {}) => {
  if (!text) return;
  blocks.push(Object.assign({ kind, sentences: splitSentences(text) }, extra));
};
push("hook", topic.hook);
topic.sections.forEach((s, i) => {
  push("heading", s.heading, { secNo: i + 1 });
  push("lead", s.lead, { secNo: i + 1 });
  push("body", s.body, { secNo: i + 1 });
  push("point", s.point, { secNo: i + 1 });
});
push("summary", topic.summary30 || topic.summary);

// ── Gemini TTS ────────────────────────────────────────────────
function ttsRequest(text, voice) {
  const body = JSON.stringify({
    contents: [{ parts: [{ text }] }],
    generationConfig: {
      responseModalities: ["AUDIO"],
      speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: voice } } },
    },
  });
  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: "generativelanguage.googleapis.com",
      path: "/v1beta/models/" + MODEL + ":generateContent?key=" + API_KEY,
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
    }, (res) => {
      let data = "";
      res.on("data", (d) => (data += d));
      res.on("end", () => {
        if (res.statusCode !== 200) return reject(new Error("HTTP " + res.statusCode + ": " + data.slice(0, 300)));
        try {
          const j = JSON.parse(data);
          const parts = ((((j.candidates || [])[0] || {}).content) || {}).parts || [];
          const part = parts.find((p) => p.inlineData && p.inlineData.data);
          if (!part) return reject(new Error("音声データなし: " + data.slice(0, 200)));
          const rate = parseInt(((part.inlineData.mimeType || "").match(/rate=(\d+)/) || [])[1] || "24000", 10);
          resolve({ pcm: Buffer.from(part.inlineData.data, "base64"), rate, usage: j.usageMetadata || {} });
        } catch (e) { reject(e); }
      });
    });
    req.on("error", reject);
    req.write(body); req.end();
  });
}

async function ttsWithRetry(text, voice) {
  let delay = 6000;
  for (let attempt = 1; attempt <= 6; attempt++) {
    try { return await ttsRequest(text, voice); }
    catch (e) {
      const msg = e.message || "";
      if ((msg.includes("HTTP 404") || msg.includes("NOT_FOUND")) && MODEL !== MODEL_FALLBACK) {
        console.log("\n  モデル " + MODEL + " が見つからないため " + MODEL_FALLBACK + " へ切替");
        MODEL = MODEL_FALLBACK; continue;
      }
      const is429 = msg.includes("HTTP 429") || msg.includes("RESOURCE_EXHAUSTED");
      // HTTP 400 はふつう「送り方が悪い」だが、このTTSは同じ本文でもまれに 400 を返し、
      // 作り直すと通る（サーバ側の一時的な失敗）。数回だけ再試行する。
      const isNet = /socket hang up|ECONNRESET|ETIMEDOUT|EAI_AGAIN|ENOTFOUND|HTTP 5\d\d|HTTP 400/i.test(msg);
      if ((!is429 && !isNet) || attempt === 6) throw e;
      const m = msg.match(/retry in ([\d.]+)s/i);
      const wait = m ? Math.ceil(parseFloat(m[1]) * 1000) + 1500 : delay;
      process.stdout.write("(" + (is429 ? "429" : "通信") + ": " + Math.round(wait / 1000) + "s待機) ");
      await new Promise((r) => setTimeout(r, wait));
      delay = Math.min(delay * 2, 60000);
    }
  }
}

// ── 読み落とし検査（Gemini 音声理解）─────────────────────────
//   TTS は文頭の短い語（例「6世紀末、」）をまれに読み飛ばす。耳で全部確かめるのは
//   19冊ぶんでは非現実的なので、生成した音声を「テキストどおりか」判定させ、NG なら作り直す。
const JUDGE_MODEL = process.env.GEMINI_JUDGE_MODEL || "gemini-3-flash-preview";
function judgeAudio(wav, expected) {
  const body = JSON.stringify({
    contents: [{ parts: [
      { inlineData: { mimeType: "audio/wav", data: fs.readFileSync(wav).toString("base64") } },
      { text: "この音声は、次の日本語テキストの読み上げです:\n「" + expected + "」\n" +
              "テキストの語がすべて読まれているかを判定してください。とくに**文の先頭**の語（数字・年号・『◯世紀』など）の"
              + "読み飛ばしがないか、余計な語が足されていないかを見ます。読みがかな書きでも内容が同じならOK。\n" +
              'JSONだけで答えて（説明不要）: {"match": true か false, "missing": "抜けている語（無ければ空文字）"}' },
    ] }],
  });
  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: "generativelanguage.googleapis.com",
      path: "/v1beta/models/" + JUDGE_MODEL + ":generateContent?key=" + API_KEY,
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
    }, (res) => {
      let data = "";
      res.on("data", (d) => (data += d));
      res.on("end", () => {
        if (res.statusCode !== 200) return reject(new Error("HTTP " + res.statusCode + ": " + data.slice(0, 200)));
        try {
          const parts = ((((JSON.parse(data).candidates || [])[0] || {}).content) || {}).parts || [];
          resolve(parts.map((p) => p.text || "").join(""));
        } catch (e) { reject(e); }
      });
    });
    req.on("error", reject);
    req.write(body); req.end();
  });
}
async function checkRead(wav, expected) {
  try {
    const ans = await judgeAudio(wav, expected);
    const m = ans.match(/\{[\s\S]*\}/);
    const j = JSON.parse(m ? m[0] : "{}");
    return { ok: j.match !== false, missing: j.missing || "" };
  } catch (e) { return { ok: true, missing: "" }; }   // 判定APIが落ちても生成は止めない
}

const OUT = path.join(BASE, "output", "web", "tts", CH_NO + "-" + topic.topicId);
const TMP = path.join(OUT, "_tmp");
fs.mkdirSync(TMP, { recursive: true });
const dur = (f) => parseFloat(execFileSync(FFPROBE, ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).toString().trim());

async function synth(id, text, voice) {
  const wav = path.join(TMP, id + ".wav");
  const stamp = path.join(TMP, id + ".txt");
  const key = voice + "|" + MODEL + "|" + SPEED + "|" + text;
  const okMark = path.join(TMP, id + ".ok");
  const cached = fs.existsSync(wav) && fs.existsSync(stamp) && fs.readFileSync(stamp, "utf8") === key;
  // 検査済みの印（.ok）が無いキャッシュは、読み落としチェックだけ後追いで行う
  if (cached && (!VERIFY || fs.existsSync(okMark))) return { wav, dur: dur(wav), cached: true };

  let usage = null, note = "";
  for (let attempt = 1; attempt <= (VERIFY ? 3 : 1); attempt++) {
    if (!(cached && attempt === 1)) {
      const got = await ttsWithRetry(text, voice);
      usage = got.usage;
      const pcm = path.join(TMP, id + ".pcm");
      fs.writeFileSync(pcm, got.pcm);
      const args = ["-y", "-loglevel", "error", "-f", "s16le", "-ar", String(got.rate), "-ac", "1", "-i", pcm];
      if (SPEED !== 1) args.push("-af", "atempo=" + SPEED);
      args.push(wav);
      execFileSync(FFMPEG, args);
      fs.writeFileSync(stamp, key);
      // レート制限よけの間隔。読み落とし検査（数秒）ぶんも実質の間隔に足されるので短めでよい。
      // 詰めすぎて 429 が返っても ttsWithRetry が指示どおり待つので、事故にはならない。
      await new Promise((r) => setTimeout(r, GAP_MS));
    }
    if (!VERIFY) break;
    const v = await checkRead(wav, text);
    if (v.ok) { fs.writeFileSync(okMark, "ok"); break; }
    note += `（読み落とし「${v.missing}」→作り直し${attempt}）`;
    if (attempt === 3) { note += "⚠3回とも NG（要試聴）"; fs.writeFileSync(okMark, "ng"); }
  }
  return { wav, dur: dur(wav), usage, cached: cached && !note, note };
}

(async () => {
  console.log(`単元: ${topic.name} ／ 声: ${VOICE} ／ モデル: ${MODEL}`);
  const GAP_SENT = 0.28;    // 文と文のあいだ
  const GAP_BLOCK = 0.65;   // 段落（節・見出し）のあいだ
  const padded = [];
  let acc = 0, promptTok = 0, audioTok = 0, n = 0;

  for (let b = 0; b < blocks.length; b++) {
    const blk = blocks[b];
    blk.times = [];
    for (let s = 0; s < blk.sentences.length; s++) {
      const isLast = s === blk.sentences.length - 1 && b === blocks.length - 1;
      const isBlockEnd = s === blk.sentences.length - 1;
      const raw = blk.sentences[s];
      const ttsText = applyReadings(stripBold(raw));
      const id = "b" + b + "_s" + s;
      process.stdout.write(`TTS ${id} (${[...ttsText].length}字)... `);
      const r = await synth(id, ttsText, VOICE);
      promptTok += r.usage ? (r.usage.promptTokenCount || 0) : 0;
      audioTok += r.usage ? (r.usage.candidatesTokenCount || r.usage.responseTokenCount || 0) : 0;
      console.log((r.cached ? `cached ${r.dur.toFixed(2)}s` : `ok ${r.dur.toFixed(2)}s`) + (r.note || ""));
      // 文の中を読点で刻む（音声は文まるごと・ハイライトだけ句単位）
      const clauses = splitClauses(raw);
      const offs = estimateClauseTimes(r.wav, clauses, r.dur);
      blk.times.push({
        start: +acc.toFixed(3), dur: +r.dur.toFixed(3),
        clauses: clauses.map((c, ci) => ({
          text: c,
          start: +(acc + offs[ci]).toFixed(3),
          dur: +((ci + 1 < offs.length ? offs[ci + 1] : r.dur) - offs[ci]).toFixed(3),
        })),
      });
      if (clauses.length > 1) console.log("    句: " + offs.map((o) => o.toFixed(2)).join(" / "));
      const gap = isLast ? 0.2 : isBlockEnd ? GAP_BLOCK : GAP_SENT;
      const pad = path.join(TMP, id + "_p.wav");
      execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-i", r.wav, "-af", "apad=pad_dur=" + gap, pad]);
      padded.push(pad);
      acc += r.dur + gap;
      n++;
    }
  }

  const list = path.join(TMP, "list.txt");
  fs.writeFileSync(list, padded.map((p) => "file '" + p.replace(/\\/g, "/") + "'").join("\n") + "\n");
  const mp3 = path.join(OUT, "narration.mp3");
  execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list,
    "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-ac", "1", mp3]);
  console.log("wrote " + mp3 + " (" + acc.toFixed(1) + "s / " + n + "文)");

  // 声くらべ用の短い試聴（先頭1文を各声で）
  const samples = [];
  if (WITH_SAMPLES) {
    const sample = applyReadings(stripBold(blocks[0].sentences[0]));
    for (const v of SAMPLE_VOICES) {
      process.stdout.write("SAMPLE " + v + "... ");
      const r = await synth("sample_" + v, sample, v);
      const out = path.join(OUT, "voice-" + v + ".mp3");
      execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-i", r.wav, "-c:a", "libmp3lame", "-b:a", "128k", out]);
      samples.push({ voice: v, file: "voice-" + v + ".mp3" });
      console.log("ok");
    }
  }

  // タイムライン JSON（chunks＝ハイライトの単位＝句／sentence 情報も持たせる）
  const timeline = {
    chapter: CHAPTER, topicId: topic.topicId, name: topic.name,
    voice: VOICE, model: MODEL, speed: SPEED, total: +acc.toFixed(3),
    chunks: [],
  };
  let idx = 0, sidx = 0;
  blocks.forEach((blk, b) => blk.sentences.forEach((raw, s) => {
    const t = blk.times[s];
    t.clauses.forEach((c) => timeline.chunks.push({
      i: idx++, block: b, sentence: sidx, kind: blk.kind, secNo: blk.secNo || null,
      text: stripBold(c.text), start: c.start, dur: c.dur }));
    sidx++;
  }));
  fs.writeFileSync(path.join(OUT, "narration.json"), JSON.stringify(timeline, null, 1));

  // ── デモ HTML（読んでいる句がハイライト・文はうっすら囲む）──
  let si = 0, ss = 0;
  const sent = (raw) => {
    const inner = splitClauses(raw)
      .map((c) => `<span class="s" data-i="${si++}" data-sent="${ss}">${rich(c)}</span>`).join("");
    ss++;
    return inner;
  };
  const parts = [];
  blocks.forEach((blk) => {
    const inner = blk.sentences.map(sent).join("");
    if (blk.kind === "hook") parts.push(`<div class="hook"><div class="bubble">${inner}</div></div>`);
    else if (blk.kind === "heading") parts.push(`<h3><span class="sec-no">${blk.secNo}</span>${inner}</h3>`);
    else if (blk.kind === "lead") parts.push(`<div class="sec-lead">${inner}</div>`);
    else if (blk.kind === "body") parts.push(`<p>${inner}</p>`);
    else if (blk.kind === "point") parts.push(`<div class="point"><span class="ptag">⭐ ここだけ覚える</span><div class="ptxt">${inner}</div></div>`);
    else parts.push(`<div class="sum30"><div class="sum30-h">⏱ 30秒まとめ</div><div class="sum30-body">${inner}</div></div>`);
  });
  const sampleHtml = samples.length ? `
  <div class="voices">
    <div class="vh">🎧 声くらべ（先頭の1文）</div>
    ${samples.map((v) => `<button class="vbtn" data-src="${v.file}">${v.voice}</button>`).join("")}
    <audio id="sampleAudio"></audio>
  </div>` : "";

  const html = `<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${escHtml(topic.name)}｜読み上げ試作</title>
<style>
  :root { --brand:#b45309; --deep:#7c2d12; --amber:#f59e0b; --cream:#fffdf8; --line:#fde68a; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
         font-size:16px; line-height:2.0; color:#1c1917; background:var(--cream); padding-bottom:120px; }
  .wrap { max-width:640px; margin:0 auto; padding:16px 16px 24px; }
  .tband { display:flex; align-items:center; gap:10px; background:var(--brand); color:#fff;
           border-radius:12px; padding:8px 14px; margin-bottom:14px; }
  .tband .tno { width:26px; height:26px; border-radius:50%; background:#fff; color:var(--brand);
                display:inline-flex; align-items:center; justify-content:center; font-weight:bold; font-size:14px; }
  .tband h2 { font-size:17px; }
  h3 { font-size:18px; color:var(--deep); margin:26px 0 8px; display:flex; gap:8px; align-items:flex-start; }
  .sec-no { flex:none; width:22px; height:22px; border-radius:50%; background:#fff; margin-top:4px;
            border:1.5px solid var(--line); color:var(--brand); font-weight:bold; font-size:13px;
            display:inline-flex; align-items:center; justify-content:center; }
  p { margin:6px 0 4px; }
  .mark { background:linear-gradient(transparent 55%, var(--line) 55%); font-weight:bold; padding:0 1px; }
  .hook { margin-bottom:8px; }
  .bubble { background:#fff; border:2px solid var(--amber); border-radius:12px; padding:10px 14px; font-size:15px; }
  .sec-lead { color:#92400e; font-weight:bold; font-size:15px; }
  .point { background:#fffbeb; border:1.5px solid var(--line); border-radius:12px; padding:10px 14px; margin:10px 0; }
  .ptag { display:inline-block; background:var(--amber); color:#fff; font-size:12px; font-weight:bold;
          border-radius:10px; padding:1px 10px; margin-bottom:4px; }
  .sum30 { background:#fff7ed; border:1.5px solid var(--line); border-radius:12px; padding:12px 14px; margin-top:22px; }
  .sum30-h { font-weight:bold; color:var(--deep); margin-bottom:4px; }
  .voices { margin-top:22px; padding:12px 14px; border:1px dashed var(--line); border-radius:12px; }
  .vh { font-size:13px; font-weight:bold; color:var(--deep); margin-bottom:6px; }
  .vbtn { border:1.5px solid var(--line); background:#fffbeb; color:var(--brand); font-weight:bold;
          border-radius:20px; padding:5px 14px; margin:2px 4px 2px 0; cursor:pointer; }

  /* ── 読み上げ位置のハイライト（読点ごとの句が単位）──
     全ての句にあらかじめ余白を持たせ、同じ幅の負マージンで打ち消す＝ハイライトが
     文字の外側へ丸く張り出しても、文字の位置はまったく動かない。
     box-decoration-break:clone ＝ 行をまたぐ句でも各行の左右が丸くなる。 */
  /* 左右の張り出しは 0.12em だけ＝隣の文字や枠にかぶらない最小限。
     上下は行間に余裕があるので 0.14em 広げて帯に見せる。 */
  .s { border-radius:6px; padding:.14em .12em; margin:0 -.12em; cursor:pointer;
       -webkit-box-decoration-break:clone; box-decoration-break:clone;
       transition:background-color .15s ease, color .15s ease; }
  .s.read { color:#8a8279; }                        /* 読み終わったところは薄く */
  .s.now { background:#fcd34d; color:#1c1917; }     /* いま読んでいる句だけを塗る */
  .s.now .mark { background:none; }                 /* 二重ハイライトを避ける */

  /* ── 下部プレーヤー ── */
  .player { position:fixed; left:0; right:0; bottom:0; background:rgba(255,253,248,.97);
            backdrop-filter:blur(6px); border-top:1px solid #f0e6d2; padding:8px 0 10px; z-index:20; }
  .pin { max-width:640px; margin:0 auto; padding:0 16px; display:flex; align-items:center; gap:10px; }
  .play { flex:none; width:48px; height:48px; border-radius:50%; border:none; background:var(--brand);
          color:#fff; font-size:20px; cursor:pointer; box-shadow:0 2px 8px rgba(180,83,9,.35); }
  .seek { flex:1; }
  .seek input { width:100%; accent-color:var(--brand); }
  .ptime { font-size:12px; color:var(--brand); font-weight:bold; min-width:82px; text-align:right; }
  .rate { flex:none; border:1.5px solid var(--line); background:#fffbeb; color:var(--brand);
          font-weight:bold; border-radius:20px; padding:5px 10px; cursor:pointer; font-size:13px; }
  .hint { max-width:640px; margin:0 auto; padding:2px 16px 0; font-size:11.5px; color:#a8a29e; }
</style></head><body>
<div class="wrap">
  <div class="tband"><span class="tno">${TOPIC_NO}</span><h2>${escHtml(topic.name)}</h2></div>
  ${parts.join("\n  ")}
  ${sampleHtml}
</div>
<div class="player">
  <div class="pin">
    <button class="play" id="play" aria-label="再生">▶</button>
    <div class="seek"><input type="range" id="seek" min="0" max="1000" value="0"></div>
    <div class="ptime" id="time">0:00 / 0:00</div>
    <button class="rate" id="rate">1.0×</button>
  </div>
  <div class="hint">文字をタップすると、そこから読み上げます。</div>
</div>
<audio id="au" src="narration.mp3" preload="metadata"></audio>
<script>
(function(){
  var TL = ${JSON.stringify(timeline.chunks.map((s) => ({ t: s.start, d: s.dur, s: s.sentence })))};
  var au = document.getElementById('au'), spans = [].slice.call(document.querySelectorAll('.s'));
  var play = document.getElementById('play'), seek = document.getElementById('seek');
  var timeEl = document.getElementById('time'), rateBtn = document.getElementById('rate');
  var cur = -1, RATES = [1, 1.25, 1.5, 0.75], ri = 0;

  function fmt(s){ s = Math.max(0, s|0); return (s/60|0) + ':' + ('0' + (s%60)).slice(-2); }
  // 現在時刻 → 文index（線形探索で十分な件数）。文の終わり〜次の文の開始（無音）は前の文を保持。
  function indexAt(t){
    var k = -1;
    for (var i = 0; i < TL.length; i++) { if (t >= TL[i].t) k = i; else break; }
    return k;
  }
  function paint(){
    var k = indexAt(au.currentTime);
    if (k === cur) return;
    cur = k;
    spans.forEach(function(el, i){
      el.classList.toggle('now', i === k);
      el.classList.toggle('read', i < k);
    });
    var el = spans[k];
    if (el) {
      var r = el.getBoundingClientRect();
      // 画面外に出たときだけ、読んでいる文が中央に来るようスクロール
      if (r.top < 70 || r.bottom > innerHeight - 130) {
        scrollTo({ top: scrollY + r.top - innerHeight * 0.4, behavior: 'smooth' });
      }
    }
  }
  function tick(){
    paint();
    if (au.duration) {
      seek.value = Math.round(au.currentTime / au.duration * 1000);
      timeEl.textContent = fmt(au.currentTime) + ' / ' + fmt(au.duration);
    }
    if (!au.paused) requestAnimationFrame(tick);
  }
  play.onclick = function(){ au.paused ? au.play() : au.pause(); };
  au.onplay = function(){ play.textContent = '❚❚'; document.body.classList.add('playing'); tick(); };
  au.onpause = function(){ play.textContent = '▶'; document.body.classList.remove('playing'); };
  au.onended = function(){ play.textContent = '▶'; };
  au.onloadedmetadata = function(){ timeEl.textContent = '0:00 / ' + fmt(au.duration); };
  seek.oninput = function(){ if (au.duration) { au.currentTime = seek.value / 1000 * au.duration; paint(); } };
  rateBtn.onclick = function(){ ri = (ri + 1) % RATES.length; au.playbackRate = RATES[ri];
                                rateBtn.textContent = RATES[ri].toFixed(2).replace(/0$/,'') + '×'; };
  spans.forEach(function(el, i){ el.onclick = function(){ au.currentTime = TL[i].t; paint(); au.play(); }; });

  var sa = document.getElementById('sampleAudio');
  [].slice.call(document.querySelectorAll('.vbtn')).forEach(function(b){
    b.onclick = function(){ au.pause(); sa.src = b.dataset.src; sa.play(); };
  });
})();
</script></body></html>`;
  fs.writeFileSync(path.join(OUT, "index.html"), html, "utf8");
  console.log("wrote " + path.join(OUT, "index.html"));

  const usd = (promptTok * 0.5 + audioTok * 10) / 1e6;
  console.log("COST 概算: 約" + (usd * 155).toFixed(1) + "円（text " + promptTok + "tok / audio " + audioTok + "tok）");
})().catch((e) => { console.error("ERROR:", e.message); process.exit(1); });
