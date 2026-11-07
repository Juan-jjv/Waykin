# WayKin threat model (draft for the pitch)

_Draft by A4 for S2. Every "protected" line has a test in `backend/tests/privacy/test_privacy.py`._

## What's protected
| Promise | How | Test |
| --- | --- | --- |
| **The server operator never sees a walker's live location** (e2ee mode) | AES-GCM-256 key generated in the walker's browser; each update encrypted with a fresh 12-byte IV and AAD bound to the journey id and sequence number. The key travels only in the share link's `#fragment`, which browsers never send to the server. The relay checks the envelope's shape and forwards it byte for byte; it never parses the ciphertext. | `test_e2ee_server_holds_only_ciphertext`, `test_ciphertext_bound_to_journey_and_seq` |
| **Nothing is kept after a walk ends** | Only the latest encrypted message is held, in memory. On arrival, stop, DELETE or expiry the journey is purged and every socket closed. No database, no disk. A restart loses nothing because there is nothing to lose. | `test_purged_after_journey_ends[end/delete/expiry]`, `test_demo_reset_purges_everything` |
| **Only the walker can end or publish a walk** | Separate walker and viewer tokens; the server stores only their SHA-256 hashes and compares in constant time. | `test_wrong_token[*]`, `test_expired_token`, `test_delete_with_viewer_token`, `test_raw_tokens_never_stored` |
| **Reroutes aren't linked to a journey** | The reroute request has no journey id, token or cookie fields (extra fields are rejected), and the handler never touches journey state. The client decides when it is affected by a closure; the server only broadcasts closures. | `test_reroute_rejects_identifiers`, `test_reroute_unlinked_*` |
| **No locations in logs** | No access log; our own log line has only method, route template, status and latency. | `test_no_coordinates_in_logs` |
| **Only published intersection-level points** | `/api/incidents` returns exactly the source's points, no addresses. EPS files are gitignored and never committed. | `test_incidents_only_published_points_*`, `test_no_data_files_tracked` |

## What's NOT protected (say this out loud)
- **Anyone holding the share link can follow the walk.** The link is the key. Share it like a house key.
- **The server sees metadata:** journey ids, when a walk starts and ends, message rate and size, and IP addresses.
- **Route and reroute requests reveal origin, position and destination to the server in transit.** They are not stored or logged, but the server must see them to compute a route.
- **A compromised phone or browser defeats everything** (malicious extensions, malware, someone with the unlocked phone).
- **Plaintext fallback mode (`RELAY_PLAINTEXT=1`) has no confidentiality.** If we ship it, we drop the encryption claim.
- Hosting/TLS-terminating proxies (e.g. a tunnel provider) see the same metadata the server sees.
