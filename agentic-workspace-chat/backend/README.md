# Backend

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp ../.env.example ../.env
aws sso login --profile your-sso-profile
uvicorn app.main:app --reload
```

AWS credentials never reach the frontend. The backend loads the SSO profile,
region, Bedrock model, workspace roots, and safety limits from `../.env`.

