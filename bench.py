# bench.py - governance assessment quality, scored against data/estate/labeled.json
# The labeled set is the answer key: 15 assets with a KNOWN correct EU AI Act tier
# and KNOWN planted policy violations. Runs the real graph, so it costs a GPU run.
# Warm the Modal lane first, then prove one asset before paying for fifteen:
#
#   uv run python bench.py --only AI-9001   # ONE asset (the cost fence: always first)
#   uv run python bench.py                  # all 15
#
# Results land in bench_governance.json next to this file.
import json
import sys
import threading
import time
from pathlib import Path
from statistics import mean

from app import audit
from app.graph import graph, initial_state

HERE = Path(__file__).resolve().parent  # data paths hang off the file, not the CWD
LABELED = HERE / "data" / "estate" / "labeled.json"
OUTFILE = HERE / "bench_governance.json"

ONLY = None
if "--only" in sys.argv:
    i = sys.argv.index("--only")
    ONLY = sys.argv[i + 1] if len(sys.argv) > i + 1 else None

# a hung asset is abandoned, logged ERROR, and the remaining ones still run;
# five inspectors serialize on the one warm container at ~2-3 min each
ASSET_TIMEOUT_S = 2700

EXPECTED_STEPS = ("inventory done", "orchestrate done", "fan-in", "decision:")


# --- pure scoring (no graph, no network - smoke-testable on a fabricated state) ---


def describe(asset: dict) -> str:
    # the labeled records go in the front door as prose, same as a live registration
    third = f" It depends on the external vendor {asset['third_party']}." if asset.get("third_party") else ""
    oversight = f" Oversight: {asset['human_oversight']}." if asset.get("human_oversight") else " Nobody reviews its output."
    return (f"{asset['name']}: a {asset['type']} owned by {asset['owner']}. "
            f"{asset['purpose']}. Lifecycle: {asset['lifecycle']}. Runs on {asset['deployment'] or 'unstated infrastructure'}. "
            f"It reads: {', '.join(asset['data_touched']) or 'no stated data'}.{third}{oversight}")


def score_asset(final_state: dict, entry: dict, elapsed_s: float | None = None) -> dict:
    expected = entry["expected"]
    assessment = ((final_state or {}).get("asset") or {}).get("assessment") or {}
    findings = assessment.get("findings", []) or []
    found_controls = {str(f.get("control_id", "")) for f in findings}
    expected_controls = set(expected.get("policy_violations", []))

    got_tier = str(final_state.get("risk_tier", "")).lower()
    caught = expected_controls & found_controls

    log = final_state.get("audit") or []
    steps = " | ".join(str(e.get("step", "")) for e in log)
    audit_complete = audit.verify(log) == -1 and all(m in steps for m in EXPECTED_STEPS)

    return {
        "asset_id": entry["asset"]["asset_id"],
        "tier_ok": got_tier == expected["risk_tier"],
        "expected_tier": expected["risk_tier"],
        "got_tier": got_tier,
        "recall": len(caught) / len(expected_controls) if expected_controls else 1.0,
        "precision": len(caught) / len(found_controls) if found_controls else 1.0,
        "caught": sorted(caught),
        "missed": sorted(expected_controls - found_controls),
        "extra": sorted(found_controls - expected_controls),
        "audit_complete": audit_complete,
        "status": final_state.get("status", "missing"),
        "elapsed_s": round(elapsed_s, 1) if elapsed_s is not None else None,
    }


def aggregate(scores: list) -> dict:
    ok = [s for s in scores if s["status"] == "assessed"]
    return {
        "assets": len(scores),
        "completed": len(ok),
        "tier_accuracy": round(mean(s["tier_ok"] for s in ok), 3) if ok else 0.0,
        "violation_recall": round(mean(s["recall"] for s in ok), 3) if ok else 0.0,
        "flag_precision": round(mean(s["precision"] for s in ok), 3) if ok else 0.0,
        "audit_completeness": round(mean(s["audit_complete"] for s in ok), 3) if ok else 0.0,
    }


# --- the runner (this part costs a GPU run) ---------------------------------


def run_one(entry: dict) -> dict:
    asset = entry["asset"]
    print(f"[bench] {asset['asset_id']} start", flush=True)
    initial = initial_state(asset["asset_id"], describe(asset))
    box = {}

    def work():
        try:
            box["final"] = graph.invoke(initial, {"recursion_limit": 40})
        except Exception as e:
            box["error"] = str(e)

    t0 = time.time()
    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(ASSET_TIMEOUT_S)
    final = box.get("final") or {**initial, "status": "error", "error": box.get("error", "timeout")}
    s = score_asset(final, entry, elapsed_s=time.time() - t0)
    print(f"[bench] {asset['asset_id']} {s['status']}: tier {s['got_tier']!r} vs {s['expected_tier']!r}, "
          f"recall {s['recall']:.2f}, precision {s['precision']:.2f}", flush=True)
    return s


def main():
    entries = json.loads(LABELED.read_text())
    if ONLY:
        entries = [e for e in entries if ONLY in e["asset"]["asset_id"]]
        if not entries:
            sys.exit(f"no labeled asset matches {ONLY!r}")
    scores = [run_one(e) for e in entries]
    result = {"mode": f"only={ONLY}" if ONLY else "full", "summary": aggregate(scores), "assets": scores}
    OUTFILE.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
    print(f"written to {OUTFILE.name}")


if __name__ == "__main__":
    main()
