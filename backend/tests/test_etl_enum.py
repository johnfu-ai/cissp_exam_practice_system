from app.models.enums import EtlRunPhase


def test_etl_run_phase_values():
    assert EtlRunPhase.preview.value == "preview"
    assert EtlRunPhase.committed.value == "committed"
    assert EtlRunPhase.rolled_back.value == "rolled_back"
    assert EtlRunPhase("preview") is EtlRunPhase.preview
