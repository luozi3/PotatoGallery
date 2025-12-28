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
    owner_user_id INTEGER,
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

-- 管理后台用户与分组
CREATE TABLE IF NOT EXISTS auth_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_user_groups (
    user_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES auth_groups(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auth_user_groups_group_id ON auth_user_groups(group_id);

CREATE TABLE IF NOT EXISTS auth_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code_hash TEXT NOT NULL UNIQUE,
    code_prefix TEXT NOT NULL,
    max_uses INTEGER,
    used_count INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_invite_usages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invite_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ip TEXT,
    used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invite_id) REFERENCES auth_invites(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auth_invite_usages_invite_id ON auth_invite_usages(invite_id);

CREATE TABLE IF NOT EXISTS upload_requests (
    uuid TEXT PRIMARY KEY,
    owner_user_id INTEGER NOT NULL,
    title TEXT,
    description TEXT,
    tags_json TEXT,
    collection_override TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES auth_users(id)
);

CREATE INDEX IF NOT EXISTS idx_upload_requests_owner ON upload_requests(owner_user_id);

-- 用户收藏（个人点赞）
CREATE TABLE IF NOT EXISTS user_favorites (
    user_id INTEGER NOT NULL,
    image_uuid TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, image_uuid),
    FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
    FOREIGN KEY (image_uuid) REFERENCES images(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_favorites_user ON user_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_user_favorites_image ON user_favorites(image_uuid);
CREATE INDEX IF NOT EXISTS idx_user_favorites_created ON user_favorites(user_id, created_at);

-- 用户画廊（手动收藏夹）
CREATE TABLE IF NOT EXISTS user_galleries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    cover_uuid TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
    FOREIGN KEY (cover_uuid) REFERENCES images(uuid)
);

CREATE INDEX IF NOT EXISTS idx_user_galleries_user ON user_galleries(user_id);

CREATE TABLE IF NOT EXISTS user_gallery_images (
    gallery_id INTEGER NOT NULL,
    image_uuid TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (gallery_id, image_uuid),
    FOREIGN KEY (gallery_id) REFERENCES user_galleries(id) ON DELETE CASCADE,
    FOREIGN KEY (image_uuid) REFERENCES images(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_gallery_images_gallery ON user_gallery_images(gallery_id);
