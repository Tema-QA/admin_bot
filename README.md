# Telegram Content Manager

Telegram-бот для генерации и публикации постов через YandexGPT.

## Возможности

- генерация поста по теме;
- генерация 3 вариантов инфографики к одобренному черновику;
- ручное подтверждение текста и итоговой версии с картинкой;
- редактирование;
- повторная генерация;
- немедленная публикация;
- планирование;
- SQLite-очередь;
- защищённый endpoint `/cron/publish`.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

На Windows:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

## Render

Start Command:

```text
python bot.py
```

Health-check:

```text
/health
```

Cron endpoint:

```text
/cron/publish
```

Cron должен отправлять заголовок:

```text
Authorization: Bearer CRON_SECRET
```

## Telegram

Бот должен быть администратором канала с разрешением на публикацию сообщений.

## Настройка ADMIN_IDS

Узнайте свой Telegram ID через специального бота Telegram и добавьте его в `.env` или Render:

```text
ADMIN_IDS=123456789
```