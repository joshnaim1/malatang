import { describe, expect, it } from "vitest";
import { formatCents, formatLineLabel, sumLineTotals } from "./format.js";

describe("format", () => {
  it("formats cents", () => {
    expect(formatCents(1299)).toBe("$12.99");
  });

  it("formats null cents as zero", () => {
    expect(formatCents(null)).toBe("$0.00");
  });

  it("formats line labels with spice", () => {
    expect(formatLineLabel("Tofu", { label: "medium" })).toBe("Tofu (medium)");
  });

  it("defaults spice when missing", () => {
    expect(formatLineLabel("Noodles", null)).toBe("Noodles (mild)");
  });

  it("sums line totals", () => {
    expect(sumLineTotals([{ total: 500 }, { total: 750 }])).toBe(1250);
  });
});
