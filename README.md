# meguru 自動SNS運用パイプライン

御朱印・参拝記録アプリ「meguru」のX / Bluesky / Threads自動運用システム。
一度セットアップすれば、投稿・画像生成・反応計測・週次分析・ネタ補充まで完全無人で回ります。

## 何が自動で動くか

| タイミング | 動作 |
|---|---|
| 平日20時・土日朝8時 | お題選択(祭事優先)→Claude APIで文面生成→豆知識カード画像生成→X/Bluesky/Threadsへ投稿 |
| 投稿の約6時間後 | いいね数チェック→しきい値超えの投稿にアプリ誘導のセルフリプ |
| 毎日13時 | 24時間経過した投稿の反応(表示・いいね等)をCSVに記録 |
| 毎週月曜 | 実績をClaudeが分析→翌週の文面生成に反映(学習ループ) |
| 毎月1日 | ネタDBに新しいお題を30件自動補充 |

宣伝投稿は10回に1回のみ。URLは本文に入れません(リーチ・コスト両面の対策)。

## セットアップ手順(初回のみ・約30〜60分)

### 1. GitHubリポジトリを作る
1. [github.com](https://github.com) にログイン → New repository
2. リポジトリ名: `meguru-auto` など。**Public**(公開)推奨
   - Threadsに画像を投稿するには公開リポジトリが必要です(画像の公開URLを使うため)
   - 非公開にする場合はThreadsがテキストのみ投稿になります
3. このフォルダの中身をすべてアップロード(GitHub Desktopか、Web画面の「uploading an existing file」でフォルダごとドラッグ)

### 2. Claude APIキーを取得
1. [platform.claude.com](https://platform.claude.com) でアカウント作成
2. 支払い設定をしてクレジットを購入(最低$5。この用途なら1年以上持ちます)
3. API Keys → Create Key → キーをコピー(後で使うのでメモ)

### 3. X APIの設定
1. [console.x.com](https://console.x.com) にXアカウントでログイン(電話番号認証が必要)
2. 従量課金(Pay-Per-Use)のクレジットを最低$5チャージ
3. アプリを作成し、以下の4つを発行してメモ:
   - API Key / API Key Secret
   - Access Token / Access Token Secret(**Read and Write権限**で発行すること)
4. コンソールで支出上限(Spending Limit)を月$3程度に設定しておくと安心

### 4. Blueskyの設定
1. [bsky.app](https://bsky.app) でアカウント作成(例: meguru-app.bsky.social)
2. 設定 → プライバシーとセキュリティ → アプリパスワード → 新規作成
3. ハンドル名とアプリパスワードをメモ

### 5. Threadsの設定(やや面倒。後回しでもOK)
1. Threadsアカウントを用意(Instagramアカウントに紐づく)
2. [developers.facebook.com](https://developers.facebook.com) でMeta開発者登録
3. アプリ作成 → ユースケースで「Threads API」を選択
4. `threads_basic` と `threads_content_publish` の権限で長期アクセストークンを発行
5. アクセストークンとThreadsユーザーIDをメモ
- 手順が複雑なので、まずXとBlueskyだけで始める場合は `config.yaml` の `threads: false` にしてください

### 6. GitHubにシークレット(APIキー)を登録
リポジトリの Settings → Secrets and variables → Actions → New repository secret で以下を登録:

| Secret名 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | 手順2のキー |
| `X_API_KEY` | 手順3のAPI Key |
| `X_API_SECRET` | 手順3のAPI Key Secret |
| `X_ACCESS_TOKEN` | 手順3のAccess Token |
| `X_ACCESS_SECRET` | 手順3のAccess Token Secret |
| `BSKY_HANDLE` | 手順4のハンドル(例: meguru-app.bsky.social) |
| `BSKY_APP_PASSWORD` | 手順4のアプリパスワード |
| `THREADS_ACCESS_TOKEN` | 手順5のトークン(使わないなら空でOK) |
| `THREADS_USER_ID` | 手順5のユーザーID(使わないなら空でOK) |

### 7. config.yaml を編集
- `app.ios_url` と `app.android_url` を実際のストアURLに変更
- 使わないプラットフォームは `platforms` で false に

### 8. テスト実行
1. リポジトリの Actions タブ → 「daily-post」 → 「Run workflow」で手動実行
2. 数分待って、X / Bluesky / Threads に投稿されていれば成功
3. 失敗した場合はログが表示されるので、エラー箇所を確認(だいたいはシークレットの登録ミス)

以上で完了。以後は放置で毎日動きます。

## 失敗時の通知

GitHub → 自分のアイコン → Settings → Notifications → Actions で
「Failed workflows only」をオンにすると、投稿失敗時だけメールが届きます。

## 日々の運用(ほぼゼロ)

- **やること**: Xアプリでリプ・DMが来たら返信するだけ
- **見たいとき**: `data/metrics.csv`(全投稿の成績)と `data/insights.md`(週次の自動分析メモ)
- **調整したいとき**: `config.yaml` を編集(投稿しきい値、宣伝頻度、ハッシュタグなど)

## 月額コスト目安

| 項目 | 金額 |
|---|---|
| Claude API(文面生成+週次分析+月次補充) | 〜30円 |
| X API(投稿30件+計測+セルフリプ数件) | 〜100円 |
| Bluesky / Threads API | 0円 |
| GitHub Actions | 0円(無料枠内) |
| **合計** | **月150円前後** |

※初回チャージとしてClaude $5+X $5(計約1,600円)が必要ですが、数ヶ月〜1年分の前払いに相当します。

## よくあるトラブル

- **402 CreditsDepleted(X)**: Xのクレジット切れ。console.x.comでチャージ
- **投稿が140字を超えてエラー**: まれに生成が長くなる場合あり。再実行(Run workflow)でOK
- **Threadsだけ失敗する**: トークンの有効期限(60日)切れの可能性。再発行して登録し直し
- **時間になっても動かない**: GitHub Actionsのcronは数分〜数十分遅れることがあります(仕様)

## ファイル構成

```
├── config.yaml            # 全設定(ここだけ触ればOK)
├── requirements.txt
├── data/
│   ├── neta_db.json       # お題DB(100件・毎月自動補充)
│   ├── seasonal_calendar.json  # 祭事カレンダー(34件)
│   ├── state.json         # 投稿履歴などの状態(自動生成)
│   ├── metrics.csv        # 反応データ(自動生成)
│   └── insights.md        # 週次分析メモ(自動生成)
├── scripts/
│   ├── generate_post.py   # お題選択+文面生成
│   ├── card.py            # 豆知識カード画像生成(デザイン案A)
│   ├── post_all.py        # 3プラットフォーム同時投稿
│   ├── self_reply.py      # セルフリプ
│   ├── collect_metrics.py # 反応計測
│   ├── weekly_review.py   # 週次分析
│   └── refill_db.py       # ネタDB補充
└── .github/workflows/     # 自動実行スケジュール(5本)
```
