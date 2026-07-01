#!/usr/bin/env python3
"""Bounded PostgreSQL readiness wait."""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> int:
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        for _ in range(30):
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                return 0
            except Exception:
                await asyncio.sleep(2)
        print("Database did not become ready within 60 seconds", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
