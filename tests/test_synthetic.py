"""Ticket 02 fixture, intent, determinism, and truth-boundary evidence."""

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from fundo_reviewer.data import load_input
from fundo_reviewer.synthetic import (
    ADVANCE,
    AS_OF,
    GENERATOR_VERSION,
    GROUPS,
    HOLDOUT_BUSINESSES,
    NSFS,
    REVENUE_EXCLUSIONS,
    SCENARIOS,
    SEED,
    UNMATCHED,
    generate_files,
    write_files,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXPECTED_SHA256 = {
    "ground_truth/main_90_days.json": "ab0ab78968383da65f9acd4df12970bbc3945a086ff8d33ce741740264d859d5",
    "ground_truth/short_61_days.json": "14382ee8f7deff0b85b7eca015b1c0b20386699b532ac69710f918d977259230",
    "transactions/main_90_days.json": "c5d09a0703be1c8a30f785752c91f547256ed870ddd045d33b9896252d434230",
    "transactions/short_61_days.json": "c2ae06e039f3ba7e1740ee9c65e7a8d641e9e6b568810836a324b5483f89ca17",
}


def _read(cohort: str):
    normalized = load_input(DATA / "transactions" / f"{cohort}.json")
    source = json.loads((DATA / "transactions" / f"{cohort}.json").read_text())
    truth = json.loads((DATA / "ground_truth" / f"{cohort}.json").read_text())
    return normalized, source, truth


def test_committed_fixtures_are_exact_regeneration_and_hashes_are_stable(tmp_path, capsys):
    expected = generate_files()
    assert set(expected) == {
        "transactions/main_90_days.json", "ground_truth/main_90_days.json",
        "transactions/short_61_days.json", "ground_truth/short_61_days.json",
    }
    for path, contents in expected.items():
        assert (DATA / path).read_bytes() == contents
        assert contents.endswith(b"\n")
        assert hashlib.sha256(contents).hexdigest() == EXPECTED_SHA256[path]
    assert generate_files() == expected
    hashes = write_files(tmp_path)
    capsys.readouterr()
    assert hashes == {name: hashlib.sha256(contents).hexdigest() for name, contents in expected.items()}
    assert all((tmp_path / name).read_bytes() == contents for name, contents in expected.items())


def test_main_cohort_schema_coverage_id_alignment_and_truth_isolation():
    normalized, source, truth = _read("main_90_days")
    assert source["as_of"] == AS_OF.isoformat()
    assert len(normalized.business_coverage) == 10
    assert len(normalized.transactions) == len(source["transactions"]) == 2000
    assert all(item.days == 90 and item.is_complete_90_days for item in normalized.business_coverage)
    assert all(item.start == date(2026, 7, 11) for item in normalized.business_coverage)
    assert not normalized.excluded
    ids = {item.transaction_id for item in normalized.transactions}
    assert len(ids) == 2000
    assert ids == set(truth["labels"])
    assert all(not item.pending and item.amount != 0 for item in normalized.transactions)
    assert all(item.raw["iso_currency_code"] == "USD" for item in normalized.transactions)
    assert all(item.amount.as_tuple().exponent >= -2 for item in normalized.transactions)
    assert sum(item.is_inflow for item in normalized.transactions) == 1023
    assert sum(item.is_outflow for item in normalized.transactions) == 977
    assert truth["generator_version"] == GENERATOR_VERSION
    assert truth["seed"] == SEED
    assert truth["cohort"] == "main_90_days"
    forbidden = {
        "truth", "ground_truth", "truth_label", "scenario_id", "intended_group",
        "intended_personal", "intended_revenue", "hard_negative", "alternative_label",
        "rationale", "revenue_eligible", "ambiguous", "ambiguity_note",
    }
    assert not forbidden.intersection(source)
    assert all(not forbidden.intersection(record) for record in source["transactions"])
    assert all(not forbidden.intersection(account) for account in source["accounts"])


def test_scenario_inventory_all_named_groups_and_intent_based_truth():
    normalized, _, truth = _read("main_90_days")
    labels = truth["labels"]
    assert {value["group"] for value in labels.values()} == GROUPS | {UNMATCHED}
    assert {value["scenario_id"] for value in labels.values()} == set(SCENARIOS)
    assert {value["status"] for value in labels.values()} == {"business", "personal"}
    counts = Counter(value["scenario_id"] for value in labels.values())
    assert all(counts[scenario_id] > 0 for scenario_id in SCENARIOS)
    assert sum(value["hard_negative"] for value in labels.values()) > 0
    assert sum(value["ambiguous"] for value in labels.values()) > 0
    assert all(value["rationale"] and isinstance(value["rationale"], str) for value in labels.values())
    for record in normalized.transactions:
        label = labels[record.transaction_id]
        intended = SCENARIOS[label["scenario_id"]]
        assert label["group"] == intended.group
        assert label["status"] == intended.status
        assert record.is_inflow == (intended.direction == "in")
        assert label["revenue_eligible"] == (
            record.is_inflow and intended.status == "business" and intended.group not in REVENUE_EXCLUSIONS
        )
        assert label["ambiguous"] == bool(label.get("ambiguity_note"))
        if "alternative_label" in label:
            alt = label["alternative_label"]
            assert set(alt) == {"group", "status"}
            assert alt["group"] in GROUPS | {UNMATCHED}
            assert alt["status"] in {"business", "personal"}
            assert (alt["group"], alt["status"]) != (label["group"], label["status"])
    assert sum("alternative_label" in value for value in labels.values()) >= 200


def test_adversarial_cases_no_fee_bank_and_held_out_split():
    normalized, _, truth = _read("main_90_days")
    labels = truth["labels"]
    by_scenario = {}
    for record in normalized.transactions:
        by_scenario.setdefault(labels[record.transaction_id]["scenario_id"], []).append(record)
    square = by_scenario["processor_square"][0]
    assert "SQUARE INC" in square.name
    assert labels[square.transaction_id]["hard_negative"]
    assert labels[square.transaction_id]["revenue_eligible"]
    funder = by_scenario["advance_disbursement"][0]
    assert "SQUARE CAPITAL" in funder.name
    assert labels[funder.transaction_id]["group"] == ADVANCE
    assert not labels[funder.transaction_id]["revenue_eligible"]
    assert any("UCC 1" in record.name for record in by_scenario["ucc_punctuation"])
    assert any("OD-FEE" in record.name for record in by_scenario["overdraft_punctuation"])
    assert any("IGNORE PRIOR INSTRUCTIONS" in record.name for record in by_scenario["instruction_text"])
    assert labels[by_scenario["nsf_name_collision"][0].transaction_id]["hard_negative"]
    metadata = truth["business_metadata"]
    assert {name for name, data in metadata.items() if data["evaluation_split"] == "held_out"} == HOLDOUT_BUSINESSES
    assert metadata["biz_10"]["nsf_fee_observable"] is False
    assert metadata["biz_10"]["unobserved_payment_failures"] == "unknown"
    nsf_by_business = Counter(
        record.business_id for record in normalized.transactions
        if labels[record.transaction_id]["group"] == NSFS
    )
    assert nsf_by_business["biz_01"] == 5
    assert nsf_by_business["biz_02"] == 6
    assert nsf_by_business["biz_10"] == 0
    assert any(
        record.business_id == "biz_03" and record.amount == -25000
        and labels[record.transaction_id]["scenario_id"] == "advance_disbursement"
        for record in normalized.transactions
    )
    assert any(
        record.business_id == "biz_04" and record.amount == -18000
        and labels[record.transaction_id]["scenario_id"] == "customer_sale"
        for record in normalized.transactions
    )


def test_short_history_is_explicitly_separate_and_not_90_days():
    normalized, source, truth = _read("short_61_days")
    assert truth["cohort"] == "short_61_days"
    assert len(normalized.business_coverage) == 1
    assert normalized.business_coverage[0].business_id == "biz_61"
    assert normalized.business_coverage[0].start == date(2026, 8, 9)
    assert normalized.business_coverage[0].days == 61
    assert not normalized.business_coverage[0].is_complete_90_days
    assert len(normalized.transactions) == len(source["transactions"]) == len(truth["labels"]) == 120
    assert {record.transaction_id for record in normalized.transactions} == set(truth["labels"])
    assert not {record.transaction_id for record in normalized.transactions}.intersection(
        set(_read("main_90_days")[2]["labels"])
    )
