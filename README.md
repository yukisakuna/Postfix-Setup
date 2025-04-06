# Postfix-Setup

## 何ができるの？

- Postfix と OpenDKIM を勝手にインストールしてくる
- SSL/TLS 証明書を自動で取ってくる
- DKIM 署名の設定

## 使い方

最初にレコードを設定してください.
```
@	IN	A サーバーのip
mail	IN	A サーバーのip
@	IN	MX mail.ドメイン
@  IN TXT v=spf1 ip4:{ip} -all
_dmarc  IN TXT v=DMARC1; p=none;
```
1. スクリプトをダウンロード
2. root 権限で実行
   ```
   sudo python3 setup.py
   ```
3. ドメイン名を入力
4. DKIM Public KeyをTXTレコードで追加
5. テストメール送ってみてね
   ```
   echo "testmail" | mail -s "testmail" -a "From: noreply@ドメイン" 送信先アドレス
   ```

## 必要なもの

- Debian/Ubuntu系
- 25番ポートアウトバウンドが使えること
## 注意点

- root権限が必要
- すみません、コードはAIです、、でもコマンドとかはAI使ってないので！？！？

