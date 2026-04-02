#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小满公众号发布监控 v4.0（时间戳特征点版）
- 阶段1（9:50）：记录所有草稿的 update_time + media_id 作为基准
- 阶段2（10:15）：查找 update_time >= 9:50 的新草稿，有则成功，无则补发
- 真正基于时间戳特征点验证，不依赖标题匹配
"""

import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import os
import requests
from datetime import datetime

# ── 配置 ──────────────────────────────────────
WECHAT_APPID = "wx67f2438c4a816f67"
WECHAT_APPSECRET = "fb920b316ba61a04ec4b0595b8d2ff82"
WORK_DIR = r"c:\Users\yiyun\WorkBuddy\20260330180243"
SNAPSHOT_FILE = os.path.join(WORK_DIR, "draft_snapshot.json")
MONITOR_LOG = os.path.join(WORK_DIR, "monitor_log.json")
MAIN_SCRIPT = os.path.join(WORK_DIR, "daily_publish.py")
PYTHON = r"C:\Users\yiyun\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

SNAPSHOT_HOUR, SNAPSHOT_MINUTE = 9, 50
CHECK_HOUR, CHECK_MINUTE = 10, 15


def get_token(appid, appsecret):
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={appsecret}"
    resp = requests.get(url, timeout=15)
    result = resp.json()
    if "access_token" not in result:
        raise Exception(f"Token获取失败: {result}")
    return result["access_token"]


def get_all_drafts(token):
    """获取草稿箱所有草稿（media_id + update_time + title）"""
    drafts = []
    page_size = 10
    offset = 0
    while True:
        url = f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={token}"
        payload = {"offset": offset, "count": page_size, "no_content": 0}
        resp = requests.post(url, json=payload, timeout=15)
        result = resp.json()
        items = result.get("item", [])
        if not items:
            break
        for item in items:
            articles = item.get("content", {}).get("news_item", [])
            for art in articles:
                drafts.append({
                    "media_id": item.get("media_id", ""),
                    "update_time": item.get("update_time", 0),
                    "title": art.get("title", ""),
                })
        if len(items) < page_size:
            break
        offset += page_size
    return drafts


def get_snapshot_and_check_ts():
    """获取今日快照时间和检查时间（Unix时间戳）"""
    today = datetime.now().replace(
        hour=SNAPSHOT_HOUR, minute=SNAPSHOT_MINUTE, second=0, microsecond=0
    )
    snapshot_ts = int(today.timestamp())
    check_ts = int(today.replace(hour=CHECK_HOUR, minute=CHECK_MINUTE).timestamp())
    return snapshot_ts, check_ts


def ts_str(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_snapshot(data):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_log():
    if os.path.exists(MONITOR_LOG):
        with open(MONITOR_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(logs):
    with open(MONITOR_LOG, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# ── 阶段1：拍快照（9:50执行）─────────────────────────────────
def take_snapshot():
    """记录当前所有草稿的 media_id + update_time"""
    log("=== 阶段1：拍摄草稿箱快照 ===")
    token = get_token(WECHAT_APPID, WECHAT_APPSECRET)
    drafts = get_all_drafts(token)
    snapshot_ts, _ = get_snapshot_and_check_ts()

    # 记录每个草稿的 media_id（精确去重）+ update_time
    snapshot = {
        "taken_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_ts": snapshot_ts,
        "drafts": [{"media_id": d["media_id"], "update_time": d["update_time"], "title": d["title"]} for d in drafts],
        "total": len(drafts),
    }
    save_snapshot(snapshot)

    log(f"快照已保存：共{len(drafts)}篇草稿，基准时间={ts_str(snapshot_ts)}")
    for d in drafts[:3]:
        log(f"  {ts_str(d['update_time'])} | {d['title'][:30]}...")
    return snapshot


# ── 阶段2：检查并补发（10:15执行）─────────────────────────────────
def check_and_remedy():
    """基于时间戳特征点检测新草稿"""
    log("=== 阶段2：检查草稿箱（时间戳特征点）===")
    token = get_token(WECHAT_APPID, WECHAT_APPSECRET)

    snapshot = load_snapshot()
    if not snapshot:
        log("⚠️ 未找到快照，将拍摄快照后直接退出（明天再监控）")
        return

    # ⚠️ 关键：必须用快照文件里存的 snapshot_ts，而不是重新计算！
    # 因为快照是昨天/今天9:50拍的，检查时间是10:15，时间窗口要对应同一天
    snapshot_ts = snapshot["snapshot_ts"]
    current_drafts = get_all_drafts(token)
    snapshot_ids = {d["media_id"] for d in snapshot["drafts"]}

    log(f"快照基准：{snapshot['taken_at']}（{ts_str(snapshot_ts)}）")
    log(f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"快照草稿数：{snapshot['total']}，当前草稿数：{len(current_drafts)}")

    # ── 核心逻辑：时间戳特征点检测 ──
    # 1. 快照中不存在的 media_id（新草稿）
    new_drafts = [d for d in current_drafts if d["media_id"] not in snapshot_ids]
    # 2. 更新时间 >= 9:50（进一步验证）
    confirmed = [d for d in new_drafts if d["update_time"] >= snapshot_ts]

    log(f"新增草稿：{len(new_drafts)} 篇，时间戳验证通过：{len(confirmed)} 篇")
    if confirmed:
        log(f"✅ 新文章已出现（{ts_str(snapshot_ts)} 之后新建）：")
        for d in confirmed:
            log(f"  → {ts_str(d['update_time'])} | {d['title'][:40]}")

    # ── 决策 ──
    if confirmed:
        log("✅ 验证通过：主任务已成功发布文章")
        result = "success"
    else:
        log("⚠️ 未检测到新文章 → 立即补发！")
        import subprocess
        proc = subprocess.run(
            [PYTHON, MAIN_SCRIPT],
            capture_output=True, text=False,
            cwd=WORK_DIR, timeout=300
        )
        stdout = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
        stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        log(f"补发输出：{stdout + stderr}"[:500])
        result = "remedied" if proc.returncode == 0 else f"remedy_failed({proc.returncode})"

    # 记录监控日志
    logs = load_log()
    logs.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_ts": snapshot_ts,
        "snapshot_total": snapshot["total"],
        "current_total": len(current_drafts),
        "new_drafts_count": len(new_drafts),
        "confirmed_count": len(confirmed),
        "new_titles": [d["title"] for d in confirmed],
        "result": result,
    })
    if len(logs) > 30:
        logs = logs[-30:]
    save_log(logs)
    log(f"监控日志已保存：{result}")
    return result


# ── 入口 ──────────────────────────────────────
if __name__ == "__main__":
    now = datetime.now()
    h, m = now.hour, now.minute

    if h == SNAPSHOT_HOUR and SNAPSHOT_MINUTE <= m < 60:
        take_snapshot()
    elif h == CHECK_HOUR and 10 <= m <= 30:
        check_and_remedy()
    else:
        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower()
            if cmd == "snapshot":
                take_snapshot()
            elif cmd == "remedy":
                check_and_remedy()
            else:
                log(f"未知命令：{cmd}，支持 snapshot / remedy")
        else:
            log(f"当前时间 {now.strftime('%H:%M')}，不在自动窗口内")
            log("手动模式：python daily_publish_monitor.py snapshot  # 拍快照")
            log("手动模式：python daily_publish_monitor.py remedy    # 检查并补发")
