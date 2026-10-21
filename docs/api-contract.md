# A02. API-контракт кредитной заявки Credit Pilot

Дата: 21 октября 2026 года. Анализ реализации: `origin/main`, коммит
`b0fc4c796d2417b52366987fb2f04fdf828f6570`.
Спецификация A01 прочитана через `git show` из remote-ветки
`origin/docs/a01-application-form-spec`, коммит
`e29c0ce8308f759132470e016f2712b43f361ed5`, без merge и копирования в A02.
Статус документа: описание действующего API и проект контрактов будущих задач.
Публикация A02 не означает согласования предложенных новых схем.

Источники:

| Код | Документ / код |
| --- | --- |
| A01 | [Спецификация анкеты, зафиксированная версия](https://github.com/StudentSK0/credit-pilot/blob/e29c0ce8308f759132470e016f2712b43f361ed5/docs/application-form-spec.md) |
| R | [Требования](requirements.md), в особенности R03–R05/R12–R19 и U01–U05 |
| A | [Архитектура](architecture.md): доступ, CSRF, команды, продукты, проверки и политика |
| D | [Модель данных](domain-model.md): поля, инварианты и миграции |
| F | [Путь заявки](application-flow.md): операции и переходы |
| P | [План MVP](mvp-plan.md): T05/T06/T07 и банковские этапы |
| C | [applications.py](../backend/applications.py): реальные маршруты, Pydantic-схемы, SQL и submit |
| S | [auth.py](../backend/auth.py): Login, сессии, роли, CSRF и Origin |
| E | [audit.py](../backend/audit.py): ApplicationEvent и allowlist истории |
| DB | [database.py](../backend/database.py), [миграции](../backend/migrations/versions): хранение и транзакции |
| M | [main.py](../backend/main.py): подключённые routers, health, создание FastAPI |
| T | [test_applications.py](../backend/tests/test_applications.py), [test_events.py](../backend/tests/test_events.py), [test_migrations.py](../backend/tests/test_migrations.py), [conftest.py](../backend/tests/conftest.py) |
| B | [README](../README.md): запуск и проверки; [AGENTS.md](../AGENTS.md): ограничения работ |

PDF исходного ТЗ отсутствует в checkout: требования организаторов проверены
по R, прямой сверки с PDF не было. Продукты, финансовые признаки и скоринг —
учебные предложения команды из A/D, не реальные условия Альфа-Банка.
Пользователь уточнил срок хакатона до 6 дней; прежние 7 дней в P не являются
основанием для расширения задачи. В A02 изменяется только этот документ.

## 1. Назначение API

API связывает веб-кабинет предпринимателя и кабинет сотрудника с одной
PostgreSQL-БД: создание и сохранение анкеты, отправка, чтение статуса и истории,
а в будущем — локальные проверки и банковское решение. Роль CLIENT может
работать только со своими заявками по `owner_id`; BANK_EMPLOYEE сейчас читает
любую существующую заявку и её историю, включая legacy без владельца.
Создавать, редактировать и отправлять от имени клиента сотрудник не может.

Компоненты уже реализованного модульного монолита: FastAPI, auth, applications,
audit, psycopg и PostgreSQL. Alembic использует SQLAlchemy для миграций;
ORM-перенос T02 отложен. React/Vite/nginx пока показывают только health, без
входа и формы. Три Compose-сервиса сохраняются; новые сервисы не проектируются.

`IMPLEMENTED` означает подтверждение исходниками базового коммита, а не запуск
endpoint в A02. `PLANNED` означает отсутствие маршрута/расширения в коде.
Для PLANNED отдельно различаются уже описанный целевой процесс и новые
**Предложения аналитика**, требующие решения в разделе 10. PLANNED JSON нельзя
отправлять в текущий backend: неизвестные поля POST/PATCH дадут 422.

T05 добавляет продукты/финансы и обязательность при submit; T06 — вход/сессию
в UI; T07 — форму, список и историю в UI. T08–T14 — банковский конвейер и
симуляции. Только синтетические данные, локальные детерминированные проверки,
никаких реальных БКИ/ФНС, подписей, платежей, платных runtime-API или LLM.
Запросы уточнений/уведомления остаются внутри веб-продукта (R, A01, A, F).

## 2. Каталог endpoints

### 2.1. IMPLEMENTED — действующие маршруты

Базовый префикс `/api`; URL в таблице полные относительно origin.
`{id}` в документации соответствует Python-параметру `{application_id}`.
CLIENT* означает владельца по owner_id. Cookie требуется всем строкам,
кроме login и health; CSRF требуется мутациям, кроме login.
Коды ниже определены по исходникам функций и схем, а не только по объявлениям OpenAPI.
Общие необработанные 5xx возможны при инфраструктурных ошибках, см. 3.1.

| HTTP method | URL | Назначение | Роль | Параметры запроса | Ответ | HTTP status codes | Состояние |
| --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/auth/login` | Создать серверную сессию | Без входа | JSON Login, Origin/Sec-Fetch-Site | LoginResult + Set-Cookie | 200, 401, 403, 422 | IMPLEMENTED |
| GET | `/api/me` | Узнать пользователя сессии | CLIENT/BANK_EMPLOYEE | Cookie, без тела | User | 200, 401 | IMPLEMENTED |
| POST | `/api/auth/logout` | Отозвать текущую сессию | CLIENT/BANK_EMPLOYEE | Cookie, CSRF, без тела | Пусто, cookie удаляется | 204, 401, 403 | IMPLEMENTED |
| POST | `/api/applications` | Создать DRAFT | CLIENT | JSON ApplicationFields, CSRF | Application | 201, 401, 403, 422 | IMPLEMENTED |
| GET | `/api/applications/{id}` | Прочитать заявку | CLIENT* / BANK_EMPLOYEE | Path integer id, без тела | Application | 200, 401, 403, 404, 422 | IMPLEMENTED |
| PATCH | `/api/applications/{id}` | Изменить DRAFT | CLIENT* | Path id, JSON ApplicationFields, CSRF | Application | 200, 401, 403, 404, 409, 422 | IMPLEMENTED |
| POST | `/api/applications/{id}/submit` | Отправить DRAFT | CLIENT* | Path id, CSRF, без тела | Application | 200, 401, 403, 404, 409, 422 | IMPLEMENTED |
| GET | `/api/applications/{id}/events` | Прочитать историю | CLIENT* / BANK_EMPLOYEE | Path id, query after_id/limit | ApplicationEvent[] | 200, 401, 403, 404, 422 | IMPLEMENTED |
| GET | `/api/health` | Проверить API/БД через SELECT 1 | Без входа | Нет | Health | 200, 503 | IMPLEMENTED |

Для GET заявок 403 предусмотрен `find_application` при неподдерживаемой роли;
сейчас штатных ролей только две и обе разрешены на чтение. 404 объединяет
отсутствие заявки и чужую заявку CLIENT. Не существует отдельного рабочего
endpoint статуса: читать `Application.status` существующим GET.

### 2.2. PLANNED — предложения методов в предусмотренных группах API

Группы URL заданы A; конкретные методы, дочерний URL ответа на уточнение,
новые тела/обёртки и коды успеха ниже — **Предложение аналитика**.
Они не считаются утверждёнными по факту A01/A02. Численные параметры
пагинации — тоже предложение, а не требование ТЗ. Детали в 3.11–3.13 и 10.

| HTTP method, предложение | URL, предложение | Назначение | Роль, предложение | Параметры | Ответ, предложение | HTTP codes, предложение | Состояние |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/products` | Получить доступные учебные условия | CLIENT/BANK_EMPLOYEE | Без query/тела | Product[] | 200, 401 | PLANNED, T05, Q01/Q02/Q05 |
| GET | `/api/applications` | Список своих / банковская очередь | CLIENT / BANK_EMPLOYEE | after_id, limit, необязательный status | ApplicationPage | 200, 401, 403, 422 | PLANNED, T07/T08, Q05 |
| POST | `/api/applications/{id}/checks` | Запуск/повтор локальных проверок | BANK_EMPLOYEE | id, expected_version, CSRF | ProcessingResult | 200, 401, 403, 404, 409, 422 | PLANNED, T08–T10, BQ01/BQ02 |
| POST | `/api/applications/{id}/information-requests` | Запросить уточнения | BANK_EMPLOYEE | id, expected_version, причина, поля, CSRF | InformationRequest | 201, 401, 403, 404, 409, 422 | PLANNED, T11, BQ01/BQ03 |
| POST | `/api/applications/{id}/information-requests/{request_id}/response` | Ответить на конкретный запрос | CLIENT* | id/request_id, expected_version, ответ, CSRF | Application | 200, 401, 403, 404, 409, 422 | PLANNED, T11, BQ01/BQ03 |
| POST | `/api/applications/{id}/decisions` | Предложить условия / отказать | BANK_EMPLOYEE | id, expected_version, решение, CSRF | Decision | 201, 401, 403, 404, 409, 422 | PLANNED, T12, BQ01/BQ03 |
| GET | `/api/applications/{id}/offer` | Прочитать предложение | CLIENT* / BANK_EMPLOYEE | id, без тела | Offer | 200, 401, 403, 404, 409 | PLANNED, T13/T14, BQ04 |
| POST | `/api/applications/{id}/sign` | Имитация подписи | CLIENT* | id, версия условий, command_key, CSRF | SimulatedContract | 200, 401, 403, 404, 409, 422 | PLANNED, T14, BQ04 |
| POST | `/api/applications/{id}/disburse` | Имитация выдачи | BANK_EMPLOYEE | id, command_key, CSRF | SimulatedDisbursement | 200, 401, 403, 404, 409, 422 | PLANNED, T14, BQ04 |

200 для sign/disburse предложен как общий код первого/идемпотентного повторного
результата, а не действующий контракт. Конкретные схемы этих трёх ресурсов
не закрываются A02 без согласования BQ04. `/api/feed` — будущая группа из A,
отдельная T15; лента не является частью анкеты или application_events.

## 3. Контракты запросов и ответов

### 3.1. Общие соглашения и ошибки IMPLEMENTED

Тело POST создания/PATCH/login — обязательный JSON-объект с
`Content-Type: application/json`. `{}` валиден для создания/PATCH, но отсутствие
тела/null вместо объекта не является пустым черновиком. Для GET, submit, logout
тела не нужны: frontend не должен отправлять ни `{}`, ни `null` вместо отсутствия
тела. Код не задаёт отдельной схемы запрета лишнего тела у submit/logout;
нельзя объявлять непредусмотренные поля такого тела способом изменить данные.

Все примеры синтетические; id, время и версии иллюстрируют один сценарий и
не фиксируют последовательность БД. Значения `<...>` — заглушки, не секреты.
Деньги в JSON-ответах строки, timestamps — ISO 8601 с часовым поясом;
в примерах UTC. Точное число цифр дробной части строкового ответа не следует
считать форматированием UI. Пропуски в последовательностях id допустимы.

| Код | Точный detail текущих HTTPException либо источник |
| --- | --- |
| 401 | `Authentication required`; `Session is invalid or expired`; на login `Invalid credentials` |
| 403 | `CSRF token is invalid`; `Origin is not allowed`; `Client role required`; для неподдерживаемой роли чтения `Role is not allowed` |
| 404 | `Application not found` |
| 409 | `Application is not a draft` |
| 422 | Массив ошибок FastAPI/Pydantic либо специально собранный массив submit |

Пример 404 (аналогичная обёртка для перечисленных строковых ошибок):

```json
{"detail":"Application not found"}
```

Пример 422 от submit при сохранённом amount `"0"`; `type` и `msg` приведены
для правила gt=0, а frontend ориентируется прежде всего на loc/тип ошибки:

```json
{
  "detail": [
    {"loc":["body","amount"],"msg":"Input should be greater than 0","type":"greater_than"}
  ]
}
```

Submit формирует только loc/msg/type; ошибки Pydantic тела/пути/query могут
дополнительно содержать input/ctx. Пример 422 на PATCH лишнего status:

```json
{
  "detail": [
    {"type":"extra_forbidden","loc":["body","status"],"msg":"Extra inputs are not permitted","input":"SUBMITTED"}
  ]
}
```

Русские тексты A01 — предложение UI, не фактические строки API. Общего
business `error_code`, request_id и отдельного Problem Details сейчас нет.
Маппинг loc: body → поле формы, path → ссылка, query → параметры списка/истории;
неизвестную ошибку показывать общей сводкой. Не журналировать полное тело ошибки
login: FastAPI может включать входное значение в input.

Только health перехватывает `psycopg.Error` и возвращает согласованный JSON 503.
Остальные маршруты не имеют общего преобразования инфраструктурных сбоев в 503:
возможен необработанный 5xx без гарантии JSON. Не выполнять слепой `response.json()`
на пустом 204 или любом не-JSON ответе. При нескольких одновременно нарушенных
условиях не обещается универсальный порядок 401/403/422; негативные проверки
контракта изолируют одну причину. При невалидной бизнес-команде нет частичной записи.

### 3.2. POST /api/auth/login — IMPLEMENTED

Назначение: проверить учётные данные локального синтетического пользователя.
`login`: обязательная string 1–255; `password`: обязательная string 1–1024.
Лишние поля запрещены. Старые cookie/CSRF не требуются; Origin и Sec-Fetch-Site
проверяются. Значение ниже — заглушка пароля, не инструкция менять seed.

Запрос:

```json
{"login":"client-a","password":"<пароль локального демоаккаунта>"}
```

Ответ 200 — LoginResult:

```json
{"id":1,"role":"CLIENT","company_id":1,"csrf_token":"<CSRF из ответа login>"}
```

Также Set-Cookie с HttpOnly session-cookie и `Cache-Control: no-store`.
Пароль и session-token не возвращаются в JSON. id — integer пользователя,
role — CLIENT/BANK_EMPLOYEE, company_id — integer/null, csrf_token — string.
Для BANK_EMPLOYEE company_id=null по текущей модели. Ошибки: 401 — неизвестный
логин/неверный пароль с одинаковым detail; 403 Origin/cross-site; 422 — схема.
Повторный login создаёт новую сессию и заменяет cookie текущего браузера;
автоматическое отзывание всех прежних сессий пользователя кодом не предусмотрено.

### 3.3. GET /api/me — IMPLEMENTED

Вход: действующая cookie, без path/query/JSON-тела и без CSRF. Назначение:
bootstrap пользователя из серверной сессии. Ответ 200 — User:

```json
{"id":1,"role":"CLIENT","company_id":1}
```

`Cache-Control: no-store`; типы совпадают с соответствующими полями LoginResult.
csrf_token отсутствует. Ошибка 401 — нет/невалидна/истекла сессия. Запрос не
продлевает срок и не создаёт новую сессию. Восстановление UI описано в разделе 7.

### 3.4. POST /api/auth/logout — IMPLEMENTED

Вход: cookie, X-CSRF-Token, допустимый Origin/Sec-Fetch-Site; JSON-тела нет.
Доступ: обе действующие роли. Назначение: удалить текущую сессию из sessions.
Ответ 204 без JSON, Set-Cookie удаляет cookie с Path=/api.
Ошибки: 401 при уже отсутствующей/отозванной сессии; 403 при CSRF/Origin.
Повтор без действующей сессии не обещает 204. Никаких событий заявки не создаётся.

### 3.5. POST /api/applications — IMPLEMENTED

Доступ CLIENT + cookie/CSRF. Вход — ApplicationFields: только пять полей
раздела 4.1, все необязательны/nullable; schema extra=forbid. Структурные
ограничения проверяются уже при создании, полнота — позже при submit.
Нельзя передавать id/status/owner_id/company_id/created_by/version/timestamps.

Минимальный запрос:

```json
{}
```

Пример ответа 201 — Application (A0):

```json
{
  "company_name":null,
  "inn":null,
  "credit_purpose":null,
  "amount":null,
  "term":null,
  "id":123,
  "status":"DRAFT",
  "created_at":"2026-10-21T12:00:00Z",
  "updated_at":"2026-10-21T12:00:00Z",
  "company_id":1,
  "created_by":1,
  "version":1,
  "owner_id":1
}
```

Владелец/автор/компания берутся из сессии. DRAFT_CREATED с версией 1
и old/new всех пяти полей пишется в той же транзакции. Повтор POST создаёт
другую заявку; ключа идемпотентности нет. Ошибки: 401, 403 роль/CSRF/Origin,
422 схема, включая неизвестные будущие поля. Права не назначаются запросом.

### 3.6. GET /api/applications/{id} — IMPLEMENTED

Вход: id — path integer; JSON-тела/query нет. Точное имя в FastAPI —
`application_id`; буквальная часть URL не меняется. Строка пути, не приводимая
к integer, даёт 422; integer вне signed BIGINT даёт 404 из find_application.
Отсутствующий, нулевой или отрицательный номер при отсутствии такой записи — 404.
Доступ: CLIENT-владелец либо BANK_EMPLOYEE; CSRF для чтения не нужен.

Ответ 200 после заполнения из следующего примера PATCH — Application (A1):

```json
{
  "company_name":"ООО «Демо-Мастер»",
  "inn":"1234567890",
  "credit_purpose":"Закупка оборудования",
  "amount":"125000.25",
  "term":12,
  "id":123,
  "status":"DRAFT",
  "created_at":"2026-10-21T12:00:00Z",
  "updated_at":"2026-10-21T12:01:00Z",
  "company_id":1,
  "created_by":1,
  "version":2,
  "owner_id":1
}
```

Все ключи ответа присутствуют, незаполненные значения null. Возвращается
сохранённое состояние; чтение не меняет timestamps/version и не пишет событие.
Ошибки: 401; 404 одинаково для отсутствующей и чужой заявки; 422 path;
403 только для неподдерживаемой роли. Legacy owner_id=null CLIENT не читает,
BANK_EMPLOYEE читает без назначения нового владельца.

### 3.7. PATCH /api/applications/{id} — IMPLEMENTED

Вход: path id, cookie/CSRF, обязательный JSON ApplicationFields. Только
CLIENT-владелец и DRAFT. Пропущенные ключи сохраняются, null очищает ключ;
пустой/не меняющий данные PATCH возвращает прежнюю запись без нового события.
Пустая/пробельная string amount/term нормализуется в null; текстовые пустые
строки остаются строками. Строгие ограничения чисел и длины — в разделе 4.

Запрос для изменения A0:

```json
{
  "company_name":"ООО «Демо-Мастер»",
  "inn":"1234567890",
  "credit_purpose":"Закупка оборудования",
  "amount":"125000.25",
  "term":12
}
```

Ответ 200 — Application (A1):

```json
{
  "company_name":"ООО «Демо-Мастер»",
  "inn":"1234567890",
  "credit_purpose":"Закупка оборудования",
  "amount":"125000.25",
  "term":12,
  "id":123,
  "status":"DRAFT",
  "created_at":"2026-10-21T12:00:00Z",
  "updated_at":"2026-10-21T12:01:00Z",
  "company_id":1,
  "created_by":1,
  "version":2,
  "owner_id":1
}
```

Реальное изменение: row lock, version +1, updated_at обновлён,
DRAFT_UPDATED только с изменёнными old/new; одна транзакция. Денежные значения
сравниваются как Decimal: `"125000.25"` и равное числовое значение не создают
различия только из-за представления строки. Ожидаемая версия не принимается.
Ошибки: 401; 403 роль/CSRF/Origin; 404 нет доступной заявки; 409 не DRAFT
(включая `{}`); 422 входы. Если body невалидно, не обещать 409 вместо 422.

### 3.8. POST /api/applications/{id}/submit — IMPLEMENTED

Вход: path id, cookie/CSRF, без JSON-тела. Доступ CLIENT-владелец, только DRAFT.
Проверяет сохранённую заявку по SubmissionFields: непустые company_name/цель,
ASCII-ИНН из 10/12 цифр, положительные amount/term. Сейчас продукт/финансы
не проверяются и не требуются. Запрос не принимает редактируемые поля:
передать их сначала PATCH и дождаться успешного ответа.

Ответ 200 для A1 — Application (A2):

```json
{
  "company_name":"ООО «Демо-Мастер»",
  "inn":"1234567890",
  "credit_purpose":"Закупка оборудования",
  "amount":"125000.25",
  "term":12,
  "id":123,
  "status":"SUBMITTED",
  "created_at":"2026-10-21T12:00:00Z",
  "updated_at":"2026-10-21T12:02:00Z",
  "company_id":1,
  "created_by":1,
  "version":3,
  "owner_id":1
}
```

SUBMITTED и одно одноимённое событие с пустым changes записываются атомарно;
updated_at/version меняются, исходные поля сохраняются. Это не одобрение и
не автоматический запуск проверки. Ошибки: 401; 403 роль/CSRF/Origin; 404;
409 не DRAFT, включая повтор; 422 путь/валидация сохранённых полей.
При ошибке submit сама команда ничего не меняет; успешный предшествующий PATCH
не откатывается, поскольку это другая транзакция.

### 3.9. GET /api/applications/{id}/events — IMPLEMENTED

Доступ и path как у чтения заявки; JSON-тела нет. Query:
`after_id`: integer, от 0 до 2⁶³−1, default=0;
`limit`: integer 1–100, default=100. Сначала проверяется доступ к заявке,
затем выбираются события `id > after_id ORDER BY id LIMIT limit`.
Пример запроса: GET `/api/applications/123/events?after_id=0&limit=100`.

Ответ 200 для последовательности A0 → A1 → A2:

```json
[
  {
    "id":501,"application_id":123,"event_type":"DRAFT_CREATED",
    "occurred_at":"2026-10-21T12:00:00Z","actor_id":1,"actor_role":"CLIENT",
    "previous_status":null,"new_status":"DRAFT","application_version":1,
    "changes":{
      "company_name":{"old":null,"new":null},
      "inn":{"old":null,"new":null},
      "credit_purpose":{"old":null,"new":null},
      "amount":{"old":null,"new":null},
      "term":{"old":null,"new":null}
    }
  },
  {
    "id":502,"application_id":123,"event_type":"DRAFT_UPDATED",
    "occurred_at":"2026-10-21T12:01:00Z","actor_id":1,"actor_role":"CLIENT",
    "previous_status":"DRAFT","new_status":"DRAFT","application_version":2,
    "changes":{
      "company_name":{"old":null,"new":"ООО «Демо-Мастер»"},
      "inn":{"old":null,"new":"1234567890"},
      "credit_purpose":{"old":null,"new":"Закупка оборудования"},
      "amount":{"old":null,"new":"125000.25"},
      "term":{"old":null,"new":12}
    }
  },
  {
    "id":503,"application_id":123,"event_type":"SUBMITTED",
    "occurred_at":"2026-10-21T12:02:00Z","actor_id":1,"actor_role":"CLIENT",
    "previous_status":"DRAFT","new_status":"SUBMITTED","application_version":3,
    "changes":{}
  }
]
```

Это массив, не `{items,total}`. Для следующей страницы использовать after_id
последнего события. Короткая/пустая страница означает отсутствие следующих
событий на момент чтения; точного общего total/next_cursor в ответе нет.
Даты внутри примера условны: код не обещает равенство occurred_at и updated_at.
Ошибки: 401/404/422 path-query; 403 неподдерживаемая роль. Пустая история
существующей legacy-заявки допустима; чтение не выдумывает события.

### 3.10. GET /api/health — IMPLEMENTED

Без сессии, CSRF, параметров и тела. SELECT 1 выполняется в PostgreSQL.
Успешный ответ 200:

```json
{"status":"ok","database":"ok"}
```

Ошибка `psycopg.Error`, ответ 503:

```json
{"status":"error","database":"unavailable"}
```

Не расширять этот контракт до проверки будущего конвейера или доступности
реальных внешних сервисов. 503 health не означает, что каждый endpoint имеет
такой обработчик ошибок. Данные основного volume ради health не удаляются.

### 3.11. GET /api/products — PLANNED, предложение Q01/Q02/Q05

Назначение: передать frontend серверные условия раздела 5. Предлагаемый доступ:
обе авторизованные роли, CSRF не нужен. Без query/JSON-тела. Ответ 200 — массив
Product с обязательными полями примера: code/name/version/currency — string,
min_amount/max_amount/annual_rate — десятичные string, min_term/max_term — integer.
`annual_rate` предлагается как доля единицы, не процентное число; UI показывает
20% для `"0.20"`. Пределы из A, но имена/формат JSON ниже ещё не согласованы.

```json
[
  {
    "code":"WORKING_CAPITAL","version":"product_v1","name":"Оборотный кредит",
    "currency":"RUB","min_amount":"50000","max_amount":"3000000",
    "min_term":3,"max_term":24,"annual_rate":"0.20"
  },
  {
    "code":"EQUIPMENT","version":"product_v1","name":"Кредит на оборудование",
    "currency":"RUB","min_amount":"100000","max_amount":"5000000",
    "min_term":6,"max_term":36,"annual_rate":"0.18"
  }
]
```

`product_v1` в примере — условная строка версии для обсуждения, не действующее
значение API. Ошибка, предложение: 401 без сессии; 200 `[]` для пустого каталога;
инфраструктурные 5xx отдельно. Политика доступности старых версий — Q02.

### 3.12. GET /api/applications — PLANNED, предложение Q05

Назначение: список своих заявок CLIENT и очередь BANK_EMPLOYEE без передачи
owner_id пользователем. Предлагается cookie без CSRF; query after_id 0..2⁶³−1,
default=0; limit 1–100/default=100 по аналогии с events; необязательный status
из действующего на этапе Enum. Эти параметры, единый маршрут для двух ролей,
сортировка id ASC и обёртка пока не согласованы.
Пример: GET `/api/applications?after_id=0&limit=100&status=DRAFT`, без тела.

Ответ 200 — предлагаемая ApplicationPage: items — массив полных Application,
next_after_id — integer/null. Пример короткой страницы до T05, без новых полей:

```json
{
  "items":[
    {
      "company_name":"ООО «Демо-Мастер»","inn":"1234567890",
      "credit_purpose":"Закупка оборудования","amount":"125000.25","term":12,
      "id":123,"status":"DRAFT","created_at":"2026-10-21T12:00:00Z",
      "updated_at":"2026-10-21T12:01:00Z","company_id":1,"created_by":1,
      "version":2,"owner_id":1
    }
  ],
  "next_after_id":null
}
```

Рекомендуемая семантика: сервер запрашивает limit+1, отдаёт не более limit;
next_after_id равен id последнего выданного элемента только если есть следующая
страница, иначе null. Пустой список — 200 с items=[] и null. Total не предлагается.
При CLIENT сервер всегда добавляет owner_id из сессии; при BANK_EMPLOYEE читает
очередь. Ошибки, предложение: 401, 403 неподдерживаемая роль, 422 query.
Это не контракт пагинации существующих events. Новейшие изменения уже загруженных
заявок перечитываются отдельно; курсор id ASC сам по себе их не отслеживает.

### 3.13. Банковские команды — PLANNED, предложения BQ01–BQ04

Ни один пример этого подраздела не проходит текущую схему как банковская команда.
Используются уже описанные в A/D/F состояния и сущности, новые статусы не вводятся.
Для всех мутаций предлагаются cookie/CSRF, path id, серверные роль/владение,
проверка состояния и будущий expected_version: обязательный integer ≥1,
сравниваемый под row lock. Это не расширение текущего PATCH. Ошибки для валидно
сформированных команд: 401/403/404; предлагаемые 409 для состояния/версии/активного
run и 422 для тела. Нет единого утверждённого списка банковских error_code.

**Проверки:** POST checks, BANK_EMPLOYEE; допустимые переходы в разделе 6.
Запрос (все показанные поля обязательны):

```json
{"expected_version":3}
```

Предлагаемый ответ 200 — ProcessingResult; run_id integer, state enum
RUNNING/COMPLETE/INCOMPLETE/FAILED, score integer/null, application — полная
актуальная Application с будущим status. Иллюстрация формы результата содержит
только фрагмент application, не выдаётся за полный response schema:

```json
{"run_id":71,"state":"INCOMPLETE","score":null,"application":{"id":123,"status":"UNDER_REVIEW","version":5}}
```

Рекомендуется 200, если команда сохранила доменный результат, включая
INCOMPLETE/FAILED; при техническом сбое до сохранения — инфраструктурный 5xx.
Такая HTTP-семантика требует BQ02. Нет данных fixture — INCOMPLETE без оценки,
а не 422 анкеты/успешная проверка; технический FAILED оставляет CHECKING.
Полный run/result/check/factor JSON, безопасные error_code и версия результата
должны быть утверждены BQ02 до независимой реализации банковского UI.

**Запрос уточнений:** POST information-requests, BANK_EMPLOYEE, UNDER_REVIEW,
нет другого открытого запроса; причина string непустая, поля — непустой массив
разрешённых финансовых имён. Новые ограничения длины/числа элементов не задаются
без решения BQ03. Запрос:

```json
{"expected_version":5,"reason":"Уточните операционные расходы","fields":["monthly_operating_expenses"]}
```

Предлагаемый ответ 201 — фрагмент InformationRequest; id/application_id integer,
reason string, fields string[], responded_at date-time/null; статус заявки
меняется сервером на NEEDS_INFO:

```json
{"id":81,"application_id":123,"reason":"Уточните операционные расходы","fields":["monthly_operating_expenses"],"responded_at":null}
```

**Ответ клиента:** POST information-requests/{request_id}/response, CLIENT-владелец,
NEEDS_INFO и актуальный открытый запрос, path request_id integer. Предлагаются
expected_version, объект financial_fields только с запрошенными полями и
непустое explanation string; обязательность пояснения/полнота набора — BQ03.
Денежные поля string Decimal; предложение — все запрошенные поля обязательны.

```json
{"expected_version":6,"financial_fields":{"monthly_operating_expenses":"110000.00"},"explanation":"Уточнили ежемесячные операционные расходы"}
```

Ответ 200 — полная актуальная Application после перехода в SUBMITTED;
ниже только фрагмент будущей схемы:

```json
{"id":123,"status":"SUBMITTED","version":7,"monthly_operating_expenses":"110000.00"}
```

Не разрешать owner_id/ИНН/продукт/исходную сумму/срок/статус/баллы. Запрос
и ответ сохраняются, новый REQUEST-run начинается отдельной банковской командой.
Чужой/не относящийся к заявке request_id предлагается скрывать через 404;
закрытый/устаревший запрос — 409. Это предложение конкретизации BQ03.

**Решение:** POST decisions, BANK_EMPLOYEE, UNDER_REVIEW, актуальная версия
и допустимость по существующей policy_v1. Предлагаемые обязательные поля:
expected_version integer, type OFFER/REJECT; для REJECT reason_code/reason_text
непустые string; для OFFER offered_amount Decimal string, offered_term integer,
comment string при MEDIUM. Перечень reason_code/прочие лимиты — BQ03.
Пример отказа при полном HIGH, не при INCOMPLETE:

```json
{"expected_version":9,"type":"REJECT","reason_code":"<код из согласуемого справочника>","reason_text":"Учебная оценка выявила недостаточный денежный поток"}
```

Предлагаемый ответ 201 — фрагмент Decision; id/application_id/run_id integer,
type enum, reason_code/reason_text string:

```json
{"id":91,"application_id":123,"run_id":72,"type":"REJECT","reason_code":"<код из согласуемого справочника>","reason_text":"Учебная оценка выявила недостаточный денежный поток"}
```

Для OFFER сравнение с исходным запросом и пересчёт для меньшей суммы отдельны;
исходный снимок не перезаписывается. Предложение запрещено при HIGH, неактивной
регистрации и других блокировках A. Подтверждённая неактивная регистрация допускает
отказ по допустимости без score; INCOMPLETE из-за неизвестных данных не означает
отказ по риску. Детали предлагаемых банковских JSON — открытые BQ, не готовые
к реализации неизменные схемы. Offer/sign/disburse имеют только границы из 2.2/6;
их отдельный контракт BQ04 нужен перед T14, не заменяется вымышленными примерами.

## 4. Модель данных заявки

### 4.1. ApplicationFields / SubmissionFields — IMPLEMENTED

На POST/PATCH все пять полей необязательны, default=null; при PATCH отсутствие
ключа сохраняет значение. На submit все обязательны и не nullable. Это внутренний
валидатор сохранённых данных, а не тело POST /submit. Строки не обрезаются молча.

| Поле, точное имя | JSON вход → хранение / JSON ответ | DRAFT | При submit сейчас | Источник |
| --- | --- | --- | --- | --- |
| company_name | string/null → VARCHAR(255) / string/null | ≤255, допустимы пустота/null | Обязательно, длина 1–255, не только whitespace | C, D |
| inn | string/null → TEXT / string/null | Формат/максимальная длина отдельно не ограничены | Ровно 10 либо 12 ASCII-цифр, без checksum, без пробелов/перевода строки | C, D |
| credit_purpose | string/null → VARCHAR(1000) / string/null | ≤1000, допустимы пустота/null | Обязательно, длина 1–1000, не только whitespace | C, D |
| amount | Decimal-совместимая string или JSON number/null → NUMERIC / string/null | Конечность, ≤2 десятичных знаков; 0/отрицательные допустимы | >0, те же точность/конечность; продуктовые лимиты пока отсутствуют | C, D, миграция 0001 |
| term | Строгий JSON integer/null → BIGINT / integer/null | −2⁶³..2⁶³−1; 0/отрицательные допустимы | >0 и ≤2⁶³−1 | C, D |

`""`/пробельная строка для amount/term становится null, для текста сохраняется.
`term:"12"`, `1.5`, `true` — 422. ИНН — строка, ведущие нули сохраняются.
amount `"1.001"`, `"1.230"`, `"NaN"`, `"Infinity"` — 422 уже в черновике.
Pydantic и БД не округляют ввод; NUMERIC в 0001 без фиксированного scale,
CHECK запрещает scale>2 и неконечные значения. DecimalJSONRequest читает JSON
числа через parse_float=Decimal; для frontend рекомендуется десятичная строка
без JS Number/parseFloat. Не объявлять иной синтаксис Decimal запрещённым API
без подтверждения: формат точки/запятой/экспоненты в UI — A01 Q04.

### 4.2. Application — серверные поля ответа IMPLEMENTED

Application содержит все пять полей 4.1 (ключи не исчезают при null) плюс:

| Поле | Тип JSON | Назначение / ограничение |
| --- | --- | --- |
| id | integer | Серверный идентификатор заявки из BIGINT sequence; frontend не назначает |
| status | string enum DRAFT/SUBMITTED | Серверное состояние, меняется только командой |
| created_at / updated_at | string date-time | Серверные timestamptz; timezone явно присутствует |
| owner_id | integer/null | Истинная граница прав CLIENT; у новых заявок id пользователя из сессии |
| company_id / created_by | integer/null | Ссылки совместимости/автора; company_id не даёт доступа |
| version | integer | Серверная версия, у новой заявки 1; растёт при реальном изменении и submit |

В текущих Pydantic-ответах integer-поля не имеют отдельных ge/le constraints;
пределы хранения определяет PostgreSQL. Не обещать сужение до 32 бит.
Frontend должен учитывать точность JS для 64-битных идентификаторов;
перевод id/version в JSON string был бы изменением API и требует отдельного
решения (BQ05), сейчас они именно JSON integer. Примеры используют безопасные id.

### 4.3. Расширение T05 — PLANNED

| Поле / предлагаемое имя | Планируемый тип | DRAFT | Submit после T05 | Неопределённость |
| --- | --- | --- | --- | --- |
| product_code | string/null, ссылка CreditProduct.code | Nullable | Существующий выбранный продукт | JSON-ключ логически предусмотрен D/A01, в коде отсутствует |
| product_version | Предложение: opaque string/null, ссылка CreditProduct.version | Nullable | Сервер фиксирует допустимую версию продукта | В D только product_code/version; точное имя/тип ещё Q01, не использовать version заявки |
| monthly_revenue | Decimal/NUMERIC, JSON string/null | Nullable | >0, конечная, ≤2 знаков | Правила записи до submit — Q03 |
| monthly_operating_expenses | Decimal/NUMERIC, JSON string/null | Nullable | ≥0, конечная, ≤2 знаков | Расходы > выручки допустимы; правила DRAFT — Q03 |
| existing_monthly_debt_payments | Decimal/NUMERIC, JSON string/null | Nullable | ≥0, конечная, ≤2 знаков | Нулевые долги — явный 0, null не ноль; DRAFT — Q03 |

Пример **предлагаемого** PATCH после T05 (Q01/Q03), не действующий запрос:

```json
{
  "product_code":"WORKING_CAPITAL",
  "product_version":"product_v1",
  "monthly_revenue":"200000.00",
  "monthly_operating_expenses":"100000.00",
  "existing_monthly_debt_payments":"10000.00"
}
```

Ожидаемое направление ответа — существующая Application плюс эти пять ключей,
без изменения смысла version заявки. Точные новые имена/типы и политика пары
code/version требуют Q01/Q03. Клиент передаёт выбранную ссылку, не назначает
ставку или авторитетную версию условий. Сервер проверяет ссылку и фиксирует её
при submit. Возраст бизнеса/просрочка/регистрация из локальных симуляторов,
баллы и решение не являются вводом анкеты (A/D/A01).

## 5. Кредитные продукты

Условия из A, **Предложение команды**, синтетические, не предложения Альфа-Банка:

| Код | Назначение | Сумма RUB, включительно | Срок, включительно | Учебная годовая ставка |
| --- | --- | --- | --- | --- |
| WORKING_CAPITAL | Оборотные средства | 50 000–3 000 000 | 3–24 целых месяца | 20% |
| EQUIPMENT | Оборудование | 100 000–5 000 000 | 6–36 целых месяцев | 18% |

Будущее взаимодействие: frontend читает каталог (предложение 3.11), показывает
условия и пометку симуляции, пользователь выбирает продукт, ссылка сохраняется
в DRAFT, сервер при submit проверяет существование/допустимость версии и
включительные лимиты. Frontend использует данные каталога для предварительной
проверки, backend проверяет независимо по своей записи CreditProduct.
Ставка/лимиты не принимаются как редактируемые поля заявки. Изменение каталога
до отправки и подтверждение версии — Q02. Новые версии не переписывают старые.

Сейчас submit проверяет только amount>0 и term>0, так что непопадание в
будущий диапазон продукта само по себе ещё не 422 текущего API. T05 вводит
новую обязательность явно, новой миграцией и тестами. Нельзя молча назначить
продукт/нулевые финансы старым заявкам. Старые DRAFT дополняются; старые
неполные SUBMITTED не переписываются и не допускаются к банковской обработке
без отдельной контролируемой процедуры (P, A01 Q07).

R>0, E≥0, D≥0 — проверка входов; E>R допускается. Порог DSCR/возраст/баллы/
наличие fixture не добавляются к submit. Скоринг и policy_v1 — отдельные
этапы обработки; неизвестный ИНН не равен хорошему результату. Альтернативная
меньшая сумма хранится в Decision и отдельно оценивается, не меняя исходные
amount/term/product. Новых банковских порогов A02 не вводит.

## 6. Статусы и жизненный цикл заявки

### 6.1. IMPLEMENTED

| Состояние | Разрешённые операции | Успешная мутация / событие | Отклонение |
| --- | --- | --- | --- |
| Отсутствует | CLIENT: POST создать | DRAFT, version=1, DRAFT_CREATED | 401/403/422 без новой записи |
| DRAFT | CLIENT-владелец: GET/events, PATCH, submit; BANK_EMPLOYEE: GET/events | PATCH реальных полей: DRAFT_UPDATED и version+1; submit: SUBMITTED и version+1 | Невалидный ввод 422 без изменений; неподходящая роль/CSRF 403; чужая CLIENT-заявка 404 |
| SUBMITTED | Владелец/сотрудник: GET/events | Чтение без событий | PATCH даже пустой и повтор submit: 409 при прочих валидных условиях; банковских команд ещё нет |

Создание с заполненными полями всё равно создаёт DRAFT, а не SUBMITTED.
Пустой/неизменяющий PATCH не меняет version/timestamps и не пишет событие.
Все успешные бизнес-мутации и их события атомарны. Ошибка журнала откатывает
мутацию; уникальность (application_id, application_version) защищает журнал.
Чтения/login/logout/ошибки доступа не пишут application_events. История
append-only через API; это не защита от администратора БД.

PATCH/submit используют SELECT FOR UPDATE, но не expected_version: разные
записи одного поля последовательно перезаписываются (last-write-wins).
Конкурентные одинаковые PATCH дают 200/200 с одним изменением; конкурентные
submit — 200/409 с одним событием. Ни автоматического retry POST создания,
ни идемпотентного ключа создания сейчас нет (C/E/T/A01).

### 6.2. PLANNED — уже описанный в F процесс

В таблице только целевые состояния из F, не новые статусы A02. Чтение своей
заявки/истории остаётся доступным, обычный PATCH разрешён только в DRAFT.

| Состояние | Следующая команда/результат по F | События будущего API |
| --- | --- | --- |
| SUBMITTED | Сотрудник начинает проверки → CHECKING | CHECKS_STARTED |
| CHECKING | Завершение текущего run → UNDER_REVIEW; FAILED остаётся CHECKING; повтор после FAILED/stale | CHECKS_COMPLETED / CHECKS_FAILED; новый run — CHECKS_STARTED |
| UNDER_REVIEW | Повтор INCOMPLETE → CHECKING; запрос → NEEDS_INFO; допустимое предложение → OFFERED; мотивированный отказ → REJECTED | CHECKS_STARTED / INFORMATION_REQUESTED / OFFER_ISSUED / REJECTED |
| NEEDS_INFO | Клиент отвечает отдельной командой на актуальный запрос → SUBMITTED | INFORMATION_PROVIDED |
| OFFERED | Клиент подтверждает условия и имитацию подписи → SIGNED | SIGNED_SIMULATED |
| SIGNED | Сотрудник имитирует выдачу → DISBURSED | DISBURSED_SIMULATED |
| REJECTED / DISBURSED | Терминальные состояния v1, только просмотр | Новые переходы не предлагаются |

RUNNING/COMPLETE/INCOMPLETE/FAILED — состояния ProcessingRun, не заявки.
Неизвестные признаки не дают score; запрос уточнений не является отказом.
Подтверждённая неактивная регистрация допускает мотивированный отказ без score
по допустимости, остальные условия policy_v1 остаются из A. UI отображает
серверные состояния, не симулирует их таймером и не создаёт APPROVED/ACCEPTED.

До банковских задач нужна новая миграция: расширить applications.status
VARCHAR(9)/CHECK, previous_status/new_status VARCHAR(9), CHECK event_type;
синхронно обновить Enum Status, ApplicationEvent Literal и API/TS-схемы.
Применённые 0001–0003 не редактируются. Подпись/выдача: будущие command_key,
неизменные условия и отсутствие дубликатов по D/F; текущий submit остаётся 409
при повторе, даже если будущие команды будут идемпотентными.

## 7. Авторизация и безопасность

### 7.1. IMPLEMENTED: порядок и границы прав

1. POST login через same-origin proxy; браузер получает Set-Cookie и csrf_token.
2. Cookie `credit_pilot_session`: HttpOnly, SameSite=Lax, Path=/api, Max-Age=28800;
   Secure только при COOKIE_SECURE=true, для HTTPS требуется настройка.
3. Для чтений браузер передаёт cookie; для мутаций также X-CSRF-Token.
   У fetch рекомендуются явные `credentials: 'same-origin'`; это указание UI,
   не новая серверная авторизация. Отдельного Bearer/JWT нет.
4. current_actor сверяет hash cookie и expires_at в sessions, получает роль/id
   из users. CLIENT доступен только при applications.owner_id=users.id.
5. На мутациях проверяются Origin, если он есть, и запрет Sec-Fetch-Site=cross-site,
   затем CSRF hash. Login тоже проверяет Origin/Sec-Fetch-Site, но не старый CSRF.
6. Logout удаляет текущую сессию, cookie и не пишет бизнес-историю заявки.

PBKDF2-SHA256 с солью и 600 000 итерациями; session/CSRF в БД только SHA-256
hash. Сессия живёт 8 часов; /me не обновляет срок. Установленная роль/owner_id/
actor не берутся из headers, тела или storage. Совпадение company_id не даёт
прав. 404 для чужой CLIENT-заявки одинаков для GET/PATCH/submit/events; BANK_EMPLOYEE
получает 403 на клиентские мутации. При валидном JSON проверка выполняется
сервером независимо от видимости кнопки.

Не заявляются CORS для произвольных origins, refresh-token, SSO/OAuth, регистрация,
rate limiting, аудит входов/просмотров или продлённая безопасность как готовые.
Не сохранять пароли, cookies, токены и тела запросов в application_events/логи.
Текущий API не имеет очистки всех истёкших сессий; это отдельное ограничение демо.

### 7.2. PLANNED T06: reload и обработка ошибок frontend

Предложение команды из A/A01: хранить только csrf_token в sessionStorage;
bootstrap — GET /api/me с cookie, роль/пользователь только по серверному ответу.
Reload той же вкладки сохраняет CSRF, затем GET заявки восстанавливает сохранённые
поля. В HttpOnly cookie frontend не заглядывает. Из csrf_hash восстановить токен
невозможно. При пустом storage и живой cookie чтения доступны; для изменений
нужен явный новый login. Отдельного CSRF-bootstrap endpoint пока нет.

| Код | Поведение UI, предложение A01 Q06 |
| --- | --- |
| 401 | Очистить устаревший CSRF, показать вход; после входа повторить GET, не бизнес-команду автоматически |
| 403 CSRF | Повторный вход, включая рассинхронизацию после login другой вкладки; не слепой retry |
| 403 роль / Origin | «Действие недоступно» / ошибка доступа; не отправлять пользователя по кругу входа |
| 404 | «Заявка не найдена или недоступна», без подтверждения существования чужой |
| 409 | Перечитать заявку, при SUBMITTED открыть результат; не сообщать о реализованном expected_version |
| 422 | Ошибки у полей по loc и общая сводка; сохранить локальный ввод, серверный статус не менять |
| Сеть / 5xx | Указать неизвестный исход; с известным id сначала GET; не обещать, что ничего не записано |

При 401/logout очищать storage; при login заменять CSRF. Новая независимая
вкладка может не иметь токена. SessionStorage доступен JS, не защита от XSS.
Автосохранение незаписанного ввода/reload local draft не реализованы и не обещаны.
При потере ответа POST создания id может быть неизвестен: автоматический retry
запрещён, будущий список помогает сверке, но не даёт гарантии идемпотентности.

## 8. Матрица Frontend ↔ Backend

UI в таблице — целевой A01/Q06; IMPLEMENTED означает только готовность API,
поскольку текущий frontend ограничен health. Все мутации ожидают cookie/CSRF,
кроме login; блокировка повторных кликов не заменяет серверную проверку.

| Действие пользователя | API endpoint | Данные запроса | Ожидаемый ответ | Изменение интерфейса | Статус реализации |
| --- | --- | --- | --- | --- | --- |
| Вход | POST /api/auth/login | login/password | 200 User+csrf_token, cookie | Запомнить CSRF, открыть кабинет по серверной роли | API IMPLEMENTED; UI T06 |
| Reload | GET /api/me, затем GET заявки | Cookie; id известной заявки | User, Application | Восстановить пользователя/сохранённые поля; проверить наличие CSRF | API IMPLEMENTED; UI T06/T07 |
| Выбор продукта | GET /api/products | Без тела | Product[] | Показать условия и отметку синтетических данных | PLANNED T05/T07, Q01/Q05 |
| Начать заявку | POST /api/applications | Сейчас `{}`/поля 4.1; после T05 ссылка продукта | 201 Application | Перейти к id, показать DRAFT | API IMPLEMENTED; расширение T05, UI T07 |
| Сохранить неполное | PATCH /api/applications/{id} | Только изменённые разрешённые поля; null очищает | 200 Application | «Черновик сохранён» только после успеха; no-op не требует нового события | API IMPLEMENTED; расширение T05, UI T07 |
| Вернуться из списка | GET /api/applications, затем GET /{id} | Query списка / path id | ApplicationPage / Application | Список и актуальный экран сохранённой заявки | Список PLANNED T07, чтение IMPLEMENTED |
| Проверить и отправить | PATCH при изменениях, затем POST /{id}/submit | Поля PATCH; submit без тела | 200 Application SUBMITTED | Перейти к результату; 422 оставить ошибки; при ошибке PATCH submit не вызывать | API IMPLEMENTED; продукт/финансы T05, UI T07 |
| Обновить статус | GET /api/applications/{id} | Без тела | Application | Показать серверный статус; не терять последний результат при сбое обновления | API IMPLEMENTED; UI T07 |
| Открыть историю | GET /api/applications/{id}/events | after_id/limit | Массив событий | Таймлайн, следующая страница отдельно | API IMPLEMENTED; UI T07 |
| Выйти | POST /api/auth/logout | Без тела, CSRF | 204 | Очистить CSRF и данные кабинета | API IMPLEMENTED; UI T06 |
| Сотрудник запускает проверки | POST /{id}/checks | Предложенный expected_version | ProcessingResult | Результаты/ошибка/повтор; INCOMPLETE без score | PLANNED T08–T10, BQ01/BQ02 |
| Сотрудник запрашивает сведения / клиент отвечает | POST information-requests / response | Предложения 3.13 | Запрос / Application | NEEDS_INFO / SUBMITTED с историей | PLANNED T11, BQ03 |
| Сотрудник принимает решение | POST /{id}/decisions | Предложенный Decision command | Decision | Результат OFFERED/REJECTED после перечитывания | PLANNED T12/T13, BQ03 |

Префикс сокращённых `/{id}` в таблице — `/api/applications`. PATCH→submit
не одна транзакция: если первый прошёл, а второй 422, сохранённый DRAFT остаётся.
Текущий API не возвращает allowed_actions, внутренние проверки или score в
Application. Их отображение нельзя строить по вымышленным полям ответа.

## 9. Приемочные тесты API Given / When / Then

Таблица — спецификация проверок, не отчёт о выполнении pytest в A02.
«Сейчас» — существующий API; финансовые/каталожные проверки ждут T05;
браузерные сценарии — T06/T07. Для негативной проверки остальные предусловия
валидны; no-op и ошибки сравнивают данные, timestamps, version и историю до/после.

| ID | Given | When | Then | Применимость / связь с тестами |
| --- | --- | --- | --- | --- |
| AT01 | CLIENT с cookie/CSRF | POST `{}` | 201 DRAFT, nullable поля, owner/actor из сессии, version=1, DRAFT_CREATED | Сейчас, T test_incomplete_draft_is_persisted / history |
| AT02 | Свой DRAFT | PATCH только company_name | 200, неполный DRAFT сохранён, GET повторяет поля | Сейчас, UI T07; T partial_update |
| AT03 | Свой DRAFT с полями | PATCH одного поля, затем другого с null | Пропущенные значения прежние, null очищает только переданное | Сейчас, T partial_update |
| AT04 | Пять валидных сохранённых полей | POST submit без тела | 200 SUBMITTED, version+1, одно событие, поля сохранены | Сейчас, T successful_submission |
| AT05 | SUBMITTED | Повтор submit | 409 Application is not a draft, нет дубликата | Сейчас, T idempotent_patch_and_repeated_submission |
| AT06 | SUBMITTED | PATCH валидного поля или `{}` | 409 без изменения данных/истории | Сейчас, T successful_submission |
| AT07 | DRAFT с 9/11 цифрами ИНН, Unicode-цифрами либо пробелом | Submit | 422; формат в DRAFT мог сохраняться; checksum не требуется | Сейчас, T failed_submission |
| AT08 | DRAFT с null/пустым названием/целью/amount/term | Submit | 422 с loc поля; записи/состояние не меняются | Сейчас; новые обязательные поля T05 |
| AT09 | Свой DRAFT | PATCH amount `1.001`, `1.230`, NaN/Infinity строкой | 422, нет округления/записи | Сейчас; аналог на трёх финансовых полях T05 |
| AT10 | Полная T05 заявка WORKING_CAPITAL | Submit с amount 49999.99/3000000.01 либо term 2/25 | 422 по продукту; 50000/3000000 и 3/24 включены | PLANNED T05/Q01/Q02 |
| AT11 | Полная T05 заявка EQUIPMENT | Submit с amount 99999.99/5000000.01 либо term 5/37 | 422; 100000/5000000 и 6/36 включены | PLANNED T05 |
| AT12 | Финансовые поля поддержаны | Submit с R=0, E<0, D<0 либо null | 422 без мутации; E/D=0 допустимы | PLANNED T05, сохранение негативного DRAFT — Q03 |
| AT13 | Полная заявка, R>0, E>R, D=0 | Submit | Отрицательный остаток не блокирует отправку; решение позже | PLANNED T05, A/D |
| AT14 | CLIENT B с cookie/CSRF, чужая заявка A, в том числе той же компании | GET/PATCH/submit/events | 404 без раскрытия/изменения | Сейчас, T other_owner / same_company |
| AT15 | Нет/истекла/отозвана cookie | Валидный запрос заявки или /me | 401 | Сейчас, T no_credentials / login_logout_expiry |
| AT16 | Cookie действительна, CSRF отсутствует/неверен | PATCH/submit/logout | 403; нет бизнес-мутации; GET/me без CSRF допустимы | Сейчас, T csrf_and_origin; UI T06 |
| AT17 | Cookie/CSRF верны, Origin запрещён или Sec-Fetch-Site=cross-site | Мутация, включая login без старого CSRF | 403 Origin is not allowed | Сейчас по S; тест Origin есть, cross-site — критерий для отдельной проверки |
| AT18 | BANK_EMPLOYEE с cookie/CSRF | Клиентские POST/PATCH/submit либо GET/events | Мутации 403, чтение существующей заявки 200 | Сейчас, T other_owner_and_bank_permissions |
| AT19 | Свой DRAFT, поля уже сохранены | PATCH `{}` или те же значения | 200, прежние version/timestamps, нет DRAFT_UPDATED | Сейчас, T idempotent_patch |
| AT20 | Выполнены создание/реальный PATCH/submit | GET events | Ровно три события, правильные actor/old/new/версии/статусы; повтор чтения не добавляет запись | Сейчас, T history_includes_actor |
| AT21 | История с несколькими событиями | GET events after_id первого и limit=1 | Только следующий id; limit=0/101, after_id<0 — 422 | Пагинация сейчас; недопустимые query — критерии из C |
| AT22 | Свой DRAFT, event write контролируемо падает | POST/PATCH/submit | Бизнес-операция целиком откатывается | Сейчас, T event_failure_rolls_back; не на основной БД |
| AT23 | Два параллельных валидных submit одного DRAFT | Отправка одновременно | Один 200 и один 409, одно SUBMITTED | Сейчас, T concurrent_identical_patches_and_submissions |
| AT24 | POST/PATCH со status/owner_id/version либо будущим product_version до T05 | Передача неизвестного поля | 422 extra_forbidden, нет мутации | Сейчас, T invalid_commands / server_fields |
| AT25 | term — дробь/bool/непустая строка или вне BIGINT | POST/PATCH | 422; пустая строка — null | Сейчас, C/T field_constraints |
| AT26 | Сохранённый DRAFT, cookie/CSRF в той же вкладке | Reload и /me, затем GET и PATCH | Сохранённые данные восстановлены, PATCH с токеном успешен | API чтения сейчас, полный UI T06/T07; A01 AC17 |
| AT27 | Живая cookie, sessionStorage пуст | Bootstrap | /me 200 без CSRF, чтения доступны; UI требует вход для мутации, сама мутация без CSRF — 403 | API сейчас, UI T06/T07; A01 AC18/Q09 |
| AT28 | Продукты/финансы ещё не реализованы | Прочитать каталог/список либо передать новые поля | Не считать рабочим API; новые поля 422, будущие маршруты не дают целевой 200 | Сейчас, статический маршрутный состав C/M |
| AT29 | T05 выбран неизвестный продукт/версия | Submit | Отправка отклонена без перехода; код/схема ошибки требуют Q01/Q02/Q03 | PLANNED T05 |
| AT30 | T07 список реализован; два CLIENT одной компании | CLIENT B читает список | Нет заявок A; server-side owner_id, не фильтрация только UI | PLANNED T07/Q05 |

AT28 не закрепляет конкретный 404/405 для отсутствующих маршрутов: например,
путь, совпавший с динамическим id, может дать 422. PLANNED отсутствие нельзя
определять как готовое бизнес-поведение. При потере ответа POST создания
проверять отсутствие автоматического повтора в UI после T06/T07 (A01 AC24).
Проверки миграций используют новые и старые изолированные PostgreSQL-БД по T/B.

## 10. Вопросы на согласование и сверка с A01

### 10.1. Сверка: подтверждения и уточнения

Прямых противоречий A01 действующим бизнес-правилам/числам не обнаружено.
Планируемые поля A01 не являются текущей Pydantic-схемой; это намеренное
разделение. Ниже зафиксированы детали, которые нельзя молча достроить при интеграции.

| Область | A01 / исходники | Уточнение A02 |
| --- | --- | --- |
| Версия продукта | A01 product_version — предложение Q01; D пишет product_code/version | В коде обоих ключей нет; version уже версия заявки. Примеры T05 имеют PLANNED и не означают согласования |
| Path parameter | A01 `{id}` | C использует `{application_id}`; URL одинаков, loc OpenAPI/422 использует имя application_id |
| Русские ошибки | A01 предлагает UI-тексты | Реальные detail строки английские; submit и FastAPI имеют разные наборы полей ошибок |
| Timestamp отправки | A01 экран показывает время отправки | В Application нет submitted_at; использовать occurred_at события SUBMITTED, а не придумывать поле; updated_at позднее может изменяться |
| Продукты/список | A01 оставляет схемы Q05 открытыми | 3.11/3.12 предлагают конкретные формы на согласование, текущие методы не объявляются реализованными |
| Отчёт о тестах | A01 AC — критерии, не результаты прогона | A02 T/AT тоже разделены; новые pytest/API-вызовы в документационной задаче не выполнялись |
| CSRF/конкурентность | A01 reload — предложение T06; expected_version нет | Подтверждено кодом; бизнес-команды банковского этапа только предлагают новый expected_version |
| OpenAPI | FastAPI автоматически формирует схему | В M нет кастомного OpenAPI/exception handlers; login/me без response_model, cookie проверяется вручную, не отдельной Security-схемой; зависимые 401/403/404/409 не все объявлены в responses |

Для независимой реализации текущего API достаточно IMPLEMENTED разделов.
Для T05/T07 разработчики должны сначала закрыть Q01/Q02/Q03/Q05/Q06;
PLANNED-образцы — подготовленные варианты решения, не причина угадывать контракт.
Перед банковским UI нужны BQ01–BQ04. Текущий runtime-контракт и недостаточная
детализация OpenAPI не устраняются изменением кода в A02.

### 10.2. Вопросы A01, сохранённые под исходными номерами

| Вопрос / неопределённость | Требуемое API-решение | Возможные варианты | Рекомендация, не согласована | Влияние frontend / backend | Кто согласует |
| --- | --- | --- | --- | --- | --- |
| Q01: имя и тип версии продукта | Ссылка на CreditProduct в запросах/ответах | Отдельные product_code/product_version; вложенный product; числовая или opaque string версия | Отдельный product_version как opaque string, version оставить заявке; ссылку клиент берёт из каталога, сервер проверяет | FE единые типы; BE новые поля/FK/схемы/история | Пользователь как аналитик, backend T05, frontend |
| Q02: каталог изменился до submit | Какие версии допустимы, как показать изменение и отказать несовпадению | Фиксировать выбранную ещё допустимую версию; требовать актуальную и подтверждение; автоматическая подмена | Клиент передаёт прочитанную ссылку; сервер не меняет молча. При недоступности условий — предложенный 409 с явным обновлением/подтверждением; точный detail/code утвердить | FE повтор каталога/подтверждение; BE неизменные версии и атомарная проверка | Аналитик, backend T05, frontend |
| Q03: новые поля DRAFT | Знак/точность/пустота и согласованность code/version при записи | Проверять всё при записи; проверять структуру при записи, полноту/знак при submit | Второй вариант как A01: конечность/≤2 знаков всегда, null для пустоты, знак при submit; для ссылки пара null/null либо известные code/version, смену передавать согласованной парой | FE сериализация/ошибки; BE nullable-миграция, валидация пары/allowlist и история | Аналитик, backend T05, frontend |
| Q04: локаль денежного ввода | Формат строки и допустимое преобразование UI | Точка; явная поддержка запятой; форматированные разделители тысяч | В первом MVP точка с подсказкой, без незаметного исправления; API не сужать без отдельного решения | FE точный ввод; BE сохраняет Decimal-контракт | Аналитик и frontend, backend сверяет |
| Q05: каталог и список | Доступ/методы/ответ/сортировка/пагинация | Каталог массив или envelope; список массив/offset/cursor; общий или отдельный банковский маршрут | Схемы 3.11/3.12: GET, Product[], ApplicationPage с id ASC cursor, limit 1–100/default100; владелец только серверный фильтр; ставка долей единицы | FE страницы/типы; BE фильтрация и pagination; это новые предложения численных параметров | Аналитик, backend T05/T07/T08, frontend |
| Q06: ошибки и последовательность формы | Русские сообщения/порядок PATCH→submit/неизвестный исход | Переводить известные type/loc на FE; новый серверный error_code; показывать msg напрямую | Сейчас mapping на FE с общим fallback, без смены действующих detail; PATCH дождаться, затем submit, повторные клики блокировать, не retry POST | FE единый fetch и состояния; BE текущая транзакционная семантика сохраняется | Пользователь как аналитик, frontend T06/T07, backend |
| Q07: старые SUBMITTED без финансов | Как дополучить сведения перед T08 без переписи истории | Не обрабатывать до контролируемого получения; отдельная новая процедура; неявное заполнение | Сохранить записи, не допускать к новой обработке до отдельной процедуры; не подставлять фиктивные значения | FE объяснение сотруднику; BE серверный запрет неполного run | Аналитик и backend до T08 |
| Q08: оригинал PDF/лента | Подтвердить трактовку требований перед сдачей | Сверка оригинала/уточнение организаторов | Сверить PDF; API ленты T15 отдельно, не менять анкету из-за отсутствия уточнения | Нет изменения текущего API | Аналитик/владелец продукта и организаторы |
| Q09: CSRF новой вкладки | Оставить повторный login или новый bootstrap | SessionStorage+повторный вход; отдельный endpoint; читаемая cookie | Для MVP предложение A/A01 без нового endpoint; альтернативу согласовать отдельно | FE ограничение вкладки; BE менять авторизацию только отдельной задачей | Аналитик, frontend T06 и backend |

Q03 не запрещает отрицательный денежный остаток после submit: E может быть >R
при E≥0. Выбор ограничений DRAFT нельзя превращать в новое банковское правило.
Q02 предложенный 409 для условий не является текущим 409 приложения.

### 10.3. Дополнительные технические вопросы A02

| Вопрос / неопределённость | Требуемое API-решение | Возможные варианты | Рекомендация, не согласована | Влияние frontend / backend | Кто согласует |
| --- | --- | --- | --- | --- | --- |
| BQ01: конфликт версии банковских команд | Где передавать ожидаемую версию и как отвечать | expected_version в body; If-Match/ETag | Body expected_version integer≥1, row lock и 409 при несовпадении; не вводить задним числом в PATCH | FE перезагрузка конфликта; BE атомарная проверка | Аналитик, backend T08, frontend банка |
| BQ02: checks/result и HTTP сбоя | Полная форма run/checks/score/factors, COMPLETE/INCOMPLETE/FAILED и безопасные коды | 200 с доменным результатом; отдельный HTTP-код для FAILED; polling/async | Сохранить синхронную схему A; 200 для сохранённого результата, в том числе FAILED; 5xx при несохранённом сбое. Полный DTO/error_code утвердить до T08–T10 | FE не принимает INCOMPLETE за score=0; BE сохраняет попытки и снимки, не теряет run | Аналитик, backend T08–T10, frontend |
| BQ03: уточнения/Decision DTO | Полные тела, обязательность пояснения, справочники причин/лимиты | Плоские или вложенные поля; explanation обязательное/необязательное; разные DTO OFFER/REJECT | Предложения 3.13; allowlist запрошенных финансов, отдельный ответ конкретному запросу; раздельная валидация OFFER/REJECT по A | FE отдельные формы; BE снимки/состояния/политика/история | Аналитик, backend T11/T12, frontend |
| BQ04: offer/sign/disburse | Полная схема документа, версия условий, command_key и ответы повтора | Отдельные DTO/идемпотентный ключ в body или header | Следовать D/F: неизменные условия, один договор/выдача; определить DTO и key отдельно перед T14, без новых банковских действий | FE явное подтверждение симуляции; BE уникальность/повторы/аудит | Аналитик, backend T14, frontend |
| BQ05: точность 64-битных id в JS | Сохранить JSON integer или мигрировать на строки | Ограничить домен; точный parser; версионируемая смена API на string | Не менять действующие типы в A02; для FE согласовать точный parser/работу со строковым представлением после чтения без потери точности; простая String(Number) потерю не исправляет | FE защита от потери id; BE/контракт при смене типов отдельно | Backend и frontend, аналитик при смене API |
| BQ06: полнота OpenAPI | Как отразить cookie/ошибки/login/me схемы | Только prose; дополнить response_model/responses/Security отдельной задачей | Сохранить A02 как точное описание сейчас; отдельно дополнить OpenAPI и сверить экспорт/коллекцию перед сдачей T16 | FE codegen не должен угадывать схемы; BE отдельное изменение кода | Backend и аналитик |

## 11. Definition of Done

Критерии документационной задачи A02, не реализации будущих API:

- Прочитаны B/R/D/A/F/P/AGENTS, A01 напрямую из remote-ветки и C/S/E/DB/M/T;
  зафиксированы базовые commit hashes и ограничение отсутствующего PDF.
- Каталог охватывает все девять действующих бизнес/health-маршрутов; методы,
  пути, роли, входы, ответы и фактические HTTP-коды сверены с исходниками.
- Для каждого IMPLEMENTED endpoint есть типы/обязательность/доступ/ошибки,
  примеры JSON там, где JSON предусмотрен; отсутствие тела/204 описано явно.
- Показаны оба продукта с точными границами/ставками A; Decimal/NUMERIC,
  nullable DRAFT, строгий term и ИНН без checksum не искажены.
- IMPLEMENTED отделён от PLANNED; новые имена, JSON и методы предложений
  помечены, полного утверждённого банковского DTO не выдумано.
- Описаны история/атомарность/no-op/row lock и отсутствие expected_version;
  409 состояния не выдан за уже реализованный конфликт версии.
- Описаны cookie/CSRF/владение/роли, 401/403/404/409/422, reload, потеря токена,
  сетевые ошибки и отсутствие автоматического retry создания.
- Есть матрица FE↔BE, Given/When/Then с текущей/будущей применимостью,
  сверка с A01 и вопросы с вариантами/рекомендациями/влиянием/согласующими.
- JSON-примеры синтаксически валидны; текущие полные Application/события
  соответствуют полям C/E, Markdown/ссылки/пробелы проверены. Это не заменяет
  runtime PostgreSQL/API-тесты, которые в A02 не выполнялись.
- До реализации PLANNED стороны явно согласуют Q01/Q02/Q03/Q05/Q06;
  до банковских DTO — соответствующие BQ. Публикация документа не закрывает вопросы.
- В commit только `docs/api-contract.md`; `anket_structure.md` нетронут,
  backend/frontend/миграции/тесты/зависимости/остальные документы не менялись.
- Документ сохранён в `docs/a02-api-contract` от актуального origin/main,
  commit называется `docs: add A02 credit application API contract`, push
  подтверждён; main не изменяется, merge не выполняется. PR создаётся только
  по отдельному явному поручению пользователя.

Если push недоступен, локальный результат и невыполненный GitHub-пункт
отражаются в отчёте без заявления об успешной публикации. Экспорт OpenAPI,
запуск backend и миграции для создания A02 не требуются и не выполняются.
