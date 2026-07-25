const LABELS: Record<string, string> = {
  kansas_city_mo: "Kansas City, Missouri",
  kansas_city_ks: "Kansas City, Kansas",
  lenexa_ks: "Lenexa, Kansas",
  overland_park_ks: "Overland Park, Kansas",
  manhattan_ks: "Manhattan, KS",
  seattle_wa: "Seattle, WA",
  austin_tx: "Austin, TX",
};

const AUTHORITIES: Record<string, string> = {
  kansas_city_mo: "Kansas City, Missouri",
  kansas_city_ks: "Unified Government of Wyandotte County/Kansas City, Kansas",
  lenexa_ks: "City of Lenexa, Kansas",
  overland_park_ks: "City of Overland Park, Kansas",
};

export function jurisdictionLabel(id: string) {
  return LABELS[id] ?? id.replace(/_/g, " ").toUpperCase();
}

export function jurisdictionAuthority(id: string) {
  return AUTHORITIES[id] ?? jurisdictionLabel(id);
}
