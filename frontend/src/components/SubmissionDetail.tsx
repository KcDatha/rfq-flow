import { useState } from "react";
import { api, Quote, Submission } from "../api";
import { ConfidenceBadge, StatusChip } from "./badges";

export default function SubmissionDetail({ submission }: { submission: Submission }) {
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState(submission.status);

  async function makeQuote() {
    setError("");
    try {
      const q = await api.generateQuote(submission.rfq_id);
      setQuote(q);
      setStatus("QUOTED");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Quote failed");
    }
  }

  return (
    <div className="rounded border bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold">{submission.customer_name || "Unknown customer"}</h3>
        <StatusChip status={status} />
        <span className="text-xs text-gray-400">
          {new Date(submission.created_at).toLocaleString()} · extractor: {submission.extractor_used}
        </span>
        <button
          className="ml-auto rounded bg-emerald-700 px-3 py-1 text-sm font-medium text-white"
          onClick={makeQuote}
        >
          Generate quote
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <table className="mt-3 w-full text-left text-sm">
        <thead>
          <tr className="border-b text-gray-500">
            <th className="py-1 pr-2">Line</th>
            <th className="py-1 pr-2">Category</th>
            <th className="py-1 pr-2">Material</th>
            <th className="py-1 pr-2">Size</th>
            <th className="py-1 pr-2">Sched / Rating</th>
            <th className="py-1 pr-2">Qty</th>
            <th className="py-1 pr-2">Confidence</th>
            <th className="py-1">Notes</th>
          </tr>
        </thead>
        <tbody>
          {submission.line_items.map((item) => (
            <tr key={item.item_id} className="border-b align-top last:border-0">
              <td className="max-w-xs truncate py-1.5 pr-2" title={item.raw_line_text}>
                {item.raw_line_text}
              </td>
              <td className="py-1.5 pr-2">{item.product_category}</td>
              <td className="py-1.5 pr-2">{item.extracted_material}</td>
              <td className="py-1.5 pr-2">{item.extracted_size}</td>
              <td className="py-1.5 pr-2">{item.extracted_schedule}</td>
              <td className="py-1.5 pr-2">
                {item.quantity} {item.unit_of_measure}
              </td>
              <td className="py-1.5 pr-2">
                <ConfidenceBadge score={item.confidence_score} />
              </td>
              <td className="py-1.5 text-xs text-red-600">
                {item.validation_notes.join(" ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {quote && (
        <div className="mt-4 rounded bg-gray-50 p-3">
          <h4 className="text-sm font-semibold">Quote — {quote.customer_name}</h4>
          <table className="mt-2 w-full text-sm">
            <tbody>
              {quote.lines.map((line) => (
                <tr key={line.item_id} className="border-b last:border-0">
                  <td className="max-w-md truncate py-1 pr-2">{line.description}</td>
                  <td className="py-1 pr-2">
                    {line.quantity} {line.unit_of_measure}
                  </td>
                  <td className="py-1 pr-2 text-right">${line.unit_price.toFixed(2)}</td>
                  <td className="py-1 text-right">${line.line_total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-right font-semibold">Total: ${quote.total.toFixed(2)}</p>
          <p className="text-xs text-gray-400">
            Prices come from the starter price book in the backend — replace with ERP pricing in
            production.
          </p>
        </div>
      )}
    </div>
  );
}
