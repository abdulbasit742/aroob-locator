# Aroob Locator

Aroob Locator is a small, consent-first location-sharing service. It creates two short-lived capability links: one link lets a recipient explicitly accept and share, while the other lets the inviter view only the latest authorized point.

## Privacy and safety model

- no account directory and no lookup by name, phone number, or user ID
- separate one-time acceptance, upload, and viewer capabilities
- capability values stay in URL fragments or authorization headers, not request paths or query strings
- approximate precision is the default; exact precision requires an explicit choice by the sharer
- only the latest point is kept; no route history is stored
- stop and expiry erase the point and disable further uploads
- all state is process memory, so a restart clears every share
- no analytics, remote scripts, map tiles, or automatic third-party coordinate requests
- both sharer and viewer can stop the share

This is an attended check-in tool, not covert tracking software. Do not use it without the informed consent of the person sharing their location.

## Local setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

python -m pip install --requirement requirements-dev.txt
pytest
python scripts/security_check.py
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

## Flow

1. The inviter creates a share with a private, non-identifying label and a 5–120 minute expiry.
2. The service returns a **sharing link** and a **viewer link**.
3. The recipient opens the sharing link, chooses approximate or exact precision, checks the consent box, and starts sharing.
4. The viewer link can read the latest point while the share is active.
5. Either side can stop the share. The point and upload capability are erased immediately.

Capability links are bearer secrets. Send them through a trusted channel, do not post them publicly, and use HTTPS outside local development.

## API boundary

- `POST /api/shares` — create short-lived capabilities
- `POST /api/shares/{share_id}/accept` — consume the one-time acceptance capability
- `POST /api/shares/{share_id}/locations` — upload with the upload bearer capability
- `GET /api/shares/{share_id}/location` — view with the viewer bearer capability
- `POST /api/shares/{share_id}/stop` — stop with either upload or viewer capability
- `GET /health` — deployment health check; exposes no share data

There is intentionally no session enumeration endpoint and no public latest-location endpoint.

## Deployment

`render.yaml` is provided for a single Render web service. Auto-deploy is disabled so changes are reviewed before release. The service is ephemeral: free-instance sleep, deploys, and restarts clear active shares. Set `FORCE_HTTPS=1` behind an HTTPS proxy. Leave `ALLOWED_ORIGINS` unset for the included same-origin web pages.

A multi-instance deployment requires a privacy-reviewed shared store with explicit TTL and deletion semantics; this repository does not silently add one.

## Verification

```bash
pytest
python -m compileall -q app.py locator scripts tests
node --check web/assets/index.js
node --check web/assets/share.js
node --check web/assets/viewer.js
python scripts/security_check.py
```

See `docs/reference-review.md` and `docs/security-audit.md` for the design rationale and residual risks.
