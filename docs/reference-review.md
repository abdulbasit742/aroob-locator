# Reference review

Reviewed on 2026-07-15.

## OwnTracks Recorder

Adopted: a clear collection/read API boundary, self-hosted operation, and explicit storage behavior. Aroob Locator deliberately stores only one point rather than a location history.

Not adopted: MQTT, user/device directories, persistent files, WebSockets, reverse geocoding, and historical tracks.

## PrivateBin

Adopted: high-entropy capability links, explicit warnings that links are bearer secrets, short expirations, and deletion semantics. Capability values are placed in URL fragments so ordinary HTTP request logs do not receive them.

Not adopted: browser encryption and persistent encrypted blobs. This small service instead holds one short-lived point in process memory and clearly documents that server memory remains trusted.

## PairDrop

Adopted: temporary rooms/capabilities, explicit recipient acceptance, and easy termination rather than invisible persistent connectivity.

Not adopted: device pairing, WebRTC, TURN, persistent browser storage, and peer discovery.

## Result

The implemented vertical slice is intentionally smaller than all three references: two capability links, one consent action, one latest point, one expiry, and a stop action available to both participants.
