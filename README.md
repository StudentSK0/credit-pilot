# Credit Pilot

Минимальный каркас веб-приложения для кредитных заявок малого бизнеса.

## Структура

- `backend/` — Python 3.12, FastAPI, psycopg, API черновиков заявок и health.
- `backend/migrations/` — миграции Alembic; `backend/tests/` — API-тесты с PostgreSQL.
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

## Миграции backend

При обычном запуске контейнер backend выполняет `alembic upgrade head` перед
запуском API. Существующий volume сохраняется; миграция создаёт таблицу заявок.
Применить миграции отдельно, без запуска API:

```bash
docker compose up -d postgres
docker compose run --rm --build backend alembic upgrade head
```

## API заявок

**Авторизация и контроль доступа пока не реализованы.** Любой, кто имеет доступ
к API, может прочитать заявку по номеру, изменить черновик и отправить его.
Используйте только синтетические данные. Интерфейс frontend пока показывает
только состояние backend и БД.

Редактируемые поля: `company_name` (до 255 символов), `inn`, `credit_purpose`
(до 1 000 символов), `amount` (рубли), `term` (целое число месяцев).
В черновике поля можно пропускать или очищать через `null`; текст допускает
пустые строки. Пустые строки в `amount` и `term` превращаются в `null`.
При PATCH отсутствующие поля сохраняют прежние значения.

Сумма хранится в PostgreSQL как точный `NUMERIC`, без округления. Допустимы
конечные значения максимум с двумя знаками после запятой, в том числе в черновике.
Например, `1.001` и `1.230` отклоняются. JSON принимает сумму числом или строкой;
рекомендуется десятичная строка, чтобы клиент не терял точность. В ответе сумма
возвращается строкой. `term` передаётся JSON-целым числом в диапазоне PostgreSQL
`BIGINT` (от −2⁶³ до 2⁶³−1).

Сервер назначает `id` (номер из последовательности БД), `created_at`, `updated_at`
и статус `DRAFT`. Передать эти поля при создании или PATCH нельзя.
Номера могут иметь пропуски. Метки времени содержат часовой пояс.

Создать неполный черновик (HTTP 201):

```bash
curl -X POST http://localhost:8000/api/applications \
  -H 'Content-Type: application/json' \
  -d '{"company_name":"Тестовая компания"}'
```

Подставьте полученный `id` вместо `1`. Прочитать и дополнить заявку:

```bash
curl http://localhost:8000/api/applications/1

curl -X PATCH http://localhost:8000/api/applications/1 \
  -H 'Content-Type: application/json' \
  -d '{"inn":"1234567890","credit_purpose":"Закупка оборудования","amount":"125000.25","term":12}'
```

Отправить заявку:

```bash
curl -X POST http://localhost:8000/api/applications/1/submit
```

Отправка требует все пять полей: название и цель не должны состоять только
из пробелов, ИНН — ровно 10 или 12 ASCII-цифр (без проверки контрольной суммы),
сумма и срок — больше нуля. Успешная отправка возвращает HTTP 200 и статус
`SUBMITTED`. При ошибке валидации (HTTP 422) данные и метки времени не меняются.
Редактировать и повторно отправлять `SUBMITTED` нельзя (HTTP 409).
Несуществующий номер возвращает HTTP 404. Решения сотрудников пока отсутствуют.

## Тесты backend

```bash
docker compose up -d postgres
docker compose run --rm --build backend sh -c 'pip install -r requirements-dev.txt && pytest -q'
```

Нужен доступ к реальному PostgreSQL. Тесты создают отдельную временную БД,
применяют к ней миграцию и удаляют её после прогона; данные основной БД
не изменяются. Пользователю БД нужно право `CREATEDB` (стандартный пользователь
PostgreSQL из Compose его имеет). Установка тестовых зависимостей требует сети.
Проверяются неполные черновики, PATCH, точность сумм, ошибки и успех отправки,
защита серверных полей, HTTP 404/409 и health.
