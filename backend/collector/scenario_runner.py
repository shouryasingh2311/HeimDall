"""Drive the eight demo scenarios through the normal collector and SaaS paths."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import json
import logging
from uuid import uuid4

from backend.collector.command_runner import NODE
from backend.collector.demo_source import RawEvent
from backend.collector.transport import DELIVERY_ERRORS
from backend.shared.models import MetadataPayload, parse_utc, utc_now, utc_text
from backend.shared.scenarios import ScenarioResult, scenario_timeout

LOG = logging.getLogger("heimdal.collector")
MARKER = "synthetic-phase7-local-secret"


class ScenarioBusy(Exception):
    pass


class ScenarioRunner:
    def __init__(self, collector, generator):
        self.collector = collector
        self.generator = generator
        self.transport = collector.transport
        self.current = None
        self.task = None
        self.lock = asyncio.Lock()
        self.pending = {}

    @property
    def active(self):
        return self.task is not None and not self.task.done()

    async def start(self, number: int):
        async with self.lock:
            if self.active or self.pending:
                raise ScenarioBusy("Wait for the current scenario and its receipt")
            self.current = ScenarioResult(run_id=str(uuid4()), scenario_id=number, status="running",
                                          started_at_utc=utc_text(utc_now()))
            self.task = asyncio.create_task(self.run(self.current))
            return self.current

    async def reset(self):
        async with self.lock:
            if self.active or self.pending or any(await self.collector.outbox.counts()):
                raise ScenarioBusy("Wait for the scenario and outbox to settle")
            if (await self.transport.observe_scenario([]))["pending_actions"]:
                raise ScenarioBusy("Finish or roll back pending demo actions first")
            self.generator.active_injections.clear()
            self.generator.memory_demand_pct.clear()
            self.current = None

    async def close(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def publish(self):
        for run_id, result in list(self.pending.items()):
            try:
                await self.transport.report_scenario(result)
            except DELIVERY_ERRORS:
                continue
            if self.pending.get(run_id) is result:
                del self.pending[run_id]

    async def flush(self):
        while True:
            await self.publish()
            await asyncio.sleep(2)

    async def run(self, result):
        methods = (self.privacy, self.outage, self.auth, self.network, self.anomaly,
                   self.correlation, self.replay, self.remediation)
        self.pending[result.run_id] = result
        checks, ids, incidents, duplicate = {}, [], [], 0
        reason = None
        try:
            async with asyncio.timeout(scenario_timeout(result.scenario_id)):
                checks, ids, incidents, duplicate = await methods[result.scenario_id - 1]()
            status = "passed" if checks and all(checks.values()) else "failed"
            reason = "evidence_mismatch" if status == "failed" else None
        except TimeoutError:
            status = "blocked" if result.scenario_id == 8 else "failed"
            reason = "operator_required" if result.scenario_id == 8 else "evidence_timeout"
        except DELIVERY_ERRORS:
            status, reason = "blocked", "transport_unavailable"
        except (ValueError, RuntimeError) as error:
            LOG.warning("Scenario %s stopped (%s)", result.scenario_id, type(error).__name__)
            status, reason = "failed", "evidence_mismatch"
        final = result.model_copy(update={
            "status": status, "finished_at_utc": utc_text(utc_now()), "checks": checks, "payload_uuids": ids,
            "incident_ids": incidents, "duplicate_count": duplicate, "reason_code": reason,
        })
        self.current = final
        self.pending[result.run_id] = final

    def event(self, node, metrics, **overrides):
        settings = self.collector.settings
        data = dict(
            tenant_id=settings.tenant_id, collector_id=settings.collector_id,
            source_key=f"{settings.tenant_id}:{node}", input_id=str(uuid4()), event_time_utc=utc_text(utc_now()),
            source_timezone="UTC", metrics=metrics,
        )
        return RawEvent(**(data | overrides))

    async def emit(self, event, *, simulation=False):
        identifier = self.collector.sanitizer.metric(event).payload_uuid
        if not await self.collector.submit(event, simulation=simulation):
            raise ValueError("Local scenario input rejected")
        return identifier

    async def evidence(self, ids, *, timeout=18):
        async with asyncio.timeout(timeout):
            while True:
                evidence = await self.transport.observe_scenario(ids)
                if set(ids) <= evidence["payloads"].keys():
                    return evidence
                await asyncio.sleep(.2)

    async def privacy(self):
        event = self.event(NODE, {"cpu_pct": 28.}, raw_text=f"password={MARKER}")
        identifier = await self.emit(event)
        evidence = await self.evidence([identifier])
        observed = evidence["payloads"][identifier]
        local = self.collector.audit.by_id(identifier)
        checks = {
            "digest_matches": local is not None and local["body_sha256"] == observed["body_sha256"],
            "secret_excluded": MARKER not in json.dumps(observed["body"]) and "raw_text" not in observed["body"],
        }
        return checks, [identifier], [], 0

    async def outage(self):
        ids = []
        self.transport.pause_metadata = True
        try:
            for _ in range(15):
                settings = self.collector.settings
                for event in self.generator.generate_tick(tenants=[settings.tenant_id]):
                    ids.append(await self.emit(replace(event, collector_id=settings.collector_id)))
                await asyncio.sleep(2)
            stored = set(await self.collector.outbox.pending_ids())
            unseen = not (await self.transport.observe_scenario(ids))["payloads"]
        finally:
            self.transport.pause_metadata = False
        evidence = await self.evidence(ids, timeout=25)
        reconciled = all(
            (record := self.collector.audit.by_id(key)) is not None
            and record["body_sha256"] == evidence["payloads"][key]["body_sha256"] for key in ids
        )
        return {"queued": set(ids) <= stored and unseen, "reconciled": reconciled}, ids, [], 0

    async def auth(self):
        run = self.current.run_id
        address = f"2001:db8::{run[:4]}:{run[4:8]}"
        before = {row["payload_uuid"] for row in self.collector.audit.latest(500)}
        ids, first_four = [], False
        for index in range(5):
            event = self.event("auth-01", None, kind="auth", source_ip=address,
                               username="synthetic-account", auth_success=False)
            if not await self.collector.submit(event):
                raise ValueError("Local auth input rejected")
            ids = [row["payload_uuid"] for row in self.collector.audit.latest(500)
                   if row["payload_uuid"] not in before and json.loads(row["approved_body"])["event_type"] == "auth_threat"]
            if index == 3:
                first_four = not ids
            await asyncio.sleep(.02)
        evidence = await self.evidence(ids)
        return {
            "four_silent": first_four, "five_counted": len(ids) == 1
            and evidence["payloads"][ids[0]]["body"]["security"]["failed_attempts_count"] == 5,
        }, ids, self.incidents(evidence), 0

    @staticmethod
    def incidents(evidence):
        return sorted({alert["incident_id"] for alert in evidence["alerts"]})

    async def network(self):
        ids = [
            await self.emit(self.event(NODE, {"latency_ms": 520.})),
            await self.emit(self.event("lb-01", {"packet_loss_pct": 14., "service_available": False})),
        ]
        evidence = await self.evidence(ids)
        alerts = evidence["alerts"]
        related = {alert["payload_uuid"] for alert in alerts} == set(ids) and len(self.incidents(evidence)) == 1
        timely = bool(alerts) and all(0 <= (parse_utc(a["created_at"]) - parse_utc(a["event_time"])).total_seconds() <= 15
                                      for a in alerts)
        return {"related": related, "alert_deadline": timely}, ids, self.incidents(evidence), 0

    async def anomaly(self):
        ids = []
        for value in [15.] * 30 + [21., 15., 31., 32.]:
            ids.append(await self.emit(self.event("worker-01", {"cpu_pct": value})))
            await asyncio.sleep(.02)
        evidence = await self.evidence(ids)
        flagged = {row["payload_uuid"] for row in evidence["alerts"]}
        return {"normal_silent": not (set(ids[:30]) & flagged), "single_silent": ids[30] not in flagged,
                "sustained_alert": ids[-1] in flagged and ids[-2] not in flagged}, ids, self.incidents(evidence), 0

    async def correlation(self):
        ids = [
            await self.emit(self.event(NODE, {"latency_ms": 550.})),
            await self.emit(self.event("lb-01", {"packet_loss_pct": 15.})),
            await self.emit(self.event("worker-01", {"cpu_pct": 98.})),
        ]
        evidence = await self.evidence(ids)
        ownership = {row["payload_uuid"]: row["incident_id"] for row in evidence["alerts"]}
        return {
            "related": len(ownership) == 3 and ownership[ids[0]] == ownership[ids[1]],
            "unrelated_separate": len(ownership) == 3 and ownership[ids[2]] != ownership[ids[0]],
        }, ids, self.incidents(evidence), 0

    async def replay(self):
        event = self.event(NODE, {"cpu_pct": 28.})
        current = await self.emit(event)
        await self.evidence([current])
        local = self.collector.audit.by_id(current)
        body = local["approved_body"].encode()
        duplicate = await self.transport.send(MetadataPayload.model_validate_json(body), body)
        previous = await self.emit(self.event(NODE, {"cpu_pct": 28.},
                                              event_time_utc=utc_text(parse_utc(event.event_time_utc) - timedelta(seconds=2))))
        ids = [current, previous]
        evidence = await self.evidence(ids)
        repeated = duplicate.status == "duplicate"
        return {"duplicate_ack": repeated, "late_historical": evidence["payloads"][previous]["analysis_status"] == "historical"}, ids, [], int(repeated)

    async def remediation(self):
        self.generator.memory_demand_pct[NODE] = 98.
        ids, breach_ids, recovered, restored, approved = [], [], False, False, False
        config = self.collector.settings
        while True:
            samples = self.generator.generate_tick(tenants=[config.tenant_id])
            emitted = {}
            for event in samples:
                is_target = event.source_key == config.demo_memory_source
                emitted[event.source_key] = (
                    await self.emit(replace(event, collector_id=config.collector_id), simulation=is_target), event,
                )
            identifier, point = emitted[config.demo_memory_source]
            ids.append(identifier)
            if point.metrics["memory_pct"] >= 95 and not approved:
                breach_ids.append(identifier)
            evidence = await self.evidence([*breach_ids, identifier])
            states = {action["status"] for action in evidence["actions"]}
            committed = evidence["payloads"][identifier]["body"]["metrics"]["memory_pct"]
            approved |= bool(states & {"succeeded", "rollback_pending", "rolled_back"})
            recovered |= approved and committed < 70
            restored |= recovered and "rolled_back" in states and committed >= 95
            if restored:
                return {"approved": approved, "recovered": recovered, "restored": restored}, ids, self.incidents(evidence), 0
            await asyncio.sleep(2)
