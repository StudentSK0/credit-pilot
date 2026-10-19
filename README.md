# Credit Pilot

Минимальный каркас веб-приложения для кредитных заявок малого бизнеса.

## Структура

- `backend/` — Python 3.12, FastAPI, проверка PostgreSQL через `SELECT 1`.
- `frontend/` — React, TypeScript и Vite; в Docker собранную страницу раздаёт nginx.
- `compose.yaml` — frontend, backend и PostgreSQL 17 с именованным volume.

## Запуск

Нужны Docker Engine / Docker Desktop и Docker Compose v2 или новее.
Из корня репозитория:

```bash
cp .env.example .env
docker compose up --build
```

В `.env` задаются имя БД, пользователь, пароль и внешние порты. Значения
из примера предназначены для локального запуска. Не добавляйте `.env` в Git.
Backend получает параметры подключения из `POSTGRES_HOST`, `POSTGRES_PORT`,
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; внутри Compose адрес БД
и её порт заданы как `postgres:5432`.

Адреса при стандартных портах:

- Frontend: http://localhost:5173
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

Откройте frontend: статус backend и БД обновляется каждые 5 секунд.
Запрос `/api/health` идёт через nginx на backend. При локальном запуске
Vite (`cd frontend && npm ci && npm run dev`) `/api` проксируется на
`http://localhost:8000`.

## Проверка

```bash
curl -i http://localhost:5173/api/health
docker compose stop postgres
curl -i http://localhost:5173/api/health
docker compose start postgres
```

При доступной БД ответ — HTTP 200 и `{"status":"ok","database":"ok"}`.
При недоступной — HTTP 503 и `{"status":"error","database":"unavailable"}`.
Страница отображает соответствующий статус. После запуска БД дождитесь
её готовности и следующего обновления страницы.

## Остановка

```bash
docker compose down
```

Данные остаются в именованном volume. `docker compose down -v` также удаляет
volume и все данные БД. Переменные `POSTGRES_*` инициализируют БД при первом
запуске с пустым volume; изменение `.env` не меняет существующих пользователей.
