# AGENTS.md

## Scope

These instructions apply to the entire `abdulbasit742/aroob-locator` repository.

Project: **Aroob Locator**, a consent-first, short-lived FastAPI location-sharing service.

## Architecture

- `app.py`: HTTP boundary, rate limits, security headers, and static pages
- `locator/core.py`: capability lifecycle and latest-point-only retention
- `web/`: same-origin UI with no remote executable assets
- `tests/`: lifecycle, authorization, API, and source-contract checks
- `scripts/security_check.py`: repository security guard
- `render.yaml`: reviewed single-process deployment baseline

## Commands

- install: `python -m pip install --requirement requirements-dev.txt`
- test: `pytest`
- compile: `python -m compileall -q app.py locator scripts tests`
- JavaScript syntax: `node --check web/assets/index.js && node --check web/assets/share.js && node --check web/assets/viewer.js`
- security scan: `python scripts/security_check.py`
- run: `uvicorn app:app --reload`

## Safety rules

1. Never add public location lookup, session enumeration, background tracking, or identity/phone-number search.
2. Keep acceptance, upload, and viewer capabilities separate and out of URLs sent to the server.
3. Preserve explicit consent, default approximate precision, bounded expiry, latest-point-only retention, and stop/erase controls for both sides.
4. Do not add analytics, remote scripts, automatic map tiles, reverse geocoding, SMS token transport, or third-party APIs without documenting the privacy boundary and obtaining an explicit product requirement.
5. Never log authorization headers, capability values, request bodies, or coordinates.
6. Persistent or multi-instance storage requires explicit TTL, deletion, encryption, authorization, and threat-model review.
7. Use only synthetic coordinates in tests and documentation.

## Completion checklist

- all tests, compile checks, JavaScript syntax checks, and the security scanner pass
- no archive-only source or generated deployment artifact is committed
- no capability or coordinate appears in logs, docs, fixtures, query strings, or public endpoints
- README and security audit match the actual retention and deployment behavior
