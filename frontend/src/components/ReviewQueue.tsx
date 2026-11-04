import { useCallback, useEffect, useState } from "react";
import { api, getCachedSubmissions, LineItem } from "../api";
import { ConfidenceBadge } from "./badges";

function ReviewCard({
  item,
  materials,
  onDone,
}: {
  item: LineItem;
  materials: string[];
  onDone: () => void;
}) {
  const [material, setMaterial] = useState(item.extracted_material ?? "");
  const [size, setSize] = useState(item.extracted_size ?? "");
  const [schedule, setSchedule] = useState(item.extracted_schedule ?? "");
  const [quantity, setQuantity] = useState(String(item.quantity ?? ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function approve() {
    setBusy(true);
    setError("");
    try {
      await api.reviewItem(item.item_id, {
        extracted_material: material || undefined,
        extracted_size: size || undefined,
        extracted_schedule: schedule || undefined,
        quantity: quantity ? parseInt(quantity, 10) : undefined,
      });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
      setBusy(false);
    }
  }

  const input = "w-full rounded border px-2 py-1 text-sm";
  return (
    <div className="rounded border bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium" title={item.raw_line_text}>
            {item.raw_line_text}
          </p>
          <p className="text-xs text-gray-500">
            {item.customer_name ?? "Unknown customer"} · {item.product_category}
          </p>
        </div>
        <span className="ml-auto">
          <ConfidenceBadge score={item.confidence_score} />
        </span>
      </div>
      {item.validation_notes.length > 0 && (
        <ul className="mt-2 list-inside list-disc text-sm text-red-600">
          {item.validation_notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      )}
      <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
        <label className="text-xs text-gray-500">
          Material
          <select className={input} value={material} onChange={(e) => setMaterial(e.target.value)}>
            <option value="">(unknown)</option>
            {materials.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
            {material && !materials.includes(material) && (
              <option value={material}>{material}</option>
            )}
          </select>
        </label>
        <label className="text-xs text-gray-500">
          Size
          <input className={input} value={size} onChange={(e) => setSize(e.target.value)} />
        </label>
        <label className="text-xs text-gray-500">
          Schedule / rating
          <input
            className={input}
            value={schedule}
            onChange={(e) => setSchedule(e.target.value)}
          />
        </label>
        <label className="text-xs text-gray-500">
          Quantity
          <input
            className={input}
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </label>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <div className="mt-3 text-right">
        <button
          className="rounded bg-sky-700 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          onClick={approve}
          disabled={busy}
        >
          {busy ? "Saving…" : "Approve line item"}
        </button>
      </div>
    </div>
  );
}

/** Flagged items from the browser mirror, reshaped like the server queue. */
function cachedQueueItems(): LineItem[] {
  return getCachedSubmissions().flatMap((sub) =>
    sub.line_items
      .filter((i) => i.requires_human_review && !i.reviewed)
      .map((i) => ({ ...i, customer_name: sub.customer_name }))
  );
}

export default function ReviewQueue({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<LineItem[]>([]);
  const [materials, setMaterials] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    // The catalog is only an aid for the material dropdown; its failure
    // must not blank the queue itself (it used to, via Promise.all).
    const mats = api.materials().catch(() => null);
    try {
      const queue = await api.reviewQueue();
      const seen = new Set(queue.map((i) => i.item_id));
      setItems([...queue, ...cachedQueueItems().filter((i) => !seen.has(i.item_id))]);
      setError("");
    } catch (e) {
      const cached = cachedQueueItems();
      if (cached.length > 0) setItems(cached);
      setError(e instanceof Error ? e.message : "Could not load the review queue");
    } finally {
      setLoading(false);
    }
    const m = await mats;
    if (m) setMaterials(m.map((x) => x.grade_id));
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  if (loading && items.length === 0) {
    return (
      <div className="rounded border bg-white p-6 text-center text-gray-500 shadow-sm">
        Loading review queue…
      </div>
    );
  }

  if (!loading && items.length === 0) {
    return (
      <div className="rounded border bg-white p-6 text-center text-gray-500 shadow-sm">
        {error ? (
          <>
            <p className="text-red-600">Could not load the review queue: {error}</p>
            <button
              className="mt-3 rounded bg-sky-700 px-4 py-1.5 text-sm font-medium text-white"
              onClick={load}
            >
              Retry
            </button>
          </>
        ) : (
          "Review queue is clear. Flagged line items will show up here."
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="flex items-center gap-3 rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          <span>Showing saved data — refresh failed: {error}</span>
          <button className="ml-auto font-medium underline" onClick={load}>
            Retry
          </button>
        </div>
      )}
      {items.map((item) => (
        <ReviewCard key={item.item_id} item={item} materials={materials} onDone={load} />
      ))}
    </div>
  );
}
