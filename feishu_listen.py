#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_listen.py — 飞书消息监听（长连接，无需公网 IP）

与微信通道的 wxlisten.py 对应，但飞书无 24h/10 条保活窗口。

用法:
  python feishu_listen.py --wait [--timeout 180]   # 提问等待模式：收到一条消息即落盘并退出(exit 0)
  python feishu_listen.py --listen                 # 常驻模式：持续落盘到 inbox/
  python feishu_listen.py --check                  # 仅自检凭证与长连接可用性

消息落盘: inbox/feishu_YYYYmmdd_HHMMSS_xxxx.txt（含发送者 open_id）
依赖: python -m pip install lark-oapi
配置: 同目录 feishu.env（FEISHU_APP_ID / FEISHU_APP_SECRET）
"""
import argparse
import json
import os
import sys
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(BASE, "feishu.env")
INBOX = os.path.join(BASE, "inbox")
HEARTBEAT = os.path.join(INBOX, ".listener.heartbeat")


def touch_heartbeat():
    """刷新监听心跳，供 feishu_chat.py --status 判断监听是否在运行"""
    os.makedirs(INBOX, exist_ok=True)
    try:
        with open(HEARTBEAT, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()} {time.time()}")
    except Exception:
        pass


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


def save_inbox(text, open_id, chat_type):
    os.makedirs(INBOX, exist_ok=True)
    fn = os.path.join(INBOX, time.strftime("feishu_%Y%m%d_%H%M%S") + f"_{abs(hash(text)) % 10000}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"来源: 飞书\n渠道类型: {chat_type}\n发送者 open_id: {open_id}\n内容: {text}\n")
    return fn


def main():
    ap = argparse.ArgumentParser(description="飞书消息监听")
    ap.add_argument("--wait", action="store_true", help="收到一条消息即退出")
    ap.add_argument("--listen", action="store_true", help="常驻监听")
    ap.add_argument("--check", action="store_true", help="仅自检")
    ap.add_argument("--timeout", type=int, default=180, help="--wait 模式超时秒数")
    a = ap.parse_args()

    cfg = load_env()
    app_id, app_secret = cfg.get("FEISHU_APP_ID", ""), cfg.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret or "xxxx" in app_id:
        print(f"[FAIL] 请先在 {ENV} 中填写 FEISHU_APP_ID / FEISHU_APP_SECRET")
        return 2

    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1  # noqa: F401
    except Exception as e:
        print(f"[FAIL] 缺少 lark-oapi: {e}\n  请运行: python -m pip install lark-oapi")
        return 2

    if a.check:
        print(f"[OK] 凭证已配置 App ID = {app_id[:10]}***")
        print("[OK] lark-oapi 可用；运行 --wait 或 --listen 即可开始监听")
        return 0

    touch_heartbeat()

    def _heartbeat_loop():
        while True:
            time.sleep(30)
            touch_heartbeat()

    threading.Thread(target=_heartbeat_loop, daemon=True).start()

    def on_message(data) -> None:
        try:
            msg = data.event.message
            open_id = data.event.sender.sender_id.open_id
            text = ""
            if msg.message_type == "text":
                try:
                    text = json.loads(msg.content).get("text", "")
                except Exception:
                    text = msg.content or ""
            touch_heartbeat()
            fn = save_inbox(text, open_id, msg.chat_type)
            print(f"[新消息] {text}\n  已存: {fn}", flush=True)
            if a.wait:
                os._exit(0)
        except Exception as e:  # noqa: BLE001
            print(f"[err] 处理消息异常: {e}", flush=True)
            if a.wait:
                os._exit(1)

    handler = (lark.EventDispatcherHandler.builder("", "")
               .register_p2_im_message_receive_v1(on_message)
               .build())
    client = lark.ws.Client(app_id, app_secret, event_handler=handler, log_level=lark.LogLevel.WARNING)

    if a.wait:
        print(f"[feishu-wait] 监听中（{a.timeout} 秒超时，收到消息即退出）…", flush=True)
        threading.Timer(a.timeout, lambda: (print("[feishu-wait] 超时，未收到消息", flush=True), os._exit(2))).start()
    else:
        print("[feishu-listen] 常驻监听中（Ctrl+C 退出）…", flush=True)
    client.start()
    return 0


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main() or 0)
