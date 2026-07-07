import { describe, expect, it } from "vitest";
import {
  configuredCurrencyCode,
  currencySymbolFor,
  dollarsToCents,
  formatMoney,
  formatMoneyDigits,
} from "./currency.js";

describe("currency", () => {
  it("formats cents as USD", () => {
    expect(formatMoney(1299)).toBe("$12.99");
  });

  it("formats null cents as zero dollars", () => {
    expect(formatMoney(null)).toBe("$0.00");
  });

  it("formats digit-only compact amounts", () => {
    expect(formatMoneyDigits(1050)).toBe("10.50");
  });

  it("reads currency symbol", () => {
    expect(currencySymbolFor(12)).toBe("$");
  });

  it("reports configured currency code", () => {
    expect(configuredCurrencyCode()).toBe("USD");
  });

  it("parses whole dollars to cents", () => {
    expect(dollarsToCents(12)).toBe(1200);
  });
});
