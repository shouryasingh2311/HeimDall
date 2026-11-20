# Phase 6 verification

An operator can request and approve a fixed 1.5× memory capacity change for the allowlisted demo API source. The collector polls over verified HTTPS and commits the simulated capacity, snapshot, and command receipt in one SQLite transaction. A repeated command returns the saved result. Rollback restores the exact pre-action capacity.

| Check | Observed evidence |
|---|---|
| V02 scope and policy | The live API rejected the wrong roles, the wrong tenant, non-demo telemetry, an unconfigured target, arbitrary parameters, premature rollback, and conflicting results. |
| V11 execution and recovery | Approval stayed pending while the collector was offline. After it restarted, new telemetry dropped from roughly 98% memory utilization to 65%. The larger capacity survived another restart, and continued normal telemetry resolved the original incident. |
| V11 rollback | The Edge dashboard loaded the real action ID and requested rollback. The same local snapshot restored 1,024 MB from 1,536 MB and fresh telemetry returned to roughly 98%. The audit log recorded the operator and collector transitions in UTC. |
| V11 idempotency and rate limit | Duplicate clicks and results reused the recorded state. Reopening local storage after a simulated lost acknowledgement did not reapply the operation. Three proposals exhausted the hourly quota, and an existing successful action could still be rolled back. |

The tested playbook changes the simulated capacity in the demo generator. It runs only in the explicit memory simulation mode. Organizer input and final scenario rehearsal remain open.
