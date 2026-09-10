"use client";

import { useEffect, useRef } from "react";
import {
  Braces,
  Check,
  ChevronRight,
  CircleAlert,
  SearchX,
  Wrench,
  X,
} from "lucide-react";

import type { TraceStep } from "@/lib/types";

function StatusIcon({
  status,
  attention,
}: {
  status: TraceStep["status"];
  attention: boolean;
}) {
  if (attention) return <CircleAlert size={15} aria-hidden="true" />;
  if (status === "ok") return <Check size={15} aria-hidden="true" />;
  if (status === "not_found") return <SearchX size={15} aria-hidden="true" />;
  return <CircleAlert size={15} aria-hidden="true" />;
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

function displayValue(value: unknown): string {
  if (value === null) return "Not specified";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ResultSummary({ step }: { step: TraceStep }) {
  const highlights: string[] = [];
  if (typeof step.result === "object" && step.result !== null) {
    const result = step.result as Record<string, unknown>;
    const items = Array.isArray(result.results) ? result.results : [];

    for (const item of items) {
      if (typeof item !== "object" || item === null) continue;
      const record = item as Record<string, unknown>;
      const entity =
        typeof record.entity === "object" && record.entity !== null
          ? (record.entity as Record<string, unknown>)
          : record;
      const label = entity.name ?? entity.term ?? entity.context;
      if (label) highlights.push(String(label));
    }

    if (step.tool === "get_entity" && result.name) {
      highlights.push(String(result.name));
    }
    if (step.tool === "identify_steward" && typeof result.registry === "object") {
      const registry = result.registry as Record<string, unknown>;
      if (registry.steward) highlights.push(`Steward: ${registry.steward}`);
    }
    if (step.tool === "get_registry_health" && Array.isArray(result.rules)) {
      for (const rule of result.rules) {
        if (
          typeof rule === "object" &&
          rule !== null &&
          (rule as Record<string, unknown>).status === "fail"
        ) {
          highlights.push(
            `Failed: ${String((rule as Record<string, unknown>).id ?? "governance rule")}`,
          );
        }
      }
    }
  }

  return (
    <div className="trace-result-summary">
      <strong>{step.summary}</strong>
      {highlights.length > 0 && (
        <ul>
          {highlights.map((highlight, index) => (
            <li key={`${highlight}-${index}`}>{highlight}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function TraceDrawer({
  open,
  steps,
  requestId,
  durationMs,
  caveatCount,
  onClose,
}: {
  open: boolean;
  steps: TraceStep[];
  requestId?: string;
  durationMs?: number;
  caveatCount: number;
  onClose: () => void;
}) {
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="drawer-layer">
      <button
        className="drawer-scrim"
        onClick={onClose}
        aria-label="Close trace"
      />
      <aside
        className="trace-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="trace-title"
      >
        <header className="trace-header">
          <span className="trace-title-icon">
            <Braces size={17} aria-hidden="true" />
          </span>
          <div>
            <h2 id="trace-title">How this answer was built</h2>
            <p>Observable tool calls &amp; governed registry trace</p>
          </div>
          <button
            ref={closeButton}
            className="icon-button"
            onClick={onClose}
            aria-label="Close trace"
          >
            <X size={20} />
          </button>
        </header>

        <div className="trace-overview">
          <div>
            <span>Trace ID</span>
            <strong title={requestId}>{requestId ? requestId.slice(0, 12) : "—"}</strong>
          </div>
          <div>
            <span>Duration</span>
            <strong>{durationMs !== undefined ? `${durationMs}ms` : "—"}</strong>
          </div>
          <div>
            <span>Policies</span>
            <strong className={caveatCount > 0 ? "has-caveats" : ""}>
              {caveatCount} Caveat{caveatCount === 1 ? "" : "s"}
            </strong>
          </div>
        </div>

        <div className="trace-list">
          {steps.map((step) => {
            const needsAttention =
              step.tool === "get_registry_health" &&
              typeof step.result === "object" &&
              step.result !== null &&
              "overall_status" in step.result &&
              step.result.overall_status === "fail";

            return (
            <details className="trace-step" key={`${step.sequence}-${step.tool}`}>
              <summary>
                <span
                  className={`trace-status trace-status--${
                    needsAttention ? "attention" : step.status
                  }`}
                >
                  <StatusIcon status={step.status} attention={needsAttention} />
                </span>
                <span className="trace-summary">
                  <small>Step {step.sequence}</small>
                  <strong>{step.label}</strong>
                  <span>{step.summary}</span>
                </span>
                <ChevronRight className="trace-chevron" size={18} aria-hidden="true" />
              </summary>
              <div className="trace-detail">
                <div className="trace-tool">
                  <Wrench size={14} aria-hidden="true" />
                  <span>Tool</span>
                  <code>{step.tool}</code>
                </div>
                <h4>Arguments</h4>
                <dl className="argument-list">
                  {Object.entries(step.arguments).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{displayValue(value)}</dd>
                    </div>
                  ))}
                </dl>
                <h4>Result</h4>
                <ResultSummary step={step} />
                {step.result !== undefined && (
                  <details className="raw-result">
                    <summary>View raw result</summary>
                    <JsonBlock value={step.result} />
                  </details>
                )}
              </div>
            </details>
            );
          })}
        </div>
      </aside>
    </div>
  );
}
