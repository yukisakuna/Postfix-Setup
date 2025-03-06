#!/usr/bin/env python3
import subprocess
import os
import time
import sys

if os.geteuid() != 0:
    print("[ERROR] rootユーザーとして実行してください。")
    sys.exit(1)

def run(cmd):
    print(f"+ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[ERROR] コマンドが失敗しました: {cmd}")
        exit(1)

DOMAIN = input("使用するドメインを入力してください:")
MAILHOST = f"mail.{DOMAIN}"


def install_packages():
    run("apt update")
    run("DEBIAN_FRONTEND=noninteractive apt install -y postfix opendkim opendkim-tools mailutils certbot")


def setup_ssl():
    run(f"certbot certonly --standalone -d {MAILHOST} --non-interactive --agree-tos --register-unsafely-without-email")


def setup_postfix():
    # main.cf の内容
    postfix_config = f"""
myhostname = {MAILHOST}
mydomain = {DOMAIN}
myorigin = $mydomain
inet_interfaces = all
inet_protocols = ipv4

mydestination =
local_recipient_maps =
local_transport = error:local delivery is disabled

# TLS設定
smtpd_tls_cert_file = /etc/letsencrypt/live/{MAILHOST}/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/{MAILHOST}/privkey.pem
smtp_tls_security_level = may
smtpd_tls_security_level = may
smtpd_use_tls = yes

# Milter(OpenDKIM)
milter_default_action = accept
milter_protocol = 6
smtpd_milters = unix:/var/spool/postfix/opendkim/opendkim.sock
non_smtpd_milters = unix:/var/spool/postfix/opendkim/opendkim.sock

# 送信元アドレス変換
sender_canonical_maps = hash:/etc/postfix/sender_canonical
"""
    with open("/tmp/main.cf", "w") as f:
        f.write(postfix_config)
    run("mv /tmp/main.cf /etc/postfix/main.cf")

    canonical_map = f"@{MAILHOST} noreply@{DOMAIN}\n"
    with open("/tmp/sender_canonical", "w") as f:
        f.write(canonical_map)
    run("mv /tmp/sender_canonical /etc/postfix/sender_canonical")
    run("postmap /etc/postfix/sender_canonical")


def setup_opendkim():
    run(f"mkdir -p /etc/opendkim/keys/{DOMAIN}")
    run(f"opendkim-genkey -b 2048 -d {DOMAIN} -s default -D /etc/opendkim/keys/{DOMAIN}")
    run("chown -R opendkim:opendkim /etc/opendkim")

    # /etc/opendkim.conf
    opendkim_conf = f"""
Syslog                  yes
UMask                   007
Mode                    sv
AutoRestart             yes
AutoRestartRate         10/1h
Canonicalization        relaxed/simple
Socket                  local:/var/spool/postfix/opendkim/opendkim.sock
PidFile                 /run/opendkim/opendkim.pid
Domain                  {DOMAIN}
Selector                default
KeyFile                 /etc/opendkim/keys/{DOMAIN}/default.private
SigningTable            refile:/etc/opendkim/SigningTable
KeyTable                refile:/etc/opendkim/KeyTable
ExternalIgnoreList      refile:/etc/opendkim/TrustedHosts
InternalHosts           refile:/etc/opendkim/TrustedHosts
"""
    with open("/tmp/opendkim.conf", "w") as f:
        f.write(opendkim_conf)
    run("mv /tmp/opendkim.conf /etc/opendkim.conf")

    # SigningTable
    signing_table = f"*@{DOMAIN} default._domainkey.{DOMAIN}\n"
    with open("/tmp/SigningTable", "w") as f:
        f.write(signing_table)
    run("mv /tmp/SigningTable /etc/opendkim/SigningTable")

    # KeyTable
    key_table = f"default._domainkey.{DOMAIN} {DOMAIN}:default:/etc/opendkim/keys/{DOMAIN}/default.private\n"
    with open("/tmp/KeyTable", "w") as f:
        f.write(key_table)
    run("mv /tmp/KeyTable /etc/opendkim/KeyTable")

    # TrustedHosts
    trusted_hosts = f"127.0.0.1\nlocalhost\n{DOMAIN}\n{MAILHOST}\n"
    with open("/tmp/TrustedHosts", "w") as f:
        f.write(trusted_hosts)
    run("mv /tmp/TrustedHosts /etc/opendkim/TrustedHosts")


def setup_systemd():
    run("mkdir -p /etc/systemd/system/opendkim.service.d")
    override = """
[Service]
# root で起動しないと、ExecStartPost 内の chown が権限不足で失敗する
User=root
Group=root

ExecStart=
ExecStart=/usr/sbin/opendkim -x /etc/opendkim.conf

# OpenDKIM起動完了後にソケットファイルのパーミッションを修正
ExecStartPost=/bin/bash -c 'sleep 1 && chown opendkim:postfix /var/spool/postfix/opendkim/opendkim.sock && chmod 660 /var/spool/postfix/opendkim/opendkim.sock'
"""
    with open("/tmp/override.conf", "w") as f:
        f.write(override)
    run("mv /tmp/override.conf /etc/systemd/system/opendkim.service.d/override.conf")

    run("mkdir -p /etc/systemd/system/postfix.service.d")
    postfix_override = """
[Unit]
Requires=opendkim.service
After=opendkim.service
"""
    with open("/tmp/postfix_override.conf", "w") as f:
        f.write(postfix_override)
    run("mv /tmp/postfix_override.conf /etc/systemd/system/postfix.service.d/override.conf")


def restart_services():

    run("systemctl daemon-reload")

    run("systemctl stop postfix opendkim")

    run("mkdir -p /var/spool/postfix/opendkim")
    run("chown opendkim:postfix /var/spool/postfix/opendkim")
    run("chmod 770 /var/spool/postfix/opendkim")

    run("rm -f /var/spool/postfix/opendkim/opendkim.sock /run/opendkim/opendkim.pid")

    run("systemctl start opendkim")
    time.sleep(2)

    run("systemctl start postfix")

#cleanup変えないとdkimできない
def fix_cleanup_master_cf():
    target_line_fields = ["cleanup", "unix", "n", "-", "y", "-", "0", "cleanup"]

    with open("/etc/postfix/master.cf", "r") as f:
        lines = f.readlines()

    replaced = False
    new_lines = []

    for line in lines:
        fields = line.split()
        if len(fields) == 8 and fields == target_line_fields:
            # 置き換え
            fields[4] = "n"
            new_line = " ".join(fields) + "\n"
            new_lines.append(new_line)
            replaced = True
        else:
            new_lines.append(line)

    if replaced:
        with open("/tmp/master.cf", "w") as f:
            f.writelines(new_lines)
        run("mv /tmp/master.cf /etc/postfix/master.cf")
        run("systemctl daemon-reload")
        run("systemctl restart postfix")
        run("chown root:root /etc/opendkim")
        run("chmod 750 /etc/opendkim")
        run("chown -R root:root /etc/opendkim/keys")
        run("chmod 750 /etc/opendkim/keys")
        run(f"chmod 600 /etc/opendkim/keys/{DOMAIN}/default.private")
        print("master.cf の cleanup 行を書き換えました。")
    else:
        print("master.cf に書き換え対象の行は見つかりませんでした。変更は行いません。")

def main():
    install_packages()
    setup_ssl()
    setup_postfix()
    setup_opendkim()
    setup_systemd()
    fix_cleanup_master_cf()
    restart_services()



    print("\n===== DKIM Public key=====\n")
    run(f"cat /etc/opendkim/keys/{DOMAIN}/default.txt")

if __name__ == "__main__":
    main()
