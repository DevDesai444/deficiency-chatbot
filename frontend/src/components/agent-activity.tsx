"use client";

import type { AgentEvent, LayerName } from "@/types";

const LAYER_LABELS: Record<LayerName, string> = {
  parse: "Parsing",
  detection: "Fault Detection",
};

function LayerStatus({ completed }: { completed: boolean }) {
  if (completed) {
    return <span className="text-green-600 text-xs font-mono">[done]</span>;
  }
  return (
    <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
  );
}

interface AgentActivityProps {
  events: AgentEvent[];
}

export function AgentActivity({ events }: AgentActivityProps) {
  if (events.length === 0) return null;

  const layers = new Map<LayerName, AgentEvent[]>();
  for (const e of events) {
    const list = layers.get(e.layer) ?? [];
    list.push(e);
    layers.set(e.layer, list);
  }

  const completedLayers = new Set(
    events
      .filter((e) => e.event_type === "layer_complete")
      .map((e) => e.layer),
  );

  return (
    <div className="border rounded-lg bg-gray-50 p-4 font-mono text-sm space-y-3 max-h-[500px] overflow-y-auto">
      {(["parse", "detection"] as LayerName[]).map(
        (layer) => {
          const layerEvents = layers.get(layer);
          if (!layerEvents) return null;

          return (
            <div key={layer}>
              <div className="flex items-center gap-2 font-semibold text-gray-700 mb-1">
                <span>{LAYER_LABELS[layer]}</span>
                <LayerStatus completed={completedLayers.has(layer)} />
              </div>
              <div className="pl-4 space-y-0.5">
                {layerEvents
                  .filter((e) => e.event_type !== "layer_complete")
                  .map((e, i) => (
                    <div key={i} className="text-gray-600 truncate">
                      <span className="text-gray-400">
                        {e.agent_name ? `${e.agent_name}: ` : ""}
                      </span>
                      {e.message}
                    </div>
                  ))}
              </div>
            </div>
          );
        },
      )}
    </div>
  );
}
