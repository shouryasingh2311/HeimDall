# Phase 8: Unified Operations Dashboard & Judge Verification Suite — Research

**Researched:** 2026-11-20
**Domain:** Real-Time Operations Dashboards, Side-by-Side Dual View Verification, WebSocket Streaming, Interactive Incident Investigation, Theme-Aware Design
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- Unified Dashboard: Consolidates fleet analytics, health state indicators, real-time latency gauges, active incidents, and scenario controls.
- Side-by-Side Verification: Explicit split view showing `[Raw Local Log with Secret]` vs `[Redacted SaaS Metadata]`, providing unassailable proof of edge data protection for judges.
- Explainable AI Visualizer: Visual representation of contributing signals, Z-score deviation meters, confidence gauges, and step-by-step reasoning chronology.
- Live Scenario Control Panel: Integrated buttons to trigger all 8 live validation scenarios and view real-time automated verification verdicts.

### Claude's Discretion
- Frontend Framework: Next.js 14 / React with Tailwind CSS, Lucide Icons, and Recharts / SVG time-series graphs for low-latency rendering.
- State & Streaming: WebSocket connection to SaaS API (`/ws/dashboard`) updating metrics and health state with sub-second reactivity.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| Central SaaS Dashboard UI | Tier 2 (Central SaaS) | Client Browser | Renders multi-tenant fleet overview, health states, incidents, and SLA metrics |
| Dual-View Comparison Viewer | Tier 2 (Central SaaS) | Tier 1 (Customer Edge) | Pulls sanitized SaaS record and embeds or bridges to local collector egress log |
| Incident & Remediation Modal | Tier 2 (Central SaaS) | Dashboard Tier | Interactive review of explainable recommendations with "Approve & Execute" and "Rollback" buttons |
| Scenario Runner Suite | Dashboard Tier | Chaos Engine | Allows hackathon judges to trigger any test case and view live pass/fail results |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 8 creates the user interface and presentation layer that ties the entire platform together. Designed specifically for the judging evaluation criteria of Checkpoint 3 & 4:
1. **Fleet Health & Real-Time Metrics**:
   - Status header showing active collectors, current health badge (`Excellent` [Green], `Good` [Blue], `Fair` [Yellow], `Poor` [Red]), and p95 latency gauge ($\le 10$s target).
2. **Side-by-Side Egress Proof Viewer**:
   - Addresses the Hackathon Judge's mandatory question: *"Can you show exactly what your local collector sends to SaaS and prove that sensitive data stays within the customer environment?"*
   - Shows raw input logs (with simulated DB credentials / API tokens) in the local collector panel and the clean, allow-listed metadata stream in the SaaS panel.
3. **AIOps Incident & Explainability Drill-Down**:
   - Displays correlated incidents (reducing 10 alerts to 1 incident card).
   - Clicking an incident opens the Explainable AI panel: visual radar/bar chart of contributing signals, baseline deviation deltas, confidence gauge, and human-readable causal reasoning path.
4. **Judge Scenario Control Panel**:
   - Dedicated runner bar with buttons `[Scenario 1: Secret Redaction]`, `[Scenario 2: Outage Reconnect]`, ..., `[Scenario 8: Remediation & Rollback]`.
</research_summary>

## Key Implementation Patterns
- React + Tailwind CSS with dark/light theme support.
- Real-time WebSocket connection streaming time series.
- Modal dialogs with action approval and rollback triggers.
