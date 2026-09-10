# feishu-notify-skill — 飞书通知（AI ↔ 你的飞书，独立工程）

让电脑上的任何 AI（DSH / Codex / Copilot / Claude Code 等）**通过飞书**给你发通知、并接收你的回复。

## 为什么单独做一个飞书工程

微信 ClawBot 通道有官方防骚扰窗口（**每 24 小时或每 10 条下发**需你主动对话一次），服务号只能单向发送。
**飞书两者都没有**：

| 能力 | 飞书（本工程） | 微信 ClawBot |
|---|---|---|
| 主动推送 | ✅ 随时，无窗口 | ⚠️ 受 24h/10 条窗口限制 |
| 接收你的消息 | ✅ 长连接实时 | ✅ 轮询 |
| 需要保活 | ❌ 不需要 | ✅ 需要 |

限制仅有：频控（单用户 5 QPS）与用户主动屏蔽机器人。

## 目录结构

```
feishu-notify-skill/
├── README.md               ← 本文件
├── install.py              ← 安装器（标记块注入，可与微信工程共存）
├── templates/
│   ├── feishu-agent-rules.md.tpl   ← 规则模板（{{TOOL_DIR}} 占位符）
│   ├── feishu-skill.md.tpl         ← Codex 技能模板
│   └── feishu.env.example          ← 凭证模板
├── feishu_send.py          ← 发送（零依赖 REST）
├── feishu_listen.py        ← 接收（长连接 WebSocket，无需公网 IP）
├── feishu_whoami.py        ← 自检 + 自动获取你的 open_id
└── feishu_test.py          ← 测试例程（配置→凭证→发送→回环）
```

## 前置：飞书端配置（约 15 分钟，一次性）

1. 手机装**飞书**并注册；创建团队（一个人也能建）
2. 打开 <https://open.feishu.cn> 用同一账号登录
3. **创建企业自建应用** → 「添加应用能力」开启**机器人**
4. **权限管理**开通：`im:message`、`im:message:send_as_bot`、`im:message.p2p_msg:readonly`
5. **事件与回调**订阅 `接收消息 im.message.receive_v1`，回调方式选「**使用长连接**」
6. **版本管理与发布**创建版本并发布（可用范围含你自己）
7. **凭证与基础信息**复制 App ID / App Secret → 填入本目录 `feishu.env`

## 快速开始

```bash
git clone https://github.com/miaoye913/feishu-notify-skill.git
cd feishu-notify-skill
python -m pip install lark-oapi          # 接收/回环需要（发送零依赖）
python install.py --project-dir <你的项目目录>   # 部署规则到 Codex/Copilot/Claude（可选项目级）
python feishu_whoami.py                   # 在飞书给机器人发条消息，自动记录你的 open_id
python feishu_test.py                     # 端到端测试（含长连接回环）
```

## 对话模式（双向多轮，直到用户喊停）

与"完成通知"的单向一次性不同，对话模式是**常驻监听 + 每轮取全部新消息 + 逐条处理回发**：

```bash
python feishu_listen.py --listen                    # ① 常驻监听（后台任务）
python feishu_chat.py --reset                       # ② 推进已读基线
python feishu_chat.py --wait-new --timeout 300      # ③ 阻塞等新消息（连发多条全部取出）
python feishu_chat.py --send "回复内容"              # ④ 回复
# ⑤ 回到 ③ 继续；用户说"停"时会输出 [STOP]，据此结束并停掉 ①
```

要点与坑（实测总结）：
- 必须用 `--listen`（常驻）；`--wait` 收到一条就退出，不适合多轮
- 一轮内可能连发多条 → `feishu_chat.py` 保证**全部取出**（手工只取最新会静默漏消息）
- 飞书是 WebSocket 推流，**监听挂上之前发的消息补不回来**
- 结束条件是"用户喊停"（行为约定，监听进程不会自己退）
- 发送频控：单用户 5 QPS

## 日常用法

| 场景 | 命令 |
|---|---|
| 发通知 | `python feishu_send.py "任务跑完了" -t "构建成功"` |
| 等待回复（提问用） | `python feishu_listen.py --wait --timeout 300` |
| 常驻收件 | `python feishu_listen.py --listen`（落盘 `inbox/`） |
| 自检 | `python feishu_listen.py --check` |
| 测试例程 | `python feishu_test.py` |

对话触发（部署后）：对 AI 说「**任务跑完用飞书通知我**」「**运行测试例程**」。

## 安全

- `feishu.env` 含 App Secret，已被 `.gitignore` 排除，切勿外传或提交
- 长连接由飞书官方 SDK（`lark-oapi`）建立，不需要开放公网端口
