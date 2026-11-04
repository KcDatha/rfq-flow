import { useState } from "react";
import ReviewQueue from "./components/ReviewQueue";
import Submissions from "./components/Submissions";
import SubmitForm from "./components/SubmitForm";

type Tab = "submit" | "submissions" | "review";

export default function App() {
  const [tab, setTab] = useState<Tab>("submit");
  const [refreshKey, setRefreshKey] = useState(0);

  const tabButton = (id: Tab, label: string) => (
    <button
      className={`rounded px-3 py-1.5 text-sm font-medium ${
        tab === id ? "bg-sky-700 text-white" : "bg-white text-gray-700"
      }`}
      onClick={() => setTab(id)}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3">
          <h1 className="text-lg font-bold">RFQ-Flow</h1>
          <span className="text-sm text-gray-500">
            Industrial RFQ parsing &amp; quoting
          </span>
          <nav className="ml-auto flex gap-2">
            {tabButton("submit", "Submit RFQ")}
            {tabButton("submissions", "Submissions")}
            {tabButton("review", "Review Queue")}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-4">
        {tab === "submit" && (
          <SubmitForm onSubmitted={() => setRefreshKey((k) => k + 1)} />
        )}
        {tab === "submissions" && <Submissions refreshKey={refreshKey} />}
        {tab === "review" && <ReviewQueue refreshKey={refreshKey} />}
      </main>
    </div>
  );
}
