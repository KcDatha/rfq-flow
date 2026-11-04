export function ConfidenceBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400">—</span>;
  const color =
    score >= 0.9
      ? "bg-green-100 text-green-800"
      : score >= 0.85
        ? "bg-yellow-100 text-yellow-800"
        : "bg-red-100 text-red-800";
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>
      {(score * 100).toFixed(0)}%
    </span>
  );
}

export function StatusChip({ status }: { status: string }) {
  const colors: Record<string, string> = {
    AUTO_APPROVED: "bg-green-100 text-green-800",
    HUMAN_REVIEW: "bg-amber-100 text-amber-800",
    REVIEWED: "bg-blue-100 text-blue-800",
    QUOTED: "bg-purple-100 text-purple-800",
    PENDING: "bg-gray-100 text-gray-700",
  };
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${colors[status] ?? colors.PENDING}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
