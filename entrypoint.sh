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

echo "Database is ready. Starting Orion Backend application..."
exec "$@"
