# API contracts

openapi.json is generated from FastAPI. Regenerate from the repository root:

```powershell
$env:PYTHONPATH = 'services/api'
.\.venv\Scripts\python.exe scripts/export_contracts.py
```

The web Project type currently mirrors ProjectRead. Keep it synchronized with this contract until generated TypeScript clients are introduced.
