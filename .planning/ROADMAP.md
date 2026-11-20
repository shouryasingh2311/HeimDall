# Roadmap: one eight-hour integrated prototype

All eight phases remain. They are capability/acceptance groups, not sequential blocking work. Read TEAM_EXECUTION.md and each MEMBER guide for executable work queues.

| Phase | Accountable | Integration target | Acceptance |
|---|---|---|---|
| 1 Core architecture/TLS/tenant scope | M1 | G0-G1 | V00,V01,V02 |
| 2 Local privacy and proof | M1; M3 local view, M2 receipt view | G1-G2 | V03 |
| 3 Durable outbox/dedup/event-time policy | M1; M3 fault tests | G2 | V04,V09 |
| 4 Metrics/health/actual performance | M1; M2 browser timing | G2-G3, final G5 | V05,V07,V10 |
| 5 Statistical AIOps/security/correlation | M1; M3 controls, M2 evidence UI | G3 | V06,V08 |
| 6 Approved demo action/snapshot rollback | M1; M3 helper, M2 controls | G4 | V11 |
| 7 Organizer adapter/eight scenario verifier | M3; M1 protected plumbing | Start G0, complete G4-G5 | V00,V03-V12 |
| 8 Live operations UI/judge evidence | M2; M1 integration, M3 runbook | Start G0, complete G5-G6 | V12,V13 and UI evidence |

## Gates

G0 0:30 contracts/ownership agreed; G1 2:00 one event visible end-to-end; G2 3:30 privacy/reliability/health; G3 5:00 minimal AIOps; G4 5:45 all eight scenario behaviors; G5 7:00 acceptance evidence/fixes; G6 8:00 clean-start rehearsal and presentation.

No phase is complete merely because its files exist. If external organizer data is missing, label the gate blocked for compatibility and demo fallback honestly. Cut optional polish/connectors, not required behavior. The full production vision is deliberately out of scope.
