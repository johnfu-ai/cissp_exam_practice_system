import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.seed import run_seed
from app.models.etl import EtlDataset


def test_cli_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "app.etl.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "preview" in result.stdout
    assert "commit" in result.stdout
    assert "run" in result.stdout


def test_cli_preview_osg10_against_real_dataset(db_session, monkeypatch):
    # Integration test against the real docs/questions/osg10 dataset. Seeds the
    # osg10 dataset row then invokes run_preview directly. With the bilingual
    # transform, one CleanedQuestion is produced per external_id (420), each
    # carrying both en + zh (every osg10 record has a zh stem).
    run_seed(db_session)
    # Point the dataset source_path at the real repo dataset.
    repo_root = Path(__file__).resolve().parents[3]
    ds = db_session.execute(select(EtlDataset).filter_by(slug="osg10")).scalar_one()
    ds.source_path = str(repo_root / "docs" / "questions" / "osg10")
    db_session.flush()

    from app.etl.runner import run_preview
    from app.models.auth import Organization
    org_id = db_session.execute(select(Organization)).scalar_one().id
    run = run_preview(db_session, org_id, ds)
    summary = run.preview_summary
    # one bilingual record per external_id (no per-language fan-out)
    assert summary["would_create"] == 420
    # every record is bilingual (en + zh) for osg10
    assert summary["by_language"] == {"en": 420, "zh": 420}
    # matching normalizes to single_choice: 379 single + 3 matching = 382
    assert summary["by_type"] == {"single_choice": 382, "multiple_choice": 38}
