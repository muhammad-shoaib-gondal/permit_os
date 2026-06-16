# Band agent registry — @gondalshoaib4444

Credentials are in `agent_config.yaml` (gitignored). **Never commit API keys.**

| Role | Band name | Handle | agent_config key | Agent UUID |
|------|-----------|--------|------------------|------------|
| Conductor | PermitOS Conductor | `@gondalshoaib4444/permitos-conductor` | `conductor` | `19d0e8b0-205e-406a-a514-835857ec2096` |
| Jurisdiction | PermitOS Jurisdiction & Zoning | `@gondalshoaib4444/permitos-jurisdiction-zo` | `jurisdiction` | `6dd33e19-c6ce-44ff-9765-cdc170116b30` |
| Building | PermitOS Building & Safety | `@gondalshoaib4444/permitos-building-safety` | `building` | `1f3e5c6e-c44f-4b92-af75-f62692ca4f04` |
| Site/Env | PermitOS Site & Environmental | `@gondalshoaib4444/permitos-site-environmen` | `site` | `e0972262-db6c-44ce-b676-9a9627da11f5` |
| Packager | PermitOS Packager & Tracker | `@gondalshoaib4444/permitos-packager` *(confirm in Band UI)* | `packager` | `ec298c8e-3e83-4ad2-be94-66b17140fb7e` |

## Verify credentials (no LLM key needed)

```powershell
cd C:\Users\HP\projects\permitos
python scripts/verify_band_setup.py conductor
python scripts/verify_band_setup.py jurisdiction
python scripts/verify_band_setup.py building
python scripts/verify_band_setup.py site
python scripts/verify_band_setup.py packager
```

## Install Band SDK (Windows workaround)

```powershell
git clone --depth 1 https://github.com/thenvoi/thenvoi-sdk-python.git _vendor/thenvoi-sdk-python
pip install ./_vendor/thenvoi-sdk-python[langgraph,anthropic]
```

## Start live agents (requires LLM keys in `.env`)

```powershell
# .env needs at minimum:
# OPENAI_API_KEY=...        (Conductor, Building)
# ANTHROPIC_API_KEY=...     (Jurisdiction, Packager)

python -m agents.conductor.agent
python -m agents.jurisdiction.agent
python -m agents.building.agent
python -m agents.site_environmental.agent
python -m agents.packager.agent
```

## Conductor @mention dispatch

When orchestrating a case, mention specialists by handle:

```
@gondalshoaib4444/permitos-jurisdiction-zo analyze zoning for case {case_id}
@gondalshoaib4444/permitos-building-safety building code pre-screen
@gondalshoaib4444/permitos-site-environmen environmental + utilities screen
@gondalshoaib4444/permitos-packager assemble permit package
```
