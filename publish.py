# -*- coding: utf-8 -*-
"""
小满公众号 - 按需发布脚本 v3.0
流程：处理新照片 → AI生成诗意文案 → 上传COS → 调用SCF → 微信发布

所有敏感信息从 publish_config.toml 读取，请先复制 publish_config.toml.example 并填入真实配置。
"""

import os
import sys
import io
import json
import random
import shutil
import requests
import toml
import re
from datetime import datetime
from PIL import Image
from pathlib import Path

# Windows 编码处理
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def load_config() -> dict:
    """加载发布配置

    优先读取 publish_config.toml，不存在则报错退出。
    """
    config_paths = [
        Path("publish_config.toml"),
        Path(__file__).parent / "publish_config.toml",
    ]
    for p in config_paths:
        if p.exists():
            print(f"✅ 加载配置: {p}")
            return toml.load(p)

    print("❌ 未找到 publish_config.toml")
    print("   请复制 publish_config.toml.example 为 publish_config.toml 并填入真实配置")
    sys.exit(1)


# ============ 加载配置 ============
CONFIG = load_config()

# COS 配置
COS_SECRET_ID: str = CONFIG["cos"]["secret_id"]
COS_SECRET_KEY: str = CONFIG["cos"]["secret_key"]
COS_BUCKET: str = CONFIG["cos"]["bucket"]
COS_REGION: str = CONFIG["cos"].get("region", "ap-chengdu")
COS_DOMAIN: str = f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com"

# SCF 配置
SCF_URL: str = CONFIG["scf"]["url"]

# 素材存储路径
MATERIAL_DIR: Path = Path(CONFIG["paths"].get("material_dir", "xiaoman_materials"))
BATCH_DIR: Path = MATERIAL_DIR / "batches"
ARCHIVE_DIR: Path = MATERIAL_DIR / "archived"

# 精选照片目录（可选，第二遍AI精选结果）
SELECTED_PHOTOS_DIR: Path = Path(CONFIG["paths"].get("selected_photos_dir", ""))
PHOTOS_PER_ARTICLE: int = CONFIG["publish"].get("photos_per_article", 4)

# 状态记录
STATE_FILE: Path = MATERIAL_DIR / "state.json"

# ============ 装饰元素库 ============
DECORATIONS = {
    "dividers": ["✨✨✨", "⋆༺ ⋯ ⋆༻", "· · ·", "◂ ▸", "～ ～ ～", "★ · ☆ · ★", "─── ⋯ ───", "·•·•·"],
    "quotes": ["这一刻", "就这样", "慢慢长大", "值得记录", "小小的她", "日常碎片", "镜头里", "窗外", "午后", "某一天"],
    "endings": ["✨", "🌱", "📷", "💫", "·", "♡"],
    "image_styles": [
        "border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);",
        "border: 3px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.15);",
        "border-radius: 8px; filter: contrast(1.05);",
        "border-radius: 4px; transform: rotate(-1deg);",
        "border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.12);",
    ],
}


def load_state() -> dict:
    """加载状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"last_publish_time": None, "next_batch_num": 1}


def save_state(state: dict) -> None:
    """保存状态"""
    MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_new_photos() -> list[Path]:
    """从精选目录或批次目录获取待发布照片"""
    state = load_state()
    used_photos = set(state.get("used_photos", []))

    # 优先从 batches 目录取（手动发送的新照片）
    batch_photos = []
    if BATCH_DIR.exists():
        for batch_folder in sorted(BATCH_DIR.iterdir()):
            if batch_folder.is_dir():
                for ext in ["*.jpg", "*.jpeg", "*.png"]:
                    batch_photos.extend(batch_folder.glob(ext))

    if batch_photos:
        print(f"[批次] 找到 {len(batch_photos)} 张手动添加的照片")
        return batch_photos[:PHOTOS_PER_ARTICLE]

    # 没有手动照片，从精选目录随机选
    if not SELECTED_PHOTOS_DIR or not SELECTED_PHOTOS_DIR.exists():
        print(f"[提示] 精选照片目录未配置或不存在: {SELECTED_PHOTOS_DIR}")
        return []

    all_selected = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]:
        all_selected.extend(SELECTED_PHOTOS_DIR.glob(ext))
    all_selected = sorted(set(all_selected))

    if not all_selected:
        print("[提示] 精选目录为空")
        return []

    # 过滤掉已用过的
    unused = [p for p in all_selected if str(p) not in used_photos]

    # 如果用完了，重置（循环使用）
    if len(unused) < PHOTOS_PER_ARTICLE:
        print(f"[提示] 精选照片已用完（共 {len(all_selected)} 张），重新循环使用")
        used_photos.clear()
        state["used_photos"] = []
        save_state(state)
        unused = all_selected[:]

    chosen = random.sample(unused, min(PHOTOS_PER_ARTICLE, len(unused)))
    print(f"[精选库] 共 {len(all_selected)} 张，已用 {len(used_photos)} 张，本次选 {len(chosen)} 张")
    return chosen


def upload_to_cos(local_path: Path, cos_key: str) -> str | None:
    """上传文件到 COS，返回 URL"""
    print(f"📤 上传到 COS: {cos_key}")

    try:
        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(
            Region=COS_REGION,
            SecretId=COS_SECRET_ID,
            SecretKey=COS_SECRET_KEY,
        )
        client = CosS3Client(config)

        with open(local_path, 'rb') as f:
            client.put_object(
                Bucket=COS_BUCKET,
                Body=f,
                Key=cos_key,
                ContentType='image/jpeg',
            )

        url = f"{COS_DOMAIN}/{cos_key}"
        print(f"✅ 上传成功: {url}")
        return url

    except Exception as e:
        print(f"❌ 上传失败: {e}")
        return None


def generate_poetry_style_content() -> tuple[str | None, str | None, str | None]:
    """调用 AI 生成诗意风格的标题、正文、摘要"""
    ai_config_path = Path(CONFIG["paths"].get("ai_config", "ai_config.toml"))
    if not ai_config_path.exists():
        print("[提示] 未找到 ai_config.toml，将使用默认文案")
        return None, None, None

    ai_config = toml.load(ai_config_path)
    api_key = ai_config.get('api', {}).get('api_key')
    model = ai_config.get('api', {}).get('model', 'deepseek-ai/DeepSeek-V3')
    base_url = ai_config.get('api', {}).get('base_url', 'https://api.siliconflow.cn/v1')

    if not api_key:
        return None, None, None

    prompt = """你是一个诗人，为公众号写最简短的一句话。

要求：
1. 标题：6-10个字，极简，意境深远，像诗一样
2. 正文：最多15个字，一句话，抽象，留白，不描述具体内容
3. 摘要：5个字以内

例子：
- 标题：阳光落在睫毛上
- 正文：影子比光更轻
- 摘要：日常

不要写任何解释，直接返回JSON：
{"title": "...", "content": "...", "digest": "..."}"""

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.0,
                "max_tokens": 200,
            },
            timeout=30,
        )

        result = response.json()
        content = result['choices'][0]['message']['content']

        json_match = re.search(r'\{.*?\}', content, re.DOTALL)
        if json_match:
            article = json.loads(json_match.group())
            print(f"✅ 诗意文案生成成功:")
            print(f"   标题: {article.get('title', '')}")
            print(f"   内容: {article.get('content', '')}")
            return article.get('title'), article.get('content'), article.get('digest')

    except Exception as e:
        print(f"❌ AI 生成失败: {e}")

    return None, None, None


def build_decorated_html(title: str, content: str, content_urls: list[str]) -> str:
    """构建带装饰的HTML内容"""
    divider1 = random.choice(DECORATIONS["dividers"])
    divider2 = random.choice(DECORATIONS["dividers"])
    quote = random.choice(DECORATIONS["quotes"])
    ending = random.choice(DECORATIONS["endings"])
    img_styles = random.sample(
        DECORATIONS["image_styles"],
        min(len(content_urls), len(DECORATIONS["image_styles"])),
    )

    # 标题区域
    title_html = f"""
<div style="text-align: center; padding: 20px 0;">
    <span style="font-size: 11px; color: #aaa; letter-spacing: 3px;">{quote}</span>
    <h2 style="margin: 12px 0; font-weight: 300; font-size: 20px; color: #333;">{title}</h2>
    <div style="color: #ddd; font-size: 14px; letter-spacing: 5px;">{divider1}</div>
</div>
"""

    # 正文内容
    body_html = f"""
<div style="padding: 20px; text-align: center;">
    <p style="font-size: 14px; color: #666; line-height: 2.2; margin: 0; letter-spacing: 1px;">{content}</p>
    <div style="color: #ddd; margin-top: 20px; letter-spacing: 5px;">{divider2}</div>
</div>
"""

    # 图片区域
    images_html = ""
    for i, url in enumerate(content_urls):
        style = img_styles[i % len(img_styles)]
        padding = "15px 20px" if i == 0 else "8px 25px"
        width = "100%" if i == 0 else "88%"

        images_html += f"""
<div style="padding: {padding};">
    <img src="{url}" style="width: {width}; display: block; margin: 0 auto; {style}" />
</div>
"""

    # 结尾
    footer_html = f"""
<div style="text-align: center; padding: 25px 0 15px;">
    <span style="font-size: 20px; color: #ccc;">{ending}</span>
    <p style="font-size: 10px; color: #ccc; margin-top: 12px; letter-spacing: 2px;">小满</p>
</div>
"""

    # 组装
    html = f"""
<div style="max-width: 100%; background: #fafafa;">
    {title_html}
    {body_html}
    {images_html}
    {footer_html}
</div>
"""
    return html


def call_scf(
    title: str,
    content: str,
    digest: str,
    cover_url: str,
    content_urls: list[str],
) -> tuple[bool, str | None]:
    """调用 SCF 创建微信草稿，返回 (是否成功, media_id)"""
    print(f"📡 调用 SCF: {SCF_URL}")

    payload = {
        "mode": "cos",
        "title": title,
        "content": content,
        "digest": digest,
        "cover_url": cover_url,
        "content_urls": content_urls,
    }

    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        proxies = {'http': None, 'https': None}
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            if key in os.environ:
                del os.environ[key]

        response = requests.post(
            SCF_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
            verify=False,
            proxies=proxies,
        )

        print(f"📨 响应状态: {response.status_code}")
        result = response.json()

        if result.get('ok'):
            print(f"✅ 草稿创建成功: {result.get('media_id')}")
            return True, result.get('media_id')
        else:
            print(f"❌ 草稿创建失败: {result.get('error')}")
            return False, None

    except Exception as e:
        print(f"❌ SCF 调用失败: {e}")
        return False, None


def archive_photos(photos: list[Path]) -> None:
    """归档已发布的照片"""
    state = load_state()
    archive_batch = ARCHIVE_DIR / f"published_{state.get('next_batch_num', 1):03d}"
    archive_batch.mkdir(parents=True, exist_ok=True)

    for photo in photos:
        dest = archive_batch / photo.name
        shutil.move(str(photo), str(dest))
        print(f"📦 归档: {dest.name}")


def publish() -> tuple[bool, str | None]:
    """主发布流程：选照片 → 上传COS → AI文案 → 发布草稿"""
    print("=" * 50)
    print("📝 小满公众号 - 按需发布")
    print("=" * 50)

    # 1. 获取待发布的照片
    photos = get_new_photos()

    if not photos:
        print("[警告] 没有照片可发布")
        print("提示：精选目录为空，或批次目录没有新照片")
        return False, None

    print(f"📸 找到 {len(photos)} 张待发布照片")

    # 2. 生成封面（用第一张，裁剪为 1200x630）
    cover_path = Path("cover_temp.jpg")
    with Image.open(photos[0]) as img:
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        target_ratio = 1200 / 630
        width, height = img.size
        current_ratio = width / height

        if current_ratio > target_ratio:
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            img = img.crop((left, 0, left + new_width, height))
        else:
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            img = img.crop((0, top, width, top + new_height))

        img = img.resize((1200, 630), Image.Resampling.LANCZOS)
        img.save(cover_path, 'JPEG', quality=90)
        print(f"✅ 封面已生成")

    # 3. 上传封面
    today = datetime.now().strftime('%Y%m%d%H%M')
    cover_key = f"covers/{today}_cover.jpg"
    cover_url = upload_to_cos(cover_path, cover_key)

    if not cover_url:
        print("❌ 封面上传失败")
        cover_path.unlink(missing_ok=True)
        return False, None

    # 4. 上传正文图片
    content_urls = []
    for i, photo in enumerate(photos):
        photo_key = f"articles/{today}_img_{i + 1}.jpg"
        photo_url = upload_to_cos(photo, photo_key)
        if photo_url:
            content_urls.append(photo_url)

    # 5. 生成诗意文案
    title, content, digest = generate_poetry_style_content()

    if not title:
        title = "小满"
        content = "记录每一天"
        digest = "成长"

    # 6. 构建 HTML
    html_content = build_decorated_html(title, content, content_urls)

    # 7. 调用 SCF 发布
    success, media_id = call_scf(title, html_content, digest or "小满", cover_url, content_urls)

    # 8. 清理临时文件
    cover_path.unlink(missing_ok=True)

    # 9. 更新状态并归档
    if success:
        state = load_state()
        state["last_publish_time"] = datetime.now().strftime("%Y%m%d%H%M%S")

        # 记录已用照片（精选库的照片只记录不移动，批次照片归档）
        used_photos = state.get("used_photos", [])
        batch_photo_paths = set()
        if BATCH_DIR.exists():
            for bf in BATCH_DIR.iterdir():
                if bf.is_dir():
                    for ext in ["*.jpg", "*.jpeg", "*.png"]:
                        for p in bf.glob(ext):
                            batch_photo_paths.add(str(p))

        for photo in photos:
            photo_str = str(photo)
            if photo_str not in batch_photo_paths:
                if photo_str not in used_photos:
                    used_photos.append(photo_str)

        state["used_photos"] = used_photos
        save_state(state)

        # 只归档批次照片
        batch_photos_to_archive = [p for p in photos if str(p) in batch_photo_paths]
        if batch_photos_to_archive:
            archive_photos(batch_photos_to_archive)

    print("=" * 50)
    print(f"{'✅ 发布成功' if success else '❌ 发布失败'}")
    if media_id:
        print(f"📋 草稿ID: {media_id}")
    print("=" * 50)

    return success, media_id


if __name__ == "__main__":
    publish()
