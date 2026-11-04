import { useCallback, useEffect, useState } from "react";
import { api, getCachedSubmissions, mergeSubmissions, Submission } from "../api";
import { StatusChip } from "./badges";
import SubmissionDetail from "./SubmissionDetail";

export default function Submissions({ refreshKey }: { refreshKey: number }) {
  const [subs, setSubs] = useState<Submission[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const server = await api.listRfqs();
      // Merge in the browser mirror: serverless instances each hold
      // their own demo data, so a bare server list can come back empty
      // right after a successful submit.
      setSubs(mergeSubmissions(server, getCachedSubmissions()));
      setError("");
    } catch (e) {
      const cached = getCachedSubmissions();
      if (cached.length > 0) setSubs(cached);
      setError(e instanceof Error ? e.message : "Could not load submissions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  if (loading && subs.length === 0) {
    return (
      <div className="rounded border bg-white p-6 text-center text-gray-500 shadow-sm">
        Loading submissions…
      </div>
    );
  }

  if (!loading && subs.length === 0) {
    return (
      <div className="rounded border bg-white p-6 text-center text-gray-500 shadow-sm">
        {error ? (
          <>
            <p className="text-red-600">Could not load submissions: {error}</p>
            <button
              className="mt-3 rounded bg-sky-700 px-4 py-1.5 text-sm font-medium text-white"
              onClick={load}
            >
              Retry
            </button>
          </>
        ) : (
          "No RFQs yet. Submit one from the first tab."
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
      {subs.map((sub) => (
        <div key={sub.rfq_id}>
          <button
            className="flex w-full items-center gap-3 rounded border bg-white px-4 py-2.5 text-left shadow-sm"
            onClick={() => setOpenId(openId === sub.rfq_id ? null : sub.rfq_id)}
          >
            <span className="font-medium">{sub.customer_name || "Unknown customer"}</span>
            <StatusChip status={sub.status} />
            <span className="text-sm text-gray-500">
              {sub.line_items.length} line items
            </span>
            <span className="ml-auto text-xs text-gray-400">
              {new Date(sub.created_at).toLocaleString()}
            </span>
          </button>
          {openId === sub.rfq_id && (
            <div className="mt-2">
              <SubmissionDetail submission={sub} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
