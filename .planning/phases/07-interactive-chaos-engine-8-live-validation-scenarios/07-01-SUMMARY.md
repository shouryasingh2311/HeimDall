# Phase 7 verification

The opt-in collector serves a loopback scenario page. The runner injects synthetic inputs through the normal collector, outbox, and SaaS ingest. It checks committed payloads, alerts, and action state before publishing a typed summary. The operator dashboard and CLI read those stored summaries. The operator still approves and rolls back the memory action.

| Coverage | Live rehearsal |
|---|---|
| V03/V06 | Matched the exact body digest while excluding the seeded secret. Four failed logins stayed local and the fifth produced one typed summary. |
| V04 | Paused metadata sending for 30 seconds while heartbeats continued. All 75 payload IDs and digests matched after recovery. |
| V07/V08 | Verified the network alert deadline, the single-spike control, the sustained deviation, and grouping with the independent alert held separate. |
| V09/V11 | Observed a duplicate receipt and a historical late event. Verified approval, fresh recovery telemetry, and restoration after rollback. |
| Repeat and isolation | Reset preserved central evidence. A repeated scenario used fresh IDs. The wrong role and tenant could not read or publish another tenant's results. |

The official organizer stream is unavailable, so V00 remains blocked. These results use the labelled synthetic source. Final rehearsal and the full submission are separate Phase 8 work.
