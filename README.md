# Postfix-Setup

## できること

- Postfix と OpenDKIM を勝手にインストールしてくれる
- Let's Encrypt から SSL/TLS 証明書を自動で取ってくる
- DKIM 署名の設定を全部やってくれる
- 細かい設定も勝手に最適化

## 使い方

1. スクリプトをダウンロード
2. root 権限で実行（sudo 忘れずに！）
   ```
   sudo ./setup.py
   ```
3. ドメイン名を入力
4. DKIM Public KeyをTXTレコードで追加
5. テストメール送ってみよ-
   ```
   echo "testmail" | mail -s "testmail" -a "From: noreply@ドメイン" 送信先アドレス
   ```

## 必要なもの

- Debian/Ubuntu系
## 注意点

- root 権限いる

