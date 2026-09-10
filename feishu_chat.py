#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_chat.py — 飞书双向对话模式（脚本化原语）

把「对话模式」从手工 bash 循环升级为可靠命令：
  · 一轮内用户连发多条 → 全部取出，不遗漏（内部用已读基线做集合比对）
  · 停词检测内置（停/结束/不用了/quit/stop…）→ 输出 [STOP] 供 agent 结束循环
  · 无需 shell 快照文件、无需 comm/sleep 拼装

前置：另开一个常驻监听进程（长连接推送落盘）
  python feishu_listen.py --listen

用法:
  python feishu_chat.py --reset                       # 把已读基线推进到当前（开始新一轮对话）
  python feishu_chat.py --pending                     # 立即取出未读消息（不等待）
  python feishu_chat.py --wait-new --timeout 300      # 阻塞等新消息（全部取出）→ exit 0；超时 exit 2
  python feishu_chat.py --loop --timeout 1800         # 连续多轮：等→打印→再等（直到停词/超时）
  python feishu_chat.py --send "回复内容" [-t 标题]     # 发送一条（包装 feishu_send.py）

退出码: 0 成功/收到消息/收到停词 · 2 超时无消息 · 1 出错
"""
import argparse
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(BASE, "inbox")
STATE = os.path.join(INBOX, ".read-state")
POLL = 2.0
STOP_WORDS = ("停", "结束", "不用了", "停止", "别发了", "quit", "exit", "bye", "stop")


def list_files():
    if not os.path.isdir(INBOX):
        return []
    return sorted(f for f in os.listdir(INBOX)
                  if f.endswith(".txt") and not f.startswith("."))


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_state(names):
    os.makedirs(INBOX, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(sorted(names), f, ensure_ascii=False)


def read_content(name):
    try:
        with open(os.path.join(INBOX, name), encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return ""
    content = ""
    sender = ""
    ts = ""
    for line in text.splitlines():
        if line.startswith("内容: "):
            content = line[len("内容: "):]
        elif line.startswith("发送者 open_id: "):
            sender = line[len("发送者 open_id: "):]
        elif line.startswith("时间: "):
            ts = line[len("时间: "):]
    return content or text.strip(), ts, sender


def is_stop(text):
    low = text.strip().lower()
    return any(w in low for w in STOP_WORDS)


def listener_status():
    """根据心跳文件判断常驻监听是否在运行"""
    hb = os.path.join(INBOX, ".listener.heartbeat")
    if not os.path.isfile(hb):
        return False, "未发现心跳（监听未启动过）"
    try:
        pid, ts = open(hb, encoding="utf-8").read().split()
        age = time.time() - float(ts)
    except Exception:
        return False, "心跳文件异常"
    return (age < 90), f"心跳 {age:.0f} 秒前，pid={pid}"


def take_new():
    """取出未读消息（全部），并把基线推进到当前所有文件"""
    files = list_files()
    state = load_state()
    new = [f for f in files if f not in state]
    if new:
        save_state(files)
    return new


def print_msgs(names):
    stop = False
    total = len(names)
    for i, n in enumerate(names, 1):
        content, ts, _sender = read_content(n)
        flag = ""
        if is_stop(content):
            flag = "  [STOP]"
            stop = True
        print(f"[新消息 {i}/{total}] {ts} | {content}{flag}", flush=True)
    return stop


def wait_new(timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        names = take_new()
        if names:
            return names
        time.sleep(POLL)
    return []


def do_send(text, title=None):
    args = [sys.executable, os.path.join(BASE, "feishu_send.py"), text]
    if title:
        args += ["-t", title]
    return subprocess.run(args).returncode


def main():
    ap = argparse.ArgumentParser(description="飞书双向对话模式")
    ap.add_argument("--reset", action="store_true", help="已读基线推进到当前")
    ap.add_argument("--pending", action="store_true", help="取出未读消息（不等待）")
    ap.add_argument("--wait-new", action="store_true", help="阻塞等新消息（全部取出）")
    ap.add_argument("--loop", action="store_true", help="连续多轮等待并打印")
    ap.add_argument("--status", action="store_true", help="显示监听状态与未读数")
    ap.add_argument("--send", default=None, help="发送回复内容")
    ap.add_argument("-t", "--title", default=None, help="发送标题")
    ap.add_argument("--timeout", type=int, default=300, help="等待超时秒数")
    a = ap.parse_args()

    if a.status:
        alive, info = listener_status()
        files, state = list_files(), load_state()
        pend = [f for f in files if f not in state]
        print(f"监听状态: {'运行中 OK' if alive else '未运行'}（{info}）")
        print(f"未读消息: {len(pend)} 条" + (f"  最新: {pend[-1]}" if pend else ""))
        print("模式提示: 常驻监听=对话模式；仅发通知=通知模式（无需监听）；--wait=单次问答")
        return 0

    if a.send is not None:
        return do_send(a.send, a.title)

    if a.reset:
        files = list_files()
        save_state(files)
        print(f"[OK] 已读基线已重置（{len(files)} 条历史消息标记为已读）")
        return 0

    if a.pending:
        names = take_new()
        if not names:
            print("[空] 没有未读消息")
            return 0
        print_msgs(names)
        return 0

    if a.wait_new:
        print(f"[对话模式] 等待新消息（最多 {a.timeout} 秒；连发多条会全部取出）…", flush=True)
        names = wait_new(a.timeout)
        if not names:
            print("[超时] 未收到新消息", flush=True)
            return 2
        stop = print_msgs(names)
        return 0 if not stop else 0

    if a.loop:
        print(f"[对话模式-连续] 持续等待（总时限 {a.timeout} 秒；收到停词即结束）…", flush=True)
        deadline = time.time() + a.timeout
        while time.time() < deadline:
            names = wait_new(min(60, max(5, int(deadline - time.time()))))
            if not names:
                continue
            if print_msgs(names):
                print("[结束] 收到停词，对话模式退出", flush=True)
                return 0
        print("[超时] 对话模式结束（无新消息）", flush=True)
        return 2

    ap.print_help()
    return 0


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
