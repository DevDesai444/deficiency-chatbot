import type { Correction, Severity } from "@/types";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-red-100 text-red-800 border-red-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-blue-100 text-blue-800 border-blue-200",
};

interface FlawCardProps {
  correction: Correction;
  index: number;
}

export function FlawCard({ correction, index }: FlawCardProps) {
  const style = SEVERITY_STYLES[correction.priority];

  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="font-medium text-gray-900">
          {index + 1}. {formatCategory(correction.flaw_category)}
        </h3>
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium border ${style}`}
        >
          {correction.priority}
        </span>
      </div>

      <p className="text-gray-700 text-sm mb-2">{correction.suggestion}</p>

      <details className="text-sm">
        <summary className="text-gray-500 cursor-pointer hover:text-gray-700">
          Explanation
        </summary>
        <p className="mt-1 text-gray-600 pl-2 border-l-2 border-gray-200">
          {correction.explanation}
        </p>
      </details>
    </div>
  );
}

function formatCategory(raw: string): string {
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
