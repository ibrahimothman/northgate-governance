export type ResultType =
  | "answer"
  | "impact"
  | "glossary_conflict"
  | "governed_fact"
  | "ambiguous"
  | "refusal";

export interface AskResponse {
  request_id: string;
  status: "completed" | "refused";
  question: string;
  answer: string;
  result_type: ResultType;
  entities: EntityView[];
  relationships: RelationshipView[];
  caveats: GovernanceCaveat[];
  citations: CitationView[];
  trace: TraceStep[];
  meta?: {
    model?: string;
    tool_call_count?: number;
    duration_ms?: number;
  };
}

export interface EntityView {
  id: string;
  entity_type: string;
  name: string;
  uri: string;
  attributes: Record<string, unknown>;
}

export interface RelationshipView {
  from_id: string;
  to_id: string;
  relationship_type: string;
}

export interface GovernanceCaveat {
  id: string;
  registry_id: string;
  registry_name: string;
  severity: "info" | "warning" | "critical";
  title: string;
  metric?: string;
  actual?: number | string;
  operator?: string;
  threshold?: number | string;
  status: "pass" | "fail";
  message?: string;
  uri?: string;
}

export interface CitationView {
  entity_id: string;
  label: string;
  uri: string;
}

export interface TraceStep {
  sequence: number;
  tool: string;
  label: string;
  arguments: Record<string, unknown>;
  status: "ok" | "not_found" | "ambiguous" | "tool_error";
  summary: string;
  result?: unknown;
}
