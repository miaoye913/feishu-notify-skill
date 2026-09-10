# 飞书对话模式（Conversation Mode）

> 一份可独立交付的 README：描述**飞书双向对话模式**——agent 挂上监听后与用户
> 一来一回持续对话，**直到用户明确喊停**。
>
> 本文只讲模式本身（怎么搭、怎么跑、坑在哪），与任何具体任务内容无关。
> 工具本体：同目录 `feishu_send.py` / `feishu_listen.py`。

---

## 0. 一句话

**常驻监听 + 每轮等待落盘 + 处理后回发**，循环执行，直到用户说停。

和「完成通知」的本质区别：那个是任务收尾单向发一次；这个是**双向、常驻、多轮**。

---

## 1. 前置条件

```bash
# 接收/长连接依赖（发送是零依赖，只用标准库 REST）
python -m pip install lark-oapi

# 自检：凭证 + 长连接可用性
python "D:/deepseek_harness/feishu-notify/feishu_listen.py" --check
```

期望输出：

```
[OK] 凭证已配置 App ID = cli_xxxxxxxx***
[OK] lark-oapi 可用；运行 --wait 或 --listen 即可开始监听
```

凭证在同目录 `feishu.env`：`FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_USER_OPEN_ID`。
**勿外传、勿入库。**

---

## 2. 启动三步

### 第 1 步 · 挂常驻监听（后台运行）

```bash
python "D:/deepseek_harness/feishu-notify/feishu_listen.py" --listen
```

关键：用 **`--listen`（常驻）**，不是 `--wait`（收到一条就退出）。
对话模式必须手里一直握着连接，否则中间发的消息全丢。

### 第 2 步 · 告诉用户已就绪

```bash
python "D:/deepseek_harness/feishu-notify/feishu_send.py" \
  "对话模式已开启，你随便发，我一条条回。说「停」就结束。" -t "对话已就绪"
```

### 第 3 步 · 进入「等待 → 处理 → 回复」循环

每轮**先阻塞等新消息落盘**，再读、再回，然后回到本轮开头继续等。

⚠️ 关键：一轮里用户可能**连发多条**，必须把新增的**全部**取出来按时间顺序逐条处理，
不能只取最新一条（只取最新会静默漏掉中间的消息——这个坑实际踩过）：

```bash
INBOX="D:/deepseek_harness/feishu-notify/inbox"
SNAP=$(mktemp); LOCK=$(mktemp)
ls -1 "$INBOX" | sort > "$SNAP"

for i in $(seq 1 145); do                      # 145 × 2s ≈ 5 分钟
  sleep 2
  ls -1 "$INBOX" | sort > "$LOCK"
  NEW=$(comm -13 "$SNAP" "$LOCK")               # 本轮新增（可能多条）
  if [ -n "$NEW" ]; then
    echo "$NEW" | while read -r f; do echo "NEW: $f"; done
    cp "$LOCK" "$SNAP"                          # 推进基线
    exit 0
  fi
done
echo "TIMEOUT"                                  # 用户没发，重新挂一轮即可
```

> `comm -13` 需要两个文件都排好序，所以两边都 `sort`。
> 输出里每行一个文件名，**逐行处理**（`ls -1` 天然按时间戳升序，同秒内也无歧义）。

之后：`Read` 每个文件 → 取 `内容:` → 处理 → `feishu_send.py` 回过去 → 回到本轮开头。

---

## 3. 消息落盘格式

一条消息 = 一个文件，**原子落盘、不覆盖、不合并**：

```
inbox/feishu_YYYYmmdd_HHMMSS_<hash>.txt
```

```text
时间: 2026-09-10 10:09:24
来源: 飞书
渠道类型: p2p
发送者 open_id: ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
内容: <用户消息原文>
```

- 目录：`D:/deepseek_harness/feishu-notify/inbox/`
- 取最新：`ls -t "$INBOX" | head -1`
- 多条连发：按文件名（时间戳）排序逐条处理

**为什么用「数文件个数」判断新消息，而不是解析监听进程的日志？**
后台任务的 stdout 缓冲和读取时机都不确定；inbox 文件是原子落盘，数个数最可靠。
2 秒轮询一次足够，开销可忽略。

---

## 4. 回复的注意事项

**长回复（含换行/引号/中文）先落文件再传**，规避 shell 转义：

```bash
python "D:/deepseek_harness/feishu-notify/feishu_send.py" "$(cat tmp_reply.txt)" -t "标题"
```

短回复直接内联即可，中文经 argv 传递实测正常。

**发送频控：单用户 5 QPS。** 正常一问一答碰不到，但别循环刷屏。

---

## 5. 结束

结束条件是**用户喊停**（「停」/「不用了」/「结束」等），这是**行为约定，不是程序行为**——
`--listen` 自己不会退出。收到停的指令后：

1. 用 `feishu_send.py` 回一句收尾（可选）
2. 停掉 `--listen` 的后台任务
3. 清理临时文件

---

## 6. 坑（实测踩过的）

| 坑 | 说明 |
|---|---|
| **一轮可能来多条，必须全部取** | 用户打字很快时会连发。只比较文件总数、只取 `ls -t \| head -1`，会**静默漏掉**中间那些消息（实际踩过：漏掉了一条「你好」）。用第 3 步的 `comm -13` 写法取全量新增。 |
| **没有历史消息拉取** | 飞书这条是 WebSocket 推流，只有监听挂上**之后**发的才收得到。挂之前发的补不回来——「帮我看看之前发的消息」做不到。 |
| **别用 `--wait`** | `--wait` 收到一条就 `exit 0`，是给「问一次等一次」场景的。对话模式必须 `--listen`。 |
| **「停」靠 agent 主动执行** | 常驻监听不会自己退出，用户说了停之后要 agent 去停后台任务。 |
| **终端也算一路** | 对话是「飞书 + 终端」双通道，用户在任一侧说的都算数。 |
| **发送频控 5 QPS** | 超了会被限流/屏蔽。 |

---

## 7. 最小命令清单

```bash
D="D:/deepseek_harness/feishu-notify"

python "$D/feishu_listen.py" --check                      # 自检
python "$D/feishu_listen.py" --listen                     # 挂常驻监听（后台）
python "$D/feishu_send.py" "<内容>" -t "<标题>"            # 发消息
ls -t "$D/inbox" | head                                   # 看收件箱
```

---

## 8. 脚本化用法（`feishu_chat.py`，推荐 · 已实现）

上面第 3 步那段 bash（`mktemp` 快照 + `comm -13` + `sleep` 循环）已封装成脚本，**无需再手搓**：

```bash
D="D:/deepseek_harness/feishu-notify"

python "$D/feishu_listen.py" --listen            # ① 常驻监听（后台任务）
python "$D/feishu_chat.py" --reset               # ② 基线推进到当前（开始新一轮对话）
python "$D/feishu_chat.py" --wait-new --timeout 300   # ③ 阻塞等新消息（连发多条全部取出）
python "$D/feishu_chat.py" --send "<回复>"        # ④ 回一条
# ⑤ 回到 ③ 继续；收到停词会自动打 [STOP]，据此结束并停掉 ①
```

其它模式：

| 命令 | 用途 |
|---|---|
| `--pending` | 立即取出未读（不等待） |
| `--loop --timeout 1800` | 连续多轮：等→打印→再等，直到停词或超时（适合纯记录/转发） |
| `--reset` | 已读基线推进到当前 |

相比 bash 版本的改进：
- **不遗漏连发**：内部用「已读基线集合」比对文件名，一次取出全部新增（实测两条连发全部取出）
- **停词内置**：`停/结束/不用了/停止/别发了/quit/exit/bye/stop` 任一命中即打 `[STOP]`
- **无 shell 依赖**：不需要 `mktemp`/`comm`/临时快照文件，Windows 下同样可用
- 退出码明确：`0` 收到消息 · `2` 超时 · `1` 出错
