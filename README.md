# 🥔 PotatoGallery 
### 为低配服务器而生的“工业级”插画展示系统

![Status](https://img.shields.io/badge/Status-Under_Development-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)
![Memory](https://img.shields.io/badge/RAM-0.5G_Required-green?style=flat-square)

~~体验地址：https://luozi.de5.net/~~（已不可用/down）

**PotatoGallery** 是一款专为 0.5G RAM 甚至更低配环境设计的画廊系统。它拒绝在访问时进行昂贵的动态计算，通过“静态发布”与“原子切换”技术，让廉价 VPS 也能拥有丝滑、稳定且防弹的 Pixiv 级体验。
<img 
  width="1847" 
  height="1009" 
  title="目前 README 截图中展示的部分视觉元素仅用于功能演示，开发者不拥有相关版权。" 
  alt="项目主页截图展示" 
  src="https://github.com/user-attachments/assets/420c10e5-d871-410e-b202-ebe2cfffd96b" 
/>

---

<details>
<summary> 🌟🌟🌟点击展开细节图片展示内容</summary>
  <img width="1851" height="1009" alt="图片" src="https://github.com/user-attachments/assets/0de83815-308d-4625-9370-4053c2349ecd" />
  <img width="310" height="193" alt="图片" src="https://github.com/user-attachments/assets/1c8c0b07-54ec-42a7-875b-a33e2ad19a3a" />
  <img width="1843" height="1004" alt="图片" src="https://github.com/user-attachments/assets/050df4ae-0864-4875-9e28-7d7620dd0ff5" />
  <img width="1829" height="1234" alt="图片" src="https://github.com/user-attachments/assets/45235c54-5011-436f-a343-e0db054e74c5" />
  <img width="1173" height="372" alt="图片" src="https://github.com/user-attachments/assets/e95ccafa-87ae-485f-8027-717cd70d84e5" />
  <img width="1583" height="917" alt="图片" src="https://github.com/user-attachments/assets/3725ba42-5862-4d88-94ff-426a7581cc66" />
  <img width="1583" height="917" alt="图片" src="https://github.com/user-attachments/assets/65260ce2-2f9e-456c-95f3-484fbc768298" />
  <img width="1184" height="328" alt="图片" src="https://github.com/user-attachments/assets/bf2c4064-0f10-4ccf-a315-418abde304e6" />

</details> 


---
## 👋 致访客

**你好！我目前因个人时间有限，无法继续积极开发新功能。
但项目代码完整可用，且非常欢迎社区贡献！**
**Hello! Due to limited personal time, I am currently unable to actively develop new features.
However, the project code is fully functional and operational, and community contributions are most welcome!**


---
## 🌟 核心理念：稳如泰山
- **极致只读**：90% 的访问直接命中 Nginx 静态文件，即便数据库宕机，站点依然可读。
- **异步解耦**：上传、图片处理、页面生成全异步串行，绝不挤占前台内存。
- **原子发布**：要么发布成功，要么完全不可见。通过目录级 `Rename` 瞬间切换版本，杜绝半成品页面。
- **保护性失败**：磁盘满或进程崩？系统会自动阻断写入，但绝不破坏已有的浏览路径。
---

## 🎨 特性一览

### 🌈 现代交互
* **丝滑布局**：响应式瀑布流，支持方向/清晰度/分区筛选。
* **自适应卡片**：严格遵循图片宽高比，无布局偏移（Anti-CLS）。
* **沉浸式详情**：主色提取、分辨率/体积信息、原图下载、SHA256 校验。
* **个性化**：主题切换、Live2D 看板娘支持。

### 🏷️ 深度标签 (Danbooru-like)
* **标签体系**：支持角色、画师、版权等多种分类。
* **智能关联**：支持**标签别名**与**父子关系**（如 `long_hair` -> `长发`）。
* **Wiki 支持**：内置标签 Wiki，管理员可在线编辑标签背景与说明。

### 🛠️ 管理与运维
* **全能后台**：作品批量管理、垃圾桶机制、标签维护。
* **多模式注册**：开放注册 / 邀请码模式 / 私人模式。
* **可视化监控**：内置状态页，实时查看磁盘、内存、CPU 负载曲线。<img width="1858" height="1009" alt="图片" src="https://github.com/user-attachments/assets/a6fca3a5-6439-40e1-a3a2-4b9fe2a3e6f7" />


---

## 🏗️ 简易架构：三层隔离

系统的核心是一套**单向生产流水线**：

1.  **接入层 (Nginx)**：只读防火墙，负责静态分发。
2.  **写入层 (Flask)**：只负责接收文件流，存入临时区。
3.  **处理层 (Worker)**：单线程大脑。图片缩放、标签索引、静态页生成全部在此完成。

---

## 📂 目录语义 (让数据井然有序)
下面是项目目录的“完整结构摘要”，只列核心目录与必要文件，并标注用途（避免过长，已折叠）。

<details>
<summary>📁 点击展开项目文件树（关键目录 + 必要文件）</summary>

```text
/opt/PotatoGallery
├── app/                        # 核心服务与生成逻辑
│   ├── upload_service.py       # 上传服务入口（Flask + Waitress）
│   ├── worker.py               # 单线程处理/发布 Worker
│   ├── static_site.py          # 静态页生成器
│   ├── auth.py                 # 账号/密码与鉴权逻辑
│   ├── auth_api.py             # 登录/注册 API
│   ├── admin_api.py            # 管理后台 API
│   ├── user_api.py             # 用户上传/收藏 API
│   ├── db.py                   # SQLite 连接与事务
│   ├── config.py               # 全局配置与环境变量读取
│   ├── storage.py              # 存储写入、校验、原子操作
│   └── maintenance.py          # 清理/备份/一致性检查
├── bin/                        # 运维脚本入口
│   ├── refresh_static.sh       # 一键刷新静态站点
│   ├── maintenance.py          # 维护任务命令行
│   ├── cron_daily.sh           # 定时任务入口（cron 调用）
│   ├── disk_guard.py           # 磁盘水位保护
│   ├── init_db.py              # 初始化数据库
│   ├── manage_users.py         # 用户管理脚本
│   └── manage_invites.py       # 邀请码管理脚本
├── config/                     # 运行期配置
│   ├── auth.json               # 认证/注册策略
│   └── upload.json.example     # 上传限制示例配置
├── db/                         # SQLite 数据库
│   ├── gallery.db              # 运行库（可备份）
│   └── schema.sql              # 表结构与索引
├── docs/                       # 运维与恢复文档
│   └── backup_restore.md        # 备份/恢复演练说明
├── frontend/                   # 前端构建源码（可选构建）
│   └── home/                   # Vue3 首页（可选实验，默认发布不依赖构建）
├── static/                     # 静态资源与模板
│   ├── templates/              # Jinja 模板（含 pages 扩展）
│   ├── styles/                 # 样式表
│   ├── js/                     # 前端脚本
│   ├── images/                 # 站点图片资源
│   ├── live2d/                 # Live2D 资源
│   └── data/                   # site/tags/collections/wiki 等配置
├── storage/                    # 运行期数据（只读站点 + 写入缓存）
│   ├── .upload_tmp/            # 上传临时文件（未完成不可见）
│   ├── config/                 # 本地运行时配置覆盖（如 auth.local.json）
│   ├── counter/                # 访问计数器旧版资源（PHP）
│   ├── raw/                    # 原图归档（只追加）
│   ├── thumb/                  # 缩略图缓存（可重建）
│   ├── www/                    # 对外发布站点（Nginx 读）
│   ├── www_staging/            # 生成中的临时站点
│   ├── www_old_*/              # 历史发布快照
│   ├── quarantine/             # 异常/非法文件隔离
│   ├── status_data/            # 状态页采集数据
│   ├── logs/                   # 服务与定时任务日志
│   ├── backups/                # 备份（DB + raw/www 镜像）
│   └── trash/                  # 回收站文件（待清理）
├── tests/                      # pytest 测试
├── venv/                       # Python 虚拟环境
├── VERSION                     # 版本号
├── LICENSE                     # 开源协议
└── requirements.txt            # Python 依赖清单
```
</details>

## ⚠️ 部署注意
- 建议将 `storage` 子目录保持在同一分区，以确保 `os.replace` 的原子移动语义。
- 若拆分到不同分区，系统会告警并自动降级为“复制 + 替换 + 删除源”，性能与原子性会下降。

## 🚀 部署
本项目默认无需前端构建，站点由 Worker 生成完整静态页。

**推荐阅读：**
- 自动部署（推荐）：`docs/deploy_auto.md`
- 手动部署（不推荐）：`docs/deploy_manual.md`
- Release 一键部署：下载 Release 包后执行 `sudo ./install.sh`

> 需要快速启动可直接参考 `docs/deploy_manual.md` 的最小步骤与 Nginx/systemd 示例。

## ⚙️ 配置与自定义

- 站点信息与 SEO：`static/data/site.json`（默认值）+ `static/data/site.local.json`（本地覆盖，不提交）。
  - `site_name`/`site_description`/`site_url` 控制 SEO 标题、描述、OG。
  - `seo.title_separator`/`seo.twitter_card`/`seo.default_og_image` 可自定义标题分隔符、Twitter 卡片、OG 兜底图。
- 标签/分区：`static/data/tags.json`、`static/data/collections.json` 可自定义标签名、类型、别名、分区顺序。
- 上传安全限制：`config/upload.json`（参考 `config/upload.json.example`）或 `config/upload.local.json` 可调整上传大小、像素上限、允许类型与开关策略（默认开启，私站可按需关闭）。
- 备份任务：维护任务优先使用 `rsync` 做 raw/www 增量镜像备份（已安装）。
- 认证与注册：`config/auth.json` 控制开放/邀请/私有注册、密码策略；本机覆盖可用 `storage/config/auth.local.json`。
