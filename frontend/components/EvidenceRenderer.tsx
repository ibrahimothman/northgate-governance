import {
  AppWindow,
  BookOpen,
  Boxes,
  Database,
  Route,
  Server,
} from "lucide-react";

import type { AskResponse, EntityView } from "@/lib/types";

function text(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function EntityCard({
  entity,
  showDescription = false,
}: {
  entity: EntityView;
  showDescription?: boolean;
}) {
  const site = text(entity.attributes.site);
  const lifecycle = text(entity.attributes.lifecycle_status);
  const owner = text(entity.attributes.owner);
  const description = text(
    entity.attributes.definition ?? entity.attributes.description,
  );

  return (
    <article className="entity-card">
      <span className="entity-icon">
        <AppWindow size={16} aria-hidden="true" />
      </span>
      <div className="entity-card__body">
        <div className="entity-card__topline">
          <h4>{entity.name}</h4>
          {site && <span className="site-tag">Site: {site}</span>}
          <span className="entity-id">{entity.id}</span>
        </div>
        {showDescription && description && <p>{description}</p>}
        {!showDescription && owner && (
          <p>{humanize(String(entity.attributes.application_type ?? "Application"))}</p>
        )}
      </div>
      <div className="entity-meta">
        <span
          className={`lifecycle ${
            owner ? `lifecycle--${lifecycle ?? "active"}` : "lifecycle--attention"
          }`}
        >
          {owner ? `Status: ${humanize(lifecycle ?? "active")}` : "Attention required"}
        </span>
      </div>
    </article>
  );
}

function ImpactView({ result }: { result: AskResponse }) {
  const applications = result.entities.filter(
    (entity) => entity.entity_type === "application",
  );
  const root =
    result.entities.find((entity) => entity.entity_type !== "application") ??
    result.entities[0];

  if (!root && applications.length === 0) return null;

  return (
    <section className="evidence-section" aria-labelledby="impact-heading">
      <div className="evidence-heading">
        <div>
          <Boxes size={19} aria-hidden="true" />
          <h3 id="impact-heading">Dependencies</h3>
        </div>
        <span>
          Graph depth: 1 · Target: {root?.name ?? "Catalogue record"}
        </span>
      </div>
      {root && (
        <div className="impact-root">
          <span className="root-icon">
            <Server size={18} aria-hidden="true" />
          </span>
          <div>
            <div className="root-title">
              <strong>{root.name}</strong>
              <span>{root.id}</span>
            </div>
            <p>
              {text(root.attributes.description) ??
                humanize(String(root.attributes.technology_type ?? root.entity_type))}
            </p>
          </div>
          {text(root.attributes.lifecycle_status) && (
            <span className={`lifecycle lifecycle--${root.attributes.lifecycle_status}`}>
              Lifecycle: {humanize(String(root.attributes.lifecycle_status))}
            </span>
          )}
        </div>
      )}
      <div className="impact-grid">
        {applications.map((entity) => (
          <EntityCard key={entity.id} entity={entity} showDescription />
        ))}
      </div>
    </section>
  );
}

function GlossaryConflictView({ entities }: { entities: EntityView[] }) {
  return (
    <section className="evidence-section" aria-labelledby="definitions-heading">
      <div className="section-kicker">
        <BookOpen size={16} aria-hidden="true" />
        Governed terminology
      </div>
      <div className="section-heading-row">
        <h3 id="definitions-heading">Context-specific definitions</h3>
        <span className="count-badge">{entities.length} definitions</span>
      </div>
      <div className="definition-note">
        No enterprise-wide canonical definition has been declared.
      </div>
      <div className="definition-grid">
        {entities.map((entity) => (
          <article className="definition-card" key={entity.id}>
            <span>{text(entity.attributes.context) ?? "Enterprise"}</span>
            <p>{text(entity.attributes.definition) ?? "No definition recorded."}</p>
            <small>Steward · {text(entity.attributes.steward) ?? "Unassigned"}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function GovernedFactView({ entity }: { entity?: EntityView }) {
  if (!entity) return null;
  const facts = [
    ["Retention", entity.attributes.retention],
    ["Classification", entity.attributes.classification],
    ["Steward", entity.attributes.steward],
  ].filter((item): item is [string, unknown] => Boolean(text(item[1])));

  return (
    <section className="evidence-section" aria-labelledby="facts-heading">
      <div className="section-kicker">
        <Database size={16} aria-hidden="true" />
        Governed record
      </div>
      <h3 id="facts-heading">{entity.name}</h3>
      <div className="fact-grid">
        {facts.map(([label, value]) => (
          <div className="fact-card" key={label}>
            <span>{label}</span>
            <strong>{text(value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function AmbiguityView({ entities }: { entities: EntityView[] }) {
  return (
    <section className="evidence-section" aria-labelledby="matches-heading">
      <div className="section-kicker">
        <Boxes size={16} aria-hidden="true" />
        Catalogue matches
      </div>
      <h3 id="matches-heading">
        {entities.length} matching record{entities.length === 1 ? "" : "s"}
      </h3>
      <p className="section-intro">
        The name maps to multiple governed records. Each is shown separately.
      </p>
      <div className="entity-grid">
        {entities.map((entity) => (
          <EntityCard key={entity.id} entity={entity} />
        ))}
      </div>
    </section>
  );
}

function GenericEvidence({ entities }: { entities: EntityView[] }) {
  if (entities.length === 0) return null;
  return (
    <section className="evidence-section" aria-labelledby="records-heading">
      <div className="section-kicker">
        <Database size={16} aria-hidden="true" />
        Governed evidence
      </div>
      <h3 id="records-heading">Catalogue records</h3>
      <div className="entity-grid">
        {entities.map((entity) => (
          <EntityCard key={entity.id} entity={entity} showDescription />
        ))}
      </div>
    </section>
  );
}

function RefusalView({ entities }: { entities: EntityView[] }) {
  const registry = entities.find((entity) => entity.entity_type === "registry");
  if (!registry) return null;

  return (
    <section className="evidence-section refusal-evidence" aria-labelledby="escalation-heading">
      <div className="section-kicker">
        <Route size={16} aria-hidden="true" />
        Catalogue gap routing
      </div>
      <h3 id="escalation-heading">Suggested escalation</h3>
      <div className="escalation-card">
        <span>{registry.name}</span>
        <strong>{text(registry.attributes.steward) ?? "Registry steward"}</strong>
        <small>Responsible for reviewing this governed catalogue gap</small>
      </div>
    </section>
  );
}

export function EvidenceRenderer({ result }: { result: AskResponse }) {
  switch (result.result_type) {
    case "impact":
      return <ImpactView result={result} />;
    case "glossary_conflict":
      return <GlossaryConflictView entities={result.entities} />;
    case "governed_fact":
      return <GovernedFactView entity={result.entities[0]} />;
    case "ambiguous":
      return <AmbiguityView entities={result.entities} />;
    case "refusal":
      return <RefusalView entities={result.entities} />;
    default:
      return <GenericEvidence entities={result.entities} />;
  }
}
