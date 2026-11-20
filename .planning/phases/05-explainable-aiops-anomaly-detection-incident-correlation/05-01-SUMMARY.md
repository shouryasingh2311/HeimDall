# Phase 5 verification

Heimdal counts fresh authentication failures inside the collector and sends only a typed summary after the fifth failure within ten seconds. The SaaS combines static severe thresholds with a rolling statistical baseline. Alerts, incident membership, baseline state, and the accepted payload commit together. The dashboard links each signal to its real payload and displays its observed value, baseline, and score inputs.

| Check | Observed evidence |
|---|---|
| V06 | Four failures and five spaced failures produced zero alerts. The fifth fresh failure in a burst produced one summary across a collector restart and duplicate input. The stored SaaS payload contained no IP address, username, or raw text. |
| V08 detection | Zero alerts on 12 normal control points and on one benign spike. Two consecutive CPU readings below the static severe threshold triggered a warning at z=7 with a baseline mean of 20 and sigma floor of 1. |
| V08 correlation | Two related alerts became one incident, a 50% reduction in that related sample. The simultaneous unrelated alert stayed separate. A dependency and its event order reproduced the 100-point heuristic score. Duplicate and late payloads had no new analytic effects. |
| Recovery and persistence | Each affected source needed five healthy eligible samples before resolution. A transaction failure rolled back the payload and its analytic effects. Restart and retry retained the baseline and produced exactly one alert. A full outbox rolled back the triggering auth attempt until a slot opened. |
| V07/V10 timing | A live synthetic packet-loss breach recorded a committed alert with a creation time 26.87 ms after injection in the final same-machine, single-sample test. |

Fresh auth windows are scoped by source and origin. Late and expired auth input does not trigger a live alert. Security recovery needs an explicit recovery signal. Organizer input, the final performance rehearsal, and live remediation remain open.
