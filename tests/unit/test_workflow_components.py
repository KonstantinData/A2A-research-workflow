"""Tests for classification, consolidation and output helpers."""

from __future__ import annotations

from pathlib import Path

from core import classify, consolidate, duplicate_check
from output import csv_export, pdf_render


def test_classify_recognises_keywords():
    data = {"description": "We provide software consulting services."}
    result = classify.classify(data)
    assert "6201" in result["wz2008"]
    assert "software" in result["gpt_tags"]


def test_consolidate_merges_agent_outputs(tmp_path: Path):
    agents = [
        {"source": "agent1", "legal_name": "Acme GmbH"},
        {"source": "agent2", "employees": 42},
    ]
    merged = consolidate.consolidate(agents)
    assert merged["legal_name"]["value"] == "Acme GmbH"
    assert merged["employees"]["source"] == "agent2"

    # verify CSV and PDF exports run without error
    csv_path = tmp_path / "out.csv"
    csv_export.export_csv({"company": "Acme"}, csv_path)
    assert csv_path.read_text().startswith("company")

    pdf_path = tmp_path / "out.pdf"
    pdf_render.render_pdf({"company": "Acme"}, pdf_path)
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_duplicate_detection():
    existing = {"domain": "https://example.com", "legal_name": "Acme Corp"}
    candidate = {"domain": "example.com", "legal_name": "ACME Corporation"}
    assert duplicate_check.is_duplicate(existing, candidate)


