import type { Fault, Severity, Tier, EvidenceClass } from "@/types";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-red-100 text-red-800 border-red-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-blue-100 text-blue-800 border-blue-200",
};

const TIER_META: Record<Tier, { label: string; style: string }> = {
  verified: {
    label: "Verified",
    style: "bg-emerald-100 text-emerald-800 border-emerald-200",
  },
  corroborated: {
    label: "Corroborated",
    style: "bg-sky-100 text-sky-800 border-sky-200",
  },
  advisory: {
    label: "Advisory",
    style: "bg-amber-100 text-amber-800 border-amber-200",
  },
};

const EVIDENCE_LABEL: Record<EvidenceClass, string> = {
  code_verified: "code-verified",
  checklist: "checklist",
  quote_anchored: "quote-anchored",
  model_judgment: "model judgment",
};

interface FaultCardProps {
  fault: Fault;
  index: number;
}

export function FaultCard({ fault, index }: FaultCardProps) {
  const tier = TIER_META[fault.tier];

  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between gap-3 mb-1">
        <h3 className="font-medium text-gray-900">
          {index + 1}. {fault.title}
        </h3>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium border ${tier.style}`}
          >
            {tier.label}
          </span>
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium border ${SEVERITY_STYLES[fault.severity]}`}
          >
            {fault.severity}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500 mb-2">
        <span className="font-mono">{EVIDENCE_LABEL[fault.evidence_class]}</span>
        {fault.section && <span>· {fault.section}</span>}
        {fault.page > 0 && <span>· p.{fault.page}</span>}
        {fault.table_ref && <span>· {fault.table_ref}</span>}
        {fault.novel && <span className="text-amber-600">· novel</span>}
        {fault.out_of_distribution && (
          <span className="text-amber-600">· out-of-distribution</span>
        )}
      </div>

      {fault.detail && (
        <p className="text-gray-700 text-sm mb-2">{fault.detail}</p>
      )}

      {fault.evidence && (
        <p className="text-sm text-gray-600 pl-2 border-l-2 border-gray-200 mb-2">
          {fault.evidence}
        </p>
      )}

      {fault.challenge_note && (
        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-2">
          <span className="font-medium">Challenged:</span> {fault.challenge_note}
        </p>
      )}

      {fault.precedents.length > 0 && (
        <details className="text-sm">
          <summary className="text-gray-500 cursor-pointer hover:text-gray-700">
            {fault.precedents.length} similar past deficienc
            {fault.precedents.length !== 1 ? "ies" : "y"}
          </summary>
          <ul className="mt-1 space-y-1">
            {fault.precedents.map((p, i) => (
              <li
                key={i}
                className="text-gray-600 pl-2 border-l-2 border-gray-200"
              >
                <span className="text-gray-400">
                  [{p.product_name || "unknown"}]
                </span>{" "}
                {p.deficiency_text.slice(0, 200)}
              </li>
            ))}
          </ul>
        </details>
      )}

      {fault.source && (
        <div className="text-[11px] text-gray-400 font-mono mt-2">
          {fault.source}
        </div>
      )}
    </div>
  );
}
