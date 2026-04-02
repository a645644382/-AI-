#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小满每日自动发布 v4.0 (AI 智能生成)
- 从小满素材库随机选取未使用的照片（3~6张）
- 每日随机应用 5 种视觉风格之一
- AI 智能生成专属文案（每次都是独一无二的）
- 自动生成封面并发布到微信公众号草稿箱
- 记录已使用照片，避免重复
- 使用 SCF JSON 模式发布（本地传文件 + SCF 创建草稿）
- AI API: SiliconFlow (DeepSeek-V3)
"""

import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import os
import random
import sys
import requests
from datetime import datetime
from io import BytesIO

# ── 配置 ──────────────────────────────────────
WECHAT_APPID = "wx67f2438c4a816f67"
WECHAT_APPSECRET = "fb920b316ba61a04ec4b0595b8d2ff82"
PHOTOS_DIR = r"C:\Users\yiyun\Desktop\小满\月份整理"
USED_JSON = r"c:\Users\yiyun\WorkBuddy\20260330180243\used_photos.json"
WORK_DIR = r"c:\Users\yiyun\WorkBuddy\20260330180243"
SCF_URL = "https://1259145203-6qo8nrc1g5.ap-guangzhou.tencentscf.com"

# ── AI 配置 ──────────────────────────────────
AI_CONFIG = {
    "api_key": "sk-enjlwqajsgwxizevvifrexyxnsibportkoknqskvvfkgmeiy",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "deepseek-ai/DeepSeek-V3",
}


# ── 工具函数 ──────────────────────────────────
def get_token(appid, appsecret):
    """获取微信 access_token"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={appsecret}"
    resp = requests.get(url, timeout=15)
    result = resp.json()
    if "access_token" not in result:
        raise Exception(f"Token获取失败: {result}")
    return result["access_token"]


def upload_permanent_material(token, file_path, material_type="image"):
    """上传永久素材，返回 (media_id, url)"""
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type={material_type}"
    with open(file_path, 'rb') as f:
        resp = requests.post(url, files={'media': f}, timeout=30)
    result = resp.json()
    if "media_id" not in result:
        raise Exception(f"素材上传失败: {result}")
    return result["media_id"], result.get("url", "")


def call_scf_json_mode(title, content, thumb_media_id, thumb_url, digest="", content_images=None):
    """调用 SCF JSON 模式创建草稿"""
    payload = {
        "title": title,
        "digest": digest,
        "content": content,
        "thumb_media_id": thumb_media_id,
        "thumb_url": thumb_url,
        "content_images": content_images or []
    }
    resp = requests.post(SCF_URL, json=payload, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"SCF调用失败: HTTP {resp.status_code}")
    result = resp.json()
    if not result.get("ok"):
        raise Exception(f"SCF创建草稿失败: {result.get('error')}")
    return result


def generate_ai_content(photo_dates, style_name):
    """调用 AI 生成专属文案"""
    # 获取年月信息用于个性化
    year_months = sorted(set(d[:6] for d in photo_dates))
    date_range = f"{year_months[0][4:6]}月" if len(year_months) == 1 else f"{year_months[0][4:6]}-{year_months[-1][4:6]}月"

    prompt = f"""你是一个温暖的亲子公众号博主，名字叫"小满爸爸"。

请为以下照片素材生成一篇微信公众号文章文案：

要求：
1. 风格：温暖、治愈、有情感共鸣
2. 语气：像日记一样真实自然，不要太正式
3. 照片涉及日期：{date_range}
4. 文章要打动读者，让有孩子的人感同身受

请生成以下 JSON 格式（不要任何其他内容）：
{{
    "title": "标题（8-16个字，有情感）",
    "digest": "摘要（20字以内，点明主题）",
    "lines": ["第1句情感文案", "第2句情感文案", "第3句情感文案", "第4句情感文案"]
}}

要求 lines 数组有 3-5 句话，每句话 5-15 个字，风格参考：
- "你看她笑的样子，整个世界都温柔了"
- "不着急，你慢慢长大，我们慢慢陪你"
- "幸福不是大事，就是你在闹，我们在笑"

直接输出 JSON，不要解释。"""

    try:
        response = requests.post(
            f"{AI_CONFIG['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {AI_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": AI_CONFIG["model"],
                "messages": [
                    {"role": "system", "content": "你是一个温暖的亲子博主。输出纯 JSON。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 400,
                "temperature": 0.85
            },
            timeout=45
        )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()

            # 尝试解析 JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            parsed = json.loads(content)
            print(f"[AI] Generated: {parsed.get('title', 'N/A')}")
            return parsed
        else:
            print(f"[AI] API error: {response.status_code}, using template")
            return None

    except Exception as e:
        print(f"[AI] Error: {e}, using template")
        return None


# ── 文案模板库（备用）─────────────────────────
TEMPLATES = [
    {
        "title": "今天的小满 依然闪闪发光",
        "digest": "每一天 都因为有你而值得被记住",
        "lines": ["你看她笑的样子", "整个世界都温柔了", "今天也是超爱小满的一天"],
    },
    {
        "title": "长大这件事 好像很突然",
        "digest": "昨天还在怀里 今天就想往外面跑",
        "lines": ["不知从哪天开始", "你不再黏着不放", "但没关系 你往前走", "我们永远在你身后"],
    },
    {
        "title": "全世界最可爱的小朋友",
        "digest": "不接受反驳 谢谢",
        "lines": ["可爱这件事", "小满从来没输过"],
    },
    {
        "title": "有你真好",
        "digest": "谢谢你选了我们当爸爸妈妈",
        "lines": ["没生你之前", "不知道自己可以这样爱一个人", "有了你之后", "才知道心可以这么满"],
    },
    {
        "title": "今天也想记录你",
        "digest": "因为每一天的你 都值得被珍藏",
        "lines": ["那些日常的瞬间", "回头看 全是宝藏"],
    },
    {
        "title": "慢慢长大 不着急",
        "digest": "你的每一步 都刚刚好",
        "lines": ["别急着长大", "我们还有很多时间", "陪你慢慢走", "慢慢看这个世界的所有美好"],
    },
    {
        "title": "日常碎片 也是爱你的证据",
        "digest": "不是什么大事 却是最重要的事",
        "lines": ["不需要什么大场面", "你在 就已经是最好的日子", "今天 也是满满的爱"],
    },
    {
        "title": "小满式撒娇 防不胜防",
        "digest": "每次都被你拿捏得死死的",
        "lines": ["她一个眼神", "全家都得投降", "这就是血脉压制吧"],
    },
    {
        "title": "关于你的那些小事",
        "digest": "小事不小 件件是爱",
        "lines": ["你说话的样子", "你跑起来的样子", "你安静发呆的样子", "每一样 都想记下来"],
    },
    {
        "title": "今天的你 比昨天更可爱",
        "digest": "虽然昨天已经很可爱了",
        "lines": ["我本来不信", "可爱可以有上限", "直到遇见了你"],
    },
    {
        "title": "给小满的一封短信",
        "digest": "不写太多 几句就够",
        "lines": ["你不用很厉害", "不用很优秀", "你只需要快乐", "剩下的 爸爸妈妈来扛"],
    },
    {
        "title": "她不知道自己有多被爱",
        "digest": "也不知道我们有多庆幸有她",
        "lines": ["等你长大了就会知道", "你被多少人偷偷爱着", "而我 是爱得最多的那个"],
    },
    {
        "title": "陪你看世界",
        "digest": "世界很大 但你是最美的风景",
        "lines": ["带你去过很多地方", "看过很多风景", "但你", "始终是我镜头里最好的风景"],
    },
    {
        "title": "这就是幸福吧",
        "digest": "简单 平凡 却让人上瘾",
        "lines": ["幸福不是什么大词", "就是你在闹 我们在笑", "日子很普通", "但有你就够了"],
    },
    {
        "title": "小满日记",
        "digest": "记录一点一滴 成长的痕迹",
        "lines": ["今天发生了什么", "其实已经不重要了", "重要的是", "这些日子有你在一起"],
    },
    {
        "title": "你的笑容 是我的充电宝",
        "digest": "电量100% 随时满血复活",
        "lines": ["在外面累了一天", "回来看到你笑", "突然觉得什么都可以了"],
    },
    {
        "title": "养女儿的快乐",
        "digest": "养女儿的人才会懂的那种快乐",
        "lines": ["给她扎辫子", "给她买裙子", "看她臭美", "看她乐呵呵", "每一件小事都是幸福的形状"],
    },
    {
        "title": "愿你永远做个快乐的小孩",
        "digest": "世界很复杂 但你可以很简单",
        "lines": ["你负责快乐就好", "其他的事情", "交给时间", "交给我们"],
    },
    {
        "title": "今天的小满 情绪稳定",
        "digest": "也有不稳定的时候 但可爱就够了",
        "lines": ["天使的时候确实很天使", "恶魔的时候", "也还是忍不住要亲她"],
    },
    {
        "title": "时间 你慢一点",
        "digest": "她还那么小 我还没抱够",
        "lines": ["一转眼", "你就会上学 交朋友 长大", "而我现在只想", "把你牢牢抱在怀里"],
    },
    {
        "title": "二月的碎碎念",
        "digest": "关于小满的日常记录",
        "lines": ["今天的小满特别开心", "不知道在笑什么", "但看到她笑", "我也就跟着笑了"],
    },
    {
        "title": "三月的阳光和你",
        "digest": "春天来了 你也来了",
        "lines": ["春暖花开", "最适合带她出去", "跑跑跳跳", "然后回来", "倒头就睡"],
    },
    {
        "title": "今天也是被小满治愈的一天",
        "digest": "小朋友的世界 真的很简单很美好",
        "lines": ["她不懂什么是压力", "只知道今天要开心", "这大概是", "我最羡慕她的地方"],
    },
    {
        "title": "家有女儿初长成",
        "digest": "每天都在发现她新的可爱之处",
        "lines": ["昨天刚学会的事", "今天就很熟练了", "小朋友的进步", "总是让人惊喜"],
    },
    {
        "title": "做你的父母 真的很幸运",
        "digest": "这份幸运 不是每个人都有的",
        "lines": ["谢谢你来到这个家", "谢谢你让我们", "体验了", "最纯粹的快乐"],
    },
]


# ── 视觉风格库 ─────────────────────────────────
STYLES = {
    "warm": {
        "name": "🌸 温暖日记风",
        "emoji_set": ["🌸", "💕", "✨", "🌷", "💗", "🌻", "🍃", "💫"],
        "header_decorator": ("╭", "╮", "│"),  # top-left, top-right, side
        "footer_decorator": ("╰", "╯", "│"),
        "divider": "・",
        "colors": {
            "bg": "#FFF8F5",
            "header_bg": "linear-gradient(135deg, #FFECD2 0%, #FCB69F 100%)",
            "header_text": "#8B4513",
            "body_bg": "#FFFFFF",
            "text": "#5D4037",
            "accent_bg": "#FFF0EB",
            "accent_text": "#E07A5F",
            "img_border": "#F4A261",
            "img_shadow": "rgba(240, 150, 100, 0.3)",
        },
        "font_size": {"h1": "22px", "body": "15px", "line_height": "1.9"},
        "img_style": {"radius": "16px", "shadow": "0 4px 12px rgba(240, 150, 100, 0.25)", "spacing": "20px"},
    },
    "minimal": {
        "name": "🌿 清新简约风",
        "emoji_set": ["🌿", "🍀", "☁️", "🌱", "💧", "🌾", "🍃", "🕊"],
        "header_decorator": ("", "", ""),
        "footer_decorator": ("", "", ""),
        "divider": "  ",
        "colors": {
            "bg": "#F8FFFE",
            "header_bg": "#E8F5E9",
            "header_text": "#2E7D32",
            "body_bg": "#FFFFFF",
            "text": "#424242",
            "accent_bg": "#E0F2F1",
            "accent_text": "#00796B",
            "img_border": "#C8E6C9",
            "img_shadow": "rgba(0, 0, 0, 0.06)",
        },
        "font_size": {"h1": "20px", "body": "14px", "line_height": "2.0"},
        "img_style": {"radius": "4px", "shadow": "0 2px 8px rgba(0,0,0,0.08)", "spacing": "24px"},
    },
    "cinema": {
        "name": "🎞️ 电影感风",
        "emoji_set": ["🎬", "📽", "🌙", "⭐", "🎭", "✨", "🌃", "🎥"],
        "header_decorator": ("━━━", "━━━", "  "),
        "footer_decorator": ("━━━", "━━━", "  "),
        "divider": "───",
        "colors": {
            "bg": "#1A1A1A",
            "header_bg": "#2C2C2C",
            "header_text": "#D4AF37",
            "body_bg": "#1A1A1A",
            "text": "#E0E0E0",
            "accent_bg": "#2C2C2C",
            "accent_text": "#D4AF37",
            "img_border": "#3A3A3A",
            "img_shadow": "rgba(212, 175, 55, 0.15)",
        },
        "font_size": {"h1": "21px", "body": "15px", "line_height": "1.85"},
        "img_style": {"radius": "2px", "shadow": "0 4px 16px rgba(0,0,0,0.5)", "spacing": "18px"},
    },
    "vintage": {
        "name": "🎀 复古文艺风",
        "emoji_set": ["📖", "🌺", "🪻", "🦢", "📜", "🌹", "🦋", "🏵"],
        "header_decorator": ("❧", "❧", "❋"),
        "footer_decorator": ("☙", "❧", "❋"),
        "divider": "✦",
        "colors": {
            "bg": "#FDF6E3",
            "header_bg": "#F5E6C8",
            "header_text": "#5D4E37",
            "body_bg": "#FDF6E3",
            "text": "#5D4037",
            "accent_bg": "#EDE0C8",
            "accent_text": "#8B6914",
            "img_border": "#C9A86C",
            "img_shadow": "rgba(100, 80, 50, 0.15)",
        },
        "font_size": {"h1": "21px", "body": "14.5px", "line_height": "2.0"},
        "img_style": {"radius": "0px", "shadow": "0 3px 10px rgba(100,80,50,0.18)", "spacing": "22px"},
    },
    "vivid": {
        "name": "✨ 活力多彩风",
        "emoji_set": ["🌈", "💫", "🔥", "💎", "🎉", "⚡", "🌟", "🎪"],
        "header_decorator": ("◈", "◈", "◆"),
        "footer_decorator": ("◈", "◈", "◆"),
        "divider": "━━",
        "colors": {
            "bg": "#FAF5FF",
            "header_bg": "linear-gradient(135deg, #E0C3FC 0%, #8EC5FC 100%)",
            "header_text": "#6A1B9A",
            "body_bg": "#FFFFFF",
            "text": "#4A148C",
            "accent_bg": "#F3E5F5",
            "accent_text": "#7B1FA2",
            "img_border": "#CE93D8",
            "img_shadow": "rgba(156, 39, 176, 0.2)",
        },
        "font_size": {"h1": "23px", "body": "15px", "line_height": "1.9"},
        "img_style": {"radius": "20px", "shadow": "0 4px 14px rgba(156,39,176,0.2)", "spacing": "20px"},
    },
}


def random_style():
    """随机选择一种风格"""
    return random.choice(list(STYLES.keys()))


def build_styled_html(style_key, photos, template, article_images, img_urls):
    """根据风格生成美化的 HTML 文章"""
    s = STYLES[style_key]
    c = s["colors"]
    img_s = s["img_style"]
    em = s["emoji_set"]
    fs = s["font_size"]
    hl, hr, hs = s["header_decorator"]
    fl, fr, fs2 = s["footer_decorator"]
    n = len(photos)
    today = datetime.now().strftime("%Y.%m.%d")

    # 随机 emoji
    e1, e2, e3, e4 = random.sample(em, 4)

    # 图片样式
    img_tag = (
        f'<img src="IMG_SRC" style="'
        f"width:100%;max-width:100%;"
        f"border-radius:{img_s['radius']};"
        f"box-shadow:0 2px 8px {c['img_shadow']};"
        f"margin:{img_s['spacing']} 0;"
        f'">'
    )

    def line_tag(text):
        return (
            f'<p style="margin:14px 0;font-size:{fs["body"]};'
            f'line-height:{fs["line_height"]};color:{c["text"]};'
            f'text-align:center">{text}</p>'
        )

    def accent_tag(text):
        return (
            f'<p style="margin:16px 24px;font-size:{fs["body"]};'
            f'line-height:{fs["line_height"]};color:{c["accent_text"]};'
            f'text-align:center;background:{c["accent_bg"]};'
            f'padding:12px 20px;border-radius:12px;'
            f'font-weight:500">{text}</p>'
        )

    def divider_tag():
        return (
            f'<p style="text-align:center;color:{c["img_border"]};'
            f'margin:8px 0;font-size:18px;opacity:0.6">{s["divider"] * 8}</p>'
        )

    # ── 构建 HTML ──────────────────────────────
    html = []
    html.append(f'<div style="background:{c["bg"]};padding:0;font-family:-apple-system,BlinkMacSystemFont,Helvetica Neue,PingFang SC,Microsoft YaHei,sans-serif">')

    # ── 头部区域 ────────────────────────────────
    html.append(f'<div style="background:{c["header_bg"]};padding:28px 20px;text-align:center;position:relative;overflow:hidden">')
    # 装饰边角
    if hl:
        html.append(f'<span style="position:absolute;top:12px;left:16px;color:{c["img_border"]};font-size:20px;opacity:0.7">{hl}</span>')
        html.append(f'<span style="position:absolute;top:12px;right:16px;color:{c["img_border"]};font-size:20px;opacity:0.7">{hr}</span>')
        html.append(f'<span style="position:absolute;bottom:12px;left:16px;color:{c["img_border"]};font-size:20px;opacity:0.7">{fl}</span>')
        html.append(f'<span style="position:absolute;bottom:12px;right:16px;color:{c["img_border"]};font-size:20px;opacity:0.7">{fr}</span>')

    # emoji 装饰
    html.append(f'<div style="font-size:28px;margin-bottom:8px;letter-spacing:8px">{e1} {e2} {e3}</div>')
    # 标题
    html.append(f'<h1 style="font-size:{fs["h1"]};font-weight:bold;color:{c["header_text"]};margin:8px 0 6px;letter-spacing:2px">{template["title"]}</h1>')
    # 日期
    html.append(f'<div style="font-size:12px;color:{c["header_text"]};opacity:0.7;margin-top:4px">{today}</div>')
    # 摘要
    html.append(f'<div style="font-size:13px;color:{c["header_text"]};opacity:0.75;margin-top:10px;font-style:italic">{template["digest"]}</div>')
    html.append(f'</div>')

    # ── 正文区域 ────────────────────────────────
    html.append(f'<div style="background:{c["body_bg"]};padding:16px 12px">')

    # 第一张照片
    html.append(img_tag.replace("IMG_SRC", img_urls[0]))

    # 交错：文案 + 照片
    for i, line in enumerate(template["lines"]):
        # 文案（加 emoji 装饰）
        if random.random() > 0.5:
            html.append(accent_tag(f"{e4}  {line}  {e4}"))
        else:
            html.append(line_tag(line))

        # 分割线
        if i < len(template["lines"]) - 1 or (i == len(template["lines"]) - 1 and i + 1 < n):
            html.append(divider_tag())

        # 下一张照片
        photo_idx = i + 1
        if photo_idx < n:
            html.append(img_tag.replace("IMG_SRC", img_urls[photo_idx]))

    html.append(f'</div>')

    # ── 底部 ────────────────────────────────────
    html.append(f'<div style="background:{c["header_bg"]};padding:20px;text-align:center">')
    html.append(f'<div style="font-size:24px;margin-bottom:6px;letter-spacing:6px">{e1} · {e2} · {e3}</div>')
    if fs2:
        html.append(f'<div style="color:{c["img_border"]};font-size:14px;opacity:0.6">{fs2} 小满成长记录 {fs2}</div>')
    html.append(f'</div>')

    html.append(f'</div>')
    return "".join(html)


def load_used():
    """加载已使用照片记录"""
    if os.path.exists(USED_JSON):
        with open(USED_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"photos": [], "published": []}


def save_used(data):
    """保存已使用照片记录"""
    with open(USED_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_available_photos(used_data, count):
    """从素材库中选取未使用的照片（支持子目录）"""
    all_photos = []
    for root, dirs, files in os.walk(PHOTOS_DIR):
        for fname in files:
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                fpath = os.path.join(root, fname)
                if fname not in used_data["photos"]:
                    all_photos.append(fpath)

    if len(all_photos) < count:
        print(f"[WARN] Available photos ({len(all_photos)}) < requested ({count}), recycling used photos")
        used_data["photos"] = []
        save_used(used_data)
        all_photos = []
        for root, dirs, files in os.walk(PHOTOS_DIR):
            for fname in files:
                if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    fpath = os.path.join(root, fname)
                    if fname not in used_data["photos"]:
                        all_photos.append(fpath)

    # 按日期分散选取
    date_groups = {}
    for p in all_photos:
        fname = os.path.basename(p)
        date = fname[:8]
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(p)

    available_dates = sorted(date_groups.keys())
    if len(available_dates) >= count:
        selected_dates = random.sample(available_dates, count)
        selected = [random.choice(date_groups[d]) for d in selected_dates]
    else:
        selected = random.sample(all_photos, min(count, len(all_photos)))

    return selected


def compress_image(img_path, max_size=1920, quality=80):
    """压缩图片到合适大小"""
    from PIL import Image

    img = Image.open(img_path)
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    if len(buf.getvalue()) / (1024 * 1024) > 2:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=60)
    buf.seek(0)
    return buf


def make_cover(photos_dir):
    """生成封面图：从第一张照片裁剪为 1200x630"""
    from PIL import Image

    img_path = photos_dir[0]
    img = Image.open(img_path)
    w, h = img.size

    target_ratio = 2.35
    new_w = w
    new_h = int(w / target_ratio)
    if new_h > h:
        new_h = h
        new_w = int(h * target_ratio)
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    cropped = img.crop((left, top, left + new_w, top + new_h))
    cropped = cropped.resize((1200, 630), Image.LANCZOS)

    cover_path = os.path.join(WORK_DIR, "daily_cover.jpg")
    cropped.save(cover_path, "JPEG", quality=85)
    return cover_path


def build_article_html(photos, lines):
    """生成 HTML 文章，返回 HTML 字符串和图片 URL 列表"""
    n_photos = len(photos)
    n_lines = len(lines)

    # 复制并压缩照片
    today_str = datetime.now().strftime("%Y%m%d")
    article_images = []
    for i, photo_path in enumerate(photos):
        dest = os.path.join(WORK_DIR, f"images", f"article_{today_str}_{i:02d}.jpg")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        buf = compress_image(photo_path)
        with open(dest, "wb") as f:
            f.write(buf.getvalue())
        article_images.append(dest)

    # 构建 HTML
    html_parts = []
    html_parts.append(f'<section style="padding:16px;font-family:-apple-system,BlinkMacSystemFont,Helvetica Neue,PingFang SC,Microsoft YaHei,sans-serif">')

    # 标题
    title_words = ['今天的小满', '又是爱你的一天', '关于小满的日常', '快乐碎片', '小满时光']
    html_parts.append(f'<h1 style="font-size:24px;font-weight:bold;color:#333;margin:20px 0 16px;text-align:center">{random.choice(title_words)}</h1>')

    # 交错排列：照片 + 文案
    photo_idx = 0
    line_idx = 0

    # 第一张照片
    html_parts.append(f'<img src="ARTICLE_IMG_0" style="width:100%;max-width:100%;margin:12px 0;border-radius:8px">')

    while line_idx < n_lines or photo_idx < n_photos - 1:
        if line_idx < n_lines:
            html_parts.append(f'<p style="margin:14px 0;font-size:15px;line-height:2;color:#333;text-align:center">{lines[line_idx]}</p>')
            line_idx += 1

        photo_idx += 1
        if photo_idx < n_photos:
            html_parts.append(f'<img src="ARTICLE_IMG_{photo_idx}" style="width:100%;max-width:100%;margin:12px 0;border-radius:8px">')

    html_parts.append('</section>')
    return "".join(html_parts), article_images


def run_daily_publish():
    """执行每日发布"""
    log = lambda msg: print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {msg}")
    log("=== Start daily publish (v4.0 AI 智能生成) ===")

    # 1. 加载已使用记录
    used_data = load_used()
    log(f"Used photos: {len(used_data['photos'])}")

    # 2. 随机选风格
    style_key = random_style()
    style_name = STYLES[style_key]["name"]
    log(f"Today's style: {style_name}")

    # 3. 随机选 3~6 张照片
    photo_count = random.randint(3, 6)
    log(f"Selecting {photo_count} photos...")
    selected_photos = get_available_photos(used_data, photo_count)

    if len(selected_photos) < 2:
        log("ERROR: Not enough photos available!")
        return False

    log(f"Selected photos: {[os.path.basename(p) for p in selected_photos]}")

    # 4. AI 生成专属文案
    photo_dates = [os.path.basename(p)[:8] for p in selected_photos]
    log("Generating AI content...")
    template = generate_ai_content(photo_dates, style_name)
    if not template:
        # AI 失败时使用模板
        template = random.choice(TEMPLATES)
        log(f"AI failed, using template: {template['title']}")
    else:
        log(f"AI Generated: {template['title']}")

    # 5. 生成封面
    cover_path = make_cover(selected_photos)
    log(f"Cover: {cover_path}")

    # 6. 复制并压缩照片
    today_str = datetime.now().strftime("%Y%m%d")
    article_images = []
    for i, photo_path in enumerate(selected_photos):
        dest = os.path.join(WORK_DIR, "images", f"article_{today_str}_{i:02d}.jpg")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        buf = compress_image(photo_path)
        with open(dest, "wb") as f:
            f.write(buf.getvalue())
        article_images.append(dest)
    log(f"Compressed {len(article_images)} photos")

    # 7. 获取 token
    log("Getting token...")
    token = get_token(WECHAT_APPID, WECHAT_APPSECRET)

    # 8. 上传封面（永久素材，获取 url）
    log("Uploading cover (permanent material)...")
    thumb_media_id, thumb_url = upload_permanent_material(token, cover_path)
    log(f"Cover: media_id={thumb_media_id[:20]}..., url={thumb_url[:50]}...")

    # 9. 上传正文图片（永久素材）
    log(f"Uploading {len(article_images)} article images...")
    content_images = []
    for i, img_path in enumerate(article_images):
        _, img_url = upload_permanent_material(token, img_path)
        content_images.append(img_url)
        log(f"  Image {i+1}: {img_url[:50]}...")

    # 10. 生成美化 HTML（根据今日风格）
    article_html = build_styled_html(style_key, selected_photos, template, article_images, content_images)
    log(f"Article HTML generated ({style_name}): {len(article_html)} chars")

    # 11. 调用 SCF JSON 模式
    log("Calling SCF JSON mode...")
    result = call_scf_json_mode(
        title=template["title"],
        content=article_html,
        thumb_media_id=thumb_media_id,
        thumb_url=thumb_url,
        digest=template["digest"],
        content_images=[{"url": url} for url in content_images]
    )

    log(f"SUCCESS! Style: {style_name}")
    log(f"SCF result: ok={result.get('ok')}, draft_msg_id={result.get('draft_msg_id')}")

    # 12. 记录已使用的素材
    for p in selected_photos:
        fname = os.path.basename(p)
        used_data["photos"].append(fname)

    publish_record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": template["title"],
        "style": style_name,
        "photos": [os.path.basename(p) for p in selected_photos],
        "draft_msg_id": result.get("draft_msg_id", ""),
        "type": "photo",
    }

    used_data["published"].append(publish_record)
    save_used(used_data)
    log(f"Saved used photos: {len(used_data['photos'])}")

    return True


if __name__ == "__main__":
    success = run_daily_publish()
    sys.exit(0 if success else 1)
