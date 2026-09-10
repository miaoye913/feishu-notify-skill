#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_send.py — 飞书通知发送（零依赖，仅标准库 REST）

用法:
  python feishu_send.py "任务跑完了" [-t 标题] [--to <open_id>] [--dry-run]

配置（同目录 feishu.env，或环境变量）:
  FEISHU_APP_ID / FEISHU_APP_SECRET   开发者后台 → 凭证与基础信息
  FEISHU_USER_OPEN_ID                 你的 open_id（feishu_whoami.py 可自动获取）

与微信通道的差异: 飞书无 24h/10 条保活窗口，可随时主动推送。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://open.feishu.cn/open-apis"


def load_env():
    cfg = {}
    ef = os.path.join(BASE, "feishu.env")
    if os.path.isfile(ef):
        try:
            with open(ef, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip()
        except Exception:
            pass
    for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_USER_OPEN_ID"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def http_json(url, body=None, headers=None, method="POST"):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    h = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"code": e.code, "msg": e.reason}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


def main():
    ap = argparse.ArgumentParser(description="飞书通知发送")
    ap.add_argument("content", help="消息内容（必填）")
    ap.add_argument("-t", "--title", default=None, help="标题（会拼在内容前）")
    ap.add_argument("--to", default=None, help="接收者 open_id（默认读 feishu.env）")
    ap.add_argument("--tag", default=None, help="消息前缀标签（如 通知/对话），用于区分模式")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = load_env()
    app_id, app_secret = cfg.get("FEISHU_APP_ID", ""), cfg.get("FEISHU_APP_SECRET", "")
    open_id = a.to or cfg.get("FEISHU_USER_OPEN_ID", "")
    if not app_id or not app_secret:
        sys.stderr.write(f"缺少凭证：请在 {os.path.join(BASE, 'feishu.env')} 填 FEISHU_APP_ID / FEISHU_APP_SECRET\n")
        return 2
    if not open_id:
        sys.stderr.write("缺少 open_id：先运行 python feishu_whoami.py 自动获取，或用 --to 指定\n")
        return 2

    text = f"{a.title}\n{a.content}" if a.title else a.content
    if a.tag:
        text = f"[{a.tag}] {text}"
    if a.dry_run:
        print(f"[DryRun] 将向 open_id={open_id[:10]}*** 发送: {text}")
        return 0

    tok = http_json(f"{API}/auth/v3/tenant_access_token/internal",
                    {"app_id": app_id, "app_secret": app_secret})
    if tok.get("code") != 0:
        sys.stderr.write(f"获取 tenant_access_token 失败: {tok}\n")
        return 1
    resp = http_json(f"{API}/im/v1/messages?receive_id_type=open_id",
                     {"receive_id": open_id, "msg_type": "text",
                      "content": json.dumps({"text": text}, ensure_ascii=False)},
                     headers={"Authorization": f"Bearer {tok['tenant_access_token']}"})
    if resp.get("code") == 0:
        print(f"OK: 飞书消息已发送 (message_id={resp.get('data', {}).get('message_id')})")
        return 0
    sys.stderr.write(f"FAIL: code={resp.get('code')} msg={resp.get('msg')}\n")
    return 1


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
