This is a Web API project to support functionalities of GameTeamWeb repo.
This Web API is an interface for the `PersonalAssistants` Azure SQL database (schema project: repo db-PersonalAssistants).
That database has a schema [GameTeam] dedicated to this web site.

GameTeamWeb deploys to https://gameteam.net
GameTeamAPI deploys to https://api.gameteam.net

## Stack

FastAPI + gunicorn/uvicorn, pyodbc against Azure SQL, containerised for Google Cloud Run.
Same layout as the `gemdb` repo.

## Endpoints

| Endpoint                    | Auth        | Purpose                             |
| --------------------------- | ----------- | ----------------------------------- |
| `GET /`                     | public      | Service banner                      |
| `GET /health`               | public      | Liveness/startup probe              |
| `GET /api/v1/auth/keys-count` | public    | Number of API keys loaded           |
| `GET /api/v1/db-check`      | `X-API-Key` | Azure SQL connectivity check        |
| `GET /docs`                 | public      | OpenAPI UI                          |

## Configuration

Set as Cloud Run environment variables / secrets (same approach as gemdb):

| Variable                   | Source                                        |
| -------------------------- | --------------------------------------------- |
| `AZURE_SQL_SERVER_NAME`    | Secret Manager                                 |
| `AZURE_SQL_DATABASE_NAME`  | Secret Manager                                 |
| `AZURE_SQL_USER_NAME`      | Secret Manager                                 |
| `AZURE_SQL_USER_PASSWORD`  | Secret Manager                                 |
| `GCP_PROJECT_ID`           | plain env var                                  |
| `GAMETEAM_API_KEYS`        | fallback for the `gameteam-api-keys` secret; format `app:key,app2:key2` |

## Local development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py          # http://localhost:8080/docs
pytest -q
```

## Deploy

First-time Google Cloud setup - creating the service, secrets and domain - is in
[SETUP.md](SETUP.md).

Afterwards, pushing to `main` deploys through the Cloud Build trigger.
`./deploy.sh` builds and pushes `gcr.io/$PROJECT_ID/gameteam-api` and deploys the
`gameteam-api` Cloud Run service manually (region defaults to `us-east1`).
`cloudrun.yaml` holds the declarative service definition.
