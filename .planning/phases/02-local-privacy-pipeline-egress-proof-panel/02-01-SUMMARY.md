# Phase 2 verification

The collector constructs approved metadata from an allow-list and masks known credential formats in its local preview. The loopback proof panel retrieves a retained record by UUID and shows its exact approved bytes, SHA-256 digest, and delivery state. The preview holds at most 500 records for 15 minutes. Delivery remains direct until the Phase 3 outbox.

V03 passed for the tested inputs. The suite checked credential masking, forbidden nested fields, local access restrictions, retention, exact outbound bytes, and the persisted SaaS receipt. Edge opened the separate proof window and used its UUID and digest to check both mismatch and match in the dashboard. The test forwarded SaaS requests through a CA-verified HTTP client and preserved the credentials entered in the dashboard. The dashboard build and seven frontend checks passed.

The digest comparison is limited to the selected body. The privacy assertions independently check that synthetic secret markers and unapproved fields are absent. The official organizer stream remains pending for V00. See [local startup and demo instructions](../../../docs/PHASE1.md).
