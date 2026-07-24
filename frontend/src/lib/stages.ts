// narration labels for the pipeline stages the store exposes
export const STAGES: Record<string, string> = {
  intake: "Cataloguing the asset",
  orchestrating: "Choosing inspectors",
  inspecting: "Inspectors at work",
  rolling_up: "Rolling up findings",
  done: "Assessment complete",
};

export const TIER_COLORS: Record<string, string> = {
  unacceptable: "#7c2d12",
  high: "#b91c1c",
  limited: "#b45309",
  minimal: "#15803d",
};
