# Phase 3 verification

The collector commits canonical approved bytes to SQLite before HTTPS delivery. Matching receipts release individual rows. Retries keep the original bytes and UUID, while rejected bodies and conflicts stay in quarantine. The configurable cap pauses input and includes quarantined rows. Heartbeats run independently and report pending depth.

| Check | Observed evidence |
|---|---|
| V04 | Real SaaS outage for 30 seconds while the collector generated inputs. Both processes restarted using the same databases. Expected and received UUIDs and bodies matched exactly, with one SaaS row per record. |
| V04 lost ACK and pressure | A simulated lost response after a real SaaS commit left the row pending. Reopening the outbox and replaying returned a duplicate receipt. A one-record cap paused the producer. |
| V09 metadata | Eight concurrent identical posts returned one acceptance and seven duplicates. A changed body for the same UUID was quarantined. Older and equal-time replays stayed historical, preserving the latest source state. |

Alert and incident deduplication still needs Phase 5 integration. The tests cover process restarts with functioning local storage. Official organizer input is still pending.
