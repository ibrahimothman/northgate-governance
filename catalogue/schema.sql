PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS registry_rules;
DROP TABLE IF EXISTS relationships;
DROP TABLE IF EXISTS entity_names;
DROP TABLE IF EXISTS entities;

CREATE TABLE entities (
    id                  TEXT PRIMARY KEY,
    entity_type         TEXT NOT NULL,
    canonical_name      TEXT NOT NULL,
    business_name       TEXT,
    source_registry_id  TEXT,
    entity_url          TEXT NOT NULL UNIQUE,
    payload_json        TEXT NOT NULL
);

CREATE TABLE entity_names (
    entity_id    TEXT NOT NULL,
    name         TEXT NOT NULL,
    name_type    TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

CREATE TABLE relationships (
    id                 TEXT PRIMARY KEY,
    from_entity_id     TEXT NOT NULL,
    to_entity_id       TEXT NOT NULL,
    relationship_type  TEXT NOT NULL,
    predicate           TEXT NOT NULL,
    FOREIGN KEY (from_entity_id) REFERENCES entities(id),
    FOREIGN KEY (to_entity_id) REFERENCES entities(id)
);

CREATE TABLE registry_rules (
    id                 TEXT PRIMARY KEY,
    registry_id        TEXT NOT NULL,
    metric             TEXT NOT NULL,
    field_name         TEXT,
    relationship_type  TEXT,
    operator           TEXT NOT NULL,
    threshold          REAL NOT NULL,
    config_json        TEXT,
    FOREIGN KEY (registry_id) REFERENCES entities(id)
);

CREATE INDEX idx_entities_type
ON entities(entity_type);

CREATE INDEX idx_entity_names_lookup
ON entity_names(name, entity_id);

CREATE INDEX idx_rel_from
ON relationships(from_entity_id, relationship_type);

CREATE INDEX idx_rel_to
ON relationships(to_entity_id, relationship_type);

CREATE INDEX idx_registry_rules_registry
ON registry_rules(registry_id);
