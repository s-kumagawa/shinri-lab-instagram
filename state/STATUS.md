# 運用ステータス

- **2026-11-09：自動運用を開始**
  - 初回投稿：2026-11-09 07:12 JST「人に好かれる心理学5選」（カルーセル）https://www.instagram.com/p/DffzSGQFEdJ/
  - 開始時点：フォロワー 11 / 投稿 0（`config.json` の baseline）
  - API：graph.facebook.com、システムユーザー `shinri-lab-bot` のトークン（60日、期限 2027-01-07）
  - Instagram アカウント ID は `config.json` の `ig_user_id` を直接使う（`me/assigned_instagram_accounts` は空で返るため）
- 経緯：2026-11-07 にビジネスポートフォリオが「自動化」を理由に制限 → 審査で解除 → システムユーザーを作り直し。
  **Meta の管理画面をブラウザの自動操作で触らないこと**（再び制限される恐れがある）。
