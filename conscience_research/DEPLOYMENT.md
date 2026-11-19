# Production deployment use case

This project can run as a real-time conscience guardrail service in front of an AI action executor.

## Reference architecture

- Client app sends proposed actions to `/v1/guardrail/decision`
- Conscience service returns `allowed`, `risk_band`, and controls
- Executor proceeds only if `allowed=true`
- Evaluator endpoint `/v1/evaluate` is used by ops for periodic benchmark health checks

## Deployment options

### Option 1: local process

```bash
cd conscience_research
cp prod.env.example .env
# Edit values if needed
set -a && source .env && set +a
python production_service.py
```

### Option 2: Docker

```bash
cd conscience_research
docker build -t conscience-research:prod .
docker run --rm -p 8080:8080 --env-file .env conscience-research:prod
```

`.dockerignore` keeps `.env`, key files (`research.key`, `*.pem`) and runtime state (history, norms, audit log) out of the image, so pass settings at run time with `--env-file`. Without `CONSCIENCE_ADMIN_TOKEN`, admin calls are refused: requests reach the container from the Docker network, not from loopback.

### Option 3: Docker Compose

```bash
cd conscience_research
docker compose up --build -d
```

`docker-compose.yml` sets only the host and port. To pass the rest of `.env`, add `env_file: .env` under the `conscience-research` service.

## Environment variables

`prod.env.example` lists them all with defaults. Flags accept `1`, `true`, `yes` or `on`; anything else is off.

| Variable | Default | Effect |
|---|---|---|
| `CONSCIENCE_HOST`, `CONSCIENCE_PORT` | `0.0.0.0`, `8080` | Address the service listens on |
| `CONSCIENCE_ORACLE_MODE` | `baseline` | Oracle for `python agent.py`: `baseline` or `third_eye`. The service ignores it; `/v1/evaluate` takes `oracle_mode` in the request |
| `CONSCIENCE_SCENARIO_EDIT_MODE` | `off` | `live` applies runtime scenario edits in `python agent.py` (baseline oracle only). The service takes `scenario_edit_mode` in the request |
| `CONSCIENCE_ADMIN_TOKEN` | unset | Bearer token required for state-changing calls. Unset: only loopback clients may change state |
| `CONSCIENCE_ALLOW_UNAUTH_ADMIN` | `0` | Trust every client for state changes. Local Docker development only |
| `CONSCIENCE_AUDIT_FILE` | `decision_audit.jsonl` | Hash-chained decision audit log |
| `CONSCIENCE_LOAD_NORMS` | `0` | Load `norms.json` at startup, so saved thresholds and weights survive a restart |
| `CONSCIENCE_PERSIST_NORMS` | `0` | Also save `norms.json` after every binding update. Threshold changes are always saved |
| `CONSCIENCE_DEBUG` | `0` | Print each domain's score, effective threshold and BLOCK/CLEAR status to stdout |

In Docker, `norms.json`, the history and the audit log are written inside the container and are lost when it is removed. Mount a volume if you need to keep them.

## API quickstart

### Health

```bash
curl -s http://localhost:8080/health
```

### Evaluate baseline oracle

```bash
curl -s -X POST http://localhost:8080/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"oracle_mode":"baseline"}'
```

### Evaluate third-eye oracle

```bash
curl -s -X POST http://localhost:8080/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"oracle_mode":"third_eye"}'
```

### Guardrail decision (dry-run)

```bash
curl -s -X POST http://localhost:8080/v1/guardrail/decision \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "disclosed_pii_without_consent",
    "context": {"agent_did_this": true, "harm_occurred": true},
    "dry_run": true
  }'
```

### Guardrail decision with state update

Evaluation is open to any caller, but changing normative state is an admin
privilege. A request that sets `dry_run: false`, `apply_binding_update: true` or
`record_episode: true` gets `403` unless it is authorised: with
`CONSCIENCE_ADMIN_TOKEN` set, send `Authorization: Bearer <token>`; with it
unset, only loopback clients are trusted. The same rule covers
`POST /v1/reset` (GET is refused) and `POST /v1/norms/threshold`.

An action the classifier cannot map is returned as `verdict: "escalate"`,
`allowed: false` (fail closed). Responses also list any code-level hard floors
(`hard_floors`, HF1–HF4) that fired.

```bash
curl -s -X POST http://localhost:8080/v1/guardrail/decision \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $CONSCIENCE_ADMIN_TOKEN" \
  -d '{
    "action": "deliberate_moderate_deception",
    "context": {"intent": "deliberate"},
    "dry_run": false,
    "apply_binding_update": true,
    "record_episode": true
  }'
```

## Production hardening checklist

- Put TLS and auth in front of the service (API gateway/ingress)
- Restrict network access to trusted internal clients
- Send request/decision logs to centralized observability
- Alert on drop in `/v1/evaluate` `conscience_score`
- Back up `moral_history.jsonl` **together with `research.key`** if using continuity recording. New episodes are Fernet-encrypted with that key, so the history cannot be read without it. Both files are created in the service's working directory, and both are gitignored: never commit the key.
- Roll out using canary or blue/green and compare decision deltas

## Suggested SLOs

- Availability: 99.9%
- p95 latency for `/v1/guardrail/decision`: < 100ms
- Error rate: < 0.1%
- Score drift alert threshold: conscience_score < 0.90
