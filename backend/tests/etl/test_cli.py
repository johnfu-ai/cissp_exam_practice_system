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
    # Integration test against the real docs/questions/osg10 dataset.
    # The dataset has 420 questions, but 6 are mislabelled as `single_choice`
    # while having multiple `correct_keys` (legitimate "Choose two/three"
    # multi-answer items). The runner's validation rejects those 6, so:
    #   would_create = (420 - 6) * 2 languages = 828
    # See task-10-report.md (concern: dataset has 6 mislabelled type entries)
    # and Task 11 (E2E verification) which should address the data fix.
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
    assert run.preview_summary["would_create"] == 828
