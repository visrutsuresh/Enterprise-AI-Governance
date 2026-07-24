from conftest import make_finding

from app.state import risk_rollup, valid_finding


def test_valid_finding_passes():
    assert valid_finding(make_finding())
    assert valid_finding(make_finding(inspector="model_monitoring"))  # sweep agents may author findings


def test_malformed_findings_dropped():
    assert not valid_finding(make_finding(severity="High"))  # the casing trap
    assert not valid_finding(make_finding(severity="critical"))
    assert not valid_finding(make_finding(inspector="made_up_agent"))
    assert not valid_finding(make_finding(control_id=""))
    assert not valid_finding(make_finding(plain=""))
    assert not valid_finding({k: v for k, v in make_finding().items() if k != "remediation"})


def test_risk_rollup_deterministic():
    findings = [make_finding(), make_finding(severity="medium"), make_finding(severity="low")]
    r = risk_rollup(findings)
    assert r == {"level": "high", "score": 39, "why": "1 serious, 1 medium, 1 minor issues"}
    assert risk_rollup(findings) == r  # same input, same output, always


def test_risk_rollup_empty_and_capped():
    assert risk_rollup([]) == {"level": "low", "score": 0, "why": "0 serious, 0 medium, 0 minor issues"}
    assert risk_rollup([make_finding()] * 10)["score"] == 100  # capped, not 250
