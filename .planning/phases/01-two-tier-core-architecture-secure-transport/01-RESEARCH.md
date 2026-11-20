# Phase 1: Two-Tier Core Architecture & Secure Transport — Research

**Researched:** 2026-11-20
**Domain:** Distributed Systems, Multi-Tenant SaaS Architecture, TLS Mutual Auth, Regional Telemetry Ingest
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- Two-Tier Model: Tier 1 (Customer Environment / Local Collector) and Tier 2 (Central SaaS Platform).
- Zero Raw Data to SaaS: Ingest endpoints accept only approved, validated metadata schemas.
- Strict Multi-Tenancy: Complete data isolation by tenant ID at ingress, query, and storage layers.
- Regional Ingest: Collectors route to regional endpoints (`us-east-1`, `eu-west-1`, `ap-south-1`) respecting data sovereignty.
- Authentication: Secure token/certificate-based authentication for all collector daemon transmissions over TLS.

### Claude's Discretion
- Choice of backend framework: FastAPI (Python 3.11+) with async Uvicorn for high-throughput metadata intake.
- Local Collector daemon: Python / Node.js lightweight background process consuming $<50\text{ MB}$ RAM.
- Configuration structure: YAML / JSON environment configurations with dotenv support.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| Collector Daemon Runtime | Tier 1 (Customer Edge) | — | Runs locally on monitored node/VM to capture telemetry without remote agent access |
| Ingestion API Endpoint | Tier 2 (Central SaaS) | Regional Edge | Ingests metadata payloads over HTTPS/TLS, validates tenant auth tokens |
| Multi-Tenant Partitioning | Tier 2 (Central SaaS) | Database Layer | Enforces tenant scoping on all metadata writes and queries |
| Regional Routing Router | Tier 1 (Customer Edge) | Tier 2 (Regional Gateway) | Collector selects regional gateway URL based on tenant residency policy |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 1 establishes the foundational two-tier boundary mandated by the CICADA 2026 Hackathon problem statement. The architecture strictly isolates the customer's on-premises/cloud infrastructure from the SaaS platform:
1. **Tier 1 (Customer Collector Daemon)**: Operates as an independent daemon. It authenticates with Tier 2 using tenant-scoped API keys (`X-Tenant-ID`, `Authorization: Bearer <collector_token>`). It automatically resolves its designated regional ingestion endpoint (`/api/v1/ingest/regional/{region}`) to comply with data residency mandates.
2. **Tier 2 (SaaS Central Ingestion API)**: Built with FastAPI for async throughput, it validates cryptographic collector tokens, enforces tenant isolation, rejects unauthenticated or malformed payloads, and stores metadata in a tenant-partitioned repository.
3. **Security Controls**: TLS 1.3 encryption in transit, rotating collector secret tokens, regional endpoint routing, and auditable connection logging.
</research_summary>

## Key Implementation Patterns & Dependencies
- **FastAPI + Pydantic v2**: Strict schema validation rejecting unallowlisted fields with HTTP 422.
- **HTTPX / aiohttp (Collector side)**: Async HTTP client with connection pooling and TLS verification.
- **Tenant Context Middleware**: Extracts `tenant_id` from request headers and binds it to request context (Python `contextvars`) to prevent cross-tenant data leaks.
