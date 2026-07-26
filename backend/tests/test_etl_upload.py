"""FR-IMP-01 / #35: CSV/XLSX/JSON upload extractors + endpoint.

Covers (a) the §10.1 row->RawQuestion mapper and the three template extractors
(Csv/Json/Xlsx) + DatasetReader auto-detection as pure units, and (b) the full
``POST /api/etl/upload`` -> preview -> commit HTTP flow, verifying an uploaded
CSV question lands with the right domain / knowledge-point / tag mappings.
"""
import json

import pytest
from openpyxl import Workbook

from app.etl.extract import (
    CsvExtractor,
    DatasetReader,
    JsonExtractor,
    XlsxExtractor,
    _row_to_raw,
)


# --------------------------------------------------------------------------- #
# Unit: §10.1 row -> RawQuestion mapper
# --------------------------------------------------------------------------- #

def _full_row(**overrides):
    row = {
        "question_text": "What is CIA?",
        "question_type": "single_choice",
        "option_a": "Confidentiality",
        "option_b": "Integrity",
        "option_c": "Availability",
        "option_d": "",
        "correct_answers": "A",
        "explanation": "The triad",
        "domain": "1",
        "knowledge_points": "risk; governance",
        "tags": "governance,risk",
        "book": "OSG 10",
        "chapter": "Chapter 1",
        "difficulty": "medium",
        "license_status": "user_owned",
        "question_text_zh": "什么是CIA？",
        "option_a_zh": "保密性",
    }
    row.update(overrides)
    return row


def test_row_to_raw_maps_template_columns():
    raw = _row_to_raw(_full_row(), 2)
    assert raw.type == "single_choice"
    assert raw.stem.en == "What is CIA?" and raw.stem.zh == "什么是CIA？"
    # option_d empty -> options stop at C (contiguous a,b,c)
    assert [o.key for o in raw.options] == ["A", "B", "C"]
    assert raw.options[0].text.zh == "保密性"
    assert raw.correct_keys == ["A"]
    assert raw.explanation.en == "The triad"
    assert raw.meta["domain"] == 1
    assert raw.meta["knowledge_points"] == ["risk", "governance"]
    assert raw.meta["tags"] == ["governance", "risk"]
    assert raw.meta["book"] == "OSG 10"
    assert raw.source.chapter == 1 and raw.source.chapter_title == "Chapter 1"
    assert raw.difficulty == 3  # medium label -> 3
    assert raw.license_status == "user_owned"
    assert raw.id.startswith("upload-")  # content-addressed external id


def test_row_to_raw_multiple_correct_split_on_semicolon_or_comma():
    raw = _row_to_raw(_full_row(
        question_type="multiple_choice", correct_answers="A,C"
    ), 1)
    assert raw.correct_keys == ["A", "C"]


def test_row_to_raw_id_is_content_addressed_not_row_based():
    """Re-uploading the same question (even at a different row) is idempotent."""
    a = _row_to_raw(_full_row(), 1)
    b = _row_to_raw(_full_row(), 99)
    assert a.id == b.id


def test_row_to_raw_option_explanations_json_string_parsed():
    row = _full_row()
    row["option_explanations"] = '{"A": "because A"}'
    raw = _row_to_raw(row, 1)
    assert raw.option_explanations is not None
    assert raw.option_explanations["A"].en == "because A"


def test_row_to_raw_invalid_option_explanations_dropped_not_fatal():
    row = _full_row()
    row["option_explanations"] = "not json"
    raw = _row_to_raw(row, 1)  # must not raise
    assert raw.option_explanations is None


def test_row_to_raw_defaults_when_optional_columns_absent():
    row = {"question_text": "Q", "question_type": "single_choice",
           "option_a": "a", "option_b": "b", "correct_answers": "A",
           "explanation": "e"}
    raw = _row_to_raw(row, 1)
    assert raw.meta["domain"] is None
    assert raw.meta["knowledge_points"] == []
    assert raw.meta["book"] == "User Import"  # default
    assert raw.source.chapter == 0  # no chapter text -> 0
    assert raw.license_status is None


# --------------------------------------------------------------------------- #
# Unit: extractors + DatasetReader auto-detection
# --------------------------------------------------------------------------- #

_CSV = (
    "question_text,question_type,option_a,option_b,correct_answers,explanation,domain,knowledge_points,tags\n"
    "Q1,single_choice,A,B,A,exp1,1,kp1;kp2,t1\n"
    "Q2,multiple_choice,A,B,A;B,exp2,2,kp3,t2\n"
)


def test_csv_extractor(tmp_path):
    p = tmp_path / "questions.csv"
    p.write_text(_CSV, encoding="utf-8")
    raws, errors = CsvExtractor(p).read()
    assert not errors
    assert len(raws) == 2
    assert raws[0].stem.en == "Q1" and raws[0].correct_keys == ["A"]
    assert raws[1].correct_keys == ["A", "B"]  # "A;B" split
    assert raws[0].meta["knowledge_points"] == ["kp1", "kp2"]


def test_csv_extractor_strips_bom(tmp_path):
    p = tmp_path / "questions.csv"
    p.write_bytes(b"\xef\xbb\xbf" + _CSV.encode("utf-8"))  # UTF-8 BOM prefix
    raws, errors = CsvExtractor(p).read()
    assert not errors and len(raws) == 2
    assert raws[0].stem.en == "Q1"  # not '﻿Q1'


def test_json_extractor_array(tmp_path):
    p = tmp_path / "questions.json"
    p.write_text(json.dumps([
        {"question_text": "Q1", "question_type": "single_choice", "option_a": "A",
         "option_b": "B", "correct_answers": "A", "explanation": "e", "domain": 1},
    ]), encoding="utf-8")
    raws, errors = JsonExtractor(p).read()
    assert not errors and len(raws) == 1
    assert raws[0].meta["domain"] == 1  # int preserved (not string-coerced)


def test_json_extractor_questions_wrapper(tmp_path):
    p = tmp_path / "questions.json"
    p.write_text(json.dumps({"questions": [
        {"question_text": "Q", "question_type": "single_choice", "option_a": "A",
         "option_b": "B", "correct_answers": "A", "explanation": "e", "domain": "1"},
    ]}), encoding="utf-8")
    raws, _ = JsonExtractor(p).read()
    assert len(raws) == 1


def test_json_extractor_rejects_non_array(tmp_path):
    p = tmp_path / "questions.json"
    p.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    raws, errors = JsonExtractor(p).read()
    assert raws == [] and len(errors) == 1
    assert "array" in errors[0].reason


def test_xlsx_extractor(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["question_text", "question_type", "option_a", "option_b",
               "correct_answers", "explanation", "domain"])
    ws.append(["Q1", "single_choice", "A", "B", "A", "exp1", 1])
    ws.append(["Q2", "multiple_choice", "A", "B", "A,B", "exp2", 2])
    p = tmp_path / "questions.xlsx"
    wb.save(p)
    raws, errors = XlsxExtractor(p).read()
    assert not errors and len(raws) == 2
    assert raws[0].stem.en == "Q1"
    assert raws[1].correct_keys == ["A", "B"]
    assert raws[0].meta["domain"] == 1


def test_dataset_reader_auto_detects_csv(tmp_path):
    (tmp_path / "questions.csv").write_text(_CSV, encoding="utf-8")
    raws, errors, h = DatasetReader(tmp_path).read()
    assert not errors and len(raws) == 2
    assert isinstance(h, str) and len(h) == 64


def test_dataset_reader_auto_detects_xlsx(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["question_text", "question_type", "option_a", "option_b",
               "correct_answers", "explanation", "domain"])
    ws.append(["Q1", "single_choice", "A", "B", "A", "e", 1])
    (tmp_path / "questions.xlsx").parent  # noop
    wb.save(tmp_path / "questions.xlsx")
    raws, errors, _ = DatasetReader(tmp_path).read()
    assert not errors and len(raws) == 1


def test_dataset_reader_jsonl_path_unchanged(tmp_path):
    """Regression guard: the existing manifest+jsonl flow is unaffected."""
    (tmp_path / "manifest.json").write_text(json.dumps({"total_questions": 1}))
    (tmp_path / "questions.jsonl").write_text(json.dumps({
        "id": "q1",
        "source": {"book": "b", "edition": 1, "section": "", "chapter": 1,
                   "chapter_title": "c", "number": 1},
        "type": "single_choice",
        "stem": {"en": "s", "zh": ""},
        "options": [{"key": "A", "text": {"en": "a", "zh": ""}}],
        "correct_keys": ["A"],
        "explanation": {"en": "e", "zh": ""},
    }) + "\n")
    raws, errors, _ = DatasetReader(tmp_path).read()
    assert not errors and len(raws) == 1 and raws[0].id == "q1"


def test_dataset_reader_unknown_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        DatasetReader(tmp_path).read()


# --------------------------------------------------------------------------- #
# HTTP: upload -> preview -> commit
# --------------------------------------------------------------------------- #

@pytest.fixture
def client(db_session, session_with_roles):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.etl import router as etl_router
    from app.core.security import InMemoryRefreshTokenStore
    from app.db.session import get_session
    from app.dependencies import get_lockout_store, get_refresh_store
    from app.services.auth import InMemoryLockoutStore

    app = FastAPI()
    app.include_router(etl_router)
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db, store, email="imp@example.com"):
    from app.core.security import create_access_token
    from app.db.seed import PERMISSIONS
    from app.models.auth import OrganizationMembership, Role
    from app.models.enums import RoleName
    from app.services.auth import register_user

    user, _ = register_user(db, email=email, password="pw123456",
                            display_name="I", refresh_store=store)
    db.flush()
    r = db.query(Role).filter_by(name=RoleName.system_admin).first()
    db.query(OrganizationMembership).filter_by(user_id=user.id).one().role_id = r.id
    db.flush()
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=[RoleName.system_admin.value], perms=[c for c, _ in PERMISSIONS],
    )
    return {"Authorization": f"Bearer {token}"}, user.default_organization_id


def _seed_blueprint_and_taxonomy(db):
    from datetime import date

    from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint, Tag

    bp = ExamBlueprint(
        version_label="t", effective_date=date(2024, 4, 15), min_items=1, max_items=2,
        duration_minutes=60, passing_score=700, max_score=1000, is_current=True,
    )
    db.add(bp)
    db.flush()
    db.add(ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100))
    db.add(KnowledgePoint(name="risk"))
    db.add(Tag(name="governance"))
    db.flush()


def test_upload_csv_preview_then_commit_creates_question(client, tmp_path, monkeypatch):
    from app.api import etl as etl_api
    from app.models.question import Question, QuestionMapping, QuestionTranslation

    c, store, db = client
    monkeypatch.setattr(etl_api.settings, "etl_upload_root", str(tmp_path))
    _seed_blueprint_and_taxonomy(db)
    h, org_id = _headers(db, store)

    csv = (
        "question_text,question_type,option_a,option_b,correct_answers,explanation,"
        "domain,knowledge_points,tags\n"
        "What is CIA?,single_choice,Confidentiality,Integrity,A,Triad,1,risk,governance\n"
    )
    resp = c.post(
        "/api/etl/upload",
        files={"file": ("questions.csv", csv.encode("utf-8"), "text/csv")},
        data={"dataset_slug": "upload-test"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    run_id = body["run_id"]
    assert body["phase"] == "preview"
    assert body["preview_summary"]["would_create"] == 1
    assert body["dataset_slug"] == "upload-test"

    resp = c.post(f"/api/etl/runs/{run_id}/commit", headers=h)
    assert resp.status_code == 200, resp.text

    q = db.query(Question).filter_by(organization_id=org_id).one()
    assert q.question_type.value == "single_choice"
    assert q.difficulty == 3  # no difficulty in CSV -> single_choice prior = medium
    assert q.available_languages == ["en"]
    tr = db.query(QuestionTranslation).filter_by(question_id=q.id, language="en").one()
    assert tr.stem == "What is CIA?"
    assert tr.correct_answer_rationale == "Triad"

    mappings = db.query(QuestionMapping).filter_by(question_id=q.id).all()
    assert all(m.domain_id is not None for m in mappings), "domain 1 must resolve"
    assert any(m.knowledge_point_id is not None for m in mappings), "KP 'risk' must map"
    assert any(m.tag_id is not None for m in mappings), "tag 'governance' must map"


def test_upload_re_import_is_idempotent(client, tmp_path, monkeypatch):
    """Re-uploading the same file -> 'unchanged' (content-addressed external id)."""
    from app.api import etl as etl_api

    c, store, db = client
    monkeypatch.setattr(etl_api.settings, "etl_upload_root", str(tmp_path))
    _seed_blueprint_and_taxonomy(db)
    h, _ = _headers(db, store)

    csv = (
        "question_text,question_type,option_a,option_b,correct_answers,explanation,domain\n"
        "Q,single_choice,A,B,A,e,1\n"
    )
    r1 = c.post("/api/etl/upload", files={"file": ("q.csv", csv.encode(), "text/csv")},
                data={"dataset_slug": "idem"}, headers=h).json()
    assert r1["preview_summary"]["would_create"] == 1
    c.post(f"/api/etl/runs/{r1['run_id']}/commit", headers=h)

    r2 = c.post("/api/etl/upload", files={"file": ("q.csv", csv.encode(), "text/csv")},
                data={"dataset_slug": "idem"}, headers=h).json()
    assert r2["preview_summary"]["unchanged"] == 1
    assert r2["preview_summary"]["would_create"] == 0


def test_upload_rejects_unsupported_file_type(client, tmp_path, monkeypatch):
    from app.api import etl as etl_api
    c, store, db = client
    monkeypatch.setattr(etl_api.settings, "etl_upload_root", str(tmp_path))
    _seed_blueprint_and_taxonomy(db)
    h, _ = _headers(db, store)
    resp = c.post(
        "/api/etl/upload",
        files={"file": ("q.txt", b"hello", "text/plain")},
        data={"dataset_slug": "bad"},
        headers=h,
    )
    assert resp.status_code == 422


def test_upload_requires_question_import_permission(client, tmp_path, monkeypatch):
    """A user whose DB role lacks question:import gets 403, not a preview.

    get_current_user loads perms fresh from the DB (#8), so the token's perms
    claim is irrelevant - the user's actual role membership decides. A plain
    individual_learner (the default register_user role) has no question:import.
    """
    from app.api import etl as etl_api
    from app.core.security import create_access_token
    from app.models.enums import RoleName
    from app.services.auth import register_user

    c, store, db = client
    monkeypatch.setattr(etl_api.settings, "etl_upload_root", str(tmp_path))
    _seed_blueprint_and_taxonomy(db)
    user, _ = register_user(db, email="noperm@example.com", password="pw123456",
                            display_name="N", refresh_store=store)
    db.flush()
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=[RoleName.individual_learner.value], perms=[],
    )
    resp = c.post(
        "/api/etl/upload",
        files={"file": ("q.csv", b"k,v\n", "text/csv")},
        data={"dataset_slug": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_upload_validation_error_surfaces_in_preview(client, tmp_path, monkeypatch):
    """A row with a bad correct_answers key is isolated: preview shows 0 creates + 1 error."""
    from app.api import etl as etl_api
    c, store, db = client
    monkeypatch.setattr(etl_api.settings, "etl_upload_root", str(tmp_path))
    _seed_blueprint_and_taxonomy(db)
    h, _ = _headers(db, store)
    # correct_answers 'Z' references no option -> validation error
    csv = (
        "question_text,question_type,option_a,option_b,correct_answers,explanation,domain\n"
        "BadQ,single_choice,A,B,Z,e,1\n"
    )
    body = c.post("/api/etl/upload", files={"file": ("q.csv", csv.encode(), "text/csv")},
                  data={"dataset_slug": "errs"}, headers=h).json()
    assert body["preview_summary"]["would_create"] == 0
    assert len(body["preview_summary"]["errors"]) == 1
