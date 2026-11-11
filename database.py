
import asyncpg
from config import settings

_pool = None


# Create users table first.
# This ensures the referenced column exists before foreign keys are created.
USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    full_name TEXT NOT NULL,
    username TEXT,
    phone TEXT,
    verification_status TEXT NOT NULL DEFAULT 'pending',
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    download_count BIGINT NOT NULL DEFAULT 0
);
"""


# Compatibility migration for an older users table.
# Existing data is preserved; no table is dropped.
USERS_MIGRATION = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'pending';
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS joined_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE users ADD COLUMN IF NOT EXISTS download_count BIGINT DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS users_user_id_unique_idx
ON users(user_id);
"""


SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'admin',
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS files (
    id BIGSERIAL PRIMARY KEY,
    public_id TEXT UNIQUE NOT NULL,
    original_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    storage_channel_id BIGINT NOT NULL,
    storage_message_id BIGINT NOT NULL,
    telegram_file_id TEXT,
    file_size BIGINT DEFAULT 0,
    mime_type TEXT,
    category_id BIGINT REFERENCES categories(id) ON DELETE SET NULL,
    subject TEXT,
    class_name TEXT,
    chapter TEXT,
    lecture_number TEXT,
    description TEXT,
    aliases TEXT[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    uploaded_by BIGINT NOT NULL,
    uploaded_at TIMESTAMPTZ DEFAULT now(),
    download_count BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS downloads (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    file_id BIGINT REFERENCES files(id),
    downloaded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contact_requests (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    message TEXT NOT NULL,
    admin_reply TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS webhook_updates (
    update_id BIGINT PRIMARY KEY,
    received_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS files_uploaded_at_idx
ON files(uploaded_at DESC);

CREATE INDEX IF NOT EXISTS files_category_idx
ON files(category_id);

CREATE INDEX IF NOT EXISTS downloads_user_idx
ON downloads(user_id);

CREATE INDEX IF NOT EXISTS downloads_file_idx
ON downloads(file_id);

CREATE INDEX IF NOT EXISTS files_search_idx
ON files USING GIN (
    to_tsvector(
        'simple',
        coalesce(display_name, '') || ' ' ||
        coalesce(original_name, '') || ' ' ||
        coalesce(subject, '') || ' ' ||
        coalesce(class_name, '') || ' ' ||
        coalesce(description, '')
    )
);
"""


async def init_db():
    global _pool

    if _pool is not None:
        return

    dsn = settings.database_url.replace(
        "postgresql://", "postgres://", 1
    )

    _pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=5,
        command_timeout=30
    )

    try:
        async with _pool.acquire() as conn:
            async with conn.transaction():

                # Step 1: Ensure users exists.
                await conn.execute(USERS_SCHEMA)

                # Step 2: Repair older users table structure.
                await conn.execute(USERS_MIGRATION)

                # Step 3: Create remaining tables and indexes.
                await conn.execute(SCHEMA)

                # Step 4: Register owner.
                if settings.owner_id:
                    await conn.execute(
                        """
                        INSERT INTO admins(user_id, role)
                        VALUES($1, 'owner')
                        ON CONFLICT(user_id)
                        DO UPDATE SET role = 'owner'
                        """,
                        settings.owner_id
                    )

                # Step 5: Register additional admins.
                for uid in settings.admin_ids:
                    if uid != settings.owner_id:
                        await conn.execute(
                            """
                            INSERT INTO admins(user_id, role)
                            VALUES($1, 'admin')
                            ON CONFLICT(user_id) DO NOTHING
                            """,
                            uid
                        )

        print("DATABASE: Connected and schema initialized successfully.")

    except Exception:
        await _pool.close()
        _pool = None
        raise


async def close_db():
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


def pool():
    if _pool is None:
        raise RuntimeError("Database is not initialized")

    return _pool
