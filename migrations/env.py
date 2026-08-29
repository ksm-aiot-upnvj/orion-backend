from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# --- Load app settings & metadata
from config.config import settings
from config.db import Base
from models import User, Member, Registration  # noqa: F401

config = context.config

# Override sqlalchemy.url with database URL from settings
db_url = settings.get_database_url()
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
