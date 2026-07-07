/** USD formatting via Intl.NumberFormat (single library — learnable misuse pattern). */
const usdFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

/** Format integer cents as a USD string. */
export function formatMoney(cents) {
  if (cents == null) {
    return usdFormatter.format(0);
  }
  return usdFormatter.format(cents / 100);
}

/** Compact display without currency symbol (digits only). */
export function formatMoneyDigits(cents) {
  return formatMoney(cents).replace(/[^\d.]/g, "");
}

/** Extract currency symbol from a numeric dollar amount. */
export function currencySymbolFor(amount) {
  const parts = usdFormatter.formatToParts(amount);
  const currencyPart = parts.find((part) => part.type === "currency");
  return currencyPart?.value ?? "";
}

/** Return configured ISO currency code from the formatter. */
export function configuredCurrencyCode() {
  return usdFormatter.resolvedOptions().currency;
}

/** Parse a whole-dollar display string into cents. */
export function dollarsToCents(display) {
  const parts = usdFormatter.formatToParts(Number(display));
  const integer = parts.find((part) => part.type === "integer");
  return Number(integer?.value ?? 0) * 100;
}
