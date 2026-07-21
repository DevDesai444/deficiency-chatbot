import type { FaultReport } from "@/types";
import { FaultCard } from "./flaw-card";

interface FaultsProps {
  report: FaultReport;
}

export function Faults({ report }: FaultsProps) {
  if (!report.faults_found) {
    return (
      <div className="border rounded-lg p-6 bg-green-50 text-center">
        <p className="text-green-800 font-medium text-lg">
          No deficiencies detected
        </p>
        <p className="text-green-600 text-sm mt-1">
          Reviewed {report.domains_checked.length} domain
          {report.domains_checked.length !== 1 ? "s" : ""} in{" "}
          {report.analysis_seconds.toFixed(1)}s
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>
          {report.faults.length} fault{report.faults.length !== 1 ? "s" : ""}
          {report.domains_checked.length > 0 && (
            <> · {report.domains_checked.length} domains reviewed</>
          )}
        </span>
        <span>{report.analysis_seconds.toFixed(1)}s</span>
      </div>

      {report.faults.map((fault, i) => (
        <FaultCard key={i} fault={fault} index={i} />
      ))}
    </div>
  );
}
