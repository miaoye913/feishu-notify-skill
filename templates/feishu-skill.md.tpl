---
name: feishu-notify
description: 通过飞书给用户发送通知（任务完成/失败/提醒），支持双通道问答与测试例程。当用户要求「任务跑完用飞书通知我」或需要飞书通道收发时使用。飞书无 24h 保活限制、双向随时可用。工具目录 {{TOOL_DIR}}，凭证已配置无需用户提供。
---

# 飞书完成通知（Feishu Notify · 独立工程）

## 执行要求

1. 任务**收尾时**（成败都必须执行）运行：
   ```
   python "{{TOOL_DIR}}/feishu_send.py" "<结果摘要>" -t "<标题>"
   ```
2. 摘要包含：任务名、成功/失败、关键结果或错误摘要（简短）
3. 飞书**无 24h/10 条保活窗口**，随时可推；仅受频控（5 QPS）与用户屏蔽限制
4. 只在完成/失败时通知一次

## 工具说明

- 发送 `{{TOOL_DIR}}/feishu_send.py`（零依赖） · 接收 `{{TOOL_DIR}}/feishu_listen.py`（长连接） · 测试 `{{TOOL_DIR}}/feishu_test.py`
- 身份获取 `{{TOOL_DIR}}/feishu_whoami.py`；配置 `feishu.env`（勿外传/勿入库）
- 接收功能依赖 `pip install lark-oapi`

## 双通道问答

1. `python "{{TOOL_DIR}}/feishu_send.py" "<问题+选项>" -t "提问"`
2. `python "{{TOOL_DIR}}/feishu_listen.py" --wait --timeout 30`（后台）
3. 用户前端或飞书任一路回复 → 结束监听（飞书回复会落盘 `inbox/`）

## 对话模式（用户说「开启对话模式」「我们聊会儿」「用飞书对话」时执行）

双向多轮对话，直到用户明确喊停：

1. 启动常驻监听（后台）：`python "{{TOOL_DIR}}/feishu_listen.py" --listen`
2. 推进已读基线：`python "{{TOOL_DIR}}/feishu_chat.py" --reset`
3. 通知用户已就绪：`python "{{TOOL_DIR}}/feishu_chat.py" --send "对话模式已开启，说「停」结束"`
4. 循环：`python "{{TOOL_DIR}}/feishu_chat.py" --wait-new --timeout 300`（阻塞等新消息，连发多条会全部取出）
   → 处理打印出的每条消息 → 用 `--send "<回复>"` 逐条回复 → 回到本步继续
5. 结束：输出出现 `[STOP]`（用户说了停/结束/不用了等）→ 回一句收尾 → **停掉第 1 步的监听进程**

注意：必须用 `--listen`（常驻）而非 `--wait`；飞书 WebSocket 推流不补历史消息；发送频控 5 QPS。

## 测试例程

`python "{{TOOL_DIR}}/feishu_test.py"` → 配置/凭证/发送/长连接回环四项检查，输出 PASS/FAIL。
