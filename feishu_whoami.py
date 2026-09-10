#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_whoami.py — 飞书接入自检 + 自动获取你的 open_id

前置:
  1) 依赖官方 SDK: python -m pip install lark-oapi
  2) 同目录 feishu.env 中填好 FEISHU_APP_ID / FEISHU_APP_SECRET
     （open.feishu.cn 开发者后台 → 你的应用 → 凭证与基础信息）

用法:
  python feishu_whoami.py [--timeout 120]
  → 启动长连接监听（无需公网 IP）→ 你在飞书里给机器人发一条消息
  → 脚本抓取你的 open_id 写入 feishu.env，并用 REST API 回一条确认消息
"""
import argparse
import json
import os
import sys
import threading
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(BASE, "feishu.env")
API = "https://open.feishu.cn/open-apis"


def load_env():
    cfg = {}
    if os.path.isfile(ENV):
        with open(ENV, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def save_open_id(open_id):
    lines, found = [], False
    if os.path.isfile(ENV):
        with open(ENV, encoding="utf-8") as f:
            lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("FEISHU_USER_OPEN_ID="):
            lines[i] = f"FEISHU_USER_OPEN_ID={open_id}"
            found = True
    if not found:
        lines.append(f"FEISHU_USER_OPEN_ID={open_id}")
    with open(ENV, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


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


def tenant_token(app_id, app_secret):
    resp = http_json(f"{API}/auth/v3/tenant_access_token/internal",
                     {"app_id": app_id, "app_secret": app_secret})
    if resp.get("code") == 0:
        return resp.get("tenant_access_token"), None
    return None, f"获取 tenant_access_token 失败: {resp}"


def send_text(app_id, app_secret, open_id, text):
    token, err = tenant_token(app_id, app_secret)
    if err:
        return False, err
    resp = http_json(f"{API}/im/v1/messages?receive_id_type=open_id",
                     {"receive_id": open_id, "msg_type": "text",
                      "content": json.dumps({"text": text}, ensure_ascii=False)},
                     headers={"Authorization": f"Bearer {token}"})
    return resp.get("code") == 0, resp


def main():
    ap = argparse.ArgumentParser(description="飞书自检并获取 open_id")
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()

    cfg = load_env()
    app_id, app_secret = cfg.get("FEISHU_APP_ID", ""), cfg.get("FEISHU_APP_SECRET", "")
    print("== 飞书接入自检 ==")
    if not app_id or not app_secret or "xxxx" in app_id:
        print(f"[FAIL] 请先在 {ENV} 中填写 FEISHU_APP_ID 与 FEISHU_APP_SECRET")
        return 2
    print(f"[1/3] 凭证检查  App ID = {app_id[:10]}***")
    token, err = tenant_token(app_id, app_secret)
    if err:
        print(f"[FAIL] {err}")
        return 1
    print("[2/3] tenant_access_token 获取 OK（凭证有效）")

    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
    except Exception as e:
        print(f"[FAIL] 缺少 lark-oapi: {e}\n  请运行: python -m pip install lark-oapi")
        return 2

    def on_message(data: "P2ImMessageReceiveV1") -> None:
        try:
            msg = data.event.message
            sender = data.event.sender
            open_id = sender.sender_id.open_id
            text = ""
            if msg.message_type == "text":
                try:
                    text = json.loads(msg.content).get("text", "")
                except Exception:
                    text = msg.content or ""
            print(f"[收到消息] open_id={open_id} chat_type={msg.chat_type} text={text!r}")
            save_open_id(open_id)
            print(f"[3/3] 已写入 {ENV}  ->  FEISHU_USER_OPEN_ID={open_id}")
            ok, resp = send_text(app_id, app_secret, open_id,
                                 "✅ 接入成功：我已收到你的消息，并记住了你的 open_id。飞书通道双向可用。")
            print(f"[回发测试] {'成功' if ok else '失败'} {resp.get('msg') if isinstance(resp, dict) else resp}")
            os._exit(0 if ok else 1)
        except Exception as e:  # noqa: BLE001
            print(f"[err] 处理消息异常: {e}")
            os._exit(1)

    handler = (lark.EventDispatcherHandler.builder("", "")
               .register_p2_im_message_receive_v1(on_message)
               .build())
    client = lark.ws.Client(app_id, app_secret, event_handler=handler, log_level=lark.LogLevel.INFO)

    print(f"[3/3] 长连接已启动，等待你在飞书里给机器人发消息（{a.timeout} 秒超时）…")
    threading.Timer(a.timeout, lambda: (print("[超时] 未收到消息，请确认：应用已发布、可用范围含你、已订阅 im.message.receive_v1 事件"), os._exit(2))).start()
    client.start()
    return 0


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main() or 0)
