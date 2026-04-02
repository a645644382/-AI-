#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能备份脚本 v1.0
基于太子教程的"智能备份"机制

核心功能：
1. 计算文件 hash，对比变化
2. 变化才备份，避免重复
3. 自动推送到 GitHub
"""

import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import json
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

WORK_DIR = r"c:\Users\yiyun\WorkBuddy\20260330180243"
GITHUB_REPO = "https://github.com/a645644382/-AI-.git"
HASH_FILE = os.path.join(WORK_DIR, ".backup_hashes.json")

# 需要备份的文件
BACKUP_FILES = {
    "used_photos.json": "照片使用记录",
    "draft_snapshot.json": "草稿快照",
    "monitor_log.json": "监控日志",
}

# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def calculate_hash(file_path):
    """计算文件的 MD5 hash"""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()

def load_hashes():
    """加载上次的 hash 记录"""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_hashes(hashes):
    """保存 hash 记录"""
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=2)

def check_changes():
    """检查哪些文件有变化"""
    old_hashes = load_hashes()
    new_hashes = {}
    changes = []

    for filename, desc in BACKUP_FILES.items():
        file_path = os.path.join(WORK_DIR, filename)
        if not os.path.exists(file_path):
            continue

        current_hash = calculate_hash(file_path)
        new_hashes[filename] = current_hash

        if filename not in old_hashes or old_hashes[filename] != current_hash:
            changes.append({
                "file": filename,
                "desc": desc,
                "old_hash": old_hashes.get(filename, "N/A")[:8],
                "new_hash": current_hash[:8]
            })

    return changes, new_hashes

def git_commit_and_push(changes):
    """Git 提交并推送"""
    if not changes:
        print("  没有需要推送的更新")
        return False

    # 自动配置代理（如果未配置）
    try:
        result = subprocess.run(["git", "config", "--global", "http.proxy"], 
                              capture_output=True, text=True)
        if "7890" not in result.stdout:
            print("  ⚙️ 自动配置 Git 代理...")
            subprocess.run(["git", "config", "--global", "http.proxy", "http://127.0.0.1:10808"],
                         capture_output=True)
    except:
        pass

    # Git add
    for change in changes:
        print(f"  git add {change['file']}")
        subprocess.run(["git", "-C", WORK_DIR, "add", change["file"]], 
                      capture_output=True)

    # Git commit
    commit_msg = f"智能备份 {datetime.now().strftime('%Y-%m-%d %H:%M')} - "
    commit_msg += ", ".join([c["file"] for c in changes])
    print(f"  git commit -m '{commit_msg}'")
    subprocess.run(["git", "-C", WORK_DIR, "commit", "-m", commit_msg], 
                  capture_output=True)

    # Git push
    print("  git push...")
    result = subprocess.run(["git", "-C", WORK_DIR, "push", "origin", "main"],
                           capture_output=True, text=True)
    if result.returncode == 0:
        print("  ✅ 推送成功")
        return True
    else:
        print(f"  ❌ 推送失败: {result.stderr}")
        return False

# ═══════════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("🧠 智能备份 v1.0")
    print("=" * 60)
    print()

    # 检查变化
    print("[1/3] 检查文件变化...")
    changes, new_hashes = check_changes()

    if not changes:
        print("  ✅ 所有文件无变化，跳过备份")
    else:
        print(f"  发现 {len(changes)} 个文件有变化:")
        for c in changes:
            status = "🆕 新文件" if c["old_hash"] == "N/A" else "📝 已修改"
            print(f"    {status} {c['file']} ({c['desc']})")
            print(f"         {c['old_hash']} → {c['new_hash']}")

    # 保存新的 hash
    print("\n[2/3] 更新 hash 记录...")
    save_hashes(new_hashes)
    print("  ✅ 已保存")

    # Git 推送
    print("\n[3/3] Git 备份...")
    if changes:
        success = git_commit_and_push(changes)
        if success:
            print("\n" + "=" * 60)
            print("🎉 智能备份完成！")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠️ 备份完成，但 Git 推送失败")
            print("   请检查网络和代理配置")
            print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✅ 无需备份，文件已是最新")
        print("=" * 60)

if __name__ == "__main__":
    main()
