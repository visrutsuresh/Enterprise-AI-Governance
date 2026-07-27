// narration labels for the pipeline stages the store exposes
export const STAGES: Record<string, string> = {
  intake: "Cataloguing the asset",
  orchestrating: "Choosing inspectors",
  inspecting: "Inspectors at work",
  rolling_up: "Rolling up findings",
  done: "Assessment complete",
};

export const TIER_COLORS: Record<string, string> = {
  unacceptable: "#a63d2a",
  high: "#c95a4a",
  limited: "#a0772d",
  minimal: "#5f9a5c",
};
