import type { RecommendationSet } from "@/types";
import { FlawCard } from "./flaw-card";

interface RecommendationsProps {
  results: RecommendationSet;
}

export function Recommendations({ results }: RecommendationsProps) {
  if (!results.flaws_found) {
    return (
      <div className="border rounded-lg p-6 bg-green-50 text-center">
        <p className="text-green-800 font-medium text-lg">
          No deficiencies detected
        </p>
        <p className="text-green-600 text-sm mt-1">
          Analysis completed in {results.analysis_seconds.toFixed(1)}s
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>
          {results.recommendations.length} recommendation
          {results.recommendations.length !== 1 ? "s" : ""}
        </span>
        <span>{results.analysis_seconds.toFixed(1)}s</span>
      </div>

      {results.recommendations.map((c, i) => (
        <FlawCard key={i} correction={c} index={i} />
      ))}
    </div>
  );
}
