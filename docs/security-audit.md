# Changed-area security audit

## Fixed

- unpacked the opaque ZIP into reviewable source files
- removed public latest-location lookup by guessable user ID
- separated acceptance, upload, and viewer capabilities
- made invitation acceptance one-time and bounded all shares to 5–120 minutes
- added explicit stop/revoke behavior for both participants
- erased the latest point and upload capability on stop or expiry
- changed the default to approximate precision
- rejected stale, future, invalid, and out-of-range observations
- removed the SMS fallback that exposed coordinates and the invitation token in a message body
- removed automatic Leaflet/OpenStreetMap tile requests; external map navigation is explicit
- removed inline and remote executable assets under a restrictive Content Security Policy
- added same-origin defaults, optional explicit CORS, request limits, no-store responses, and security headers
- disabled automatic production deployment and added a health check
- added API, lifecycle, source-contract, and security-scanner verification

## Residual risks

- the server can read the latest point in process memory; there is no end-to-end encryption
- bearer links grant access to anyone who obtains them until stop or expiry
- in-memory rate limiting and state do not coordinate across multiple workers or instances
- a process dump, malicious server operator, compromised browser, or unsafe observability tool can expose location data
- automatic stop on page hide is best effort; the server-side expiry remains the final backstop
- the external OpenStreetMap link discloses coordinates only after the viewer explicitly opens it

Do not present this service as suitable for covert tracking, emergency dispatch, continuous family monitoring, or safety-critical use.
