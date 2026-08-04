"""Bias and drift, as arithmetic.

Nothing in here touches the model, the network or the database. It takes the
counts a reviewer or a pipeline hands us and returns the numbers a regulator
recognises. That purity is the point: this module is the first thing in the
estate whose output is MEASURED rather than judged, so it has to be provable,
and it costs nothing to run.

The warning that belongs at the top of the file: the fairness metrics below are
mutually incompatible. Unless every group has the same base rate, or the model
is perfect, you cannot have equal precision AND equal false positive rate AND
equal false negative rate at once (Kleinberg et al. 2016; Chouldechova 2016).
So the product does NOT pick one. It makes the reviewer pick one, per asset,
with a reason, and puts that choice on the audit chain.
"""

import math

# --- the definitions of fair an asset can be bound to ------------------------
# "better" says which direction is good, so one comparison serves them all.

METRICS = {
    "dir": {
        "label": "Disparate impact ratio", "short": "DIR", "threshold": 0.80, "better": "high",
        "needs_labels": False,
        "plain": "The worst-treated group's approval rate as a share of the best-treated group's. "
                 "Below 0.80 is the four-fifths rule, the threshold regulators actually cite.",
    },
    "dpd": {
        "label": "Demographic parity difference", "short": "DPD", "threshold": 0.10, "better": "low",
        "needs_labels": False,
        "plain": "The raw gap in approval rates between the best and worst treated group.",
    },
    "eod": {
        "label": "Equal opportunity difference", "short": "EOD", "threshold": 0.10, "better": "low",
        "needs_labels": True,
        "plain": "Among the people who genuinely deserved a yes, the gap in how often each group got one.",
    },
    "eq_odds": {
        "label": "Equalised odds difference", "short": "EqO", "threshold": 0.10, "better": "low",
        "needs_labels": True,
        "plain": "The stricter test: the deserving and the undeserving must both be treated alike.",
    },
    "ppd": {
        "label": "Predictive parity difference", "short": "PPD", "threshold": 0.10, "better": "low",
        "needs_labels": True,
        "plain": "When the model says yes, is it right equally often for every group?",
    },
}

DEFAULT_METRIC = "dir"

# PSI bands, from credit-risk scorecards. Conventional thresholds, which is
# exactly why they are worth displaying: a number with an agreed line beats a
# number without one.
PSI_BANDS = ((0.10, "stable"), (0.25, "moderate"), (float("inf"), "significant"))


def metric_pass(key: str, computed: dict) -> bool:
    m = METRICS[key]
    v = computed["fairness"][key]
    return v >= m["threshold"] if m["better"] == "high" else v <= m["threshold"]


# --- per group, from the four confusion counts ------------------------------


def group_rates(g: dict) -> dict:
    tp, fp, fn, tn = (int(g.get(k, 0) or 0) for k in ("tp", "fp", "fn", "tn"))
    n = tp + fp + fn + tn
    selected = tp + fp
    return {
        "n": n,
        "selected": selected,
        "selection_rate": selected / n if n else 0.0,          # got a yes
        "tpr": tp / (tp + fn) if tp + fn else 0.0,             # of those who deserved one
        "fpr": fp / (fp + tn) if fp + tn else 0.0,             # of those who did not
        "precision": tp / selected if selected else 0.0,       # of the yeses, how many were right
        "accuracy": (tp + tn) / n if n else 0.0,
    }


def fairness(groups: dict) -> dict:
    """The five group-fairness numbers, plus who is worst off."""
    if not isinstance(groups, dict) or len(groups) < 2:
        raise ValueError("fairness needs at least two groups: one group cannot be unfair to itself")
    rows = {name: group_rates(g) for name, g in groups.items()}
    if any(r["n"] == 0 for r in rows.values()):
        raise ValueError("every group needs at least one decision in it")
    srs = {k: v["selection_rate"] for k, v in rows.items()}
    tprs = [v["tpr"] for v in rows.values()]
    fprs = [v["fpr"] for v in rows.values()]
    precs = [v["precision"] for v in rows.values()]
    lo, hi = min(srs.values()), max(srs.values())
    tpr_gap, fpr_gap = max(tprs) - min(tprs), max(fprs) - min(fprs)
    return {
        "rows": rows,
        "dpd": hi - lo,
        "dir": (lo / hi) if hi else 0.0,
        "eod": tpr_gap,
        "eq_odds": max(tpr_gap, fpr_gap),
        "ppd": max(precs) - min(precs),
        "worst_group": min(srs, key=srs.get),
        "best_group": max(srs, key=srs.get),
    }


def from_rows(rows: list) -> dict:
    """Build the group counts from raw decisions: (group, prediction, label).

    The ten-second path for an owner who has a spreadsheet and no metrics
    pipeline. prediction and label are 1 or 0.
    """
    groups: dict = {}
    for group, prediction, label in rows:
        g = groups.setdefault(str(group), {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        if int(prediction) == 1:
            g["tp" if int(label) == 1 else "fp"] += 1
        else:
            g["fn" if int(label) == 1 else "tn"] += 1
    return groups


# --- drift: always two windows compared -------------------------------------


def psi(ref: list, curr: list) -> float:
    """Population Stability Index: one number for 'has this shape changed'."""
    eps = 1e-6
    total = 0.0
    for r, c in zip(ref, curr):
        r, c = max(float(r), eps), max(float(c), eps)
        total += (c - r) * math.log(c / r)
    return total


def jsd(ref: list, curr: list) -> float:
    """Jensen-Shannon distance: 0 to 1, symmetric, so it displays as a bar."""
    eps = 1e-12

    def kl(p, q):
        return sum(pi * math.log(pi / max(qi, eps)) for pi, qi in zip(p, q) if pi > 0)

    m = [(float(r) + float(c)) / 2 for r, c in zip(ref, curr)]
    return math.sqrt(max(0.0, (kl([float(x) for x in ref], m) + kl([float(x) for x in curr], m)) / 2) / math.log(2))


def psi_band(value: float) -> str:
    return next(label for edge, label in PSI_BANDS if value < edge)


def drift(features: dict | None, scores: dict | None) -> list:
    """One row per signal, worst first. Prediction drift is its own kind because
    it needs no labels, which is why it is the signal that lands first."""
    rows = []
    for name, f in (features or {}).items():
        if not (f.get("ref") and f.get("curr")):
            continue  # a half-filled feature is a data problem, not a drift signal
        rows.append({"name": name, "kind": "input",
                     "psi": psi(f["ref"], f["curr"]), "jsd": jsd(f["ref"], f["curr"]),
                     "bins": f.get("bins", []), "ref": f["ref"], "curr": f["curr"]})
    if scores and scores.get("ref") and scores.get("curr"):
        rows.append({"name": "model score", "kind": "prediction",
                     "psi": psi(scores["ref"], scores["curr"]),
                     "jsd": jsd(scores["ref"], scores["curr"]),
                     "bins": scores.get("bins", []),
                     "ref": scores["ref"], "curr": scores["curr"]})
    for r in rows:
        r["band"] = psi_band(r["psi"])
    return sorted(rows, key=lambda r: r["psi"], reverse=True)


# --- the whole computed blob, stored beside the raw payload -----------------


def compute(payload: dict) -> dict:
    """Everything derived from one period's snapshot. Stored, never recomputed,
    so a number an auditor saw last quarter is the number they see today even
    after these formulas change."""
    f = fairness(payload["groups"])
    out = {
        "period": payload["period"],
        "n": payload.get("n") or sum(r["n"] for r in f["rows"].values()),
        "protected_attribute": payload.get("protected_attribute") or "unstated",
        "fairness": f,
        "drift": drift(payload.get("features"), payload.get("scores")),
        "performance": dict(payload.get("performance") or {}),
    }
    perf = out["performance"]
    if perf.get("auc") is not None and perf.get("baseline_auc") is not None:
        perf["drop"] = round(float(perf["baseline_auc"]) - float(perf["auc"]), 4)
    return out


# --- the deterministic inspector these numbers unlock -----------------------


def findings_from(asset_id: str, computed: dict, metric_key: str) -> list:
    """The first findings in the estate whose evidence is a measurement rather
    than a sentence. Plain code, not an agent: no cost, no variance, benchable."""
    out = []
    f, m = computed["fairness"], METRICS[metric_key]
    if not metric_pass(metric_key, computed):
        out.append({
            "finding_id": f"f-{asset_id}-fair-1",
            "inspector": "fairness_monitoring",
            "control_id": "EU-H-04",
            "severity": "high",
            "plain": f"Group '{f['worst_group']}' is approved at "
                     f"{f['dir'] * 100:.0f}% of the rate for '{f['best_group']}'.",
            "evidence": f"{m['short']} = {f[metric_key]:.3f} against a threshold of {m['threshold']}, "
                        f"measured on {computed['n']} decisions by "
                        f"{computed['protected_attribute']} in {computed['period']}",
            "remediation": "Re-threshold or retrain, then measure again before the next release.",
            "status": "open",
        })
    worst = computed["drift"][0] if computed["drift"] else None
    if worst and worst["psi"] > 0.25:
        out.append({
            "finding_id": f"f-{asset_id}-fair-2",
            "inspector": "fairness_monitoring",
            "control_id": "EU-H-01",
            "severity": "medium",
            "plain": f"The population this model sees has changed: '{worst['name']}' has shifted significantly.",
            "evidence": f"PSI {worst['psi']:.3f} (above 0.25 is a significant shift), period {computed['period']}",
            "remediation": "Review the population change and decide whether the model needs revalidating.",
            "status": "open",
        })
    drop = computed.get("performance", {}).get("drop")
    if drop is not None and drop > 0.05:
        out.append({
            "finding_id": f"f-{asset_id}-fair-3",
            "inspector": "fairness_monitoring",
            "control_id": "EU-H-04",
            "severity": "medium",
            "plain": "The model is measurably less accurate than when it was signed off.",
            "evidence": f"AUC {computed['performance']['auc']} against a baseline of "
                        f"{computed['performance']['baseline_auc']}, down {drop * 100:.0f} points",
            "remediation": "Revalidate against fresh data, or retire the model.",
            "status": "open",
        })
    return out
