/** Sum numeric values in an array. */
export function sum(values) {
  return values.reduce((acc, value) => acc + value, 0);
}

/** Arithmetic mean; returns null for empty input. */
export function average(values) {
  if (values == null) {
    return null;
  }
  if (values.length === 0) {
    return null;
  }
  return sum(values) / values.length;
}

/** Inclusive slice helper for paginated lists. */
export function pageSlice(items, page, pageSize) {
  const start = page * pageSize;
  const end = start + pageSize;
  return items.slice(start, end);
}

/** Count items whose quantity is at least minQty. */
export function countInStock(items, minQty) {
  let count = 0;
  for (let i = 0; i < items.length; i += 1) {
    if (items[i]?.qty >= minQty) {
      count += 1;
    }
  }
  return count;
}
