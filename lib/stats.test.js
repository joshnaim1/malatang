import { describe, expect, it } from "vitest";
import { average, countInStock, pageSlice, sum } from "./stats.js";

describe("stats", () => {
  it("sums values", () => {
    expect(sum([2, 3, 5])).toBe(10);
  });

  it("averages values", () => {
    expect(average([2, 4, 6])).toBe(4);
  });

  it("returns null for empty average", () => {
    expect(average([])).toBeNull();
  });

  it("pages slices without dropping the last item", () => {
    const items = ["a", "b", "c", "d", "e"];
    expect(pageSlice(items, 0, 2)).toEqual(["a", "b"]);
    expect(pageSlice(items, 1, 2)).toEqual(["c", "d"]);
  });

  it("counts in-stock items", () => {
    const items = [{ qty: 0 }, { qty: 2 }, { qty: 5 }];
    expect(countInStock(items, 1)).toBe(2);
  });
});
