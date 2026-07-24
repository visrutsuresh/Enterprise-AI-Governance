"""fan_in is plain code on purpose: these tests pin its exact behaviour."""

from conftest import make_finding

from app.graph import fan_in, inspector_status
from app.state import INSPECTORS


def _state(**over):
    s = {
        "asset_id": "AI-test1",
        "status": "processing",
        "asset": {"asset_id": "AI-test1", "source": "pipeline"},
        "applicable_inspectors": list(INSPECTORS),
        "findings_raw": [],
        "inspector_reports": [{"inspector": n, "status": "ok", "note": ""} for n in INSPECTORS],
        "risk_tier": "High",
        "audit": [],
    }
    s.update(over)
    return s


def test_findings_kept_and_malformed_dropped():
    good = make_finding()
    bad = make_finding(severity="")  # half-formed: never shown
    out = fan_in(_state(findings_raw=[good, bad, "not even a dict"]))
    a = out["asset"]["assessment"]
    assert a["findings"] == [good]
    assert a["risk"]["score"] == 25
    assert "1 findings kept, 2 dropped" in out["audit"][0]


def test_tier_lowercased_at_fan_in():
    out = fan_in(_state(risk_tier="Unacceptable"))
    assert out["risk_tier"] == "unacceptable"
    assert out["asset"]["assessment"]["risk_tier"] == "unacceptable"


def test_failed_inspector_recorded_not_swallowed():
    reports = [{"inspector": n, "status": "ok", "note": ""} for n in INSPECTORS if n != "security_third_party"]
    reports.append({"inspector": "security_third_party", "status": "failed", "note": "step cap"})
    out = fan_in(_state(inspector_reports=reports))
    assert out["asset"]["assessment"]["inspector_status"]["security_third_party"] == "failed"


def test_missing_report_never_assumed_ok():
    status = inspector_status([], applicable=list(INSPECTORS))
    assert all(v == "failed" for v in status.values())


def test_skipped_by_design_is_not_failed():
    applicable = [n for n in INSPECTORS if n != "data_governance"]
    reports = [{"inspector": n, "status": "ok", "note": ""} for n in applicable]
    status = inspector_status(reports, applicable)
    assert status["data_governance"] == "skipped"
    assert status["policy_compliance"] == "ok"
