# 飞书完成通知规则（Feishu Notify · 独立工程）

当用户要求「任务/对话/项目跑完后用飞书通知我」（或等价说法）时，agent 必须遵守：

## 执行要求

1. 在任务**收尾时**（无论成功还是失败都必须执行）运行：
   ```
   python "{{TOOL_DIR}}/feishu_send.py" "<结果摘要>" -t "<标题>"
   ```
2. 结果摘要须包含：任务名、成功/失败、关键结果或错误摘要（简短）
3. **飞书通道无 24h/10 条保活限制**，可随时主动推送；限制仅有频控（单用户 5 QPS）与用户主动屏蔽
4. 只在任务完成或失败时通知一次，不要每个中间步骤都通知

## 工具说明（无需用户再提供任何配置）

- 发送：`{{TOOL_DIR}}/feishu_send.py`（零依赖 REST；`-t` 标题、`--to` 指定 open_id、`--dry-run` 预览）
- 接收：`{{TOOL_DIR}}/feishu_listen.py`（长连接 WebSocket，无需公网 IP；`--wait` 等待 / `--listen` 常驻 / `--check` 自检）
- 自检与获取身份：`{{TOOL_DIR}}/feishu_whoami.py`（自动抓取并记录你的 open_id）
- 测试：`{{TOOL_DIR}}/feishu_test.py`（配置 → 凭证 → 发送 → 长连接回环）
- 配置：`feishu.env`（App ID / App Secret / 你的 open_id）——本工程目录，勿外传
- 依赖：`python -m pip install lark-oapi`（仅接收/长连接相关需要；发送脚本零依赖）
- 成功判据：输出 `OK: 飞书消息已发送 (message_id=...)`

## 双通道问答（提问时可选增强，推荐用飞书——无保活限制）

1. 推送问题：`python "{{TOOL_DIR}}/feishu_send.py" "<问题+选项>" -t "提问"`
2. 启动纯代码监听：`python "{{TOOL_DIR}}/feishu_listen.py" --wait --timeout 30`（后台运行）
3. 告知用户：可直接回复，也可去飞书回复
4. 结束条件（任一满足即停）：前端回复 → 主动结束监听；飞书回复 → 监听自动退出（exit 0），
   消息落盘 `inbox/`，读取最新一条作为用户回答
5. 处理完后如有必要，用 feishu_send.py 回发结果

## 测试例程（用户说「运行测试例程」时执行）

运行 `python "{{TOOL_DIR}}/feishu_test.py"`，它会检查配置 → 校验凭证 → 发送测试消息 → 启动长连接等你在飞书回复 ok，最后输出 PASS/FAIL 汇总。会真发消息，属预期行为。
