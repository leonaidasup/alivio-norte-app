-- Cola de mensajes: cada mensaje que entra (ya con datos sensibles redactados)
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE NOT NULL,          -- evita duplicados si el webhook reintenta
    lead_id     TEXT NOT NULL,
    received_at TEXT NOT NULL,
    creator     TEXT DEFAULT '',
    channel     TEXT DEFAULT '',
    phone       TEXT DEFAULT '',
    text        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'nuevo', -- nuevo | procesado | error | escalado_por_error
    attempts    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);

-- Lo que decidió el clasificador
CREATE TABLE IF NOT EXISTS decisions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    INTEGER NOT NULL REFERENCES messages(id),
    lead_id       TEXT NOT NULL,
    decided_at    TEXT NOT NULL,
    decision      TEXT NOT NULL,               -- responder | ignorar | escalar_humano
    reason        TEXT NOT NULL,
    explanation   TEXT NOT NULL,
    rules_version TEXT DEFAULT '',
    payload       TEXT NOT NULL                -- decisión completa en JSON
);

-- Borradores que esperan revisión humana
CREATE TABLE IF NOT EXISTS drafts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    lead_id    TEXT NOT NULL,
    body       TEXT NOT NULL,
    path       TEXT DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'pendiente_revision',
    created_at TEXT NOT NULL
);

-- Casos escalados a un agente humano
CREATE TABLE IF NOT EXISTS handoffs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    lead_id    TEXT NOT NULL,
    reason     TEXT NOT NULL,
    summary    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pendiente',
    created_at TEXT NOT NULL
);

-- Leads que pidieron no recibir más mensajes
CREATE TABLE IF NOT EXISTS do_not_contact (
    lead_id TEXT PRIMARY KEY,
    since   TEXT NOT NULL
);

-- Un registro por lead: su teléfono y en qué etapa del embudo está
CREATE TABLE IF NOT EXISTS leads (
    lead_id          TEXT PRIMARY KEY,
    phone            TEXT DEFAULT '',
    stage            TEXT NOT NULL DEFAULT 'nuevo',
    stage_changed_at TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

-- Todo lo que se hace sobre un lead, en orden
CREATE TABLE IF NOT EXISTS audit_trail (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    lead_id    TEXT NOT NULL,
    actor      TEXT NOT NULL,       -- quién aplicó la disposición
    action     TEXT NOT NULL,       -- disposicion_aplicada | disposicion_rechazada | ...
    from_stage TEXT DEFAULT '',
    to_stage   TEXT DEFAULT '',
    detail     TEXT DEFAULT ''
);

-- WhatsApp generados, esperando envío
CREATE TABLE IF NOT EXISTS outbox (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         TEXT NOT NULL,
    phone           TEXT DEFAULT '',
    body            TEXT NOT NULL,
    disposition     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pendiente',   -- pendiente | enviado | fallido
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    last_error      TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    sent_at         TEXT
);

-- Cola de fallos: lo que una persona debe resolver
CREATE TABLE IF NOT EXISTS failures (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    lead_id    TEXT NOT NULL,
    kind       TEXT NOT NULL,       -- sin_telefono | gateway_caido | disposicion_desconocida
    detail     TEXT NOT NULL,
    outbox_id  INTEGER,
    status     TEXT NOT NULL DEFAULT 'abierto'
);