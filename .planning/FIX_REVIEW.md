# Review findings addressed by the revised planning

This is a planning correction log, not evidence of implemented fixes.

| Prior finding | Planning correction | Evidence still required |
|---|---|---|
| 24h assumptions; serial phases | Eight-hour gates, three concurrent owned workstreams, phase contributions for everyone | Gate timing during build |
| Custom stream mistaken for organizer stream | Actual adapter task and V00 external dependency; labelled fallback | Organizer sample test |
| Central raw-data bridge | Separate loopback inspector and metadata-only SaaS view | V03 network/storage inspection |
| Contradictory schema/IDs | CONTRACTS.md strict nested fields/UUID/security/heartbeat; REQUIREMENTS.md single ID catalog | Model and adapter tests |
| Ingest latency called dashboard latency | First-visible-render receipts, cohorts and clock assumptions | V10 |
| Loss window and volatile dedup | Persist-before-send, WAL/FULL, unique tenant/UUID and transactional analytic effects | V04/V09 |
| Identity/region/TLS underspecified | Role/token binding, scope every route, verified CA/SAN configuration; residency design-only | V01/V02/V13 |
| Unsupported causal confidence | One explicit detector, graph constraints, reproducible heuristic evidence score | V08 negative controls |
| Incomplete health/staleness | Complete thresholds, severity precedence, heartbeat/source separation, deadline margin | V05 |
| Tamper-evident/immutable claims | Exact-body receipts and durable application audit; no stronger integrity claim | V03/V11 |
| Imports/grep/masked builds as proof | Behavioral test catalog and genuine build failure gate | V00-V13 |
| Excess remediation/inverse restart | One demo-only resource action and persistent snapshot rollback | V11 |
| Missing setup/API/UI integration | Explicit scaffolding, dependency locks, API inventory and early vertical slice | G1/V12 |
| Inflated originality/competitor claims | Conservative evidence-focused differentiation and corrected research | No market uniqueness claim |
| Requirement count and IDs | 43 requirements, stable IDs, explicit owners/checks | Documentation audit |
| Multi-agent editing collisions | Owned files, feature branches, small PRs, lead-only contract/main integration | Team adherence |

## Tooling migration

Old plans referenced unavailable local GSD execution templates and single-agent conventions. This user-authorized planning revision uses repository-contained team guides and ordinary Git instead. .claude/CLAUDE.md and team-config.json point to this workflow; no model-specific slash command is a prerequisite. The original config.json is preserved for optional GSD compatibility, but its single-agent branch settings do not control this manual team workflow. Application implementation remains unstarted.

The two extracted guide text files are regenerated from the provided actual PDF in this revision to remove paraphrased-source drift. PDF wording describes a 24-hour event; the user's eight-hour build budget still governs execution.

## Open external dependencies and limits

- Organizer stream schema/transport/sample and final numeric target confirmation.
- Teammates need repository collaborator access or forks; never share credentials.
- Certificate trust, Python/Node versions and actual performance verified at kickoff.
- Single-host region policy is not geographic residency.
- All code tests, demo results and claims remain unverified until implemented.
