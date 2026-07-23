"""Seed Weaviate with a starter set of past governance DECISIONS.

These are authored prior verdicts, NOT derived from the estate: if an
inspector could retrieve a planted answer for an asset it is judging, the
eval's recall would measure nothing (the Papyrus discipline). source='seed'
so re-running wipes only these, never a real filed decision.

Run:  uv run python seed_precedent.py
"""

from app import precedent

DECISIONS = [
    ("Loan pre-screen model rejected for missing fairness assessment",
     "A production credit pre-screening model reading credit history was flagged high risk. "
     "No bias test was on record (POL-03, EU-H-04). Verdict: blocked from release until a "
     "documented fairness assessment was attached. Precedent: credit-adjacent models are high "
     "tier by default and fairness evidence is a release gate."),
    ("Support chatbot approved with disclosure banner",
     "A customer-facing support agent was assessed limited tier. It touched customer PII but "
     "stayed in-house. Verdict: approved on condition of an always-on AI disclosure banner "
     "(POL-06, EU-L-01). Precedent: disclosure is sufficient for limited-tier conversational agents."),
    ("Marketing generator approved with content labelling",
     "A copy-generation model on public web data was assessed limited tier. Verdict: approved "
     "with mandatory AI-content labels on output (EU-L-02). Precedent: generation without "
     "personal data is limited tier, labelling is the only obligation."),
    ("Emotion recognition pilot terminated as prohibited",
     "A workplace sentiment pilot reading employee faces was assessed unacceptable tier "
     "(EU-U-01, POL-05). Verdict: terminated and data deleted. Precedent: biometric emotion "
     "reading in the workplace is prohibited regardless of consent or accuracy."),
    ("Fraud engine approved with quarterly review",
     "A transaction fraud model was assessed high tier for its effect on account access. "
     "Oversight existed; financial data access triggered POL-09. Verdict: approved with "
     "quarterly access review. Precedent: fraud tooling is approvable when oversight is named."),
    ("Third-party summariser rejected over PII egress",
     "A meeting summariser sending transcripts with customer PII to an external API violated "
     "POL-01. Verdict: rejected; team moved to the in-house model lane. Precedent: PII to "
     "third-party models is a hard block, the fix is the private lane, not a waiver."),
    ("Retired churn model force-undeployed",
     "A churn model marked retired was found still serving traffic (POL-08). Verdict: "
     "undeployed within one sprint, owner recorded. Precedent: retired means undeployed; "
     "the register is reality, not paperwork."),
    ("HR screening ranker paused for oversight gap",
     "A CV ranking model in production had no named human reviewer (POL-02, EU-H-02). "
     "Verdict: paused until a reviewer-of-record was assigned. Precedent: employment-affecting "
     "models never run unsupervised."),
]


def main():
    precedent.ensure_collection()
    wiped = precedent.clear_seeded()
    for title, content in DECISIONS:
        precedent.index_decision(title, content, source="seed")
    print(f"wiped {wiped} old seed decisions, indexed {len(DECISIONS)}")
    hits = precedent.search("credit scoring model without bias test")
    print(f"probe search: {len(hits)} hits, top: {hits[0]['title'] if hits else 'NONE'}")


if __name__ == "__main__":
    main()
