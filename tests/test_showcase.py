"""
Unit and Integration Tests for Checkpoint 8: Showcase Scenario & Evidence Pack.
"""

import os
import subprocess
import pytest
from pathlib import Path

torch = pytest.importorskip("torch", reason="PyTorch is required for evidence pack neural surrogate evaluation")

from src.control.showcase import run_showcase_episode

from src.evidence_pack import export_complete_evidence_pack
from src.control.state import load_limits_config


def test_showcase_episode_execution_and_events():
    """Verify 12-step showcase episode executes cleanly and triggers all 6 required events."""
    limits = load_limits_config()
    log = run_showcase_episode(limits=limits, run_id="test_showcase_run")

    assert log.total_steps == 12
    assert len(log.steps) == 12

    # 1. Verification check: solver converged on all 12 steps, safe on non-infeasible steps
    for step_rec in log.steps:
        assert step_rec.verification_result.converged
        if not step_rec.infeasible_flag and not step_rec.fallback_used:
            assert step_rec.verification_result.is_safe
        else:
            assert step_rec.fallback_used is not None


    # 2. Check presence of all 6 required events across step labels & tags
    all_labels = " ".join([(s.error_label or "") for s in log.steps]).lower()

    # Event 1: Injected forecast error
    assert "injected forecast error" in all_labels
    # Event 2: Battery saturation
    assert "battery saturation" in all_labels
    # Event 3: Infeasible period fallback
    assert "infeasible stress" in all_labels
    # Event 4: Near-limit state
    assert "near-limit state" in all_labels
    # Event 5: Surrogate disagreement
    assert "surrogate disagreement" in all_labels
    # Event 6: Battery depletion
    assert "battery depletion" in all_labels


def test_export_complete_evidence_pack(tmp_path):
    """Verify complete evidence pack and EVIDENCE_INDEX.md export."""
    out_dir = str(tmp_path / "evidence")
    res = export_complete_evidence_pack(base_dir=out_dir)

    assert res["status"] == "success"
    assert Path(res["evidence_index_path"]).is_file()

    index_text = Path(res["evidence_index_path"]).read_text(encoding="utf-8")
    assert "Checkpoint 8 Evidence Index" in index_text
    assert "solver_config.json" in index_text
    assert "cp8_showcase_12step_soc.csv" in index_text
    assert "cp8_showcase_12step_verification.json" in index_text


def test_cli_final_demo(capsys):
    """Verify python main.py --final-demo CLI execution."""
    from main import run_final_demo
    run_final_demo()
    captured = capsys.readouterr()
    assert "CHECKPOINT 8 FINAL DEMO & EVIDENCE PACK GENERATED SUCCESSFULLY!" in captured.out
