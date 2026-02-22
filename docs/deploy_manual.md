# 手动部署指南

适用范围：手工部署在 Debian/Ubuntu 等常见 Linux 发行版，Nginx 负责静态分发与反代上传服务。

## 1. 系统依赖
- Python 3.9+（含 venv/pip）
- Nginx
- SQLite3
- libmagic（python-magic 依赖）
- rsync（可选，用于备份/维护）
- git

Debian/Ubuntu 示例：
```bash
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx sqlite3 libmagic1 rsync git
```

## 2. 获取代码
```bash
git clone <你的仓库地址> /opt/PotatoGallery
cd /opt/PotatoGallery
```

## 3. Python 环境
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 4. 初始化目录与数据库
```bash
./venv/bin/python -c "from app import storage; storage.ensure_dirs()"
./venv/bin/python bin/init_db.py
```

## 5. 配置文件
- 站点配置：`static/data/site.json`（默认） + `static/data/site.local.json`（本机覆盖，不提交）。
- 上传限制：复制 `config/upload.json.example` → `config/upload.json`，或新建 `config/upload.local.json`。
- 认证配置：`config/auth.json` 为默认；本机覆盖可用 `storage/config/auth.local.json`。
- 若部署路径不是 `/opt/PotatoGallery`，请设置环境变量 `GALLERY_ROOT`。

## 6. 创建管理员用户
```bash
./venv/bin/python bin/manage_users.py create admin
```

## 7. 启动服务（手动方式）
在两个终端分别运行：
```bash
export GALLERY_ROOT=/opt/PotatoGallery
export PYTHONPATH=/opt/PotatoGallery
./venv/bin/python -m app.upload_service
```

```bash
export GALLERY_ROOT=/opt/PotatoGallery
export PYTHONPATH=/opt/PotatoGallery
./venv/bin/python -m app.worker
```

生产环境建议使用 systemd，见下方示例。

## 8. 首次发布静态站点
```bash
./bin/refresh_static.sh
```

## 9. Nginx 最小示例（手动）
```nginx
server {
  listen 80;
  server_name example.com;
  client_max_body_size 40m;

  root /opt/PotatoGallery/storage/www;
  index index.html;

  location /static/ { alias /opt/PotatoGallery/storage/www/static/; }
  location /thumb/  { alias /opt/PotatoGallery/storage/thumb/; }
  location /raw/    { alias /opt/PotatoGallery/storage/raw/; }

  location ~ ^/(api|upload/admin)/ {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location ~ ^/auth/(login|register|logout|me)$ {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

## 10. systemd 示例（可选）

### Upload Service
```ini
[Unit]
Description=PotatoGallery Upload Service
After=network.target

[Service]
User=gallery
Group=www-data
WorkingDirectory=/opt/PotatoGallery
Environment=GALLERY_ROOT=/opt/PotatoGallery
Environment=PYTHONPATH=/opt/PotatoGallery
ExecStart=/opt/PotatoGallery/venv/bin/python -m app.upload_service
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
```

### Worker
```ini
[Unit]
Description=PotatoGallery Worker
After=network.target

[Service]
User=gallery
Group=www-data
WorkingDirectory=/opt/PotatoGallery
Environment=GALLERY_ROOT=/opt/PotatoGallery
Environment=PYTHONPATH=/opt/PotatoGallery
ExecStart=/opt/PotatoGallery/venv/bin/python -m app.worker
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
```

启用示例：
```bash
systemctl daemon-reload
systemctl enable gallery-upload gallery-worker
systemctl start gallery-upload gallery-worker
```

## 11. 验证
- `http://127.0.0.1:5000/health` 返回 ok
- 访问 `/status/` 与 `/` 确认静态站点可读

## 12. 自动部署
详见 `docs/deploy_auto.md`（包含发布包打包与一键部署脚本）。
