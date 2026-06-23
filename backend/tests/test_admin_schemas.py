import pytest
from pydantic import ValidationError

from app.schemas.admin import CatParams, CatParamsIn, UserStatusIn, ReportSummaryOut


def test_cat_params_valid():
    p = CatParams(k0=0.5, decay=0.1, base_se=1.0, early_stop_enabled=True)
    assert p.k0 == 0.5


@pytest.mark.parametrize("bad", [
    {"k0": 0, "decay": 0.1, "base_se": 1.0, "early_stop_enabled": True},      # k0 must be >0
    {"k0": 0.5, "decay": -1, "base_se": 1.0, "early_stop_enabled": True},     # decay >=0
    {"k0": 0.5, "decay": 0.1, "base_se": 0, "early_stop_enabled": True},      # base_se >0
])
def test_cat_params_rejects_invalid(bad):
    with pytest.raises(ValidationError):
        CatParams(**bad)


def test_report_summary_optional_top_error_questions():
    r = ReportSummaryOut(
        scope="global", window_days=30, active_users=0, practice_session_count=0,
        exam_session_count=0, total_answers=0, correct_answers=0, accuracy=0.0,
        published_question_count=0, used_question_count=0, question_bank_usage_pct=0.0,
        top_error_questions=[],
    )
    assert r.top_error_questions == []
