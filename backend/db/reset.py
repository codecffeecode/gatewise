import asyncio
import subprocess
import sys

from sqlalchemy import text

from backend.db.seed import main as seed_main
from backend.db.session import get_engine


async def drop_everything() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


def main() -> None:
    asyncio.run(drop_everything())
    print("Schema dropped. Running migrations...")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    seed_main()


if __name__ == "__main__":
    main()
