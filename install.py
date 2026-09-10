#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书通知工程 安装器（标记块注入式，可与微信工程共存于同一配置文件）

用法:
  python install.py [--tool-dir PATH] [--project-dir PATH] [--dry-run]

部署目标:
  ~/.codex/AGENTS.md                     ← 注入 <!-- FEISHU-NOTIFY:BEGIN --> 标记块
  ~/.codex/skills/feishu-notify/SKILL.md ← 独立技能文件（覆盖）
  ~/.github/copilot-instructions.md      ← 注入标记块
  ~/.claude/CLAUDE.md                    ← 注入标记块
  <project-dir>/AGENTS.md                ← 注入标记块（可选）

标记块机制：只替换自己标记块内的内容，文件其它部分（含微信工程/用户内容）保持不动。
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "templates")
MARK_BEGIN = "<!-- FEISHU-NOTIFY:BEGIN -->"
MARK_END = "<!-- FEISHU-NOTIFY:END -->"
SKILL_DIR_NAME = "feishu-notify"
RULES_TPL = "feishu-agent-rules.md.tpl"
SKILL_TPL = "feishu-skill.md.tpl"


def render(name, tool_dir):
    with open(os.path.join(TPL, name), encoding="utf-8") as f:
        return f.read().replace("{{TOOL_DIR}}", tool_dir)


def inject_block(path, block, dry):
    text = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    section = f"{MARK_BEGIN}\n{block.rstrip()}\n{MARK_END}\n"
    if MARK_BEGIN in text and MARK_END in text:
        pre = text.split(MARK_BEGIN)[0]
        post = text.split(MARK_END, 1)[1]
        new, action = pre + section + post.lstrip("\n"), "更新标记块"
    else:
        new = (text.rstrip() + "\n\n" if text.strip() else "") + section
        action = "追加标记块"
    if dry:
        print(f"  [dry] {action}: {path}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"  [OK] {action}: {path}")


def write_file(path, text, dry):
    if dry:
        print(f"  [dry] 写入 {path}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  [OK] 写入 {path}")


def main():
    ap = argparse.ArgumentParser(description="飞书通知工程安装器")
    ap.add_argument("--tool-dir", default=ROOT, help="工具所在目录（默认本仓库根）")
    ap.add_argument("--project-dir", default=None, help="额外注入项目根 AGENTS.md（如 DSH 工作区）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    tool_dir = os.path.abspath(a.tool_dir).replace("\\", "/")
    home = os.path.expanduser("~")
    print("== 飞书通知工程 安装 ==")
    print(f"工具目录: {tool_dir}")

    rules = render(RULES_TPL, tool_dir)
    skill = render(SKILL_TPL, tool_dir)

    print("[1/2] 注入规则标记块")
    for path, label in [
        (os.path.join(home, ".codex", "AGENTS.md"), "Codex 全局"),
        (os.path.join(home, ".github", "copilot-instructions.md"), "Copilot 全局"),
        (os.path.join(home, ".claude", "CLAUDE.md"), "Claude Code 全局"),
    ]:
        print(f"  - {label}")
        inject_block(path, rules, a.dry_run)
    if a.project_dir:
        print("  - 项目级")
        inject_block(os.path.join(os.path.abspath(a.project_dir), "AGENTS.md"), rules, a.dry_run)
    else:
        print("  - (未指定 --project-dir，跳过项目级)")

    print("[2/2] 部署独立技能文件")
    for base in (".codex", ".claude"):  # Codex 与 Claude Code(含 VSCode 扩展) 各读自家 skills 目录
        write_file(os.path.join(home, base, "skills", SKILL_DIR_NAME, "SKILL.md"), skill, a.dry_run)

    print("完成。下一步：")
    print(f"  1) 确认 feishu.env 已配置（本目录）")
    print(f"  2) 接收功能需: python -m pip install lark-oapi")
    print(f"  3) 运行测试例程: python \"{tool_dir}/feishu_test.py\"")
    print("  4) 各 AI 客户端需开新会话，规则才生效")
    return 0


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
