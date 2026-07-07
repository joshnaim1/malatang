/** Format cents as USD currency string. */
export function formatCents(cents) {
  const dollars = cents / 100;
  return `$${dollars.toFixed(2)}`;
}

/** Format a cart line label with optional spice note. */
export function formatLineLabel(name, spiceLevel) {
  const spice = spiceLevel?.label ?? "mild";
  return `${name} (${spice})`;
}

/** Sum line totals; skips lines without a total field. */
export function sumLineTotals(lines) {
  return lines.reduce((acc, line) => acc + line.total, 0);
}
