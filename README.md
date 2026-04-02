无公网下的公众号 AI 自动发布
🔥 基于腾讯云 SCF 云函数 + 微信公众号 API + DeepSeek AI，实现零运维的公众号每日自动发布

 

功能特性
特性	说明
🤖 AI 智能生成	基于 DeepSeek AI 根据照片日期自动生成专属文案
🎨 封面自动生成	从当日照片自动裁剪生成 1200x630 标准封面
⏰ 定时发布	每天 10:00 自动执行，无需人工干预
🔍 发布监控	09:50 快照 + 10:15 核查，双重保险确保发布成功
🖼️ 照片管理	自动从照片库选择未使用照片，循环利用
📝 5 种视觉风格	温暖日记/清新简约/电影感/复古文艺/活力多彩
🌐 无公网适配	专为没有公网 IP 的家庭/企业环境设计
核心架构
核心技术方案
痛点：SCF 无法直接上传图片到微信
❌ 直接调用微信素材 API 失败
   SCF 环境 ──✗──► 微信 API (40005 invalid file type)
   
   原因：微信拒绝 SCF 网络环境
解决方案：JSON 模式
✅ 本地上传永久素材 ──► 获取 thumb_url
                                  │
                                  ▼
                         SCF 用 thumb_url
                         创建草稿 (thumb_media_id_in_url)
原理：微信允许通过图片 URL 直接引用永久素材，无需 media_id 上传。

快速开始
1. 环境要求
Python 3.7+
腾讯云账号（开通 SCF 云函数）
微信公众号（已认证订阅号/服务号）
SiliconFlow API Key（调用 DeepSeek）
2. 安装依赖
bash
复制
pip install requests pillow toml
3. 配置 AI
bash
复制
cp ai_config.toml.example ai_config.toml
编辑 ai_config.toml：

toml
复制
[api]
provider = "openai"
api_key = "sk-xxxxxxxxxxxx"  # SiliconFlow API Key
base_url = "https://api.siliconflow.cn/v1"
model = "deepseek-ai/DeepSeek-V3"
4. 部署云函数
登录 腾讯云 SCF 控制台
创建函数，选择「从头开始」
运行环境选择「Python 3.9」
复制 scf_publish_v5.py 代码粘贴到编辑器
配置环境变量：
WECHAT_APP_ID = 你的微信 AppID
WECHAT_APP_SECRET = 你的微信 AppSecret
设置超时时间为 30 秒
部署并获取函数 URL
5. 配置本地脚本
编辑 daily_publish.py，修改以下配置：

python
复制
# 云函数 URL
SCF_URL = "https://service-xxxx.gz.apigw.tencentcs.com/release/你的函数名"

# 照片目录
PHOTO_DIR = r"C:\你的照片目录\月份整理"

# 微信公众号配置
WECHAT_APP_ID = "wx1234567890"
WECHAT_APP_SECRET = "xxxxxxxxxxxx"
6. 配置定时任务
方式一：WorkBuddy 自动化（推荐）
09:50 快照任务
  命令：python daily_publish_monitor.py snapshot

10:00 主发布任务
  命令：python daily_publish.py

10:15 监控任务
  命令：python daily_publish_monitor.py remedy
方式二：Windows 任务计划程序
09:50 快照任务
  程序：python
  参数：daily_publish_monitor.py snapshot

10:00 主发布任务
  程序：python
  参数：daily_publish.py

10:15 监控任务
  程序：python
  参数：daily_publish_monitor.py remedy
监控机制详解（v4.0）
python
复制
# 09:50 快照阶段
1. 调用微信 draft/batchget API
2. 记录所有草稿的 media_id + update_time（Unix时间戳）
3. 保存到 draft_snapshot.json

# 10:00 发布阶段
1. 执行完整的发布流程
2. 创建新草稿

# 10:15 核查阶段
1. 再次获取草稿箱
2. 找出同时满足：
   - update_time >= 09:50 的快照时间
   - media_id 不在快照中的草稿
3. 找到 = 发布成功 ✅
   未找到 = 发布失败，触发告警 ❌
为什么用时间戳？

比标题匹配更可靠
时间戳由微信服务器生成，无法伪造
跨天也不会混淆（精确到秒）
项目文件
文件	说明	版本
daily_publish.py	主发布脚本，协调整个流程	v4.0
daily_publish_monitor.py	监控脚本，基于时间戳检测发布状态	v4.0
scf_publish_v5.py	腾讯云 SCF 云函数代码	v5
ai_config.toml.example	AI 配置模板	-
效果预览
AI 生成文案示例
【温暖日记风格】

📅 2026年4月1日 · 小满成长记录

四月的第一天，阳光正好。

今天的小满又长大了一点点。
看着她好奇地探索这个世界，
每一个瞬间都值得被记录。

📷 来自日常的温柔捕捉
封面效果
生成的封面为 1200x630 像素，自动从照片中裁剪最佳区域，适配公众号封面比例。

常见问题
Q: SCF 调用失败怎么办？
A: 检查云函数超时设置是否 ≥ 30 秒，确认环境变量配置正确。

Q: AI 生成的内容不满意？
A: 可以在 ai_config.toml 中调整 temperature 参数（0-1，越高越有创意）。

Q: 照片重复使用？
A: 系统会自动记录已使用的照片，循环利用。如需重置，删除 used_photos.json。

Q: 如何添加更多视觉风格？
A: 编辑 daily_publish.py 中的 VISUAL_STYLES 字典。

项目演进
版本	日期	主要更新
v1.0	2026-03-30	基础功能，实现草稿发布
v2.0	2026-03-31	引入 AI 生成文案
v3.0	2026-04-01	SCF JSON 模式解决网络问题
v4.0	2026-04-02	全新监控机制，基于时间戳检测
License
MIT License - 随便用，开心就好！

贡献
欢迎 Star ⭐、Fork、提 Issue！

如果你觉得这个项目有帮助，欢迎请我喝咖啡 ☕
