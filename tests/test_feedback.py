"""M3 destination behavior on real disposable SQLite, never live providers."""

from __future__ import annotations

import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading

import pytest

from scripts import feedback as f
from scripts import workflow_budget as b
from scripts import workflow_state as ws
from test_model_router import config, make_packet, resource, request, attempt

ANCHOR = "a" * 64
BASE = datetime(2026, 10, 14, 22, tzinfo=timezone.utc)


def stamp(n=0):
    return (BASE + timedelta(seconds=n)).isoformat().replace("+00:00", "Z")


def policy(**updates):
    return {"schema_version": "1.0", **copy.deepcopy(f.LIMITS), **updates}


def options(**updates):
    return {
        "task_class": "synthetic-parser",
        "input_tokens": 10000,
        "output_tokens": 1000,
        "unavailable_providers": [],
        "unavailable_resources": [],
        "context_envelope": {
            "brief": "Synthetic rendered brief",
            "rules": "Synthetic rules",
            "overhead_tokens": 100,
        },
        **updates,
    }


def result(dispatch, packet, outcome="FAIL", passed=False, **updates):
    return {
        "dispatch_id": dispatch["dispatch_id"],
        "outcome": outcome,
        "summary": "Synthetic result",
        "scope_status": "within",
        "architecture_conflict": False,
        "validation": [
            {
                "check_id": v["id"],
                "passed": passed,
                "failure_code": "" if passed else "VALUE_MISMATCH",
                "expected": "expected value",
                "actual": "observed wrong value",
                "evidence": ["Synthetic check"],
            }
            for v in f.wp.current(packet)["contract"]["validation"]
        ],
        "evidence": ["Synthetic original evidence"],
        "discoveries": [],
        "api_cost_usd": 0,
        "cost_evidence": "Synthetic claim; no provider call",
        **updates,
    }


@pytest.fixture
def journal(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    root.mkdir()
    (root / "config").mkdir()
    # Explicit fixture authority only. Production still uses the frozen adapter.
    (root / "config/workflow-bootstrap.json").write_text(
        json.dumps(
            {
                "policy": {
                    "resources_enabled": True,
                    "task_api_budget_usd": 100,
                    "role_api_budget_usd": 100,
                    "project_api_budget_usd": 100,
                }
            }
        )
    )
    monkeypatch.setattr(ws, "control_directory", lambda _: tmp_path / "state")
    monkeypatch.setattr(ws.approval, "git", lambda *args: str(root / ".git").encode())
    monkeypatch.setattr(ws, "active_anchor", lambda *args: ANCHOR)
    monkeypatch.setattr(f, "active_anchor", lambda *args: ANCHOR)
    value = ws.Journal(root)
    value.initialize()
    f.initialize_accounts(
        value, "synthetic", {"role": 100, "project": 100}, timestamp=stamp()
    )
    return value


def start(
    journal,
    name="TASK",
    settings=None,
    packet=None,
    caps=None,
    limits=None,
    project="synthetic",
):
    settings = settings or config(
        resource(), resource("reviewer", tier=2, provider="mistral")
    )
    packet = packet or make_packet(retries=2, reviewer=2)
    if packet["task_id"] != name:
        contract = f.wp.current(packet)["contract"]
        packet = f.wp.create(
            name,
            packet["domain_profile"],
            contract,
            "Architect",
            "Synthetic fixture",
            stamp(),
        )
        for target in ("ARCHITECTED", "READY"):
            packet = f.wp.transition(
                packet,
                target,
                "architect",
                "Architect",
                "Fixture",
                ["Synthetic"],
                timestamp=stamp(),
            )
    f.initialize(
        journal,
        "task:" + name,
        packet,
        [packet],
        limits or policy(),
        settings,
        "Architect",
        project=project,
        implementer="Implementer",
        caps=caps or {"task": 100, "role": 100, "project": 100},
        timestamp=stamp(),
    )
    return "task:" + name, settings


def reserve(journal, stream, settings, n=1, **kwargs):
    opts = options()
    if kwargs.get("role") == "reviewer":
        opts["reviewer_actor"] = "Independent"
    return f.reserve(journal, stream, settings, opts, timestamp=stamp(n), **kwargs)


def done(journal, stream, dispatch, n=2, **updates):
    packet = f.replay(journal, stream)[0]["packet"]
    return f.complete(
        journal, stream, result(dispatch, packet, **updates), timestamp=stamp(n)
    )


def usage(journal, attempt, **updates):
    path = journal.directory / "run-usage" / (attempt["id"] + ".json")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"Synthetic coordinator usage; no provider call")
    evidence = journal.evidence(path.relative_to(journal.directory).as_posix())
    return {
        "dispatch_id": attempt["id"],
        "rates_hash": f.router.digest(attempt["rates"]),
        "input_tokens": 1000,
        "output_tokens": 100,
        "cached_input_tokens": 500,
        "evidence_sha256": evidence.sha256,
        **updates,
    }, (evidence,)


def rejection(state, reviewer="Independent", tier=2, verdict="REJECT_BOUNDED"):
    contract = f.wp.current(state["packet"])["contract"]
    return {
        "review_id": f.router.digest({"pending": state["review_pending"]}),
        "verdict": verdict,
        "reviewer": {"actor": reviewer, "tier": tier, "model_family": "mistral"},
        "summary": "Synthetic bounded rejection",
        "evidence": ["Synthetic reviewer evidence"],
        "contract_failures": [
            {
                "kind": "validation",
                "failed_ref": contract["validation"][0]["id"],
                "what_failed": "Incorrect value",
                "corrective_action": "Fix within scope",
            }
        ]
        if verdict == "REJECT_BOUNDED"
        else [],
        "acceptance_reference": "Synthetic review fixture; M5 not accepted",
        "binding": {k: v for k, v in f.binding(state["packet"]).items() if k != "role"},
        "result_dispatch_id": state["attempts"][-1]["id"],
    }


def test_atomic_reservation_deadline_saved_replay_and_double_pending(journal):
    stream, settings = start(journal)
    before = journal.read(stream)[1]
    dispatched = reserve(journal, stream, settings)
    state, _, _ = f.replay(journal, stream)
    a = state["attempts"][0]
    assert (f.instant(a["deadline"]) - f.instant(a["issued_at"])).total_seconds() == 600
    for account in f.accounts(state, "worker"):
        data, head = journal.replay(account, b.apply)
        assert head.sequence == 2 and list(data["entries"]) == [a["id"]]
    events, _ = journal.read(stream)
    assert (
        f.router.verify(events[-1]["data"]["plan"]["routing"])
        == dispatched["routing"]["decision"]
    )
    with pytest.raises(ValueError, match="pending"):
        reserve(journal, stream, settings, 2)
    with pytest.raises(ValueError, match="Stale"):
        reserve(journal, stream, settings, 2, expected=before)
    assert f.replay(journal, stream)[0] == state


def test_lifetime_worker_cap_and_normalized_repeated_failure(journal):
    stream, settings = start(journal, packet=make_packet(retries=8, reviewer=2))
    first = reserve(journal, stream, settings)
    state = done(journal, stream, first)
    second = reserve(journal, stream, settings, 3)
    reported = result(second, state["packet"])
    for check in reported["validation"]:
        check["actual"] = "\x1b[31mobserved   wrong\nvalue\x1b[0m"
    state = f.complete(journal, stream, reported, timestamp=stamp(4))
    assert len(state["attempts"]) == 2 and state["total_cap"] == 2
    assert state["attempts"][0]["fingerprint"] == state["attempts"][1]["fingerprint"]
    assert state["reason"] == "REPEATED_FAILURE_TIER_LIMIT"
    assert reserve(journal, stream, settings, 5)["reason"] == "TOTAL_ATTEMPT_LIMIT"


def test_tier_caps_take_minimum_of_packet_task_and_policy(journal):
    packet = make_packet(retries=8, reviewer=2)
    contract = copy.deepcopy(f.wp.current(packet)["contract"])
    contract["retry_budget"]["max_attempts_by_tier"] = {"1": 8, "4": 8}
    packet = f.wp.create(
        "TASK", "software-hardware", contract, "Architect", "Fixture", stamp()
    )
    for target in ("ARCHITECTED", "READY"):
        packet = f.wp.transition(
            packet,
            target,
            "architect",
            "Architect",
            "Fixture",
            ["Fixture"],
            timestamp=stamp(),
        )
    stream, _ = start(journal, packet=packet)
    assert f.replay(journal, stream)[0]["caps"] == {
        "0": 2,
        "1": 2,
        "2": 2,
        "3": 2,
        "4": 1,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("attempt_timeout_seconds", 601),
        ("max_history_entries", 6),
        ("max_context_chars", 40001),
        ("max_architect_diagnoses", 6),
        ("max_blocker_resumptions", 4),
        ("max_contract_repairs", 2),
        ("repeated_failure_total", 4),
        ("repeated_failure_per_tier", 3),
    ],
)
def test_policy_bounds_cannot_be_increased(journal, field, value):
    with pytest.raises(ValueError, match="approved"):
        start(journal, limits=policy(**{field: value}))
    assert "task:TASK" not in journal.verify()


@pytest.mark.parametrize("claim", [None, 0, 0.75])
def test_all_unmeasured_metered_claims_remain_liability(journal, claim):
    stream, settings = start(journal, settings=config(resource(api=0.01)))
    dispatch = reserve(journal, stream, settings)
    state = done(journal, stream, dispatch, api_cost_usd=claim)
    account = f.accounting(state)
    assert account["settled"] == 0 and account["unknown"] == [dispatch["dispatch_id"]]
    assert account["liability"] >= max(state["attempts"][0]["ceiling"], claim or 0)
    assert state["attempts"][0]["raw_result"]["api_cost_usd"] == claim
    for stream_id in f.accounts(state, "worker"):
        assert b.totals(journal.replay(stream_id, b.apply)[0]) == account
    assert reserve(journal, stream, settings, 3)["dispatch_id"] is None


def test_measured_usage_saved_rates_cache_conservatism_round_up_and_reconcile(journal):
    stream, settings = start(journal, settings=config(resource(api=0.01)))
    dispatch = reserve(journal, stream, settings)
    state = done(journal, stream, dispatch)
    a = state["attempts"][0]
    measured, evidence = usage(
        journal, a, input_tokens=1, output_tokens=0, cached_input_tokens=1
    )
    expected = b.ceiling(a["rates"], 1, 0)
    assert expected == 0.000005
    with pytest.raises(ValueError, match="evidence"):
        f.reconcile(journal, stream, a["id"], measured, timestamp=stamp(3))
    before = journal.verify()
    wrong = {**measured, "rates_hash": "0" * 64}
    with pytest.raises(ValueError, match="rates"):
        f.reconcile(
            journal, stream, a["id"], wrong, timestamp=stamp(3), evidence=evidence
        )
    assert journal.verify() == before
    state = f.reconcile(
        journal, stream, a["id"], measured, timestamp=stamp(3), evidence=evidence
    )
    assert f.accounting(state) == {
        "settled": expected,
        "liability": 0,
        "committed": expected,
        "unknown": [],
    }
    assert state["attempts"][0]["raw_result"]["api_cost_usd"] == 0
    assert reserve(journal, stream, settings, 4)["status"] == "DISPATCH"


def test_unmetered_cost_is_zero_and_timeout_cannot_pass(journal):
    stream, settings = start(journal)
    dispatch = reserve(journal, stream, settings)
    state = done(
        journal, stream, dispatch, 602, outcome="PASS", passed=True, api_cost_usd=10
    )
    assert state["attempts"][0]["routing_outcome"] == "FAIL"
    assert state["reason"] == "ATTEMPT_TIMEOUT"
    assert f.accounting(state)["committed"] == 0
    assert state["attempts"][0]["raw_result"]["api_cost_usd"] == 10


def test_abandoned_possibly_charged_run_preserves_unknown_cost(journal):
    stream, settings = start(journal, settings=config(resource(api=0.01)))
    dispatch = reserve(journal, stream, settings)
    packet = f.replay(journal, stream)[0]["packet"]
    abandoned = result(
        dispatch,
        packet,
        scope_status="unknown",
        validation=[],
        evidence=["attempt-abandoned: no trustworthy outcome"],
        api_cost_usd=None,
    )
    state = f.abandon(journal, stream, abandoned, timestamp=stamp(2))
    assert f.accounting(state)["liability"] > 0
    assert f.accounting(state)["unknown"] == [dispatch["dispatch_id"]]
    assert state["status"] == "NEEDS_ARCHITECT"


def test_repair_preserves_lifetime_spend_and_nondescending_tiers(journal):
    stream, settings = start(journal, settings=config(resource(tier=2, api=0.01)))
    dispatch = reserve(journal, stream, settings)
    state = done(journal, stream, dispatch, scope_status="unknown")
    contract = copy.deepcopy(f.wp.current(state["packet"])["contract"])
    contract["goal"] += " Clarified wording."
    diagnosis = {
        "classification": "REPAIR_CONTRACT",
        "reason": "Clarify",
        "evidence": ["Synthetic"],
        "architecture_fingerprint": ANCHOR,
        "revised_contract": contract,
    }
    old_accounting = f.accounting(state)
    state = f.diagnose(journal, stream, diagnosis, "Architect", timestamp=stamp(3))
    assert len(state["attempts"]) == 1 and state["repairs"] == 1
    assert f.accounting(state) == old_accounting
    assert (
        state["attempts"][0]["revision"] == 1
        and f.binding(state["packet"])["revision"] == 2
    )
    # Repricing a retired resource cannot clear the old metered liability.
    changed = copy.deepcopy(settings)
    changed["resources"] = [resource(tier=1), resource("other", tier=2)]
    second = reserve(journal, stream, changed, 4)
    assert second["routing"]["decision"]["selected"]["tier"] == 2
    state = done(journal, stream, second, 5)
    assert len(state["attempts"]) == 2 and f.accounting(state)["unknown"] == [
        dispatch["dispatch_id"]
    ]
    assert reserve(journal, stream, changed, 6)["reason"] == "TOTAL_ATTEMPT_LIMIT"


def test_review_resubmission_keeps_attempts_and_repeated_rejection_holds(journal):
    stream, settings = start(journal)
    for n in (1, 5):
        dispatch = reserve(journal, stream, settings, n)
        state = done(journal, stream, dispatch, n + 1, outcome="PASS", passed=True)
        reserve(journal, stream, settings, n + 2, role="reviewer")
        state = f.replay(journal, stream)[0]
        decision = rejection(state)
        state = f.review(
            journal,
            stream,
            {
                "dispatch_id": state["review_pending"],
                "decision": decision,
                "usage": None,
            },
            timestamp=stamp(n + 3),
        )
    assert len(state["attempts"]) == len(state["review_attempts"]) == 2
    assert state["reason"] == "REPEATED_REVIEW_REJECTION"
    assert state["status"] == "NEEDS_ARCHITECT"
    with pytest.raises(ValueError):
        reserve(journal, stream, settings, 9, role="reviewer")


@pytest.mark.parametrize(
    "change", ["same_actor", "low_tier", "wrong_result", "approve"]
)
def test_review_negatives_do_not_settle_or_consume_new_authority(journal, change):
    stream, settings = start(journal)
    dispatch = reserve(journal, stream, settings)
    done(journal, stream, dispatch, outcome="PASS", passed=True)
    reserve(journal, stream, settings, 3, role="reviewer")
    state = f.replay(journal, stream)[0]
    decision = rejection(state)
    if change == "same_actor":
        decision["reviewer"]["actor"] = "Implementer"
    if change == "low_tier":
        decision["reviewer"]["tier"] = 0
    if change == "wrong_result":
        decision["result_dispatch_id"] = "b" * 64
    if change == "approve":
        decision.update(verdict="APPROVE", contract_failures=[])
    before = journal.verify()
    with pytest.raises(ValueError):
        f.review(
            journal,
            stream,
            {
                "dispatch_id": state["review_pending"],
                "decision": decision,
                "usage": None,
            },
            timestamp=stamp(4),
        )
    assert journal.verify() == before


def test_context_counts_rendered_brief_rules_overhead_and_output(journal):
    stream, settings = start(journal)
    huge = options(
        context_envelope={"brief": "x" * 40000, "rules": "x", "overhead_tokens": 1}
    )
    state = f.replay(journal, stream)[0]
    assert (
        f.plan(state, settings, huge)["reason"]
        == "CONTEXT_LIMIT_REQUIRES_DECOMPOSITION"
    )
    small = copy.deepcopy(settings)
    small["resources"][0]["context_window"] = 10000
    small["resources"][1]["context_window"] = 10000
    assert f.plan(state, small, options())["routing"]["decision"]["status"] == "STOP"
    bad = options(input_tokens=True)
    with pytest.raises(ValueError):
        f.plan(state, settings, bad)


def test_concurrent_same_task_has_one_whole_batch_winner(journal):
    stream, settings = start(journal)
    barrier = threading.Barrier(6)

    def contender(_):
        barrier.wait()
        try:
            return reserve(journal, stream, settings)["dispatch_id"]
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(contender, range(6)))
    assert sum(value is not None for value in results) == 1
    state = f.replay(journal, stream)[0]
    for account in f.accounts(state, "worker"):
        assert len(journal.replay(account, b.apply)[0]["entries"]) == 1


def test_project_budget_race_and_later_stale_head_roll_back_every_stream(journal):
    # Separate task streams contend for one project/role cap.
    settings = config(resource(api=0.01))
    ceiling = b.ceiling(settings["resources"][0], 10000, 1000)
    caps = {"task": 100, "role": ceiling, "project": ceiling}
    f.initialize_accounts(journal, "tiny", caps, timestamp=stamp())
    first, settings = start(
        journal, name="ONE", settings=settings, caps=caps, project="tiny"
    )
    second, _ = start(journal, name="TWO", settings=settings, caps=caps, project="tiny")
    for stream in (first, second):
        assert len(f.replay(journal, stream)[0]["attempts"]) == 0
    barrier = threading.Barrier(2)

    def contender(stream):
        head = journal.read(stream)[1]
        state = f.replay(journal, stream)[0]
        proposed = f.plan(state, settings, options())
        data = {"config": settings, "options": options(), "plan": proposed}
        dispatch_id = proposed["routing"]["decision"]["decision_id"]
        batch = [
            ws.Append(
                stream=stream,
                kind="DISPATCH",
                data=data,
                expected=head,
                timestamp=stamp(1),
                reducer=f.reducer(head),
            )
        ]
        for account in f.accounts(state, "worker"):
            _, account_head = journal.replay(account, b.apply)
            batch.append(
                ws.Append(
                    stream=account,
                    kind="RESERVE",
                    data={
                        "dispatch_id": dispatch_id,
                        "task_id": state["packet"]["task_id"],
                        "role": "worker",
                        "ceiling": ceiling,
                        "metered": True,
                    },
                    expected=account_head,
                    timestamp=stamp(1),
                    reducer=b.apply,
                )
            )
        barrier.wait()
        try:
            journal.append_many(tuple(batch))
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(contender, (first, second))) == [False, True]
    assert sum(len(f.replay(journal, s)[0]["attempts"]) for s in (first, second)) == 1


def test_router_destination_attempt_floor_and_unknown_negatives():
    packet = make_packet(retries=8)
    settings = config(resource(), resource("paid", api=0.1))
    history = [attempt(1), attempt(2)]
    assert f.router.route(packet, settings, request(packet, attempts=history))[
        "reason_codes"
    ] == ["ATTEMPT_BUDGET_EXHAUSTED"]
    with pytest.raises(ValueError):
        f.router.route(
            packet, settings, request(packet, attempts=history + [attempt(3)])
        )
    unknown = f.router.route(
        packet, settings, request(packet, attempts=[attempt(api=None)])
    )
    assert unknown["selected"]["resource_id"] == "local"
    assert "PRIOR_API_COST_UNKNOWN" in unknown["candidates"][1]["reason_codes"]
    settings["policy"]["risk_floor"]["high"] = 2
    with pytest.raises(ValueError, match="floor"):
        f.router.route(packet, settings, request(packet))


def test_source_hash_chain_import_preserves_semantics_and_refuses_relabel(
    journal, tmp_path
):
    packet = make_packet(retries=8)
    settings = config(resource())
    state = None
    source = tmp_path / "source"
    source.mkdir()
    previous = None
    data = {
        "packet": packet,
        "graph": [packet],
        "policy": policy(),
        "router_config": settings,
        "anchor": "c" * 64,
        "architect": "Source architect",
    }
    events = [("INIT", data)]
    initial = f.source_apply(None, {"kind": "INIT", "data": data, "timestamp": stamp()})
    proposed = f.source_plan(
        initial,
        settings,
        {k: v for k, v in options().items() if k != "context_envelope"},
    )
    events.append(
        (
            "DISPATCH",
            {
                "config": settings,
                "options": {
                    k: v for k, v in options().items() if k != "context_envelope"
                },
                "plan": proposed,
            },
        )
    )
    raw = []
    for sequence, (kind, payload) in enumerate(events, 1):
        event = {
            "kind": kind,
            "data": payload,
            "sequence": sequence,
            "previous": previous,
            "timestamp": stamp(sequence),
        }
        state = f.apply(state, event, stored=True)
        event["hash"] = hashlib.sha256(ws.approval.canonical(event)).hexdigest()
        content = json.dumps(event, indent=2).encode()
        (source / f"{sequence:08d}.json").write_bytes(content)
        raw.append(content)
        previous = event["hash"]
    journal.import_chain(
        "imported:TASK",
        source,
        family="feedback",
        binding=f.binding(packet),
        reducer=f.reducer(),
    )
    replayed, _, last = f.replay(journal, "imported:TASK")
    assert replayed == state and last == previous
    exported = tmp_path / "export"
    journal.export("imported:TASK", exported)
    assert [p.read_bytes() for p in sorted(exported.iterdir())] == raw
    with pytest.raises(ValueError, match="relabeled"):
        f.reserve(journal, "imported:TASK", settings, options(), timestamp=stamp(3))


def test_default_timestamp_returns_exact_durable_deadline(journal, monkeypatch):
    stream, settings = start(journal)
    monkeypatch.setattr(f.wp, "now", lambda: stamp(1))
    dispatched = f.reserve(journal, stream, settings, options())
    state = f.replay(journal, stream)[0]
    assert dispatched["deadline"] == state["attempts"][-1]["deadline"]
    for account in f.accounts(state, "worker"):
        assert journal.read(account)[0][-1]["timestamp"] == stamp(1)


@pytest.mark.parametrize("bad", ["0", True, -1, float("nan")])
def test_invalid_raw_cost_claim_is_refused_before_normalization(journal, bad):
    stream, settings = start(journal)
    dispatched = reserve(journal, stream, settings)
    before = journal.verify()
    with pytest.raises(ValueError):
        done(journal, stream, dispatched, api_cost_usd=bad)
    assert journal.verify() == before


def test_direct_append_cannot_bypass_atomic_budget_bookkeeping(journal):
    stream, _ = start(journal)
    before = journal.verify()
    for kind in ("DISPATCH", "RESULT", "ABANDON", "REVIEW", "COST_RECONCILED"):
        with pytest.raises(ValueError, match="atomic"):
            f.append(journal, stream, kind, {}, expected=journal.read(stream)[1])
    assert journal.verify() == before


@pytest.mark.parametrize("risk", ["high", "critical"])
def test_cross_family_floor_filters_before_reserving_review(journal, risk):
    tier = 3 if risk == "high" else 4
    settings = config(
        resource("worker", tier=tier, latency=1),
        resource("cross", tier=tier, provider="mistral", latency=10),
    )
    packet = make_packet(risk=risk, minimum=tier, reviewer=tier, retries=2)
    stream, settings = start(journal, settings=settings, packet=packet)
    dispatched = reserve(journal, stream, settings)
    done(journal, stream, dispatched, outcome="PASS", passed=True)
    review = reserve(journal, stream, settings, 3, role="reviewer")
    assert review["routing"]["decision"]["selected"]["resource_id"] == "cross"
    state = f.replay(journal, stream)[0]
    decision = rejection(state, tier=tier)
    decision["reviewer"]["model_family"] = "lmstudio"
    before = journal.verify()
    with pytest.raises(ValueError, match="reservation"):
        f.review(
            journal,
            stream,
            {
                "dispatch_id": state["review_pending"],
                "decision": decision,
                "usage": None,
            },
            timestamp=stamp(4),
        )
    assert journal.verify() == before


def test_measured_overrun_records_actual_cost_and_holds_even_with_large_caps(journal):
    stream, settings = start(journal, settings=config(resource(api=0.01)))
    dispatched = reserve(journal, stream, settings)
    state = f.replay(journal, stream)[0]
    measured, evidence = usage(
        journal, state["attempts"][0], input_tokens=20000, output_tokens=0
    )
    reported = result(dispatched, state["packet"], usage=measured, api_cost_usd=0)
    state = f.complete(journal, stream, reported, timestamp=stamp(2), evidence=evidence)
    assert (
        state["reason"] == "MEASURED_USAGE_EXCEEDS_RESERVATION"
        and state["status"] == "NEEDS_DECISION"
    )
    assert f.accounting(state)["settled"] == 0.1
    for account in f.accounts(state, "worker"):
        assert b.totals(journal.replay(account, b.apply)[0])["settled"] == 0.1
    with pytest.raises(ValueError, match="hold"):
        reserve(journal, stream, settings, 3)


@pytest.mark.parametrize("cap_kind", ["task", "role", "project"])
def test_each_budget_cap_refuses_atomic_reservation(journal, cap_kind):
    caps = {"task": 100, "role": 100, "project": 100}
    caps[cap_kind] = 0
    f.initialize_accounts(journal, "zero", caps, timestamp=stamp())
    stream, settings = start(
        journal, caps=caps, project="zero", settings=config(resource(api=0.01))
    )
    before = journal.verify()
    with pytest.raises(ValueError, match="cap"):
        reserve(journal, stream, settings)
    assert journal.verify() == before


def test_resume_preserves_lifetime_counts_and_second_repair_is_refused(journal):
    stream, settings = start(journal)
    dispatched = reserve(journal, stream, settings)
    state = done(journal, stream, dispatched, outcome="BLOCKED")
    diagnosis = {
        "classification": "RESUME_WORK",
        "reason": "Blocker resolved",
        "evidence": ["Synthetic"],
        "architecture_fingerprint": ANCHOR,
        "revised_contract": None,
    }
    state = f.diagnose(journal, stream, diagnosis, "Architect", timestamp=stamp(3))
    assert state["resumptions"] == 1 and len(state["attempts"]) == 1
    dispatched = reserve(journal, stream, settings, 4)
    state = done(journal, stream, dispatched, 5, scope_status="unknown")
    diagnosis.update(
        classification="REPAIR_CONTRACT",
        revised_contract=copy.deepcopy(f.wp.current(state["packet"])["contract"]),
    )
    with pytest.raises(ValueError, match="budget"):
        f.diagnose(journal, stream, diagnosis, "Architect", timestamp=stamp(6))
    assert len(f.replay(journal, stream)[0]["attempts"]) == 2


def test_diagnosis_and_blocker_resume_limits_without_new_attempts(journal):
    stream, settings = start(journal)
    unavailable = options(unavailable_providers=["lmstudio", "mistral"])
    diagnosis = {
        "classification": "RESUME_WORK",
        "reason": "Temporary filter resolved",
        "evidence": ["Synthetic"],
        "architecture_fingerprint": ANCHOR,
        "revised_contract": None,
    }
    for n in range(3):
        halted = f.reserve(
            journal, stream, settings, unavailable, timestamp=stamp(n * 2 + 1)
        )
        assert halted["status"] == "BLOCKED"
        state = f.diagnose(
            journal, stream, diagnosis, "Architect", timestamp=stamp(n * 2 + 2)
        )
    assert state["resumptions"] == 3 and not state["attempts"]
    f.reserve(journal, stream, settings, unavailable, timestamp=stamp(7))
    with pytest.raises(ValueError, match="resumption"):
        f.diagnose(journal, stream, diagnosis, "Architect", timestamp=stamp(8))
    diagnosis["classification"] = "BLOCKED"
    for n in (8, 9):
        state = f.diagnose(journal, stream, diagnosis, "Architect", timestamp=stamp(n))
    assert state["diagnoses"] == 5
    with pytest.raises(ValueError, match="Diagnosis budget"):
        f.diagnose(journal, stream, diagnosis, "Architect", timestamp=stamp(10))


def test_actual_active_gate_stays_disabled_and_zero_in_disposable_repository(journal):
    path = journal.root / "config/workflow-bootstrap.json"
    foundation = {
        "policy": {
            "resources_enabled": False,
            "task_api_budget_usd": 0,
            "role_api_budget_usd": 0,
            "project_api_budget_usd": 0,
        }
    }
    path.write_text(json.dumps(foundation))
    with pytest.raises(ValueError, match="Budget"):
        start(journal)
    with pytest.raises(ValueError, match="disables"):
        start(journal, caps={"task": 0, "role": 0, "project": 0})
    disabled = config(resource())
    disabled["resources"][0]["enabled"] = False
    stream, settings = start(
        journal, settings=disabled, caps={"task": 0, "role": 0, "project": 0}
    )
    assert reserve(journal, stream, settings)["dispatch_id"] is None
    assert not f.replay(journal, stream)[0]["attempts"]


def test_reviewer_timeout_abandonment_keeps_lifetime_budget_and_cost(journal):
    settings = config(
        resource(), resource("reviewer", tier=2, provider="mistral", api=0.01)
    )
    stream, settings = start(journal, settings=settings)
    dispatched = reserve(journal, stream, settings)
    done(journal, stream, dispatched, outcome="PASS", passed=True)
    review = reserve(journal, stream, settings, 3, role="reviewer")
    state = f.replay(journal, stream)[0]
    with pytest.raises(ValueError, match="deadline"):
        f.review(
            journal,
            stream,
            {
                "dispatch_id": review["dispatch_id"],
                "decision": rejection(state),
                "usage": None,
            },
            timestamp=stamp(604),
        )
    state = f.finish(
        journal,
        stream,
        "REVIEW_ABANDONED",
        {"dispatch_id": review["dispatch_id"], "reason": "No trustworthy outcome"},
        timestamp=stamp(604),
    )
    assert len(state["review_attempts"]) == 1 and f.accounting(state)["unknown"] == [
        review["dispatch_id"]
    ]
    assert (
        reserve(journal, stream, settings, 605, role="reviewer")["dispatch_id"] is None
    )


def test_duplicate_task_identity_and_repeated_init_cannot_reset(journal):
    stream, _ = start(journal)
    before = journal.verify()
    with pytest.raises(ValueError, match="already exists"):
        start(journal)
    state = f.replay(journal, stream)[0]
    with pytest.raises(ValueError, match="canonical"):
        f.initialize(
            journal,
            "alias",
            state["packet"],
            state["graph"],
            state["policy"],
            config(),
            "Architect",
            project="synthetic",
            implementer="Implementer",
        )
    assert journal.verify() == before


@pytest.mark.parametrize("actor", [" Implementer ", "implementer", "IMPLEMENTER"])
def test_reviewer_name_normalization_cannot_evade_independence(journal, actor):
    stream, settings = start(journal)
    dispatched = reserve(journal, stream, settings)
    done(journal, stream, dispatched, outcome="PASS", passed=True)
    before = journal.verify()
    opts = options(reviewer_actor=actor)
    with pytest.raises(ValueError):
        f.reserve(journal, stream, settings, opts, role="reviewer", timestamp=stamp(3))
    assert journal.verify() == before
