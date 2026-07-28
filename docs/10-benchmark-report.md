# 10. Benchmark Report

**Version 1, 2026-07-28.** Raw results are committed as `bench_governance.json`.

## 1. Method

Fifteen labelled assets, each with a known correct regulatory tier and a known set of violations, and **zero overlap with the 185-asset estate**, so nothing can be retrieved instead of judged. Each asset runs through the full pipeline on the live model lane and is scored on four measures:

| Measure | Definition |
|---|---|
| Tier accuracy | Assets given the correct regulatory risk tier |
| Violation recall | Known violations the system found |
| Flag precision | Of the flags raised, the share that were in the answer key |
| Audit completeness | Assets whose audit chain covers every step, intact |

## 2. Results

| Measure | Result |
|---|---|
| Assets | 15 |
| Completed | **15 of 15, zero retries, zero errors** |
| Tier accuracy | **73.3%** |
| Violation recall | **74.3%** |
| Flag precision | 46% |
| Audit completeness | **1.0** |

A single-asset probe before the full run completed cleanly with the correct tier and a complete audit chain, which is the cost fence that protects the full run.

## 3. What these numbers mean

- **Every asset completed on the first attempt.** For a five-agent parallel pipeline on one rented GPU, zero errors and zero retries across fifteen assets is the reliability result, and it is the number that took the most engineering to earn.
- **Audit completeness is exactly 1.0**, which is the point of the product: whatever the model judged, the record of how it judged is complete and verifiable.
- **Tier accuracy of 73 percent is the honest headline, and it is the weakest link.** One asset was rated high where the answer key says unacceptable. Under-rating is the dangerous direction of error for a governance tool, and it should be said plainly rather than averaged into a friendlier number.
- **Violation recall of 74 percent** means the system finds about three in four known problems. Useful as a first pass, not a substitute for review.
- **Flag precision of 46 percent** means roughly half of the flags were not in the answer key. Some are genuine issues the corpus author did not label, some are noise. They cannot be separated without a second reviewer, so the raw figure stands.

## 4. Limits, stated plainly

- Fifteen assets is a batch, not a statistical sample.
- The corpus and its answer key were written by the same person who built the system, which is the strongest bias here.
- Precision is measured against a key that was never intended to be exhaustive, so it understates real precision by an unknown amount.
- The measures depend on a warm lane; a cold start adds about a minute per asset.
- Nothing measures whether a remediation is good advice.

## 5. What the numbers are not

They are not a claim that the system can replace a governance function. They are evidence that a multi-agent pipeline can produce a **complete, control-referenced, tamper-evident record** for an estate, with roughly three-quarters accuracy on judgement, which is exactly how it should be described to a reviewer.

## 6. Reproducing

```bash
uv run python bench.py --only AI-9001    # one asset, the cost fence
uv run python bench.py                   # the full labelled set, one warm window
```

The benchmark's own scoring is covered by unit tests, so the numbers it prints are checked as well as the system it measures.
