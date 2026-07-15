# Security policy

Aroob Locator handles precise location data and capability links. Report suspected authorization bypasses, capability disclosure, unintended retention, or silent third-party requests privately to the repository owner. Do not include real coordinates or working capability links in a public issue.

## Supported boundary

The current version is a single-process, short-lived service. It does not support persistent tracking, background mobile collection, account recovery, public sharing, multi-instance state, or long-term route history.

## Deployment requirements

- use HTTPS outside localhost
- keep access and proxy logs free of request bodies and authorization headers
- do not place capability values in query strings
- review `ALLOWED_ORIGINS`; wildcard credentialed CORS is not supported
- treat process memory, crash dumps, and observability tooling as sensitive
- rotate or end a share immediately if either link is disclosed
