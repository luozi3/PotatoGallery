PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 基础图片信息表
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    ext TEXT NOT NULL,
    mime TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','processed','quarantined','published')),
    stored_path TEXT NOT NULL,       -- raw 目录下的文件相对路径
    thumb_path TEXT,                 -- thumb 目录下的相对路径
    thumb_width INTEGER,
    thumb_height INTEGER,
    dominant_color TEXT,             -- #RRGGBB
    title_override TEXT,
    description TEXT,
    tags_json TEXT,                  -- JSON 数组字符串
    collection_override TEXT,
    deleted_at DATETIME,
    trash_path TEXT,
    purge_after DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);
CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at);
CREATE INDEX IF NOT EXISTS idx_images_deleted_at ON images(deleted_at);

-- 相册表
CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    cover_uuid TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cover_uuid) REFERENCES images(uuid)
);

CREATE TABLE IF NOT EXISTS album_images (
    album_id INTEGER NOT NULL,
    image_uuid TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    PRIMARY KEY (album_id, image_uuid),
    FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
    FOREIGN KEY (image_uuid) REFERENCES images(uuid) ON DELETE CASCADE
);

-- 处理流水/任务表
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_uuid TEXT,
    stage TEXT NOT NULL,                 -- upload/validate/thumb/metadata/build/publish
    status TEXT NOT NULL CHECK (status IN ('pending','running','done','failed')),
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_uuid) REFERENCES images(uuid)
);

CREATE INDEX IF NOT EXISTS idx_jobs_stage ON jobs(stage);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- 构建与发布记录
CREATE TABLE IF NOT EXISTS builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('pending','building','ready','published','failed')),
    staging_path TEXT NOT NULL,
    published_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 审计/异常日志
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    ref TEXT,
    payload TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
