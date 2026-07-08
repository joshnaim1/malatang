import { average, pageSlice } from "../lib/stats.js";
import { formatCents, formatLineLabel, sumLineTotals } from "../lib/format.js";

const SAMPLE_CART = [
  { name: "Tofu", spiceLevel: { label: "medium" }, total: 650, qty: 2 },
  { name: "Noodles", spiceLevel: null, total: 450, qty: 1 },
  { name: "Mushrooms", spiceLevel: { label: "hot" }, total: 550, qty: 3 },
];

export default function App() {
  const visible = pageSlice(SAMPLE_CART, 0, 2);
  const avgQty = average(SAMPLE_CART.map((line) => line.qty));
  const grandTotal = sumLineTotals(SAMPLE_CART);

  return (
    <main>
      <h1>Malatang Cart</h1>
      <p className="meta">Avg qty per line: {avgQty?.toFixed(1)}</p>
      <ul className="items">
        {visible.map((line) => (
          <li key={line.name}>
            <span>{formatLineLabel(line.name, line.spiceLevel)}</span>
            <span>{formatCents(line.total)}</span>
          </li>
        ))}
      </ul>
      <p className="total">Total: {formatCents(grandTotal)}</p>
    </main>
  );
}
