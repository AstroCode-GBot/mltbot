import asyncpg
from config import settings

_pool = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 user_id BIGINT PRIMARY KEY, full_name TEXT NOT NULL, username TEXT,
 phone TEXT, verification_status TEXT NOT NULL DEFAULT 'pending',
 is_blocked BOOLEAN NOT NULL DEFAULT FALSE, joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 download_count BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS admins (
 user_id BIGINT PRIMARY KEY, role TEXT NOT NULL DEFAULT 'admin',
 added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS categories (
 id BIGSERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS files (
 id BIGSERIAL PRIMARY KEY, public_id TEXT UNIQUE NOT NULL,
 original_name TEXT NOT NULL, display_name TEXT NOT NULL,
 storage_channel_id BIGINT NOT NULL, storage_message_id BIGINT NOT NULL,
 telegram_file_id TEXT, file_size BIGINT DEFAULT 0, mime_type TEXT,
 category_id BIGINT REFERENCES categories(id) ON DELETE SET NULL,
 subject TEXT, class_name TEXT, chapter TEXT, lecture_number TEXT,
 description TEXT, aliases TEXT[] DEFAULT '{}', tags TEXT[] DEFAULT '{}',
 uploaded_by BIGINT NOT NULL, uploaded_at TIMESTAMPTZ DEFAULT now(),
 download_count BIGINT NOT NULL DEFAULT 0, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS files_search_idx ON files USING GIN
 (to_tsvector('simple', coalesce(display_name,'') || ' ' || coalesce(original_name,'') || ' ' ||
 coalesce(subject,'') || ' ' || coalesce(class_name,'') || ' ' || coalesce(description,'')));
CREATE TABLE IF NOT EXISTS downloads (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT REFERENCES users(user_id),
 file_id BIGINT REFERENCES files(id), downloaded_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS contact_requests (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT REFERENCES users(user_id),
 message TEXT NOT NULL, admin_reply TEXT, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bot_settings (
 key TEXT PRIMARY KEY, value JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS webhook_updates (
 update_id BIGINT PRIMARY KEY, received_at TIMESTAMPTZ DEFAULT now()
);
"""

async def init_db():
    global _pool
    dsn = settings.database_url.replace("postgresql://", "postgres://", 1)
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, command_timeout=30)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)
        if settings.owner_id:
            await conn.execute(
                "INSERT INTO admins(user_id,role) VALUES($1,'owner') ON CONFLICT(user_id) DO UPDATE SET role='owner'",
                settings.owner_id
            )
        for uid in settings.admin_ids:
            if uid != settings.owner_id:
                await conn.execute("INSERT INTO admins(user_id,role) VALUES($1,'admin') ON CONFLICT DO NOTHING", uid)

async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

def pool():
    if _pool is None: raise RuntimeError("Database is not initialized")
    return _pool
