# GameTeamAPI - Cloud Run Setup

One-time setup to get `gameteam-api` running on Google Cloud Run at
`https://api.gameteam.net`.

Target configuration:

| Setting        | Value                                  |
| -------------- | -------------------------------------- |
| Service name   | `gameteam-api`                         |
| Region         | `us-east1` (South Carolina, Tier 1)    |
| Memory / CPU   | 512 MiB / 1 vCPU                       |
| Scaling        | min 0, max 10                          |
| Concurrency    | 40                                     |
| Billing        | request-based (CPU during requests)    |
| Domain         | `api.gameteam.net`                     |

`us-east1` is a [Tier 1 pricing region](https://cloud.google.com/run/pricing#tiers).
Tier 2 regions cost about 40% more per vCPU-second and per GiB-second under
request-based billing, and the free tier is granted as a spending-based discount
at Tier 1 rates, so it stretches less far in Tier 2. `us-west2` (Los Angeles),
`us-west3`, `us-west4`, Montreal and Toronto look like ordinary North American
regions but are Tier 2.

## 1. Project prerequisites

Enable these APIs under **APIs & Services > Library**:

- Cloud Run Admin API
- Cloud Build API
- Artifact Registry API
- Secret Manager API

Note the **Project ID** (the ID from the console top bar, not the display name).
Every step below needs it.

## 2. Create the service

Letting Cloud Run build from GitHub creates the service and wires up continuous
deployment in a single pass.

**Cloud Run > Create Service**

1. Select **Continuously deploy from a repository** > **Set up with Cloud Build**
2. **Repository provider**: GitHub, authenticate, pick `BusyStas/GameTeamAPI`
3. **Branch**: `^main$`
4. **Build Type**: Dockerfile, source location `/Dockerfile`, then **Save**
5. **Service name**: `gameteam-api`
6. **Region**: `us-east1 (South Carolina)`
7. **Authentication**: **Allow unauthenticated invocations** (required - this is
   a public API; requests are authorised by the `X-API-Key` header instead)
8. Expand **Container(s), Volumes, Networking, Security** > **Container** tab:
   - Container port `8080`
   - Memory `512 MiB`, CPU `1`
   - **CPU is only allocated during request processing** - this keeps the
     service on request-based billing, which is the cheaper mode at min 0
   - Check **CPU boost** to shorten cold starts
   - Request timeout `300`, max concurrent requests per instance `40`
9. **Revision autoscaling**: min `0`, max `10`. Min 0 is what makes idle cost
   nothing; the tradeoff is a cold start on the first request after idle.
10. **Variables & Secrets** > **Add Variable**: `GCP_PROJECT_ID` = your project ID
11. **Create**

The first build takes around 5 minutes because the Dockerfile installs the
Microsoft ODBC driver.

Expected result: the deploy succeeds and
`https://gameteam-api-<hash>-ue.a.run.app/health` returns JSON with
`"database": "not configured"`. That is correct at this point - credentials come
next.

## 3. Credentials

The service reads Azure SQL settings from environment variables and API keys
from Secret Manager, the same arrangement as `gemdb`.

Create these under **Secret Manager > Create Secret**:

| Secret name                | Value                                        |
| -------------------------- | -------------------------------------------- |
| `azure-sql-server-name`    | Azure SQL server hostname                     |
| `azure-sql-database-name`  | `db-PersonalAssistants`                       |
| `azure-sql-user-name`      | SQL login                                     |
| `azure-sql-user-password`  | SQL password                                  |
| `gameteam-api-keys`        | `gameteamweb:<random-key>` (see format below) |

Then **Cloud Run > `gameteam-api` > Edit & Deploy New Revision > Variables &
Secrets > Reference a Secret**, exposing each **as an environment variable**,
version `latest`:

| Environment variable       | Secret                     |
| -------------------------- | -------------------------- |
| `AZURE_SQL_SERVER_NAME`    | `azure-sql-server-name`    |
| `AZURE_SQL_DATABASE_NAME`  | `azure-sql-database-name`  |
| `AZURE_SQL_USER_NAME`      | `azure-sql-user-name`      |
| `AZURE_SQL_USER_PASSWORD`  | `azure-sql-user-password`  |

`gameteam-api-keys` is read through the Secret Manager client at runtime rather
than mounted, so it does not need an env var - only `GCP_PROJECT_ID`.

### Grant the runtime service account access

Cloud Run runs as the Compute Engine default service account
(`PROJECT_NUMBER-compute@developer.gserviceaccount.com`) unless changed. Grant it
**Secret Manager Secret Accessor**, either per-secret or once at **IAM > Grant
Access**.

Without this the revision fails to start, and the error surfaces as a generic
startup failure rather than a permissions message.

### API key format

`gameteam-api-keys` holds comma-separated `name:key` pairs:

```
gameteamweb:<random-key>,admin:<another-key>
```

Generate keys with `openssl rand -hex 32`. GameTeamWeb sends its key as the
`X-API-Key` header.

## 4. Azure SQL access

Cloud Run egress IPs are dynamic, so one of the following is required on the
Azure side:

- Enable **Allow Azure services and resources to access this server** on the
  Azure SQL firewall (simplest), or
- Attach a VPC connector with Cloud NAT to get a static egress IP, then
  allowlist that IP (tighter, costs more)

Confirm the Azure region for `db-PersonalAssistants`. The API makes a SQL round
trip per request, so cross-region latency dominates anything saved on compute.
`us-east1` assumes the database is in or near **East US**; if it is elsewhere,
reconsider the Cloud Run region.

## 5. Custom domain

**Cloud Run > Manage Custom Domains > Add Mapping**: `gameteam-api` to
`api.gameteam.net`.

Google returns a `CNAME` record to add at the registrar. Certificates provision
automatically once DNS resolves, which takes 15 minutes to a few hours.

## 6. Verify

```bash
curl https://api.gameteam.net/health    # {"status":"healthy","database":"connected"}
curl https://api.gameteam.net/docs      # FastAPI Swagger UI
```

## Deploying afterwards

Pushing to `main` triggers the Cloud Build trigger created in step 2. GitHub
Actions runs the test suite on pull requests and pushes but does not deploy.

`deploy.sh` is for manual deploys from a workstation with `gcloud` and Docker:

```bash
PROJECT_ID=your-project-id ./deploy.sh
```

It defaults to `REGION=us-east1`.

> The script uses `gcloud run deploy --update-env-vars`, not `--set-env-vars`.
> `--set-env-vars` replaces the entire environment of the service, which would
> silently erase the Azure SQL credentials configured in step 3. The deploy
> would still report success and the service would then fail on its next
> database call. Keep this in mind for any manual `gcloud run deploy` too.

## Cost notes

At min-instances 0 with request-based billing, an idle service costs nothing
beyond image storage in Artifact Registry. The free tier (180,000 vCPU-seconds,
360,000 GiB-seconds and 2 million requests per month) is shared across all
services on the billing account.

If you ever set min-instances to 1, switch to instance-based billing: the Tier 1
instance rate is 25% below the request-based active rate and carries no
per-request fee.
