#!/usr/bin/env python3
"""Software + hardware domain rules: keep simulated success and hardware verification distinct.

This module owns nothing the controllers already own. It adds structure to a
software-hardware contract's `domain` block, decides which validations are machine-runnable
and which must be observed on physical hardware, and derives the hardware status a task has
actually earned from its acceptance ledger. It executes nothing and invokes no model.
"""
from __future__ import annotations

if __name__ == "__main__":  # A Ctrl+C while the imports below load also exits 130 (#31).
    import cli_exit
    cli_exit.guard_startup()

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import cli_exit

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    raise SystemExit("Domain tools require: python -m pip install -r requirements-work-packets.txt")

ROOT = Path(__file__).resolve().parent.parent
PROFILE = "software-hardware"
SCHEMA = json.loads((ROOT / "config/domains/software-hardware.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
# The ladder, lowest rung first. A rung at or below integration is reproduced by re-executing a
# declared command; a rung above it exists only as an observation of physical hardware.
LEVELS = tuple(SCHEMA["$defs"]["validation_level"]["enum"])
MACHINE_LEVELS = frozenset(LEVELS[:LEVELS.index("integration") + 1])
HARDWARE_LEVELS = frozenset(LEVELS[LEVELS.index("integration") + 1:])
COMPONENTS = tuple(SCHEMA["$defs"]["component"]["enum"])
UNVERIFIED, VERIFIED, NOT_FACING = "UNVERIFIED_ON_HARDWARE", "VERIFIED_ON_HARDWARE", "NOT_HARDWARE_FACING"
DIGEST_PREFIX = "hardware-evidence:sha256="
# Lines a hardware-rung attestation must carry; each is derived from the bound evidence record.
# dispatch_id and artifact_sha256 (ADR-049) bind the attestation to the ledger's current
# submission at append time, not only when a record is later re-verified. validation_id
# (post-merge independent review, ADR-056) binds it to the check it is attesting: without it, a
# schema-valid record for one hardware-rung check could be appended unchanged for a different one
# at the same rung, since level/device/firmware/observed_at/outcome/operator/dispatch_id/
# artifact_sha256 can all legitimately match across two checks in the same submission.
EVIDENCE_KEYS = ("level", "device", "firmware", "observed_at", "outcome", "operator",
                 "dispatch_id", "artifact_sha256", "validation_id")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


FORMATS = FormatChecker()
RFC3339 = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
                      r"(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])")


def parse_timestamp(value: str) -> datetime:
    """An RFC 3339 string as a real calendar value; the pattern alone would admit 2026-99-99."""
    if not RFC3339.fullmatch(value):
        raise ValueError(f"not an RFC 3339 timestamp: {value!r}")
    return datetime.fromisoformat(value.upper().replace("Z", "+00:00"))


@FORMATS.checks("date-time", raises=ValueError)
def valid_timestamp(value):
    """An RFC 3339 timestamp that is also a real calendar value; the pattern alone admits 2026-99-99."""
    if not isinstance(value, str):
        return True  # The schema's type rule reports nonstrings.
    parse_timestamp(value)
    return True


def _validator(name):
    return Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}, format_checker=FORMATS)


def _no_duplicate_keys(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}; a record cannot carry two values for one field")
        seen.add(key)
    return dict(pairs)


def load_record(text: str) -> dict:
    """The one way a hardware evidence record is read from text: a JSON object with no duplicate
    key at any depth. `json.loads` would keep the last of duplicates, resolving a contradiction
    by position instead of refusing it (ADR-034)."""
    def no_constants(name):
        raise ValueError(f"{name} is not a JSON value a record may carry")

    value = json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=no_constants)
    if not isinstance(value, dict):
        raise ValueError("a hardware evidence record is a JSON object")
    canonical(value)  # an overflowing literal parses to infinity, which no canonical form admits
    return value


def _schema_errors(name, value) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path)) or '$'}: {e.message}"
            for e in sorted(_validator(name).iter_errors(value), key=lambda e: str(list(e.absolute_path)))]


def _strings(value, path="domain"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _strings(child, f"{path}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _strings(child, f"{path}/{index}")


def validate_contract_domain(contract: dict) -> list[str]:
    """Cross-field rules over a schema-valid common contract; returns error strings."""
    domain = contract.get("domain")
    errors = _schema_errors("contract_domain", domain)
    # The block is closed by schema, so every string it can carry is enumerable; none may assert
    # the status only the ledger can earn, whichever field it is written into.
    errors.extend(f"{path}: {VERIFIED} is earned in the acceptance ledger, never authored"
                  for path, text in _strings(domain) if re.search(rf"\b{VERIFIED}\b", text))
    if errors:
        return errors
    sources = {entry["id"] for entry in contract["sources"]}
    validation_ids = [check["id"] for check in contract["validation"]]
    levels = domain["validation_levels"]
    mapped, declared = set(levels), set(validation_ids)
    if mapped != declared:
        missing, extra = sorted(declared - mapped), sorted(mapped - declared)
        if missing:
            errors.append("validation_levels: every validation needs exactly one rung; unmapped: " + ", ".join(missing))
        if extra:
            errors.append("validation_levels: names validations the contract does not declare: " + ", ".join(extra))
    for check in contract["validation"]:
        level = levels.get(check["id"])
        if level is None:
            continue
        has_command = check.get("command") is not None
        if level in MACHINE_LEVELS and not has_command:
            errors.append(f"validation/{check['id']}: a {level} check must declare a command; "
                          "attestation cannot stand in for a runnable check")
        if level in HARDWARE_LEVELS and has_command:
            errors.append(f"validation/{check['id']}: a {level} check must not declare a command; "
                          "a re-executed command is a simulation, not hardware")
    for index, item in enumerate(domain["hardware_assumptions"]):
        if item["source_id"] not in sources:
            errors.append(f"hardware_assumptions/{index}: unknown source {item['source_id']}")
    for reference in domain["protocol_references"]:
        if reference not in sources:
            errors.append(f"protocol_references: unknown source {reference}")
    hardware_facing = bool(domain["hardware_assumptions"])
    hardware_checks = sorted(v for v, level in levels.items() if level in HARDWARE_LEVELS)
    if hardware_facing:
        if domain["hardware_status"] != UNVERIFIED:
            errors.append(f"hardware_status: a packet with hardware assumptions is {UNVERIFIED} until the ledger earns otherwise")
        if not domain["protocol_references"]:
            errors.append("protocol_references: a packet with hardware assumptions must cite its protocol or interface specification")
    else:
        if domain["hardware_status"] != NOT_FACING:
            errors.append(f"hardware_status: a packet with no hardware assumptions is {NOT_FACING}; "
                          "declare the assumptions if hardware behavior matters")
        if hardware_checks:
            errors.append("validation_levels: a packet with no hardware assumptions cannot carry a hardware-rung check: "
                          + ", ".join(hardware_checks))
    if domain["component"] == "hardware_adapter" and not hardware_facing:
        errors.append("component: a hardware adapter without a declared hardware assumption is a contradiction")
    return errors


def evidence_digest(record: dict) -> str:
    return hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()


def validate_hardware_evidence(record: dict) -> dict:
    errors = _schema_errors("hardware_evidence", record)
    if errors:
        raise ValueError("hardware evidence: " + "; ".join(errors))
    canonical(record)
    return record


def evidence_lines(record: dict) -> list[str]:
    """The attestation evidence an operator hands to `acceptance.py attest` for this record."""
    validate_hardware_evidence(record)
    values = {"level": record["level"], "device": record["device_identity"],
              "firmware": record["firmware_version"], "observed_at": record["observed_at"],
              "outcome": record["outcome"], "operator": record["operator"],
              "dispatch_id": record["dispatch_id"], "artifact_sha256": record["artifact_sha256"],
              "validation_id": record["validation_id"]}
    return [DIGEST_PREFIX + evidence_digest(record)] + [f"{key}={values[key]}" for key in EVIDENCE_KEYS]


def parsed_evidence(lines) -> tuple[str | None, dict]:
    """The digest and the recognized key=value lines of an attestation; see `parsed_evidence_strict`."""
    return parsed_evidence_strict(lines)[:2]


def parsed_evidence_strict(lines) -> tuple[str | None, dict, list[str]]:
    """The digest, the recognized key=value lines, and every other line an attestation carries.

    A recognized key that appears more than once is refused: keeping the first (or last) value
    would let a contradictory line ride along unverified. Every other line is returned so a
    hardware-rung attestation can refuse it (ADR-038): a line is recognized exactly or not at all,
    so ` outcome=fail` with a leading space is an unrecognized line, never a second outcome.
    """
    digests, values, unrecognized = [], {}, []
    for line in lines:
        if line.startswith(DIGEST_PREFIX):
            digests.append(line[len(DIGEST_PREFIX):])
            continue
        key, separator, value = line.partition("=")
        if separator and key in EVIDENCE_KEYS:
            if key in values:
                raise ValueError(f"Attestation carries more than one {key}= line; each attested line is "
                                 "verified, so a duplicate cannot be resolved by choosing one")
            values[key] = value
        else:
            unrecognized.append(line)
    return (digests[0] if len(digests) == 1 else None), values, unrecognized


def validate_attestation(contract: dict, attestation: dict, attested_at: str,
                         dispatch_id: str, artifact_sha256: str, submitted_at: str) -> None:
    """Refuse a hardware-rung attestation that does not bind a passing hardware evidence record.

    `attested_at` is the ATTESTATION event's own timestamp: an observation cannot be attested
    before it happened, so a declared `observed_at` later than the event that attests it is
    refused, whether or not a hardware evidence record is ever supplied to re-verify it.

    `dispatch_id` and `artifact_sha256` are the ledger's current submission (ADR-049): contract
    identity survives a RESUBMIT unchanged, so without checking these here an operator could
    re-attest an unchanged, rejected record and have it reported VERIFIED_ON_HARDWARE on the
    attestation basis alone, never reaching record_problems's equivalent check.

    `submitted_at` is when the current result and artifact were submitted (the ledger's INIT, or
    its latest RESUBMIT): checking dispatch_id/artifact_sha256 alone still lets a genuinely
    matching record predate the submission it claims to observe (ADR-052), so `observed_at` must
    fall between this lower bound and `attested_at`, the upper bound.
    """
    level = contract["domain"]["validation_levels"].get(attestation["validation_id"])
    if level not in HARDWARE_LEVELS:
        return  # A machine rung has a command; the controller already refuses attesting over it.
    broken = [line for line in attestation["evidence"] if "\n" in line or "\r" in line]
    if broken:
        raise ValueError(f"A {level} attestation element is one line; these carry a line break: "
                         + "; ".join(repr(line) for line in broken))
    digest, values, unrecognized = parsed_evidence_strict(attestation["evidence"])
    if digest is None or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"A {level} attestation must carry exactly one {DIGEST_PREFIX}<digest> line "
                         "binding its hardware evidence record")
    if unrecognized:
        raise ValueError(f"A {level} attestation carries only the digest line and the "
                         f"{len(EVIDENCE_KEYS)} lines `hardware-evidence` prints for its record; every "
                         "line is verified, so these are refused: " + "; ".join(repr(l) for l in unrecognized))
    missing = [key for key in EVIDENCE_KEYS if not values.get(key, "").strip()]
    if missing:
        raise ValueError(f"A {level} attestation must carry the bound record's " + ", ".join(missing))
    if values["level"] != level:
        raise ValueError(f"Hardware evidence was recorded at {values['level']} but the contract requires {level}")
    if values["validation_id"] != attestation["validation_id"]:
        # Post-merge independent review, ADR-056: without this, a schema-valid record for one
        # hardware-rung check could be appended unchanged for a different check at the same rung
        # -- level, device, firmware, observed_at, outcome, operator, dispatch_id and
        # artifact_sha256 can all legitimately match across two checks in the same submission.
        raise ValueError(f"Hardware evidence was recorded for {values['validation_id']} but this "
                         f"attestation is for {attestation['validation_id']}")
    if values["outcome"] != "pass":
        raise ValueError("A failed hardware observation is reported through the worker, never attested")
    if values["operator"].strip().casefold() != attestation["operator"].strip().casefold():
        raise ValueError("The attesting operator must be the operator who recorded the hardware evidence")
    observed = parse_timestamp(values["observed_at"])
    if observed > parse_timestamp(attested_at):
        raise ValueError(f"Hardware evidence observed_at {values['observed_at']} is after the "
                         f"attestation recording it at {attested_at}; an observation cannot be "
                         "attested before it happens")
    if observed < parse_timestamp(submitted_at):
        raise ValueError(f"Hardware evidence observed_at {values['observed_at']} is before the "
                         f"current result and artifact were submitted at {submitted_at}; an "
                         "observation of a resubmission cannot predate it")
    if values["dispatch_id"] != dispatch_id:
        raise ValueError(f"Hardware evidence was recorded for result {values['dispatch_id']} but "
                         f"the ledger's current result is {dispatch_id}; a resubmission clears "
                         "prior attestations and must be observed again")
    if values["artifact_sha256"] != artifact_sha256:
        raise ValueError(f"Hardware evidence was recorded for artifact {values['artifact_sha256']} "
                         f"but the ledger's current artifact is {artifact_sha256}")


def _find_record(evidence_dir: Path, digest: str):
    """The file whose canonical digest the attestation bound, whatever it contains; verification is
    separate. A file the loader refuses is named rather than skipped, so a contradictory record
    cannot hide behind "no matching record"."""
    refused = []
    for path in sorted(evidence_dir.glob("*.json")):
        try:
            record = load_record(path.read_text(encoding="utf-8-sig"))
            matched = evidence_digest(record) == digest
        except (OSError, ValueError) as exc:
            refused.append(f"{path.name}: {exc}")
            continue
        if matched:
            return path, record, refused
    return None, None, refused


# What a found record must agree with: the ledger binding, the contract, and every line the
# attestation carried. A digest proves the bytes; it does not prove they are a hardware record.
RECORD_FIELDS = {"device": "device_identity", "firmware": "firmware_version", "observed_at": "observed_at",
                 "operator": "operator", "level": "level", "outcome": "outcome",
                 "dispatch_id": "dispatch_id", "artifact_sha256": "artifact_sha256",
                 "validation_id": "validation_id"}


def record_problems(record, binding, validation_id, level, attestation) -> list[str]:
    """Why a digest-matched record does not verify the attestation; empty means it does."""
    try:
        validate_hardware_evidence(record)
    except ValueError as exc:
        return [f"record found by digest is not a valid hardware evidence record ({exc})"]
    problems = []
    if record["task_id"] != binding["task_id"]:
        problems.append(f"record task_id {record['task_id']} is not {binding['task_id']}")
    if record["revision"] != binding["revision"]:
        # A revised contract keeps the same task_id and can keep the same validation_id and rung,
        # so nothing else here would refuse a record made against a different, changed revision.
        problems.append(f"record revision {record['revision']} is not the ledger's {binding['revision']}")
    if record["contract_hash"] != binding["contract_hash"]:
        # Revision numbers are lineage-local (Codex round 13): two independently revised variants
        # of the same task can both be "revision 2" with different content, so the exact contract
        # is checked too, not merely its revision number.
        problems.append(f"record contract_hash {record['contract_hash']} is not the ledger's {binding['contract_hash']}")
    if record["dispatch_id"] != binding["dispatch_id"]:
        # Contract identity does not identify which implementation was tested (Codex round 16): a
        # rejected result can be resubmitted under the same contract and revision, clearing prior
        # attestations, and an unchanged evidence file must not silently re-verify the new one.
        problems.append(f"record dispatch_id {record['dispatch_id']} is not the ledger's {binding['dispatch_id']}")
    if record["artifact_sha256"] != binding["artifact_sha256"]:
        problems.append(f"record artifact_sha256 {record['artifact_sha256']} is not the ledger's "
                         f"{binding['artifact_sha256']}")
    if record["validation_id"] != validation_id:
        problems.append(f"record validation_id {record['validation_id']} is not {validation_id}")
    if record["level"] != level:
        problems.append(f"record level {record['level']} is not the contract's {level}")
    if record["outcome"] != "pass":
        problems.append("record outcome is not pass")
    if record["operator"].strip().casefold() != attestation["operator"].strip().casefold():
        problems.append("record operator is not the attesting operator")
    attested = parsed_evidence(attestation["evidence"])[1]
    for key in ("device", "firmware", "observed_at", "level", "outcome", "dispatch_id", "artifact_sha256",
               "validation_id"):
        # Exact: a device identity or firmware version that differs in case is a different unit.
        if attested.get(key) != str(record[RECORD_FIELDS[key]]):
            problems.append(f"attested {key} differs from the record's {RECORD_FIELDS[key]}")
    if attested.get("operator", "").strip().casefold() != record["operator"].strip().casefold():
        problems.append("attested operator differs from the record's operator")
    return problems


def status(ledger, evidence_dir=None) -> dict:
    """Derive the hardware status a task has earned; a compile or simulation pass never upgrades it."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import acceptance  # noqa: E402 — lazily, so the domain module never imports the controllers eagerly.
    state = acceptance.replay(ledger)[0]
    binding = state["binding"]
    # Contract identity alone does not identify which implementation was tested: a rejected
    # result can be resubmitted under the same contract and revision (ADR-047), so record
    # verification also binds the observation to the submission the ledger currently holds.
    submission = {**binding, "dispatch_id": state["result"]["dispatch_id"],
                  "artifact_sha256": acceptance.artifact_identity(state["artifact"])}
    if binding["domain_profile"] != PROFILE:
        raise ValueError(f"Ledger profile is {binding['domain_profile']}, not {PROFILE}")
    if state.get("domain_shortfall"):
        raise ValueError("Ledger contract predates the software-hardware domain rules and yields no hardware "
                         "status; it replays for audit and acceptance only: " + "; ".join(state["domain_shortfall"]))
    domain = state["contract"]["domain"]
    levels = domain["validation_levels"]
    gate = acceptance.deterministic_status(state)
    checks = []
    problems = []
    for check in state["contract"]["validation"]:
        identifier = check["id"]
        entry = {"validation_id": identifier, "level": levels[identifier], "gate": gate[identifier],
                 "machine_runnable": levels[identifier] in MACHINE_LEVELS, "evidence_digest": None,
                 "evidence_verified": None, "evidence_path": None}
        attestation = state["attestations"].get(identifier)
        if attestation is not None:
            if attestation.get("domain_shortfall"):  # stored before the rule that would refuse it (ADR-032)
                entry["evidence_verified"] = False
                problems.append(f"{identifier}: stored attestation fails the current rule: {attestation['domain_shortfall']}")
                checks.append(entry)
                continue
            entry["evidence_digest"] = parsed_evidence(attestation["evidence"])[0]
            if evidence_dir is not None and levels[identifier] in HARDWARE_LEVELS:
                path, record, refused = _find_record(Path(evidence_dir), entry["evidence_digest"] or "")
                # The digest proves which bytes were bound. Verification then requires those bytes to
                # be a valid hardware evidence record for this task, validation and rung, a passing
                # observation, recorded by the attesting operator, and saying exactly what the
                # attestation's lines say — a matching digest over anything else is not verification.
                if record is None:
                    found = [f"{identifier}: no hardware evidence record with the attested digest"
                             + (f" (refused: {'; '.join(refused)})" if refused else "")]
                else:
                    found = [f"{identifier}: {problem}" for problem in
                             record_problems(record, submission, identifier, levels[identifier], attestation)]
                entry["evidence_verified"] = not found
                entry["evidence_path"] = str(path) if path else None
                problems.extend(found)
        checks.append(entry)
    hardware_ids = [c["validation_id"] for c in checks if not c["machine_runnable"]]
    # What the verdict rests on. Without an evidence directory the ledger's attestations are the
    # only stream read: the digests they declare are reported, not re-verified against records.
    basis = "record" if evidence_dir is not None else "attestation"
    if domain["hardware_status"] == NOT_FACING:
        earned, reason = NOT_FACING, "The contract declares no hardware assumption."
    elif state["status"] != "ACCEPTED":
        earned, reason = UNVERIFIED, f"Acceptance ledger is {state['status']}, not ACCEPTED."
    elif not hardware_ids:
        earned, reason = UNVERIFIED, "No validation reaches a hardware rung; machine-runnable checks cannot verify hardware."
    elif problems:
        earned, reason = UNVERIFIED, "; ".join(problems)
    elif not all(gate[v] == "ATTESTED" for v in hardware_ids):
        earned, reason = UNVERIFIED, "A hardware-rung validation lacks an attestation."
    elif domain.get("synthetic"):
        # Codex round 18 on PR #34: synthetic:true declares every input fictional, establishing
        # no real hardware behavior. Checked last, only once nothing else disqualifies the
        # contract, so this refuses the upgrade to VERIFIED_ON_HARDWARE specifically -- a genuine
        # mismatch still reports its own reason above -- rather than masking real problems.
        earned, reason = UNVERIFIED, ("The contract declares synthetic: true; every input is fictional and "
                                      "establishes no real hardware behavior, so this profile refuses to "
                                      "derive VERIFIED_ON_HARDWARE for it.")
    else:
        earned = VERIFIED
        reason = ("Accepted with every hardware-rung validation attested; each attestation's declared digest "
                  "is reported as attested, not record-verified (no --evidence-dir was supplied)."
                  if basis == "attestation" else
                  "Accepted with every hardware-rung validation attested and every bound evidence record "
                  "re-verified by digest, task, validation, rung, outcome and operator.")
    # On the record basis a hardware rung counts only when its record verified; an attested rung
    # whose record is missing, invalid or inconsistent is not a satisfied rung. For a synthetic
    # contract a hardware rung never counts here either, for the same reason it never earns
    # VERIFIED_ON_HARDWARE above: an attested fictional observation is not a satisfied rung.
    satisfied = [c["level"] for c in checks
                 if c["gate"] == "PASSED"
                 or (c["gate"] == "ATTESTED" and c["evidence_verified"] is not False and not domain.get("synthetic"))]
    highest = max(satisfied, key=LEVELS.index) if satisfied else None
    return {"task_id": binding["task_id"], "revision": binding["revision"], "ledger_status": state["status"],
            "declared_hardware_status": domain["hardware_status"], "earned_hardware_status": earned,
            "evidence_basis": basis, "reason": reason, "component": domain["component"],
            "highest_level_satisfied": highest, "validations": checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate-contract", help="Apply the domain rules to a contract JSON")
    check.add_argument("contract", type=Path)
    evidence = commands.add_parser("hardware-evidence",
                                   help="Validate a hardware evidence record and print the attestation lines it binds")
    evidence.add_argument("record", type=Path)
    evidence.add_argument("--validation-id", help="Refuse a record recorded for a different validation")
    derive = commands.add_parser("status", help="Derive the earned hardware status from an acceptance ledger")
    derive.add_argument("ledger", type=Path)
    derive.add_argument("--evidence-dir", type=Path,
                        help="Re-verify every attested digest against the record files here; without it the "
                             "status rests on the ledger's attestations alone and says so")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-contract":
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import work_packet as wp
            contract = wp.read_json(args.contract)
            errors = wp.validate_contract(contract, PROFILE)
            if errors:
                raise ValueError("; ".join(errors))
            domain = contract["domain"]
            result = {"valid": True, "component": domain["component"],
                      "declared_hardware_status": domain["hardware_status"],
                      "validation_levels": domain["validation_levels"],
                      "note": "Structure only; no check was executed and no hardware behavior is established."}
        elif args.command == "hardware-evidence":
            record = load_record(args.record.read_text(encoding="utf-8-sig"))
            validate_hardware_evidence(record)
            if args.validation_id and record["validation_id"] != args.validation_id:
                raise ValueError(f"Record is for {record['validation_id']}, not {args.validation_id}")
            result = {"valid": True, "digest": evidence_digest(record), "outcome": record["outcome"],
                      "attest_evidence": evidence_lines(record),
                      "note": "An operator declaration the controller cannot authenticate; the digest binds it."}
        else:
            result = status(args.ledger, args.evidence_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Domain rule refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli_exit.run(main))
