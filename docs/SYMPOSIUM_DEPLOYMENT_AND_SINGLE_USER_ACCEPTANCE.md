# Symposium deployment and single-user acceptance runbook

This runbook is the deployment and acceptance gate for the bounded symposium
demonstration. It is deliberately organized around a new workshop user and a
fresh browser session, rather than administrator-owned pre-existing assets.

It does not authorize use of production patient data. `/ohdsi` inputs must not
contain patient-level information.

## 1. Symposium 2026 release manifest

This is the final source record for the successful OHDSI 2026 Global Symposium
demonstration. Record the deployed Git commit and build artifact digest for
every component in the deployment record. The Study Agent, Strategus-assistant,
and ACP-client releases use the shared `ohdsi-global-symposium-2026` release
tag; the code commits exercised in the demonstration are listed here as well.

| Component | Commit to deploy | Required role |
| --- | --- | --- |
| [Study Agent](https://github.com/OHDSI/StudyAgent) (ACP and MCP) | `f777963953132c47b91bf56336328be7265a3da5` | ACP flows, MCP tools, prompts, index/vocabulary access |
| [WebAPI3](https://github.com/vinci-ohdsi/WebAPI3) | [`f7c0d5fabad5fd052461362b8ab3c502e3c22929`](https://github.com/vinci-ohdsi/WebAPI3/commit/f7c0d5fabad5fd052461362b8ab3c502e3c22929) | authorization, provenance/session persistence, ACP proxy |
| [Atlas3](https://github.com/vinci-ohdsi/Atlas3) | [`da4cc12e46d7ab7e393f08d657855a65540fbe68`](https://github.com/vinci-ohdsi/Atlas3/commit/da4cc12e46d7ab7e393f08d657855a65540fbe68) | browser user interface |
| [slashOhdsiAcpClient](https://github.com/OHDSI/SlashOhdsiAcpClient) | `8d02e87cbd78b04e25c11f58588a873beff3838e` | R ACP client; confirm the substantive parent history is included |
| [slashOhdsiStrategusAssistant](https://github.com/OHDSI/SlashOhdsiStrategusAssistant) | `e8283e687141dc00b94889eeabf97008046b03d4` | R incidence/cohort-method shells; confirm the substantive parent history is included |
| [StudyAgent-Conference-ChatKit](https://github.com/rkboyce/StudyAgent-Conference-ChatKit) | [`a7b99badd38f45c4ddb5a1c91696559e17a2afc5`](https://github.com/rkboyce/StudyAgent-Conference-ChatKit/commit/a7b99badd38f45c4ddb5a1c91696559e17a2afc5) | interactive conference demonstration client |

The public, coordinated component record is maintained in the
[AtlasWebAPISandbox Symposium 2026 manifest](https://github.com/vinci-ohdsi/AtlasWebAPISandbox/blob/dad39d7dfa4d4e95db2bd5ef8e445b0ac77ebcb4/demos/study-agent-demo/releases/ohdsi-global-symposium-2026.json).
It is a source-provenance record, not a production deployment recipe. The
normal release tag identifies the final documentation commit in each released
OHDSI repository; use the component commits above to reproduce the code that
was exercised during the demonstration.

Before deployment, write down the following alongside the table: the image or
JAR SHA-256 values, the exact R library path and package versions, the phenotype
index build/version, vocabulary/CDM source, LLM model identifier and serving
configuration, and the public Atlas, WebAPI, ACP, MCP, and RStudio URLs.

## 2. Deployment checklist

### A. Preserve and validate the target host

- [ ] Take a recoverable backup/snapshot of the WebAPI database schemas and
  persistent Study Agent workflow/output storage.
- [ ] Record the currently running service versions and health endpoints.
- [ ] Confirm the EC2 security group, reverse proxy, HTTPS certificates, DNS,
  and public origins. Do not place tokens, API keys, database credentials, or
  RStudio credentials in QR links.
- [ ] Confirm the target OMOP vocabulary and phenotype-index directories are
  readable by the MCP service account, and the configured output/work roots are
  writable only where needed.

### B. Install immutable application artifacts

- [ ] Check out the five commits above in their respective repositories.
- [ ] Build WebAPI from its checked-out commit and retain the resulting JAR/image
  identifier.
- [ ] Build Atlas with `npm ci`, `npm run lint`, `npm run type-check`, and
  `npm run build`; deploy only the generated production bundle from this commit.
- [ ] Install both R packages from their checked-out commits into the workshop
  R library. Start a clean R session and verify `packageVersion()` and package
  source paths, rather than assuming the source checkout is in use.
- [ ] Verify the shared HADES/R library contains the pinned/known working
  Strategus, CohortIncidence, CohortMethod, CohortGenerator, DatabaseConnector,
  Capr, CirceR, and SqlRender versions. Do not run `renv::restore()` as part of
  this release exercise.

### C. Configure services and apply WebAPI state

- [ ] Put Study Agent non-secret settings in `config.yaml`; retain secrets only
  in the host-approved secret store or private environment. In particular,
  retain the LLM credential outside YAML.
- [ ] Configure MCP vocabulary/OMOP connectivity, phenotype index, model endpoint,
  output roots, and logging. Keep LLM prompt/response logging off during the
  workshop unless a time-limited, approved diagnostic need arises.
- [ ] Configure WebAPI with the ACP base URL and the actual public Atlas origin.
  Configure reverse-proxy/CORS behavior for the public HTTPS origin; do not
  embed ACP addresses or credentials in Atlas client code.
- [ ] Apply the WebAPI migrations before exposing Atlas. Verify that the Study
  Agent workflow/provenance migrations and permissions are present, including
  `study-agent:concept-set-assist` and
  `study-agent:cohort-definition-assist`.
- [ ] Verify that the `Study Agent` role grants normal new-concept-set and
  new-cohort creation plus both assistance permissions. Entity ownership rules
  remain in force.
- [ ] Configure each workshop R account's `.Rprofile` or equivalent protected
  session environment with:

  ```sh
  STUDY_AGENT_WEBAPI_URL=https://<public-host>/WebAPI
  STUDY_AGENT_ATLAS_URL=https://<public-host>/Atlas3
  STUDY_AGENT_WEBAPI_API_KEY=<that-user's-one-time-issued-key>
  ```

  The API key must be readable only by that workshop account. It must never be
  written to generated workflow artifacts, sent to ACP/MCP, embedded in the
  Atlas URL, or displayed in facilitator logs.

### D. Start in dependency order and prove reachability

- [ ] Start/restart MCP after tool, retrieval, index, prompt, or MCP-config
  changes. Confirm its health endpoint and vocabulary lookup against the target
  source.
- [ ] Start/restart ACP after MCP and after ACP server/client-contract changes.
  Confirm that it reaches MCP and the configured LLM shim without exposing
  credentials in logs.
- [ ] Start WebAPI only after its migrations/configuration are current; verify
  its ACP connection and Study Agent permission endpoints.
- [ ] Publish the Atlas production bundle, invalidate any relevant cache, and
  use a hard-refresh/new browser profile to verify that this build calls the
  matching WebAPI.
- [ ] Restart RStudio Server only if its packages, `.Rprofile`, or service
  environment changed. Start a clean user session after the restart.
- [ ] From an external browser, verify HTTPS access, login, and the public URLs
  for Atlas and RStudio. From the RStudio host-network session, verify ACP is
  reachable at the configured endpoint.

## 3. Scripted test-workshop-user and API-key rehearsal

Perform this once with a disposable user before creating the participant pool.
The goal is to test the production account model, role assignment, API-key
issuance, and R-to-Atlas handoff together.

### Account provisioning contract

The account provisioner must be idempotent and must:

1. Create or enable `symposium-test-01` in the **configured WebAPI
   authentication provider** (database authentication, LDAP/OIDC provisioning,
   or other configured mechanism).
2. Create/synchronize the matching WebAPI security user and assign the least
   privilege workshop role, including the `Study Agent` role and normal
   concept-set/cohort creation rights.
3. Create the matching non-administrative RStudio/Linux account and private home
   directory, if RStudio is part of the account model.
4. Never print a password, API key, connection string, or secret to standard
   output, shell history, source control, or a shared file.

Account creation is intentionally deployment-specific. Use the approved identity
provider's administrative API or a parameterized, access-controlled database
provisioning job; do **not** make the R shell or ACP create WebAPI users.

### API-key issuance contract

WebAPI exposes personal-key issuance only to an authenticated principal:

```text
POST /WebAPI/user/apikeys
{ "name": "symposium-r-handoff", "description": "single-user rehearsal", "expiresInDays": <event-window> }
```

The response contains `rawKey` exactly once. The provisioning wrapper must
capture it directly into the test user's protected R environment file (mode
`0600`) and retain only the public `keyIdentifier` in its audit record. Do not
try to manufacture an API-key database row or hash outside WebAPI.

### Rehearsal steps

- [ ] Run the account provisioner twice. The first run creates the account;
  the second makes no duplicate user, role, or RStudio account.
- [ ] Log into Atlas as `symposium-test-01` in a fresh browser profile. Verify
  it is not an administrator and can create/save its own concept sets and
  cohort definitions.
- [ ] Authenticate as that same user and call `POST /user/apikeys` once. Save
  the raw key directly to the protected test-user R environment; record only
  the returned public identifier and expiry date.
- [ ] Verify `GET /user/apikeys` lists the public identifier but never a raw
  secret. Use a harmless authenticated WebAPI request with `X-API-KEY` to prove
  the key works, then verify `last_used_at`/equivalent audit metadata advances.
- [ ] Start a clean RStudio session as the test account. Confirm the three
  `STUDY_AGENT_*` values are present without printing the key.
- [ ] Complete the R-to-Atlas review/resume case in section 4. This is the
  actual end-to-end proof that the user, role, API key, and public links agree.
- [ ] Revoke the rehearsal key with `DELETE /user/apikeys/{keyIdentifier}` and
  verify it can no longer authenticate. Reissue a final key only when preparing
  the real participant account.

## 4. Single-user cloud acceptance matrix

Use the disposable test account, a clean browser profile, unique asset names
prefixed `symposium-test-01-`, and a fresh RStudio session. Record the asset
IDs, review IDs, timestamps, expected result, actual result, and relevant
request IDs/log locations. Do not record raw API keys or user-entered sensitive
information.

| ID | Journey | Acceptance evidence |
| --- | --- | --- |
| A1 | Atlas landing `/ohdsi` → direct concept-set help | A concise response renders; expandable details and follow-up work; normal concept search/save works. |
| A2 | Atlas landing `/ohdsi` → AI phenotype search → Circe-ready candidate | A candidate opens as an unsaved normal Atlas cohort draft; user can inspect and save it under a compliant title. |
| A3 | Atlas landing `/ohdsi` → CIPHER/non-computable candidate as evidence | Evidence is clearly advisory; source/provenance displays; scope choices remain human-confirmed; concept-set review opens the normal drawer with retained `/ohdsi` context. |
| A4 | Supported new-computable patterns | Test a direct Condition index, a Drug plus supporting Condition, and a Condition plus Visit qualifier. Each requires explicit scope and policy confirmation, technically validates before draft creation, and saves/reloads with provenance. |
| A5 | Complex/unprojectable request | Example: multiple myeloma with exclusions/additional logic. The UI explains that normal Atlas editing is needed, preserves the `/ohdsi` task context into concept-set and cohort editing, and does not claim the manual additions are technically or clinically validated. |
| A6 | Phenotype-library browse | Direct library browse, candidate details, computability labels, and both executable/evidence transitions behave correctly. |
| R1 | Incidence shell: computable/PL source | The shell accepts study intent, selects/imports a cohort, retains readable labels, and returns safely to the next role. Do not execute participant analyses. |
| R2 | Incidence shell: R-to-Atlas review/resume | Use `create`, confirm scope, request an Atlas review, curate/save the user-owned concept set, resume R, and verify the immutable approved snapshot/checksum is recorded. |
| R3 | R shell: supported multi-component scope | Exercise one supported Condition/Visit or Drug/Condition pattern. Each review opens a distinct Atlas asset and R resumes only after all required snapshots are accepted. |
| R4 | R shell: unsupported/no-match path | The shell gives a clear Atlas/manual-authoring next step or safe recovery; it does not fabricate a computable definition. |
| X1 | Authorization and recovery | Refresh/back navigation, expired/revoked API key, denied permission, duplicate title/409 save, and cancelled review give understandable recoverable outcomes without data loss. |

For A4 and R3, do not treat technical ACP validation, a generated Circe draft,
or a successfully saved Atlas asset as clinical validation.

## 5. Exit, freeze, and scale decision

- [ ] Every acceptance row has a recorded pass, or the feature is removed from
  the participant-facing path and its fallback is documented.
- [ ] Re-run at least the R-to-Atlas handoff and one Atlas-only path after a
  service restart and browser refresh.
- [ ] Freeze commits, configuration digests, migrations, R library versions,
  index/vocabulary version, and model/serving settings after the last passing
  rehearsal.
- [ ] Create the remaining workshop accounts and personal API keys by the same
  tested provisioner. Give each account its own R home, `.Rprofile`, and API
  key; never use a shared API key.
- [ ] Before conference use, conduct a separate 10–20-user concurrency smoke
  test against the frozen AWS stack. A capacity failure is a no-go for the
  single-host plan; use the documented scale-out/load-balancer contingency.
- [ ] Prepare QR links, facilitator recovery steps, health-check/log locations,
  and a pre-created fallback demonstration. Validate the QR links from an
  external device and unrecognized browser session.

