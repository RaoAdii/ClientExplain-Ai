"""Cross-platform local-only configuration. Never prints credentials."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = root / ".env"
if not env.exists():
    password, token = secrets.token_hex(32), secrets.token_hex(32)
    env.write_text(
        "APP_ENV=development\n"
        "AUTH_MODE=development\n"
        f"DEV_AUTH_TOKEN={token}\n"
        f"POSTGRES_PASSWORD={password}\n"
        f"DATABASE_URL=postgresql+psycopg://clientexplain:{password}@127.0.0.1:5433/clientexplain\n"
        "REDIS_URL=redis://127.0.0.1:6379/0\n"
        "STORAGE_BACKEND=local\n"
        "PRIVATE_STORAGE_ROOT=.local/private-storage\n"
        "MAX_UPLOAD_BYTES=26214400\n"
        "AI_EXTERNAL_PROCESSING_ALLOWED=false\n"
        "EMBEDDING_MODEL=text-embedding-3-small\n"
        "EMBEDDING_DIMENSIONS=1536\n"
        "IMAGE_PROVIDER=disabled\n",
        encoding="utf-8",
    )
web_env = root / "apps/web/.env.local"
if not web_env.exists():
    values = dict(
        line.split("=", 1)
        for line in env.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    web_env.write_text(
        f"APP_ENV=development\nNEXT_PUBLIC_SITE_URL=http://localhost:3000\nNEXT_PUBLIC_AUTH_MODE=development\nAPI_INTERNAL_URL=http://127.0.0.1:8000\nAUTH_MODE=development\nDEV_AUTH_TOKEN={values.get('DEV_AUTH_TOKEN', '')}\n",
        encoding="utf-8",
    )
print("Local environment is ready. Existing files were preserved; credentials were not printed.")
