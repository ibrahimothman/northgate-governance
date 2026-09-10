"use client";

import { FormEvent, useCallback, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  ArrowRight,
  Braces,
  CircleAlert,
  Database,
  ExternalLink,
  Landmark,
  Search,
  ShieldAlert,
} from "lucide-react";

import { askQuestion } from "@/lib/api";
import type { AskResponse, GovernanceCaveat } from "@/lib/types";
import { EvidenceRenderer } from "./EvidenceRenderer";
import { TraceDrawer } from "./TraceDrawer";

const SUGGESTED_PROMPTS = [
  "What's affected if we retire PostgreSQL 11?",
  "What is a patient?",
  "How long do we keep inpatient clinical records?",
  "Which applications duplicate each other across sites for Medication Management?",
  "Who owns Pharmacy System?",
];

function metricLabel(caveat: GovernanceCaveat): string {
  if (caveat.id.includes("owner")) return "Owner completeness";
  const labels: Record<string, string> = {
    maximum_age_days: "Freshness",
    field_completeness: "Field completeness",
    relationship_coverage: "Relationship coverage",
    parent_completeness: "Parent completeness",
    hierarchy_violations: "Hierarchy violations",
  };
  return labels[caveat.metric ?? ""] ?? "Governance rule";
}

function formatMetric(
  value: number | string | undefined,
  metric?: string,
): string {
  if (value === undefined) return "Not recorded";
  if (
    typeof value === "number" &&
    (metric === "field_completeness" ||
      metric === "relationship_coverage" ||
      metric === "parent_completeness")
  ) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (metric === "maximum_age_days") return `${value} days`;
  return String(value);
}

function GovernanceCaveats({ caveats }: { caveats: GovernanceCaveat[] }) {
  if (caveats.length === 0) return null;

  return (
    <section
      className="governance-section"
      aria-labelledby="governance-heading"
    >
      <div className="governance-heading">
        <div>
          <h3 id="governance-heading">
            <ShieldAlert size={18} aria-hidden="true" />
            Governance Context &amp; Registry Caveats
          </h3>
          <p>
            The answer uses verified catalogue records, but these registry
            policies are outside their declared thresholds.
          </p>
        </div>
        <span className="attention-badge">
          {caveats.length} {caveats.length === 1 ? "Policy" : "Policies"}{" "}
          Failing Thresholds
        </span>
      </div>
      <div className="caveat-grid">
        {caveats.map((caveat) => (
          <article className="caveat-card" key={caveat.id}>
            <div className="caveat-card__head">
              <div>
                <h4>
                  <CircleAlert size={15} aria-hidden="true" />
                  {caveat.registry_name}
                </h4>
              </div>
              <span className="status-badge status-badge--fail">
                <CircleAlert size={12} aria-hidden="true" />
                Failing
              </span>
            </div>
            <div className="metric-comparison">
              <div>
                <span>Metric:</span>
                <strong>
                  {metricLabel(caveat)}{" "}
                  {formatMetric(caveat.actual, caveat.metric)}
                </strong>
                <span className="metric-target">
                  (Target: {caveat.operator}{" "}
                  {formatMetric(caveat.threshold, caveat.metric)})
                </span>
              </div>
            </div>
            <h5>{caveat.title}</h5>
            {caveat.message && <p>{caveat.message}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}

function ResultView({
  result,
  onOpenTrace,
}: {
  result: AskResponse;
  onOpenTrace: () => void;
}) {
  const resultLabel = result.result_type.replaceAll("_", " ").toUpperCase();

  return (
    <section
      className={`result-shell result-shell--${result.result_type}`}
      aria-label="Governed result"
    >
      <article
        className={`answer-summary-card answer-summary-card--${result.result_type}`}
      >
        <div className="answer-summary-meta">
          <span className="result-type-badge">{resultLabel}</span>
          <div>
            {result.meta?.duration_ms !== undefined && (
              <>
                <span>
                  Latency: <strong>{result.meta.duration_ms}ms</strong>
                </span>
                <span className="meta-separator">·</span>
              </>
            )}
            <button onClick={onOpenTrace}>
              {result.trace.length} Tool Steps
              <ExternalLink size={12} aria-hidden="true" />
            </button>
          </div>
        </div>
        <div className="answer-markdown">
          <ReactMarkdown skipHtml>{result.answer}</ReactMarkdown>
        </div>
      </article>

      <EvidenceRenderer result={result} />
      <GovernanceCaveats caveats={result.caveats} />

      {(result.citations.length > 0 || result.trace.length > 0) && (
        <section className="sources-section" aria-labelledby="sources-heading">
          <div className="sources-content">
            <h3 id="sources-heading">Sources:</h3>
            <div className="source-list">
              {result.citations.map((citation) => (
                <span
                  className="source-chip"
                  key={citation.uri}
                  title={citation.uri}
                >
                  {citation.label}
                </span>
              ))}
            </div>
          </div>
          {result.trace.length > 0 && (
            <button className="trace-button" onClick={onOpenTrace}>
              <Braces size={16} aria-hidden="true" />
              View Execution Trace ({result.trace.length})
              <ArrowRight size={16} aria-hidden="true" />
            </button>
          )}
        </section>
      )}
    </section>
  );
}

export function GovernanceAssistant() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const closeTrace = useCallback(() => setTraceOpen(false), []);

  async function submitQuestion(nextQuestion: string) {
    const trimmed = nextQuestion.trim();
    if (!trimmed || loading) return;

    setQuestion(trimmed);
    setLoading(true);
    setError(null);
    setResult(null);
    window.setTimeout(() => {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);

    try {
      const nextResult = await askQuestion(trimmed);
      setResult(nextResult);
      window.setTimeout(() => {
        resultRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 50);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The assistant could not complete the request.",
      );
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion(question);
  }

  function selectPrompt(prompt: string) {
    setQuestion(prompt);
    setError(null);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

  return (
    <>
      <main>
        <section className="hero">
          <nav className="product-bar" aria-label="Product identity">
            <div className="brand-mark" aria-hidden="true">
              <Landmark size={21} />
            </div>
            <div className="brand-copy">
              <strong>Northgate</strong>
              <span>Enterprise Governance</span>
            </div>
          </nav>

          <form className="question-composer" onSubmit={onSubmit}>
            <label htmlFor="governance-question">Ask a governed question</label>
            <div className="question-field">
              <Search size={19} aria-hidden="true" />
              <input
                ref={inputRef}
                id="governance-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask about applications, technologies, retention, terminology..."
                disabled={loading}
                autoComplete="off"
              />
              <button
                type="submit"
                disabled={loading || question.trim().length === 0}
                aria-label="Submit question"
              >
                {loading ? <span className="button-spinner" /> : null}
                <span>Ask</span>
                {!loading && <ArrowRight size={15} aria-hidden="true" />}
              </button>
            </div>
          </form>

          <div className="suggestions">
            <span>Try asking</span>
            <div className="suggestion-list">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  type="button"
                  key={prompt}
                  className={question === prompt ? "is-selected" : undefined}
                  aria-pressed={question === prompt}
                  onClick={() => selectPrompt(prompt)}
                  disabled={loading}
                >
                  {prompt}
                  <ArrowRight size={13} aria-hidden="true" />
                </button>
              ))}
            </div>
          </div>
        </section>

        <div ref={resultRef} className="result-region">
          {loading && (
            <div className="loading-panel" role="status" aria-live="polite">
              <span className="catalogue-loader">
                <Database size={18} aria-hidden="true" />
              </span>
              <div>
                <strong>Consulting governed catalogue...</strong>
                <span>
                  Checking enterprise records and their governance context.
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="error-panel" role="alert">
              <CircleAlert size={19} aria-hidden="true" />
              <div>
                <strong>The request could not be completed</strong>
                <span>{error}</span>
              </div>
            </div>
          )}

          {result && (
            <ResultView
              result={result}
              onOpenTrace={() => setTraceOpen(true)}
            />
          )}
        </div>
      </main>

      <TraceDrawer
        open={traceOpen}
        steps={result?.trace ?? []}
        requestId={result?.request_id}
        durationMs={result?.meta?.duration_ms}
        caveatCount={result?.caveats.length ?? 0}
        onClose={closeTrace}
      />
    </>
  );
}
