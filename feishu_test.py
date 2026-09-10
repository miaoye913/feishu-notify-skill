#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_test.py — 飞书通知链路测试例程（独立于微信工程）

运行: python feishu_test.py [--timeout 120]
步骤:
  1) 配置检查   (feishu.env: App ID / App Secret / 你的 open_id)
  2) 凭证校验   (tenant_access_token)
  3) 发送测试   (发一条消息到你的飞书)
  4) 回环验证   (长连接等待你在飞书回复 ok，收到即通过)

退出码: 0 全部通过 / 1 有失败 / 2 缺配置
"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://open.feishu.cn/open-apis"
ENV = os.path.join(BASE, "feishu.env")
PASS_N, FAIL_N = 0, 0


def log(ok, msg):
    global PASS_N, FAIL_N
    if ok:
        PASS_N += 1
        print(f"  [PASS] {msg}", flush=True)
    else:
        FAIL_N += 1
        print(f"  [FAIL] {msg}", flush=True)
    return ok


def summary_and_exit(code):
    print(f"== 汇总: {PASS_N} PASS / {FAIL_N} FAIL ==", flush=True)
    os._exit(code)


def http(body=None, url=None, headers=None, timeout=20):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    h = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"code": e.code, "msg": e.reason}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


def load_env():
    cfg = {}
    if os.path.isfile(ENV):
        with open(ENV, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_USER_OPEN_ID"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def main():
    timeout = 120
    if len(sys.argv) > 1 and sys.argv[1] == "--timeout" and len(sys.argv) > 2:
        try:
            timeout = int(sys.argv[2])
        except Exception:
            pass

    print("== 飞书通知链路测试例程 ==", flush=True)
    print("[1/4] 配置检查", flush=True)
    cfg = load_env()
    app_id = cfg.get("FEISHU_APP_ID", "")
    app_secret = cfg.get("FEISHU_APP_SECRET", "")
    open_id = cfg.get("FEISHU_USER_OPEN_ID", "")
    log(bool(app_id and app_secret and "xxxx" not in app_id),
        f"feishu.env 凭证已配置 (App ID {app_id[:10]}***)" if app_id else "feishu.env 缺少 App ID/Secret")
    log(bool(open_id), f"open_id 已记录 ({open_id[:12]}***)" if open_id else "open_id 缺失（运行 feishu_whoami.py 获取）")
    if not (app_id and app_secret):
        print("请先在 feishu.env 中配置凭证", flush=True)
        summary_and_exit(2)

    print("[2/4] 凭证校验", flush=True)
    tok = http({"app_id": app_id, "app_secret": app_secret},
               url=f"{API}/auth/v3/tenant_access_token/internal")
    token = tok.get("tenant_access_token")
    log(bool(token), f"tenant_access_token 获取 ({tok.get('msg') if not token else 'OK'})")
    if not token:
        summary_and_exit(1)

    print("[3/4] 发送测试消息", flush=True)
    if open_id:
        resp = http({"receive_id": open_id, "msg_type": "text",
                     "content": json.dumps({"text": "【feishu_test】发送链路测试——看到这条消息请在飞书回复 ok"}, ensure_ascii=False)},
                    url=f"{API}/im/v1/messages?receive_id_type=open_id",
                    headers={"Authorization": f"Bearer {token}"})
        log(resp.get("code") == 0, f"消息已发送 ({resp.get('msg')})")
    else:
        log(False, "缺少 open_id，无法发送（先运行 feishu_whoami.py）")

    print(f"[4/4] 回环验证：{timeout} 秒内请在飞书回复 ok", flush=True)
    try:
        import lark_oapi as lark
    except Exception as e:
        log(False, f"缺少 lark-oapi（pip install lark-oapi）: {e}")
        summary_and_exit(1)

    def on_message(data) -> None:
        try:
            text = ""
            if data.event.message.message_type == "text":
                try:
                    text = json.loads(data.event.message.content).get("text", "")
                except Exception:
                    text = data.event.message.content or ""
            log(True, f"收到飞书回复: {text}")
            summary_and_exit(0 if FAIL_N == 0 else 1)
        except Exception as e:  # noqa: BLE001
            log(False, f"处理消息异常: {e}")
            summary_and_exit(1)

    handler = (lark.EventDispatcherHandler.builder("", "")
               .register_p2_im_message_receive_v1(on_message)
               .build())
    client = lark.ws.Client(app_id, app_secret, event_handler=handler, log_level=lark.LogLevel.WARNING)
    threading.Timer(timeout, lambda: (log(False, "超时未收到飞书回复"), summary_and_exit(2))).start()
    client.start()
    return 0


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main() or 0)
