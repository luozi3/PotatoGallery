# 自动部署指南

本指南包含两部分：
1) 打包发布包（过滤本地配置/版权图片）
2) 目标机一键部署（安装依赖、生成配置、启动服务）

> 自动部署不会把本地配置与可能存在版权风险的图片打包进发布包。

---

## 1. 打包发布包（在开发机执行）

发布包会自动排除：
- `*.local.json`、`config/upload.json`、`storage/config/auth.local.json` 等本地配置
- `storage/` 运行时数据
- `static/images/*`、`static/live2d/` 等可能涉及版权的资源

执行：
```bash
/opt/PotatoGallery/bin/build_release.sh
```

输出：
```
/opt/PotatoGallery/dist/PotatoGallery_<VERSION>_<TIMESTAMP>.tar.gz
```
若系统支持 `sha256sum`，同时会生成 `.sha256` 校验文件。

排除规则见：`deploy/.releaseignore`

> 若需要错误页插图、Live2D 等资源，请在部署后自行放入 `static/images/` 或 `static/live2d/`。

---

## 2. 目标机自动部署

### 2.1 解压并进入目录
```bash
tar -xzf PotatoGallery_<VERSION>_<TIMESTAMP>.tar.gz -C /opt
cd /opt/PotatoGallery
```

### 2.2 Release 一键部署（推荐）
```bash
sudo ./install.sh
```

### 2.3 运行自动部署脚本（可选）
```bash
# 必要参数可通过环境变量覆盖
export GALLERY_ROOT=/opt/PotatoGallery
export GALLERY_SERVER_NAME=example.com
export GALLERY_UPLOAD_PORT=5000

sudo /opt/PotatoGallery/bin/deploy_auto.sh --apply
```

默认行为：
- 安装依赖（apt-get）
- 创建用户与权限
- 创建 venv 并安装 requirements
- 初始化数据库与目录
- 渲染并写入 Nginx/systemd 配置
- 刷新静态站点并启动服务

可选参数：
- `--enable-cron`：安装维护与请求统计的 cron 任务
- `--skip-apt`：跳过依赖安装
- `--skip-nginx`：不写入/重载 Nginx
- `--skip-systemd`：不写入/启动 systemd
- `--skip-venv`：跳过 venv/pip
- `--skip-db`：跳过数据库初始化
- `--skip-refresh`：跳过 refresh_static.sh

环境变量（可覆盖默认值）：
- `GALLERY_CRON_DAILY`：维护任务 cron 表达式（默认 `@daily`）
- `GALLERY_CRON_STATS`：请求统计 cron 表达式（默认 `*/5 * * * *`）
- `GALLERY_CRON_DAILY_USER`：维护任务运行用户（默认 `GALLERY_USER`）
- `GALLERY_CRON_STATS_USER`：请求统计运行用户（默认 `root`）

### 2.4 渲染配置（不落地）
仅生成配置文件到输出目录：
```bash
/opt/PotatoGallery/bin/deploy_auto.sh --output /tmp/gallery_deploy
```

生成文件包含：
- `potato_gallery.conf`（Nginx）
- `gallery-upload.service` / `gallery-worker.service`（systemd）
- `gallery_root.env`
- `cron/potato_gallery_maintenance` / `cron/potato_gallery_requests`

---

## 3. 需要你手动配置的内容
- 站点信息：`static/data/site.json` / `static/data/site.local.json`
- 上传限制：`config/upload.json`（可从 `config/upload.json.example` 复制）
- Auth 覆盖：`storage/config/auth.local.json`（可选）
- 站点图片与 Live2D 资源（若需展示）

---

## 4. 验证
- `http://127.0.0.1:5000/health` 返回 ok
- 访问 `/status/` 和 `/` 检查静态站点
