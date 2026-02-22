# 提案：基于 Cloudflare 全栈部署 PotatoGallery

> 本文档是一份技术可行性分析和迁移方案建议，供社区讨论参考。

---

## 背景

PotatoGallery 当前的架构是为低配 VPS 设计的：Nginx 做静态分发，Flask 处理上传与管理 API，
单线程 Worker 轮询处理图片并用 Jinja2 生成静态页面，SQLite 做数据持久化。
这套架构在"一台 0.5G 内存机器跑所有东西"的场景下非常合理。

但 Cloudflare 近年来推出了一整套边缘计算基础设施（Workers、D1、R2、Queues、Pages），
这些服务拼在一起，刚好能覆盖 PotatoGallery 的全部功能需求，而且不需要任何传统服务器。
本文讨论的是：如果要做这件事，具体怎么做，以及做了之后能得到什么。

---

## 一、当前架构与 Cloudflare 服务的对应关系

| 当前组件 | 职责 | Cloudflare 对应 | 说明 |
|---------|------|----------------|------|
| Nginx | 静态文件分发（www/thumb/raw） | **Cloudflare Pages + R2** | Pages 托管前端，R2 存储图片，通过自定义域名访问 |
| Flask (upload_service.py) | 上传和管理 API | **Cloudflare Workers** | 用 JavaScript/TypeScript 重写 API 层 |
| SQLite (gallery.db) | 数据存储 | **Cloudflare D1** | D1 本身就是 SQLite，schema.sql 几乎可以直接用 |
| Pillow (image_utils.py) | 缩略图、主色提取、校验 | **Cloudflare Images / Workers** | 缩略图用 Images API 实时变换；主色提取可在 Worker 内用轻量方案 |
| Worker (worker.py) | 文件处理、静态页生成、发布 | **Cloudflare Queues + Cron Triggers** | 上传完成后推入队列，消费者 Worker 处理 |
| Jinja2 (static_site.py) | 预渲染静态 HTML | **前端 SPA 化（或 Workers SSR）** | 这是改动最大的一块，下面详细说 |
| 磁盘文件系统 | 原图/缩略图/临时文件 | **Cloudflare R2** | 对象存储，兼容 S3 API，有免费额度 |
| systemd | 进程管理 | 不再需要 | Workers 由 Cloudflare 托管，自动扩缩容 |
| cron 定时任务 | 维护、统计 | **Cron Triggers** | 可以在 wrangler.toml 里配置定时触发 |

---

## 二、重点改造模块分析

### 2.1 数据库层（改动最小）

当前的 `db/schema.sql` 定义了 13 张表，包括 images、albums、jobs、auth_users 等。
D1 和 SQLite 的语法高度兼容，大部分 DDL 可以直接迁移。需要注意的点：

- D1 不支持 `PRAGMA journal_mode = WAL`，这行需要删掉（D1 有自己的事务机制）。
- D1 的 `datetime` 处理和标准 SQLite 一致，CURRENT_TIMESTAMP 正常工作。
- 查询代码从 Python 的 `sqlite3` 模块迁移到 D1 的 `env.DB.prepare().bind().run()` 风格。
  语义不变，只是调用方式不同。

整体来说，数据层是迁移成本最低的部分。

### 2.2 文件存储层

当前系统用本地磁盘做存储，通过 `storage.py` 管理几个关键目录：
raw（原图）、thumb（缩略图）、www（发布站点）、quarantine（隔离区）、trash（回收站）。

迁移到 R2 后的对应关系：

```
storage/raw/          -> R2 bucket: potato-gallery-raw/
storage/thumb/        -> R2 bucket: potato-gallery-thumb/  (或用 Images API 实时生成)
storage/quarantine/   -> R2 bucket: potato-gallery-quarantine/
storage/trash/        -> R2 bucket: potato-gallery-trash/ (配合 R2 生命周期规则自动清理)
storage/www/          -> Cloudflare Pages (或 R2 + Workers 路由)
```

R2 的免费额度是每月 10GB 存储 + 1000 万次读取 + 100 万次写入，对于个人画廊来说绑绑有余。

原有的"原子发布"逻辑（目录级 rename）在对象存储上没有直接等价物，
但可以通过版本号前缀或者 Pages 的部署机制来实现类似效果——每次发布就是一次新的部署，
自动具备原子性和回滚能力。

### 2.3 图片处理

`image_utils.py` 目前做四件事：SHA256 校验、读取尺寸、生成缩略图、提取主色调。

- **SHA256 校验**：Workers 原生支持 `crypto.subtle.digest('SHA-256', buffer)`，直接替代。
- **读取尺寸**：可以用轻量的 JS 库（如 image-size）在 Worker 内解析图片头部。
- **缩略图生成**：Cloudflare Images 提供按需变换能力，通过 URL 参数（如 `/cdn-cgi/image/width=400,format=webp/原图路径`）实时生成缩略图，不需要预先处理和存储。这比当前的预生成方案更灵活，也省存储空间。
- **主色提取**：可以在 Worker 中用简单的采样算法实现（取图片头部几个像素的平均值），
  或者在上传时用 Cloudflare Images 的 metadata 接口获取。精度会比 Pillow 略低，
  但对于 UI 背景色来说完全够用。

### 2.4 API 层（工作量最大）

`admin_api.py`（1877 行）和 `user_api.py`（1869 行）是整个系统的 API 核心，
加上 `auth.py`（387 行）和 `auth_api.py`（241 行），总共约 4400 行 Python 代码。

这些需要用 TypeScript 重写为 Cloudflare Workers 的 fetch handler 风格。
好在逻辑本身并不复杂——主要是参数校验、数据库 CRUD、鉴权检查——
不涉及复杂的第三方依赖。Flask 的 Blueprint 路由对应 Workers 的 `Router` 模式（如 itty-router），
转换是比较机械的工作。

鉴权方面，当前系统用 `itsdangerous` 做 HMAC 签名 cookie。
Workers 环境下可以用 Web Crypto API 实现相同的 HMAC-SHA256 签名逻辑，行为完全一致。

### 2.5 静态站点生成（需要架构决策）

这是改造中最需要讨论的部分。当前的 `static_site.py`（1448 行）用 Jinja2 遍历所有图片数据，
预渲染出完整的 HTML 页面（首页、详情页、标签页、搜索页等），然后通过 Nginx 直接分发。

迁移到 Cloudflare 后，有两条路可以走：

**方案 A：保留预渲染，但改用 JS 模板引擎**

把 Jinja2 模板翻译成 Handlebars 或 ETA 模板，在 Workers 触发构建时预渲染 HTML，
然后上传到 Pages 或 R2。这样能保留"数据库挂了站点还能看"的极致只读特性。

优点是保持了原有架构的核心理念，缺点是 30 个 Jinja2 模板需要逐个翻译。

**方案 B：改为前端动态渲染（SPA）**

把当前的 Jinja2 模板改成纯前端 Vue3/React 应用，通过 API 动态获取数据。
项目本身已经有 `frontend/home/` 目录和大量前端 JS 代码（`ui.js` 73KB、`admin.js` 116KB），
说明前端能力已经很强，很多交互逻辑本来就是客户端在做。

全面 SPA 化后，Pages 只需要托管一份前端构建产物，所有数据通过 Workers API 获取。
缩略图通过 Images API 实时生成，详情页、标签页等全部动态渲染。

优点是开发更灵活、热更新方便，缺点是失去了"数据库挂了也能看"的特性（不过 D1 本身有 SLA）。

**建议采用方案 B。** 理由是：Cloudflare 的基础设施本身有高可用保障，
"数据库挂了站点还能看"这个需求在 serverless 环境下不再那么迫切；
而 SPA 方案可以大幅减少维护成本，也更容易持续迭代。

### 2.6 后台任务

当前的 `worker.py` 是一个每 5 秒轮询一次的死循环：扫描 raw 目录新文件 -> 处理 -> 重建静态站 -> 发布。

迁移后的流程：

1. 用户通过 Workers API 上传图片到 R2。
2. 上传完成后，向 Cloudflare Queues 推送一条处理消息。
3. 消费者 Worker 从队列取出消息，执行：读取图片元数据、写入 D1、生成缩略图（如果不用 Images API 实时变换的话）。
4. 定时任务（Cron Trigger）负责维护性工作：清理过期 trash、统计数据采集等。

这种事件驱动的方式比定时轮询更高效——有新图才处理，空闲时不消耗任何资源。

---

## 三、相比当前方案的优势

### 不需要服务器

最直接的好处。不需要购买和维护 VPS，不需要管 Nginx 配置、systemd 服务、磁盘空间、
系统更新、安全补丁。对于个人项目来说，这意味着零运维成本。

### 免费额度基本够用

Cloudflare 的免费计划提供：
- Workers：每天 10 万次请求
- D1：每天 500 万行读取，10 万行写入
- R2：10GB 存储，1000 万次读取/月
- Pages：无限静态站点部署
- Queues：每天 100 万条消息

一个个人画廊的日常访问量远远用不完这些额度。即使超了，按量收费也很便宜。

### 全球边缘网络加速

Cloudflare 在全球有 300 多个数据中心。Workers 在离用户最近的节点执行，
D1 的读取副本也会分布到边缘。这意味着无论访客在哪里，都能获得低延迟的访问体验。
相比之下，一台固定位置的 VPS 对远距离用户的体验会比较差。

### 自动扩缩容

不需要担心突然的流量高峰。Workers 可以并发处理数千个请求，不存在"0.5G 内存被撑爆"的问题。
当然，对于个人画廊来说，这个优势可能不那么明显，但它免除了容量规划的心智负担。

### 直接继承安全能力

DDoS 防护、WAF、Bot 管理、SSL 证书自动续期——这些在传统部署中需要额外配置的东西，
在 Cloudflare 生态里是默认就有的。

### 简化部署流程

当前部署需要：安装 Python、创建 venv、配置 Nginx、设置 systemd、初始化数据库、
配置 cron 定时任务。迁移后只需要 `wrangler deploy` 一条命令，
前端部署也只需要推送到 Git 仓库即可通过 Pages 自动构建。

---

## 四、代价和权衡

不回避问题，这个迁移有明确的代价：

### 后端需要用 TypeScript 重写

约 7000 行 Python 代码（包括 API、Worker、工具函数）需要翻译成 TypeScript。
虽然业务逻辑一致、不涉及算法上的困难，但这仍然是一项不小的工作量。
粗略估计需要 3000-4000 行 TypeScript 代码（因为 TS 在某些场景下比 Python 更紧凑）。

### 模板层需要重构

30 个 Jinja2 模板要么翻译成 JS 模板引擎，要么改成前端组件。
如果选择 SPA 方案，前端需要从"Jinja2 预渲染 + JS 增强"转变为纯客户端渲染。
现有的 11 个 JS 文件（总计约 350KB）中的很多逻辑可以复用，但需要重新组织。

### 失去本地文件系统操作的灵活性

当前系统大量依赖 `os.replace`、`shutil.copytree` 等本地文件操作来实现原子性。
R2 是对象存储，不支持目录级的原子操作。需要用不同的模式来保证数据一致性
（比如先写数据库再写文件，配合幂等重试）。

### 对 Cloudflare 平台的依赖

这不是一个可以"随便换一个云"的方案。D1、R2、Queues 都是 Cloudflare 特有的服务。
虽然 R2 兼容 S3 API，但 D1 和 Workers 的编程模型是平台专属的。
不过反过来说，当前方案也依赖于 Linux + Nginx + Python + SQLite 这个组合。

---

## 五、建议的实施路径

如果社区有兴趣推进这件事，建议按以下阶段进行：

### 第一阶段：基础框架搭建

1. 初始化 Cloudflare Workers 项目（wrangler），配置 D1、R2 绑定。
2. 将 `schema.sql` 导入 D1（去掉不兼容的 PRAGMA，验证所有表和索引正常创建）。
3. 实现基础的健康检查接口 `/health`，确认 Workers + D1 的链路跑通。

### 第二阶段：存储与图片处理

1. 实现 R2 文件上传接口，替代 `storage.py` 的 `write_stream_to_tmp` 和 `atomic_move`。
2. 配置 Cloudflare Images 或 Workers 图片处理，实现缩略图生成和元数据提取。
3. 实现上传 -> 队列 -> 处理 -> 入库的完整流程。

### 第三阶段：API 层迁移

1. 迁移鉴权逻辑（auth.py -> Workers 中间件）。
2. 迁移管理 API（admin_api.py，按功能模块逐步迁移）。
3. 迁移用户 API（user_api.py）。

### 第四阶段：前端改造

1. 将 Jinja2 模板转换为 Vue3 组件（或其他前端框架）。
2. 部署到 Cloudflare Pages，配置路由规则。
3. 处理 SEO 需求（如果需要，可以用 Workers 做关键页面的 SSR）。

### 第五阶段：运维与收尾

1. 配置 Cron Triggers 替代 cron 定时任务。
2. 实现数据迁移工具（从现有 SQLite + 本地文件导入到 D1 + R2）。
3. 文档更新、测试。

---

## 六、Cloudflare 部署的最小配置参考

```toml
# wrangler.toml
name = "potato-gallery"
main = "src/index.ts"
compatibility_date = "2026-02-01"

[[d1_databases]]
binding = "DB"
database_name = "potato-gallery-db"
database_id = "<your-database-id>"

[[r2_buckets]]
binding = "RAW_BUCKET"
bucket_name = "potato-gallery-raw"

[[r2_buckets]]
binding = "THUMB_BUCKET"
bucket_name = "potato-gallery-thumb"

[[queues.producers]]
binding = "IMAGE_QUEUE"
queue = "potato-gallery-processing"

[[queues.consumers]]
queue = "potato-gallery-processing"
max_batch_size = 10
max_batch_timeout = 30

[triggers]
crons = ["0 3 * * *"]  # 每天凌晨 3 点执行维护任务
```

---

## 七、总结

PotatoGallery 的功能在 Cloudflare 全栈上是完全可以实现的。
D1 替代 SQLite、R2 替代本地磁盘、Workers 替代 Flask、Pages 替代 Nginx，
每个组件都有对应的替代方案，没有功能上的死角。

核心的取舍是：用"重写后端和模板层"的一次性成本，换来"零服务器运维、全球加速、自动扩容"的长期收益。
对于希望长期运营一个画廊站点、但不想持续维护服务器的用户来说，这笔账是划算的。

这份提案不是要替换当前的 VPS 部署方案，而是提供一种额外的部署选择。
两种方案可以并行存在：想折腾服务器的用传统方案，想省心的用 Cloudflare 方案。
