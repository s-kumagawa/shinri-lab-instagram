# 運用ステータス

- **2026-11-07：自動投稿は一時停止中**（定期タスク「しんりラボ 毎日の投稿とインサイト改善」を無効化済み）
  - 理由：Meta の一時的な操作制限で、Instagram アカウントをビジネスポートフォリオ（システムユーザー）に割り当てられない。
  - 次の予定：オーナーが Facebook ページ経由で Instagram を連携し、トークンを再発行する。
  - 再開の条件：新しいトークンを graph.facebook.com 用に保存し、`python3 tools/ig_api.py whoami` で
    心理学アカウントが取得できることを確認してから、定期タスクを有効に戻す。
  - `tools/ig_api.py` は Facebook ページ経由の連携（`me/accounts` → `instagram_business_account`）にも対応済み。
