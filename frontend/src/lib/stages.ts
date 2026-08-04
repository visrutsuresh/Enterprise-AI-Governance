// narration labels for the pipeline stages the store exposes
export const STAGES: Record<string, string> = {
  intake: "Cataloguing the asset",
  orchestrating: "Choosing inspectors",
  inspecting: "Inspectors at work",
  rolling_up: "Rolling up findings",
  done: "Assessment complete",
};

// Severity and tier are shown by WEIGHT, not hue: a solid chip is the worst
// thing on the page, an outlined chip is the middle, plain text recedes. That
// survives a bad projector, a greyscale print and a colour-blind reader, none
// of which the old four-colour scale did.
export const TIER_CLASS: Record<string, string> = {
  unacceptable: "sev sev-hi",
  high: "sev sev-hi",
  limited: "sev sev-mid",
  minimal: "sev sev-low",
};

export const SEV_CLASS: Record<string, string> = {
  high: "sev sev-hi",
  critical: "sev sev-hi",
  serious: "sev sev-hi",
  medium: "sev sev-mid",
  moderate: "sev sev-mid",
  low: "sev sev-low",
};

export const sevClass = (s: string | null | undefined) =>
  SEV_CLASS[(s ?? "").toLowerCase()] ?? "sev sev-low";
export const tierClass = (t: string | null | undefined) =>
  TIER_CLASS[(t ?? "").toLowerCase()] ?? "sev sev-low";
