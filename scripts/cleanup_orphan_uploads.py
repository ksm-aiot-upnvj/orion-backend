"""
One-off cleanup of stored avatars/CVs that no database record references
(left over from before uploads were staged in tmp/ until the form is saved).

Dry run (default) only lists the files:
    uv run python scripts/cleanup_orphan_uploads.py
Move orphans into tmp/ so the staged-upload purge removes them after the TTL:
    uv run python scripts/cleanup_orphan_uploads.py --apply
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

from config.db import AsyncSessionLocal
from services.storage_service import KIND_EXTENSIONS, StorageService


async def collect_referenced_paths() -> set[str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                SELECT photo FROM registrations WHERE photo IS NOT NULL
                UNION SELECT cv_url FROM registrations WHERE cv_url IS NOT NULL
                UNION SELECT avatar FROM members WHERE avatar IS NOT NULL
                UNION SELECT avatar FROM users WHERE avatar IS NOT NULL
                """
            )
        )
        return {row[0] for row in result.fetchall()}


async def cleanup(apply: bool) -> None:
    storage = StorageService()
    referenced = await collect_referenced_paths()

    orphans: list[str] = []
    for kind in KIND_EXTENSIONS:
        for file_path in sorted((storage.base_dir / kind).iterdir()):
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            relative_path = f"{kind}/{file_path.name}"
            if relative_path not in referenced:
                orphans.append(relative_path)

    for relative_path in orphans:
        print(f"{'MOVE' if apply else 'ORPHAN'} {relative_path}")
        if apply:
            kind, _, filename = relative_path.partition("/")
            target = storage.tmp_dir / kind / filename
            os.replace(storage.base_dir / kind / filename, target)
            # Reset mtime so the file gets a full TTL grace period (recoverable by moving it back)
            os.utime(target)

    action = "moved to tmp/ (purged after STAGED_UPLOAD_TTL_HOURS)" if apply else "found (dry run, use --apply)"
    print(f"{len(orphans)} orphan file(s) {action}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Move orphan files into tmp/ instead of only listing them")
    asyncio.run(cleanup(parser.parse_args().apply))
