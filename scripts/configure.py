"""Cross-platform local-only configuration. Never prints credentials."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = root / ".env"
if not env.exists():
    password, token = secrets.token_hex(32), secrets.token_hex(32)
    env.write_text(
        f"APP_ENV=development\nAUTH_MODE=development\nDEV_AUTH_TOKEN={token}\nPOSTGRES_PASSWORD={password}\nDATABASE_URL=postgresql+psycopg://clientexplain:{password}@127.0.0.1:5432/clientexplain\nREDIS_URL=redis://127.0.0.1:6379/0\nIMAGE_PROVIDER=disabled\n",
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
        f"NEXT_PUBLIC_SITE_URL=http://localhost:3000\nNEXT_PUBLIC_AUTH_MODE=development\nAPI_INTERNAL_URL=http://127.0.0.1:8000\nAUTH_MODE=development\nDEV_AUTH_TOKEN={values.get('DEV_AUTH_TOKEN', '')}\n",
        encoding="utf-8",
    )
print("Local environment is ready. Existing files were preserved; credentials were not printed.")
