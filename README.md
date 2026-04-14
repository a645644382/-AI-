# 小满公众号 AI 发布系统 v3.0

> 基于腾讯云 SCF + 微信公众号 API + AI 诗意文案，**按需发布**宝宝成长记录

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

## 功能特性

| 特性 | 说明 |
|------|------|
| 🤖 **AI 诗意文案** | DeepSeek AI 生成意境深远的短文案，不描述具体内容 |
| 🎨 **封面自动生成** | 从照片自动裁剪 1200x630 标准封面 |
| 🖼️ **COS 图床** | 图片上传腾讯云 COS，稳定可靠 |
| 🌐 **无公网适配** | 通过 SCF 中转调用微信 API，无需公网 IP |
| 📝 **按需发布** | 手动触发，你来决定什么时候发 |
| ✨ **装饰排版** | 随机分割线、引言、图片样式，每篇不重样 |

## 架构流程

```
你发照片到微信
       │
       ▼
┌──────────────┐
│  批次目录     │ ← 照片存入 batches/
│  或精选库     │ ← AI 筛选后的精选照片
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  AI 生成文案   │ ← DeepSeek 诗意风格
│  生成封面      │ ← 自动裁剪 1200x630
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  上传 COS      │ ← 图片 → 腾讯云对象存储
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  调用 SCF      │ ← 云函数中转（解决无公网问题）
│  创建草稿      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  微信草稿箱    │ ← 登录后台手动发布
└──────────────┘
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- 腾讯云账号（开通 COS + SCF）
- 微信公众号（已认证）
- AI API Key（SiliconFlow / DeepSeek）

### 2. 安装依赖

```bash
pip install requests pillow toml cos-python-sdk-v5
```

### 3. 配置

```bash
# 发布配置（COS密钥、SCF地址、路径等）
cp publish_config.toml.example publish_config.toml

# AI 配置（文案生成）
cp ai_config.toml.example ai_config.toml
```

编辑 `publish_config.toml`，填入你的真实信息：

```toml
[cos]
secret_id = "你的COS密钥ID"
secret_key = "你的COS密钥Key"
bucket = "your-bucket-1259145203"
region = "ap-chengdu"

[scf]
url = "http://xxxxxx.ap-chengdu.tencentscf.com"

[paths]
material_dir = "xiaoman_materials"
selected_photos_dir = "C:/你的精选照片目录"
ai_config = "ai_config.toml"
```

### 4. 发布

```bash
python publish.py
```

## 配置说明

### publish_config.toml

| 配置项 | 说明 |
|--------|------|
| `cos.*` | 腾讯云 COS 对象存储凭证 |
| `scf.url` | 腾讯云 SCF 云函数 URL |
| `paths.material_dir` | 素材根目录 |
| `paths.selected_photos_dir` | AI 精选照片目录（可选） |
| `paths.ai_config` | AI 配置文件路径 |
| `publish.photos_per_article` | 每篇文章照片数（默认 4） |

### ai_config.toml

| 配置项 | 说明 |
|--------|------|
| `api.api_key` | AI 服务 API Key |
| `api.base_url` | API 地址（默认 SiliconFlow） |
| `api.model` | 模型名称（默认 DeepSeek-V3） |
| `limits.temperature` | 创意度 0-1（越高越有创意） |

## 文案风格

**诗意风格**（v3.0）：
- 标题：6-10 字，意境深远
- 正文：最多 15 字，一句话，抽象留白
- 不描述具体内容，图片是孩子玩水，文案只给意象

示例：
```
标题：月光浸透纸张
正文：沉默在字里行间流淌
摘要：日常
```

## 项目文件

| 文件 | 说明 |
|------|------|
| `publish.py` | 主发布脚本 |
| `publish_config.toml.example` | 发布配置模板 |
| `ai_config.toml.example` | AI 配置模板 |

## 项目演进

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-03-30 | 基础功能，实现草稿发布 |
| v2.0 | 2026-03-31 | 引入 AI 生成文案 + 定时发布 |
| v3.0 | 2026-04-06 | 按需发布 + 诗意风格 + 配置文件管理 |

## License

MIT License - 随便用，开心就好！

欢迎 Star ⭐、Fork、提 Issue！
