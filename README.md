# 🥔 PotatoGallery 
### 为低配服务器而生的“工业级”插画展示系统

![Status](https://img.shields.io/badge/Status-Under_Development-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)
![Memory](https://img.shields.io/badge/RAM-0.5G_Required-green?style=flat-square)

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
However, the project code is fully functional and operational, and community contributions are most welcom**


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
* **沉浸式详情**：主色提取、EXIF 信息展示、原图下载、SHA256 校验。
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
```text
/opt/PotatoGallery
├── app/             # 逻辑核心
├── db/              # SQLite 元数据
├── storage/         
│   ├── raw/         # 归档：已入库的原图
│   ├── thumb/       # 缓存：可随时重建的缩略图
│   ├── www/         # 门面：Nginx 直接服务的静态站点
│   ├── .upload_tmp/ # 隔离：未完成的临时文件
│   └── quarantine/  # 隔离：异常或超限文件
└── static/          # 前端静态资产
