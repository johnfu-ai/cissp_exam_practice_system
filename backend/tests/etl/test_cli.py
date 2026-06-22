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
    # This is an integration test against the real docs/questions/osg10 dataset.
    # It seeds the osg10 dataset row then invokes run_preview directly, asserting
    # 840 would-create (420 questions x 2 languages).
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
    assert run.preview_summary["would_create"] == 840
