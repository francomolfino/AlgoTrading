from pathlib import Path
from uuid import uuid4

from algotrading.product_check import run_product_check


def test_product_flow_offline_end_to_end():
    root = Path("tests/.tmp") / f"product_flow_{uuid4().hex}"
    result = run_product_check(
        workspace=root / "workspace",
        report_path=root / "product_validation_report.md",
    )

    assert result.passed
    assert result.report_path.exists()
    assert "Product Validation Report" in result.report_path.read_text(encoding="utf-8")
    assert len(result.steps) >= 10
    assert all(step.passed for step in result.steps)
    assert (result.data_dir / "SPY_1D.csv").exists()
    assert (result.data_dir / "QQQ_1D.csv").exists()
    assert "primary_experiment" in result.artifacts
    assert (result.artifacts["primary_experiment"] / "research" / "stress_comparison.csv").exists()
    assert (result.artifacts["primary_experiment"] / "research_notes.json").exists()
