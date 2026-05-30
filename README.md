# blumer-bot

Проактивный Telegram-бот заботы о Блумере (лаготто-романьоло): пуши по расписанию, журнал, стрики/ачивки, трюфель-тренинг. Стек: **aiogram 3.x · SQLite · APScheduler · Railway**.

Сделано по **Sprint 8** (`v0.8.0`): каркас + планировщик (тихие часы, снуз), M0 адаптация + астма-чек Макса, геймификация (стрики 🚶/👃/🧠, XP, уровни, ачивки, заморозки), M3 груминг, M5 тренинг/трюфели, M4 здоровье (прививки/обработки/вет, журнал веса), M6 социализация и M7 путешествия (проверка жары, чек-лист тура), **Claude API** (`/ask` + свободный текст + персональные нюхо-задачи с контекстом из БД). **Sprint 8 (полировка):** настоящий недельный обзор, экспорт журнала (`/export` — zip с CSV+JSON), ежедневные **бэкапы БД** (online backup + ротация + офсайт-копия в Telegram, `/backup`), видимость заморозок стриков, **настройки времени пушей прямо из бота** (`/settings`, `/settime`, `/setquiet`, `/setweekly` — с персистентностью и живым перепланированием). Эксплуатация — см. [`OPERATIONS.md`](OPERATIONS.md).

## Структура

```
blumer-bot/
├── Procfile               # worker: python -m bot.main  (Railway)
├── runtime.txt            # python-3.12
├── requirements.txt
├── .env.example           # все секреты и расписание — копировать в .env
└── bot/
    ├── main.py            # точка входа: БД → override-ы → бот → планировщик → polling
    ├── config.py          # чтение .env + дефолты расписания, тихие часы, бэкапы
    ├── pushconf.py         # лейблы пушей + мердж override-ов времени (БД поверх .env)
    ├── db.py              # aiosqlite: connect/init + хелперы (вкл. экспорт, kv-настройки)
    ├── schema.sql         # полная схема под M0–M7 (+ setting kv для правок времени)
    ├── texts.py           # персона C: NEUTRAL + BLOOMER_VOICE
    ├── middlewares.py     # whitelist-доступ по chat_id
    ├── scheduler.py       # APScheduler: cron-пуши, тихие часы, снуз, бэкапы, reschedule
    ├── backup.py          # online-бэкап SQLite + ротация (Sprint 8)
    ├── reports.py         # сборка пушей: бриф, итог дня, недельный обзор
    ├── context.py         # снимок состояния из БД для Claude (Sprint 7)
    ├── claude_client.py   # Claude API клиент (Sprint 7)
    ├── weather.py         # погодное API (Open-Meteo) + проверка жары (M7/бриф)
    ├── handlers/
    │   ├── __init__.py    # сбор роутеров
    │   ├── common.py      # /start /help /profile /ping /today /weekly /stats /backup …
    │   ├── settings.py    # /settings /settime /setquiet /setweekly (Sprint 8)
    │   ├── export.py      # /export — выгрузка журнала zip (Sprint 8)
    │   ├── logging.py     # лог прогулок/кормёжки/нюхо + снуз
    │   ├── asthma.py      # астма-чек Макса
    │   └── ask.py         # Claude API: /ask + свободный текст (Sprint 7)
    └── modules/           # M0,M3–M7 (роутеры + логика по модулям)
```

## Локальный запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # вписать BOT_TOKEN и OWNER_CHAT_IDS
python -m bot.main
```

Получить токен — у [@BotFather](https://t.me/BotFather). Узнать свой `chat_id` — написать боту [@userinfobot](https://t.me/userinfobot), либо запустить бота с пустым `OWNER_CHAT_IDS`, отправить `/start` и посмотреть id в ответе/логах, затем вписать его в `.env`.

Проверка живости: `/ping` — должен прийти тестовый пуш сразу (минуя тихие часы).

## Деплой на Railway

1. Запушить репозиторий `vasaris/bloomer` на GitHub.
2. Railway → New Project → Deploy from GitHub → выбрать репо.
3. Variables → добавить из `.env.example` (минимум `BOT_TOKEN`, `OWNER_CHAT_IDS`, `TIMEZONE`).
4. Railway подхватит `Procfile` и поднимет процесс типа **worker** (long polling, без публичного порта).

> SQLite-файл живёт в контейнере. На Railway для персистентности подключи **Volume** и укажи `DB_PATH` внутрь него (иначе БД, настройки и `backups/` обнулятся при редеплое). При росте — миграция на Postgres (см. спеку §9). Подробнее — в [`OPERATIONS.md`](OPERATIONS.md).

## Что дальше

- ✅ **Sprint 1–6** — адаптация+астма, геймификация, груминг, тренинг/трюфели, здоровье+вес, социализация+путешествия.
- ✅ **Sprint 7** — Claude API (`/ask` с системным промптом из `BLUMER_SYSTEM.md` + контекст из БД).
- ✅ **Sprint 8** — полировка: недельный обзор, экспорт журнала (CSV+JSON), бэкапы БД, заморозки стриков, настройки времени пушей из бота, `OPERATIONS.md`.

Полный план — `BLUMER_BOT_SPEC.md` в проекте. Эксплуатация и траблшутинг — `OPERATIONS.md`.
