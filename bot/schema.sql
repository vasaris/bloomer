-- BLUMER BOT — схема БД (SQLite).
-- Полная схема под все модули M0–M7, чтобы не делать миграции в каждом спринте.
-- В Sprint 0 реально используются: app_user, dog. Остальное — задел.

PRAGMA foreign_keys = ON;

-- ── Пользователи (мультиюзер на одну собаку: Иван, Лена, позже дети) ──
CREATE TABLE IF NOT EXISTS app_user (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_chat_id  INTEGER UNIQUE NOT NULL,
    name        TEXT,
    role        TEXT NOT NULL DEFAULT 'owner',   -- owner | partner | child
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Профиль собаки (одна сейчас; задел под мультипёс) ──
CREATE TABLE IF NOT EXISTS dog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    birth_date      TEXT,
    breed           TEXT,
    neutered        INTEGER NOT NULL DEFAULT 0,
    vet_name        TEXT,
    breeder_contact TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Задачи / расписание пушей ──
CREATE TABLE IF NOT EXISTS task (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id        INTEGER NOT NULL REFERENCES dog(id) ON DELETE CASCADE,
    module        TEXT NOT NULL,          -- M0..M7
    code          TEXT NOT NULL,          -- машинный ключ, напр. 'walk_morning'
    title         TEXT NOT NULL,
    schedule_cron TEXT,                   -- напр. '0 8 * * *'
    active        INTEGER NOT NULL DEFAULT 1,
    last_fired_at TEXT
);

-- ── Универсальный лог событий (прогулки, кормёжка, тренинг, груминг…) ──
CREATE TABLE IF NOT EXISTS event_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id       INTEGER NOT NULL REFERENCES dog(id) ON DELETE CASCADE,
    user_id      INTEGER REFERENCES app_user(id),  -- кто отметил (семейный режим)
    module       TEXT NOT NULL,
    type         TEXT NOT NULL,           -- walk | feed | nose | groom | health
    payload_json TEXT,                    -- {duration_min, place:'danube', kind:'sniff'}
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_event_dog_created ON event_log(dog_id, created_at);

-- ── Тайм-серия здоровья (вес и пр.) ──
CREATE TABLE IF NOT EXISTS health_metric (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id      INTEGER NOT NULL REFERENCES dog(id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,            -- weight | ...
    value       REAL NOT NULL,
    unit        TEXT,
    measured_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Астма-мониторинг Макса (первые ~21 день) ──
CREATE TABLE IF NOT EXISTS asthma_check (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,
    status        TEXT,                   -- ok | mild | concern
    symptoms_json TEXT,
    note          TEXT
);

-- ── Геймификация: стрики ──
CREATE TABLE IF NOT EXISTS streak (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id       INTEGER NOT NULL REFERENCES dog(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,           -- walk | nose | command | groom
    current      INTEGER NOT NULL DEFAULT 0,
    best         INTEGER NOT NULL DEFAULT 0,
    last_day     TEXT,
    freezes_left INTEGER NOT NULL DEFAULT 2,
    freeze_month TEXT,                     -- 'YYYY-MM' — месяц последнего пополнения
    UNIQUE(dog_id, kind)
);

-- ── Геймификация: ачивки (user_id — под персональные детские) ──
CREATE TABLE IF NOT EXISTS achievement (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id      INTEGER NOT NULL REFERENCES dog(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES app_user(id),
    code        TEXT NOT NULL,
    unlocked_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(dog_id, user_id, code)
);

-- ── Геймификация: XP / уровень ──
CREATE TABLE IF NOT EXISTS xp (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id  INTEGER NOT NULL REFERENCES dog(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES app_user(id),
    total   INTEGER NOT NULL DEFAULT 0,
    level   INTEGER NOT NULL DEFAULT 1,
    UNIQUE(dog_id, user_id)
);

-- ── Трюфель-программа: этапы ──
CREATE TABLE IF NOT EXISTS truffle_stage (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id       INTEGER NOT NULL REFERENCES dog(id) ON DELETE CASCADE,
    stage        INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'locked',  -- locked | active | done
    started_at   TEXT,
    completed_at TEXT,
    UNIQUE(dog_id, stage)
);

-- ── Снуз пушей («отложить») ──
CREATE TABLE IF NOT EXISTS snooze (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES app_user(id),
    push_code  TEXT NOT NULL,
    remind_at  TEXT NOT NULL,
    fired      INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
