# 17. User Guide

**Version 1, 2026-07-28.** For the reviewer using the control tower, and the administrator running it.

## 1. Signing in

There is no self-service signup. An administrator creates your account. Sign in and you land on the tower.

## 2. The estate

The tower lists every AI asset the company has registered: what it is, who owns it, where it is in its lifecycle, its risk level, its regulatory tier, and how many findings are open against it.

An asset being assessed narrates its progress: intake, orchestrating, inspecting, rolling up, done.

## 3. Registering an asset

Paste a paragraph describing the system in plain language: what it does, who owns it, what data it touches, who it affects. You do not fill in a form; the system turns the paragraph into a structured record.

Then it assesses the asset across up to five dimensions:

| Reviewer | Asks |
|---|---|
| Policy compliance | Does this break one of our own rules? |
| Risk assessment | What regulatory tier is this, and what makes it risky? |
| Data governance | What data does it use, on what basis, kept for how long? |
| Responsible AI | Has anyone tested it for bias, is it transparent, does a human oversee it? |
| Security and third party | What does it depend on, and who else can reach it? |

Not all five run on every asset: an orchestrator decides which apply, and records that decision.

Expect a few minutes. If it is the first assessment after a quiet period, add a minute for the model server to wake.

## 4. Reading an assessment

Each finding tells you five things: which rule or control it pins to, how severe it is, what it means in plain words, the evidence in the record that triggered it, and what to do about it. A finding that arrives incomplete is discarded before you see it.

The asset ends up either **compliant** or **flagged**. Flagged means there is work for a person. It does not mean the asset has been stopped, and the system has no ability to stop anything.

## 5. Flags

Route a flag to whoever should deal with it. That is the whole enforcement model: a work item for a human being.

## 6. Swapping the rulebook

This is the feature worth understanding. The rules are data, not code. Activating a different policy pack re-scores every asset in the estate against the new rules **immediately and at no cost**, because rule applicability is decided by plain matching rather than by the model.

One honest limit, worth knowing before anyone asks: the regulatory **tier** does not move in a re-score. Tiering needs the model, so it changes only when an asset is reassessed.

## 7. The audit trail

Every asset has a chain recording each step of its assessment, where each entry is sealed against the one before it. Open the audit panel to read it. If any past entry were altered, the panel reports exactly where the chain broke. Seeded demonstration assets have no chain at all, so anything you see was produced by a real run.

## 8. The sweep and the brief

The sweep runs three extra reviewers across a slice of the estate: one looks for monitoring and drift signals, one for what has changed in the regulations, and one produces reporting. The executive brief rolls the estate up for leadership.

## 9. For administrators

The people page creates reviewer and administrator accounts and deactivates them. Activating a pack is an administrator action, since it changes how the whole estate is judged.

## 10. Worth knowing

- **Nothing is ever auto-blocked.** By design, and there is no code that could.
- **Assets never leave for an outside model provider.** One self-hosted model, no cloud path.
- **The system governs what it is told.** It reads descriptions of AI systems, not the systems themselves, so a flattering registration produces a flattering result. Treat a clean assessment as a starting point, not assurance.
- **Tiers are about three-quarters accurate.** Confirm every one that matters.
