import { describe, expect, it } from "vitest";
import {
  fetchSpiceLabel,
  firstSpiceLabel,
  loadCartTotal,
  validateCartSpices,
} from "./asyncCart.js";

const LINES = [
  { spiceLevel: { label: "medium" }, total: 650 },
  { spiceLevel: { label: "hot" }, total: 550 },
];

describe("asyncCart", () => {
  it("resolves spice labels", async () => {
    await expect(fetchSpiceLabel("hot")).resolves.toBe("Hot");
  });

  it("sums cart totals", async () => {
    await expect(loadCartTotal(LINES)).resolves.toBe(1200);
  });

  it("validates known spices", async () => {
    await expect(validateCartSpices(LINES)).resolves.toBe(true);
  });

  it("rejects unknown spices", async () => {
    await expect(
      validateCartSpices([{ spiceLevel: { label: "ghost" }, total: 100 }]),
    ).resolves.toBe(false);
  });

  it("returns null for empty first spice", async () => {
    await expect(firstSpiceLabel([])).resolves.toBeNull();
  });

  it("rejects invalid spice ids", async () => {
    await expect(fetchSpiceLabel("invalid")).rejects.toThrow("unknown spice");
  });
});
