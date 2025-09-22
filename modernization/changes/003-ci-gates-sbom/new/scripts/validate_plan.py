#!/usr/bin/env python3
"""Validate modernization diagnostics against the execution plan."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Set

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "modernization" / "plan.json"
DIAGNOSTICS_PATH = ROOT / "modernization" / "diagnostics.md"
PLAN_ID_PATTERN = re.compile(r"^P\d{3}$")


@dataclass(frozen=True)
class DiagnosticsRow:
    """Represents a parsed row from ``diagnostics.md``."""

    id: str
    finding: str
    impact: str
    evidence: str
    status: str
    fix_id: str
    plan_id: str
    adr_id: str
    research_doc: str
    changeset_path: str

    @classmethod
    def from_row(cls, headers: Sequence[str], cells: Sequence[str]) -> "DiagnosticsRow":
        normalized = {header: cell.strip() for header, cell in zip(headers, cells)}
        return cls(
            id=normalized.get("id", ""),
            finding=normalized.get("finding", ""),
            impact=normalized.get("impact", ""),
            evidence=normalized.get("evidence", ""),
            status=normalized.get("status", ""),
            fix_id=normalized.get("fix_id", ""),
            plan_id=normalized.get("plan_id", ""),
            adr_id=normalized.get("adr_id", ""),
            research_doc=normalized.get("research_doc", ""),
            changeset_path=normalized.get("changeset_path", ""),
        )


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    return set(stripped.replace("|", "").strip()) <= {"-"}


def parse_diagnostics(path: Path) -> List[DiagnosticsRow]:
    lines = path.read_text(encoding="utf-8").splitlines()
    headers: List[str] | None = None
    rows: List[DiagnosticsRow] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if _is_separator(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if headers is None:
            headers = cells
            continue
        # Pad the cells to the number of headers in case the Markdown row ends with a trailing pipe.
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(DiagnosticsRow.from_row(headers, cells))
    if headers is None:
        raise ValueError("Failed to parse diagnostics header row")
    return rows


def parse_plan(path: Path) -> Dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    plan: Dict[str, dict] = {}
    for item in items:
        identifier = item.get("id")
        if not identifier:
            raise ValueError("Plan item is missing an 'id' field")
        if identifier in plan:
            raise ValueError(f"Duplicate plan id detected: {identifier}")
        plan[identifier] = item
    return plan


def collect_plan_ids(rows: Sequence[DiagnosticsRow]) -> Set[str]:
    plan_ids: Set[str] = set()
    for row in rows:
        for candidate in (row.plan_id, row.fix_id):
            value = candidate.strip()
            if value and PLAN_ID_PATTERN.match(value):
                plan_ids.add(value)
    return plan_ids


def extract_finding_ids(source_field: str) -> Set[str]:
    """Return the finding identifiers declared in a plan item's ``source`` field."""
    if not source_field:
        return set()
    findings: Set[str] = set()
    for segment in source_field.split(","):
        segment = segment.strip()
        if not segment:
            continue
        if segment.startswith("finding:"):
            _, value = segment.split(":", 1)
            findings.update(part.strip() for part in value.split(";") if part.strip())
        else:
            findings.add(segment)
    normalized: Set[str] = set()
    for finding in findings:
        normalized.update(part.strip() for part in finding.split(",") if part.strip())
    return normalized


def main() -> int:
    errors: List[str] = []

    if not PLAN_PATH.exists():
        errors.append(f"Missing plan file at {PLAN_PATH}")
    if not DIAGNOSTICS_PATH.exists():
        errors.append(f"Missing diagnostics file at {DIAGNOSTICS_PATH}")

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return 1

    diagnostics_rows = parse_diagnostics(DIAGNOSTICS_PATH)
    diagnostics_plan_ids = collect_plan_ids(diagnostics_rows)
    diagnostic_ids = {row.id for row in diagnostics_rows if row.id}

    plan_items = parse_plan(PLAN_PATH)
    plan_ids = set(plan_items.keys())

    missing_plan_entries = sorted(diagnostics_plan_ids - plan_ids)
    if missing_plan_entries:
        errors.append(
            "Plan IDs referenced in diagnostics.md are missing from plan.json: "
            + ", ".join(missing_plan_entries)
        )

    orphan_plan_entries = sorted(plan_ids - diagnostics_plan_ids)
    if orphan_plan_entries:
        errors.append(
            "Plan items listed in plan.json are not referenced in diagnostics.md: "
            + ", ".join(orphan_plan_entries)
        )

    for plan_id, item in plan_items.items():
        declared_findings = extract_finding_ids(item.get("source", ""))
        missing_findings = sorted(find_id for find_id in declared_findings if find_id and find_id not in diagnostic_ids)
        if missing_findings:
            errors.append(
                f"Plan item {plan_id} references unknown findings: " + ", ".join(missing_findings)
            )

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return 1

    print("Diagnostics and plan metadata are consistent ✅")
    print(f"Plan entries validated: {len(plan_items)}")
    print(f"Diagnostics rows parsed: {len(diagnostics_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
