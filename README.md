# MLT CLASSES VAULT

Telegram-only educational file vault. PostgreSQL stores metadata and bot state; file bytes remain in a private Telegram channel.

## Important limitations

- This starter uses the official Telegram Bot API. Its upload/download limits apply. It does not provide 10 GB uploads.
- Telegram Local Bot API can support larger files (up to 2 GB in supported workflows) but requires separately hosted infrastructure.
- MTProto/Telethon large-file upload is not included in this starter build. Do not assume 10 GB works until a real account/API transfer test succeeds.
- Render Free services sleep after inactivity. They are not a guaranteed 24/7 host.
- Contact relay, broadcast job controls, custom welcome editor, complete category/admin CRUD, MTProto transfer, and durable upload wizard are not implemented in this starter.

## Setup

1. Create a Telegram bot with BotFather.
2. Create a private Telegram channel and add the bot as an administrator with permission to post.
3. Copy the numeric channel ID (usually starts with `-100`).
4. Create a PostgreSQL database (Neon is supported).
5. Copy `.env.example` to `.env` locally and fill values. Never commit `.env`.
6. Install dependencies: `pip install -r requirements.txt`
7. Run locally: `uvicorn main:app --host 0.0.0.0 --port 8000`
8. Set `PUBLIC_BASE_URL` to your public HTTPS service URL and `WEBHOOK_SECRET` to a long random secret.
9. Deploy to Render using the included `render.yaml`; add all environment variables in Render Dashboard.

## Admin workflow

- Add your Telegram numeric ID to `OWNER_ID`.
- Additional initial admins can be added in `ADMIN_IDS`, comma-separated.
- Reply to a document/video/audio message with `/addfile` to copy it into the private storage channel and register metadata.
- `/verify UID`, `/unverify UID`, `/ban UID`, `/unban UID`, `/stats`, `/admin`.

## User workflow

- `/start` registers the user as pending.
- Admin verifies with `/verify UID`.
- Verified users can search by sending a keyword, browse categories, list recent files, and retrieve files.
- Users may voluntarily share their own contact using the keyboard button.

## Security

- Rotate any database password that has been pasted into a chat or committed to a repository.
- Store `BOT_TOKEN`, `DATABASE_URL`, `WEBHOOK_SECRET`, and MTProto sessions only in environment variables / secret stores.
- Use a private storage channel and never share its invite link with ordinary users.
- This starter uses an in-memory FSM only for transient framework state; durable upload/broadcast workflows require dedicated PostgreSQL-backed job/session tables and workers.

## Database

The application initializes core PostgreSQL tables at startup. `migrations/001_initial.sql` is a placeholder version marker; schema changes should be added as forward-only migrations.
