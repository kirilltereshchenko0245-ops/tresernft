# Настройка на Bothost.ru

## Переменные окружения

Обязательные:
- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `GROUP_ID`

Для MTProto выберите ровно один способ авторизации:

### Вариант A — StringSession (подходит для Bothost)

- `STRING_SESSION` — свежая Telethon StringSession.
- `PHONE_NUMBER` — оставить пустым.
- `SESSION_NAME` не используется, если задан `STRING_SESSION`.

### Вариант B — файл `.session`

- Загрузите `tracker_session.session` в папку проекта рядом с `app.py`.
- `SESSION_NAME=tracker_session`
- `STRING_SESSION` оставить пустым.
- `PHONE_NUMBER` оставить пустым.

Не задавайте одновременно `STRING_SESSION` и `PHONE_NUMBER`.
Не вставляйте строку сессии в публичные сообщения, Git или открытый `.env`.
Если строка сессии уже публиковалась/передавалась посторонним, завершите соответствующий сеанс в Telegram → Настройки → Устройства и создайте новую сессию.

## Остальные параметры

- `POLL_INTERVAL=60`
- `GIFT_IDS=` (пусто — использовать каталог)
- `SEED_EXISTING=true`
- `MAX_PAGES_PER_GIFT=5`
- `LOG_LEVEL=INFO`
- `DB_PATH=data/gifts.db`

## Команда запуска

```bash
python app.py
```

При использовании `STRING_SESSION` приложение подключается напрямую и проверяет авторизацию. Оно не вызывает `SendCodeRequest` и не пытается отправлять код на номер телефона.
