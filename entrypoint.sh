#!/bin/sh
set -e

echo "Waiting for PostgreSQL database..."
until python - <<EOF
import asyncpg, asyncio, os
dsn = os.getenv('DATABASE_URL')
if not dsn:
    user = os.getenv('PGUSER', 'orion_dev_user')
    password = os.getenv('PGPASSWORD', 'orion_dev_password')
    host = os.getenv('PGHOST', 'localhost')
    port = os.getenv('PGPORT', '5432')
    database = os.getenv('PGDATABASE', 'orion_dev_db')
    dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
else:
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

async def main():
    try:
        conn = await asyncpg.connect(dsn)
        await conn.close()
    except Exception as e:
        print(f"Still waiting for DB... ({e})")
        exit(1)
asyncio.run(main())
EOF
do
  sleep 2
done

echo "Database is ready."

echo "Checking database initialization state..."
DB_STATE=$(python - <<EOF
import asyncpg, asyncio, os
dsn = os.getenv('DATABASE_URL')
if not dsn:
    user = os.getenv('PGUSER', 'orion_dev_user')
    password = os.getenv('PGPASSWORD', 'orion_dev_password')
    host = os.getenv('PGHOST', 'localhost')
    port = os.getenv('PGPORT', '5432')
    database = os.getenv('PGDATABASE', 'orion_dev_db')
    dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
else:
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

async def check():
    conn = await asyncpg.connect(dsn)
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users');"
    )
    await conn.close()
    print("EXISTS" if exists else "FRESH")

asyncio.run(check())
EOF
)

if [ "$DB_STATE" = "FRESH" ]; then
    echo "Fresh database detected (no tables found). Initializing enums and schema from models..."
    python -c "
import asyncio, models
from config.db import engine, ensure_enums_and_tables
async def init():
    async with engine.begin() as conn:
        await ensure_enums_and_tables(conn)
asyncio.run(init())
"
    echo "Stamping Alembic migration version to head..."
    python -m alembic stamp head
    echo "Initial schema created and stamped to head successfully."
else
    echo "Existing database detected. Applying pending Alembic migrations..."
    python -m alembic upgrade head
fi

echo "Starting Orion Backend application..."
exec "$@"
