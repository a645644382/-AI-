# 无公网下的公众号 AI 自动发布

基于腾讯云 SCF 云函数和微信公众号 API，实现**无公网 IP 环境**下的 AI 自动发布公众号文章。

## 功能特性

- 🤖 **AI 智能生成**：基于 DeepSeek AI 自动生成每日专属文案
- 🎨 **封面自动生成**：从当日照片自动裁剪生成 1200x630 封面
- ⏰ **定时发布**：每天 10:00 自动执行发布任务
- 🔍 **发布监控**：09:50 快照 + 10:15 核查，确保发布成功
- 🖼️ **照片管理**：自动从照片库选择未使用照片，循环利用
- 📝 **5 种视觉风格**：温暖日记/清新简约/电影感/复古文艺/活力多彩

## 核心架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  本地照片素材库   │     │  腾讯云 SCF      │     │   微信公众平台   │
│  C:\Photos      │ ──► │  云函数          │ ──► │   草稿箱        │
│  (无公网)        │     │  (公网出口)      │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        ▼                       ▼
   AI 生成文案              API 发布
   (本地调用)              (云函数执行)
```

## 核心文件

| 文件 | 说明 |
|------|------|
| `daily_publish.py` | 主发布脚本（v4.0），协调整个发布流程 |
| `daily_publish_monitor.py` | 监控脚本（v4.0），基于时间戳检测发布状态 |
| `scf_publish_v5.py` | 腾讯云 SCF 云函数代码 |
| `ai_config.toml.example` | AI 配置模板 |

## 快速开始

### 1. 准备环境

```bash
# 安装 Python 依赖
pip install requests pillow toml

# 配置 AI API（复制模板并填入真实信息）
cp ai_config.toml.example ai_config.toml
```

### 2. 配置参数

编辑 `ai_config.toml`：
```toml
[api]
api_key = "你的 SiliconFlow API Key"
base_url = "https://api.siliconflow.cn/v1"
model = "deepseek-ai/DeepSeek-V3"
```

### 3. 部署云函数

1. 将 `scf_publish_v5.py` 代码部署到腾讯云 SCF
2. 配置环境变量：`WECHAT_APP_ID`、`WECHAT_APP_SECRET`
3. 设置超时时间为 30 秒

### 4. 配置照片库

设置照片目录结构：
```
photos/
├── 2024-11/
├── 2024-12/
└── ...
```

### 5. 配置定时任务

使用 WorkBuddy 自动化配置：
- **09:50** 快照任务：获取草稿箱状态
- **10:00** 主任务：执行 `daily_publish.py`
- **10:15** 监控任务：核查发布状态

## 关键技术方案

### 问题：SCF 无法直接调用微信素材 API

**原因**：SCF 网络环境被微信拒绝（40005 invalid file type）

**解决方案**：JSON 模式
1. 本地上传永久素材到微信 → 获取 `thumb_url`
2. 将数据发送给 SCF → SCF 用 `thumb_media_id_in_url` 创建草稿

### 监控机制（v4.0）

```python
# 09:50 快照：记录所有草稿的 media_id + update_time
# 10:00 发布：创建新草稿
# 10:15 核查：
#   - update_time >= 09:50 的草稿
#   - 且 media_id 不在快照中
#   = 新发布的文章 ✅
```

## 项目结构

```
wechat-daily-publisher/
├── daily_publish.py           # 主发布脚本
├── daily_publish_monitor.py   # 监控脚本
├── scf_publish_v5.py          # 云函数代码
├── ai_config.toml.example     # 配置模板
├── README.md                  # 本文件
└── docs/
    └── architecture.md        # 架构详细说明
```

## 注意事项

- ⚠️ `ai_config.toml` 包含敏感信息，请勿提交到版本控制
- 📸 照片会循环使用，请定期备份已用照片记录
- 🔑 微信 AppID/AppSecret 存储在 SCF 环境变量中

## License

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
