// ⚠️ このファイルは【本番では使われていない】参考実装です。
//
// 正本は Cloud Function:
//   marutto-study/functions/src/tsudumonLpChat.ts（HTTPハンドラ）
//   marutto-study/functions/src/tsudumonLpChatCore.ts（プロンプト・上限・整形の純ロジック）
//
// 2026-07-25、つづもんを chatstudy.jp のVercelプロキシから切り離して独自ドメイン
// （tsudumon.jp / Firebase Hosting 直配信）へ移行した際に移設した。
// Firebase Hosting は静的配信専用でサーバー関数を持てないため、Vercel Serverless Function
// のままでは /api/chat が動かせなかったのが理由。
// 現在 https://tsudumon.jp/api/chat は firebase.json の rewrite で Cloud Function に届く。
//
// プロンプトや上限を変えるときは Cloud Function 側を編集すること。
// （このファイルは移行前の挙動を確認するための記録として残している）
//
// ── 以下、移行前の Vercel Serverless Function 版 ──────────────────
//
// つづもんLP チャットボットAPI（Vercel Serverless Function）
//
// デプロイ: LPディレクトリ（pdf-workbook/lp）をVercelプロジェクトのルートにすると
//           /api/chat がこのファイルで応答する。
// 必要な環境変数:
//   GEMINI_API_KEY        … Google AI Studio のAPIキー（必須）
//   CHAT_DAILY_LIMIT      … 全体の1日あたりAI応答回数上限（省略時 300）
//   CHAT_USER_DAILY_LIMIT … 1人（IP＋ブラウザID）あたりの1日上限（省略時 15）
//
// コスト設計（ここで全部ガードする）:
//   - モデルは gemini-2.5-flash-lite（$0.10/M入力・$0.40/M出力）。1応答 ≒ 0.05円
//   - maxOutputTokens 400 / 履歴は直近8メッセージのみ / 1リクエスト300文字まで
//   - 全体で1日 CHAT_DAILY_LIMIT 回まで（超えたらFAQとLINEへ丁寧に誘導）
//   - クライアント側でも 1セッション10回まで。定番質問チップのみローカルFAQで即答（自由入力は原則AI）
//   ※ サーバーレスはインスタンスが分かれるため日次カウンタは目安。厳密にしたい場合は
//     Upstash Redis 等に置き換える（COUNTER部分を差し替えるだけ）。

const MODEL = 'gemini-2.5-flash-lite';
const MAX_OUTPUT_TOKENS = 400;
const MAX_HISTORY = 8;
const MAX_CHARS_PER_MSG = 300;

const SYSTEM_PROMPT = `
あなたは中学歴史のWeb教材「つづもん」の相談窓口です。名乗るときは「つづもん相談チャット」。

## 一番大事な姿勢
- 営業マンではありません。保護者や中学生の疑問・不安に寄り添って解消するのが役目です。
- 売り込み・煽り・「今だけ」等の表現は禁止。購入を急かさない。
- 相手が迷いを口にしたとき（「うちの子に合うかな」「買おうか迷う」等）だけ、
  「まず無料体験で確かめてからで大丈夫ですよ」と、そっと一歩だけ背中を押す。
- 分からないこと・ここに書かれていないことは、正直に「わかりかねます」と伝えて
  公式LINE（https://lin.ee/XGIhuYi）での問い合わせを案内する。絶対に作り話をしない。
- 回答は日本語で、3〜6文程度。やわらかい敬語。相手の気持ちへの共感を先に。

## 商品の事実（この範囲だけ答えてよい）
- 商品名: つづもん（中学歴史のWeb教材＝問題集＋参考書、スマホ等のブラウザで開くレッスン形式）。“日本一つづけやすい”を目指す教材
- 価格: 月額1,280円（税込）の定額制、1プランのみ（学年の区別なし・中1〜中3の歴史 全19単元すべて込み）
- 提供形態: PDFダウンロード販売ではなく、Web教材（レッスンプレイヤー）を直接ブラウザで利用する形。紙で解きたい場合はWeb画面からブラウザ印刷ができる（無料）
- 契約中は全19単元＋公式LINEの問題演習・AI採点・AI先生への質問・学習記録がすべて追加料金なしで使い放題
- 解約: 月額サブスクリプションなので、いつでも解約可能。次回請求日より前に解約すれば以降の課金は発生しない
- 紙面（画面）の内容: 穴埋め年表 / 要点まとめ / 一問一答 / 4択実戦問題 / 記述問題 / 写真つき資料問題 / 読みがなつき解答
- 使い方: スマホ・タブレット・PCのブラウザでWeb教材を開いて解く。画面上のQRコードや導線から
  公式LINEでAIがその場で丸つけ・解説（記述問題も採点）。LINEだけで解くこともできる
- 続く仕組み: すぐ丸がつく / 1単元15分 / 正答率・レベル・連続正解の記録 / まちがえた問題の自動再出題
- 無料体験: 3日間、全19単元（参考書＋問題集）をまるごと無料で試せる。期限後も「律令国家と奈良時代」の1単元はずっと無料。体験開始は教材ページの「3日間ぜんぶ無料で試す」ボタンから（公式LINE https://lin.ee/XGIhuYi でログインするだけ）
- 対象: 中学1〜3年生。学年をまたぐ復習・先取りOK。教科書を問わず定期テスト・実力テスト対策に使える
- 利用開始: お申し込み・決済確認後、公式LINE経由でWeb教材の利用を有効化（即時〜24時間以内）
- ロードマップ（予定）: 今後、社会・英語・理科・数学を順次追加予定
- 販売: ぐっとスクール（つづもん開発者・石本大貴、塾講師・家庭教師歴10年）。現在は歴史のみ販売
- AIとのやり取りは担当者も定期的に確認している

## 答えられない・答えてはいけないもの
- 返金や個別のトラブル対応、決済の詳細 → 公式LINEへ案内
- 歴史の学習内容そのものの長い解説（それは教材の役目）→ 簡潔に触れる程度は可
- つづもんと無関係の話題 → やわらかく本題に戻す
`.trim();

// 簡易日次カウンタ（インスタンス単位の目安。厳密にするならUpstash等へ）
// total = 全体、perUser = 「IP｜ブラウザID」ごと。日付（JST）が変わるとリセット。
let counters = { date: '', total: 0, perUser: new Map() };

function jstToday() {
  return new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

function clientKey(req) {
  const fwd = req.headers['x-forwarded-for'];
  const ip = (typeof fwd === 'string' && fwd.split(',')[0].trim()) || req.socket?.remoteAddress || 'unknown';
  const uid = typeof (req.body && req.body.uid) === 'string' ? req.body.uid.slice(0, 40) : '';
  return ip + '|' + uid;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'method not allowed' });
    return;
  }
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    res.status(500).json({ reply: 'ただいまチャットを準備中です。お手数ですが公式LINEでご質問ください。 https://lin.ee/XGIhuYi' });
    return;
  }

  // 日次上限（JSTで日付が変わるとリセット）
  const today = jstToday();
  if (counters.date !== today) counters = { date: today, total: 0, perUser: new Map() };

  // 全体上限（サービス全体のコスト上限）
  const dailyLimit = parseInt(process.env.CHAT_DAILY_LIMIT || '300', 10);
  if (counters.total >= dailyLimit) {
    res.status(200).json({ reply: '申し訳ありません、本日のチャット対応が上限に達しました。よくある質問はページ下部のFAQに、その他は公式LINEでお答えできます。 https://lin.ee/XGIhuYi' });
    return;
  }

  // 1人あたりの上限（IP＋ブラウザID単位）
  const userLimit = parseInt(process.env.CHAT_USER_DAILY_LIMIT || '15', 10);
  const key = clientKey(req);
  if ((counters.perUser.get(key) || 0) >= userLimit) {
    res.status(200).json({ reply: '本日のチャットのご利用上限に達しました。また明日お使いいただけます。\nお急ぎのご質問や無料体験は、公式LINEでどうぞ。 https://lin.ee/XGIhuYi' });
    return;
  }

  // 入力の検証と切り詰め
  let messages = Array.isArray(req.body && req.body.messages) ? req.body.messages : [];
  messages = messages
    .filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
    .slice(-MAX_HISTORY)
    .map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content.slice(0, MAX_CHARS_PER_MSG) }] }));
  if (!messages.length || messages[messages.length - 1].role !== 'user') {
    res.status(400).json({ error: 'bad request' });
    return;
  }

  try {
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
        contents: messages,
        generationConfig: { maxOutputTokens: MAX_OUTPUT_TOKENS, temperature: 0.6 },
      }),
    });
    if (!r.ok) throw new Error('gemini ' + r.status);
    const data = await r.json();
    const reply = data?.candidates?.[0]?.content?.parts?.map(p => p.text).join('')
      || 'すみません、うまく答えられませんでした。公式LINEでもご質問いただけます。 https://lin.ee/XGIhuYi';
    counters.total++;
    counters.perUser.set(key, (counters.perUser.get(key) || 0) + 1);
    if (counters.perUser.size > 5000) counters.perUser.clear(); // メモリ保護（日内リセットの保険）
    res.status(200).json({ reply });
  } catch (e) {
    res.status(200).json({ reply: 'すみません、いま回答の生成に失敗しました。少し時間をおいて試すか、公式LINEでご質問ください。 https://lin.ee/XGIhuYi' });
  }
}
