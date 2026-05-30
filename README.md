# blumer-bot

Проактивный Telegram-бот заботы о Блумере (лаготто-романьоло): пуши по расписанию, журнал, стрики/ачивки, трюфель-тренинг. Стек: **aiogram 3.x · SQLite · APScheduler · Railway**.

Это **Sprint 0 — каркас**: бот деплоится, отвечает на `/start`, держит профиль собаки и шлёт пуши по расписанию (с тихими часами). Фичи — со Sprint 1.

## Структура

```
blumer-bot/
├── Procfile               # worker: python -m bot.main  (Railway)
├── runtime.txt            # python-3.12
├── requirements.txt
├── .env.example           # все секреты и расписание — копировать в .env
└── bot/
    ├── main.py            # точка входа: БД → бот → планировщик → polling
    ├── config.py          # чтение .env + дефолты расписания, тихие часы
    ├── db.py              # aiosqlite: connect/init + хелперы
    ├── schema.sql         # полная схема под M0–M7 (мультиюзер, семейный режим)
    ├── texts.py           # персона C: NEUTRAL + BLOOMER_VOICE
    ├── middlewares.py     # whitelist-доступ по chat_id
    ├── scheduler.py       # APScheduler: cron-пуши, тихие часы, снуз
    ├── handlers/
    │   ├── __init__.py    # сбор роутеров
    │   └── common.py      # /start /help /profile /ping
    └── modules/
        └── __init__.py    # реестр модулей M0–M7 (задел)
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

> SQLite-файл живёт в контейнере. На Railway для персистентности подключи **Volume** и укажи `DB_PATH` внутрь него (иначе БД обнулится при редеплое). При росте — миграция на Postgres (см. спеку §9).

## Что дальше

- **Sprint 1** — M0 адаптация (гид первых 2–3 недель, астма-чек Макса) + ядро логирования (прогулки/кормёжка в один тап), утренний бриф и итог дня с реальным содержимым.
- **Sprint 2** — стрики, XP, ачивки (тут включается слой `BLOOMER_VOICE`).

Полный план — `BLUMER_BOT_SPEC.md` в проекте.
