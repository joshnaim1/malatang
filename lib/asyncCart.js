const SPICE_LABELS = {
  mild: "Mild",
  medium: "Medium",
  hot: "Hot",
};

/** Resolve a spice id to a display label. */
export async function fetchSpiceLabel(spiceId) {
  if (spiceId === "invalid") {
    return Promise.reject(new Error("unknown spice"));
  }
  return SPICE_LABELS[spiceId] ?? "Unknown";
}

/** Sum line totals asynchronously. */
export async function loadCartTotal(lines) {
  const totals = await Promise.all(
    lines.map(async (line) => line.total),
  );
  return totals.reduce((acc, value) => acc + value, 0);
}

/** Return true when every line has a known spice label. */
export async function validateCartSpices(lines) {
  const checks = lines.map((line) => {
    const key = line.spiceLevel?.label?.toLowerCase();
    return fetchSpiceLabel(key);
  });
  const results = await Promise.all(checks);
  return results.every((label) => label !== "Unknown");
}

/** First spice label for a cart, or null when empty. */
export async function firstSpiceLabel(lines) {
  if (lines.length === 0) {
    return null;
  }
  const key = lines[0].spiceLevel?.label?.toLowerCase();
  return fetchSpiceLabel(key);
}
