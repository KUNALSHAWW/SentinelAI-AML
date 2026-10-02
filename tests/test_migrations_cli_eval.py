"""Alembic matches the ORM; CLI smoke tests; benchmark regression floors and metric maths."""

import json

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from sentinelai.evaluation import metrics as M
from sentinelai.models.database import Base


def test_migration_creates_exactly_the_orm_schema(tmp_path):
    db = tmp_path / "mig.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": False}), Base.metadata)
    assert diff == [], diff
    command.downgrade(cfg, "base")


def test_cli_screen_and_scenarios(capsys):
    from sentinelai.cli import main
    main(["screen", "Sanctioned Russian Bank"])
    out = capsys.readouterr().out
    assert "MATCH" in out and "SYNTHETIC" in out
    main(["scenarios"])
    assert "sanctions-hit" in capsys.readouterr().out


def test_cli_analyze_deterministic_runs_all_scenarios(capsys, tmp_path):
    from sentinelai.cli import main
    out_file = tmp_path / "out.json"
    main(["analyze", "--no-llm", "-o", str(out_file)])
    results = json.loads(out_file.read_text())
    assert len(results) >= 12 and any(r["sar_required"] for r in results)
    assert "BLOCK" in capsys.readouterr().out


def test_cli_audit_verify_exit_code(capsys, tmp_path, monkeypatch):
    from sentinelai.cli import main
    from sentinelai.db import session as dbs
    dbs.configure_engine(f"sqlite+aiosqlite:///{tmp_path / 'a.db'}")
    with pytest.raises(SystemExit) as e:
        main(["audit", "verify"])
    assert e.value.code == 0 and json.loads(capsys.readouterr().out)["valid"] is True


# --------------------------------------------------------------------------- metrics maths
def test_roc_auc_known_values():
    assert M.roc_auc([.1, .4, .35, .8], [0, 0, 1, 1]) == pytest.approx(.75)
    assert M.roc_auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0 and M.roc_auc([4, 3, 2, 1], [0, 0, 1, 1]) == 0.0
    assert M.roc_auc([1, 1, 1, 1], [0, 1, 0, 1]) == .5
    assert M.roc_auc([1, 2], [1, 1]) != M.roc_auc([1, 2], [1, 1])          # undefined -> NaN


def test_prf_and_average_precision():
    c = M.confusion([.9, .8, .3, .2], [1, 0, 1, 0], .5)
    assert c == {"tp": 1, "fp": 1, "tn": 1, "fn": 1}
    p = M.prf(c)
    assert (p["precision"], p["recall"], p["f1"], p["fpr"]) == (.5, .5, .5, .5)
    assert M.average_precision([.9, .8, .7], [1, 0, 1]) == pytest.approx((1 + 2 / 3) / 2)


def test_dataset_is_reproducible_and_labelled():
    from sentinelai.evaluation.generator import make_dataset
    a, b = make_dataset(120, 5), make_dataset(120, 5)
    assert [s.id for s in a] == [s.id for s in b] and json.dumps([s.request for s in a]) == json.dumps([s.request for s in b])
    assert 0.15 <= sum(s.label for s in a) / len(a) <= 0.25 and any(s.hard_negative for s in a)
    assert {s.typology for s in a if s.label} >= {"structuring", "sanctions", "tbml", "round_trip", "mule_fan_in", "crypto"}


def test_benchmark_regression_floors():
    """Guard rails: a refactor that silently wrecks detection fails CI."""
    from sentinelai.evaluation.runner import run_benchmark, run_sanctions_matcher_eval
    b = run_benchmark(600, 7)
    e = b["engine"]
    assert e["roc_auc"] >= 0.92 and e["average_precision"] >= 0.70
    assert b["review_point"]["recall"] >= 0.95 and e["fpr"] <= 0.08
    naive = b["baselines"]["naive_threshold_rules"]
    assert naive["fpr"] > 0.4 and e["fpr"] < naive["fpr"] / 5                       # decisive FPR win over legacy rules
    assert b["per_typology_recall"]["round_trip"]["recall"] >= 0.9 and b["per_typology_recall"]["sanctions"]["recall"] >= 0.8
    m = run_sanctions_matcher_eval(n_random_names=800)
    assert m["false_positive_rate_random_names"]["rate"] <= 0.01
    assert all(m["variant_recall"][k]["recall_any_hit"] >= 0.9 for k in ("typo", "transposition", "reorder", "translit", "case_punct"))
