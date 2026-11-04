import { useState } from "react";
import { api, Submission } from "../api";
import SubmissionDetail from "./SubmissionDetail";

const SAMPLE = `Hi team,

Please quote the below for the Baytown turnaround:

20 pcs 4" SCH 40 A106 Gr B pipe
12 ea 2" SCH 80 316L elbow 90 deg
4 ea 3" 150# gate valve A105
8 ea 2" Monel 400 flange 300#
6 pcs 5" SCH 40 A106 Gr B pipe

Thanks,
Mike
Bayou Process Services`;

export default function SubmitForm({ onSubmitted }: { onSubmitted: () => void }) {
  const [customer, setCustomer] = useState("");
  const [text, setText] = useState("");
  const [result, setResult] = useState<Submission | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const sub = await api.submitText(text, customer || undefined);
      setResult(sub);
      onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    setBusy(true);
    setError("");
    try {
      const sub = await api.submitFile(file);
      setResult(sub);
      onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded border bg-white p-4 shadow-sm">
        <label className="block text-sm font-medium text-gray-700">Customer name (optional)</label>
        <input
          className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
          value={customer}
          onChange={(e) => setCustomer(e.target.value)}
          placeholder="e.g. Bayou Process Services"
        />
        <label className="mt-3 block text-sm font-medium text-gray-700">RFQ text</label>
        <textarea
          className="mt-1 h-48 w-full rounded border px-2 py-1.5 font-mono text-sm"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the customer's email here…"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            className="rounded bg-sky-700 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            onClick={submit}
            disabled={busy || !text.trim()}
          >
            {busy ? "Processing…" : "Submit RFQ"}
          </button>
          <label className="cursor-pointer text-sm text-sky-700 underline">
            or upload a PDF / text file
            <input
              type="file"
              accept=".pdf,.txt"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
          </label>
          <button
            className="text-sm text-gray-500 underline"
            onClick={() => setText(SAMPLE)}
          >
            load a sample RFQ
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>
      {result && <SubmissionDetail submission={result} />}
    </div>
  );
}
