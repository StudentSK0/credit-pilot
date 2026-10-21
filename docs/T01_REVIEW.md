# Техническое ревью T01 Credit Pilot

## Закрытие T01 и синхронизация документации

21 октября 2026 года пользователь сообщил о предварительной приёмке внешним
техническим ревью и закрыл T01. Последующая работа ограничена документацией:
бизнес-логика, миграции, тесты и frontend сохранены без изменений.

Ветка `korobov/project_setup`, HEAD `b41e567a675ee9917f23480a2905f6ac5d4b9b8d`.
При начале синхронизации index пуст; unstaged — 6 изменённых файлов T01,
7 новых backend-файлов и этот отчёт в docs. Полнота реализации сверена по
исходникам, миграциям, тестам и контрольным суммам; новые файлы не потеряны.

AGENTS.md и пять проектных документов безопасно включены в рабочую копию из
`korobov/docs` (`a8b3544eccd3d9715db5dbfb236eff7b6b8d8c94`), затем обновлены.
Переносились только эти Markdown-файлы, существующий отчёт не перезаписывался,
код из другой ветки не сливался; ветка и Git index сохранены. Теперь источники
текущего состояния доступны локально, а не только в прежнем ZIP.

Актуализированы CLIENT/BANK_EMPLOYEE, права только по owner_id, sessions/CSRF,
application_events и частично выполненные T03/T04. Текущий frontend — health,
полноценного входа и форм нет. T02 отложена. Далее T05 и параллельно T06;
это готовность к началу отдельных задач, не факт их реализации.

CSRF выдаётся только login и хранится в БД хешем; /api/me его не возвращает.
Предложение для T06 — sessionStorage для reload той же вкладки, с явным повторным
входом при отсутствии токена. Новая авторизация/endpoint не реализовывались.
До банковских статусов нужны расширение VARCHAR(9) и CHECK applications.status,
полей статусов и типов событий application_events, а также Enum/API-схем.

Повторная проверка при закрытии: **54 passed, 8 warnings, 9.53 s**, frontend
`npm run build` — успешно. Live-БД: head 0003_application_owner, все три поля
статусов имеют длину 9; CHECK подтверждены запросом к pg_constraint.
Предупреждения прежние: Starlette/httpx и Alembic path_separator.
HTTP-сверка CSRF подтвердила: login выдаёт токен, действующая cookie читает /api/me
без CSRF в ответе, изменение без токена возвращает 403, logout с исходным CSRF — 204.

Ниже сохранён исходный отчёт подготовки внешнего ревью, включая результаты
предыдущего прогона и состав прежнего архива. Упоминания отсутствовавших документов
и копий из другой ветки в нём описывают тот момент, не текущее состояние.
ZIP предыдущего этапа не пересобирался: это исторический снимок до синхронизации.

## Исходный отчёт внешнего ревью

Дата проверки: 21 октября 2026 года. Объём: журнал создания, редактирования
и отправки заявки с минимальными локальными сессиями и владением по пользователю.
Код приложения при подготовке этого ревью не изменялся; T02 не выполнялась.

## Что было реализовано

- Заявки сохраняются в PostgreSQL; доступны создание неполного DRAFT, чтение,
  частичное обновление черновика и переход DRAFT → SUBMITTED.
- События DRAFT_CREATED, DRAFT_UPDATED и SUBMITTED записываются в той же транзакции,
  что и изменение заявки. При сбое записи события откатывается вся операция.
- Событие содержит идентификатор заявки, тип операции, серверное время,
  actor_id/actor_role, предыдущий и новый статус, версию заявки и изменения
  разрешённых бизнес-полей. Decimal в JSON изменений сериализуется строкой.
- Добавлены локальные тестовые аккаунты, серверные сессии в БД, CSRF и роли
  CLIENT / BANK_EMPLOYEE. Владелец новой заявки — текущий пользователь из сессии.
- Есть защищённое чтение истории с пагинацией. Другой CLIENT не имеет доступа,
  даже если работает в той же компании. BANK_EMPLOYEE имеет только чтение.
- Пустой PATCH и PATCH с уже сохранёнными значениями не меняют данные, timestamps,
  version и историю. Повтор submit возвращает 409 без нового события.
  Параллельные PATCH/submit сериализуются блокировкой строки заявки.
- Исходные поля и проверки сохранены: название ≤255, цель ≤1000, ИНН при отправке
  из 10/12 ASCII-цифр без checksum, точная сумма с максимум двумя десятичными
  знаками без округления ввода, положительные сумма и целый срок при отправке.
- Health продолжает выполнять SELECT 1 и возвращать 200/503.

### Сверка с архитектурой и AGENTS.md

Текущая ветка — `korobov/project_setup`, базовый HEAD:
`b41e567a675ee9917f23480a2905f6ac5d4b9b8d`. Изменения T01 не закоммичены;
этот hash обозначает базу, а не готовую версию T01. Снимок для ревью включает
как tracked-изменения, так и новые untracked-файлы. Git index не изменялся.

В текущей ветке отсутствуют AGENTS.md и пять проектных документов. Для сверки
прочитаны их исходные версии из локальной ветки `korobov/docs`, commit
`a8b3544eccd3d9715db5dbfb236eff7b6b8d8c94`. В ZIP они включены без изменения
содержимого как контекст архитектуры. В рабочую ветку они не переносились.
Эти документы описывают целевой MVP, а не готовность всех его функций.

| Правило или проектное решение | Результат сверки |
| --- | --- |
| Развивать существующее приложение небольшим инкрементом | Сохранены FastAPI, psycopg, Alembic и три сервиса Compose. ORM-перенос T02 отсутствует |
| Не менять применённые миграции | Исходная 0001 сохранена; журнал добавлен 0002, уточнение владельца и роли — отдельной 0003 |
| Серверные статусы, инициаторы и транзакционный журнал | Проверены по коду и тестам отката/подделки полей |
| Не терять данные и не выдумывать историю | Миграции сохраняют прежние записи; нет автоматического назначения неизвестного владельца |
| Только синтетические данные, без платных API и LLM | Тестовые аккаунты и seed локальны, внешних интеграций T01 не добавляет |
| Контроль доступа на сервере | Проверяется сессия, роль и owner_id для чтения, PATCH, submit и истории |
| Роль BANK и доступ по компании в первоначальном проекте | Уточнено явным последующим запросом пользователя: BANK_EMPLOYEE и доступ только владельцу owner_id. Это намеренное изменение требований |
| В первоначальном плане T01 разрешён ANONYMOUS до T04 | Пользователь отдельно согласовал минимальные аккаунты, сессии и владение в T01; полноценные T03/T04 не реализованы |
| Полный аудит входов/просмотров и оптимистическая проверка версии | Ещё не реализованы; version увеличивается и используется для уникальности событий. Границы раскрыты ниже |

## Какие файлы изменены

Список изменений T01 относительно указанного базового HEAD. Новые файлы,
которые пока не добавлены в Git index, также обязательны для ревью и входят в ZIP.

| Файл | Изменение |
| --- | --- |
| `backend/applications.py` | Доступ по owner_id/роли, создание событий, версии, история, отсутствие лишних событий для no-op PATCH |
| `backend/main.py` | Подключение API сессий |
| `backend/auth.py` | Новый модуль пользователей текущей сессии, ролей, локального входа/выхода, CSRF, хеширования |
| `backend/audit.py` | Модель ответа события и запись разрешённых бизнес-изменений |
| `backend/seed.py` | Явный идемпотентный seed синтетических аккаунтов |
| `backend/migrations/versions/0002_application_events.py` | Пользователи, компании, сессии, журнал и поля автора/версии |
| `backend/migrations/versions/0003_application_owner.py` | owner_id, индекс, перенос известного автора и BANK → BANK_EMPLOYEE |
| `backend/tests/conftest.py` | Seed и аутентифицированный клиент в изолированной тестовой БД |
| `backend/tests/test_events.py` | Журнал, атомарность, конкуренция, права, CSRF, сессии, секреты |
| `backend/tests/test_migrations.py` | Переходы со старых схем без потери данных, событий и сессий |
| `compose.yaml` | Передача настроек cookie, Origins и синтетических seed-паролей; набор сервисов сохранён |
| `.env.example` | Документированные локальные настройки доступа |
| `README.md` | Запуск, seed, вход, запросы, права, миграции и ограничения |
| `docs/T01_REVIEW.md` | Этот отчёт; единственный новый исходный документ данной подготовки ревью |

Frontend, зависимости, Dockerfile и исходная миграция 0001 в T01 не менялись.
Файлы проектирования из `korobov/docs` в архиве — контекст, не изменения T01.

## Какие таблицы и API добавлены

### PostgreSQL

Цепочка Alembic: `0001_applications → 0002_application_events → 0003_application_owner`.
На проверенном стенде current и единственный head — `0003_application_owner`.

| Таблица | Назначение |
| --- | --- |
| `users` | Уникальный login, password_hash, роль CLIENT/BANK_EMPLOYEE, совместимая ссылка company_id |
| `sessions` | Хеши случайного токена и CSRF, user_id, expires_at; при logout запись удаляется |
| `application_events` | События с FK на заявку и инициатора; UNIQUE(application_id, application_version), индекс (application_id, id) |
| `companies` | Минимальные синтетические записи для ранее введённых связей; API управления компаниями отсутствует |

Существующая `applications` расширена company_id, created_by, version, owner_id
и индексами. owner_id — FK на users; он nullable для неизвестных legacy-владельцев,
но при создании через API всегда заполняется сервером. company_id/created_by
сохранены для совместимости и не предоставляют права на чужую заявку.

0003 переносит owner_id только из ранее записанного created_by пользователя CLIENT.
Неизвестные авторы не угадываются, события не дописываются задним числом.
Переименование роли сохраняет идентификаторы пользователей и действующие сессии.

### API

| Метод и путь | Доступ и результат |
| --- | --- |
| POST `/api/auth/login` | Новый. Login/password → cookie сессии и CSRF-токен; без OAuth/JWT |
| POST `/api/auth/logout` | Новый. Действующая сессия и CSRF → отзыв сессии, HTTP 204 |
| GET `/api/me` | Новый. Идентификатор, роль и совместимый company_id текущего пользователя |
| GET `/api/applications/{id}/events` | Новый. Владелец или BANK_EMPLOYEE; события по возрастанию id, limit 1–100 и after_id |
| POST `/api/applications` | Существующий. Теперь только CLIENT с сессией/CSRF; создаёт DRAFT и событие, HTTP 201 |
| GET `/api/applications/{id}` | Существующий. Только владелец или BANK_EMPLOYEE |
| PATCH `/api/applications/{id}` | Существующий. CLIENT-владелец, сессия/CSRF, только DRAFT |
| POST `/api/applications/{id}/submit` | Существующий. CLIENT-владелец, сессия/CSRF, валидация и смена статуса |
| GET `/api/health` | Существующий публичный endpoint; контракт 200/503 сохранён |

Ошибки: 401 — нет действующей сессии; 403 — неподходящая роль, CSRF или Origin;
404 — недоступная/несуществующая заявка; 409 — несовместимое состояние;
422 — неверные поля. Назначать owner_id, actor_id, роль, статус или timestamps
через поля заявки нельзя. Списка заявок и банковских решений в T01 нет.

## Как работает авторизация и определение владельца заявки

1. Явный `python seed.py` создаёт client-a, client-b и bank. Повтор не меняет
   существующие пароли, не удаляет данные и не присваивает старые заявки.
2. Пароль проверяется по PBKDF2-HMAC-SHA256 с солью и 600 000 итерациями.
   При входе сервер генерирует случайные session/CSRF-токены; в БД — SHA-256 хеши.
3. Сессия действует 8 часов. Cookie `credit_pilot_session` имеет HttpOnly,
   SameSite=Lax и Path=/api. Secure включается через COOKIE_SECURE для HTTPS.
4. На каждый запрос сервер по хешу cookie получает users.id и users.role из БД
   и проверяет срок сессии. Cookie не содержит доверенных frontend-claims.
5. Для изменения дополнительно нужен X-CSRF-Token; проверяются Origin, если он
   присутствует, и Sec-Fetch-Site. Допустимые адреса настраиваются ALLOWED_ORIGINS.
6. Новая заявка получает owner_id=users.id. Для CLIENT запрос к заявке содержит
   фильтр `owner_id = current_user.id`; этот же фильтр используется перед историей.
   При PATCH/submit добавляется FOR UPDATE. BANK_EMPLOYEE может только читать.
7. Инициатор события берётся из этой же серверной сессии, а не из тела/заголовков
   frontend. Payload строится из разрешённых полей, request/session не сериализуются.

## Какие тесты выполнены и с какими результатами

Проверки повторно выполнены при подготовке этого отчёта 21 октября 2026 года.

| Проверка | Результат |
| --- | --- |
| `docker compose run --rm --build backend sh -c 'pip install -r requirements-dev.txt && pytest -q'` | **54 passed, 8 warnings**, 9.29 s; 36 исходных и 18 дополнительных случаев |
| Миграция с 0001 на head, повтор upgrade head и downgrade до 0001 | PASS в отдельной одноразовой БД; данные и timestamps сохранены, владельцы/история не придуманы |
| Миграция с 0002 на head | PASS; owner_id перенесён из автора, неизвестный owner остаётся NULL, BANK переименован, события/сессии неизменны |
| Чужой владелец, в том числе клиент той же компании | PASS: GET/PATCH/submit/events возвращают 404, исходные данные и история не меняются |
| BANK_EMPLOYEE и неподлинные frontend-claims | PASS: сотруднику доступны чтения, мутации дают 403; без сессии поддельные заголовки не обходят 401 |
| Ошибки валидации и сбой записи журнала | PASS: нет частично сохранённой операции или ложного события |
| Последовательные и параллельные повторы | PASS: одинаковые PATCH не дублируются; один submit успешен, второй получает 409 |
| CSRF/Origin, истечение и отзыв сессий, отсутствие секретов в событиях | PASS |
| `npm ci --cache /tmp/credit-pilot-review-npm && npm run build` | PASS: TypeScript и Vite; npm audit сообщил 0 известных уязвимостей на момент проверки |
| `alembic current`, `heads`, `history` | PASS: единая линейная цепочка, current=head=0003_application_owner |
| `python -m pip check`, `git diff --check` | PASS |
| HTTP через frontend proxy и реальный restart backend | PASS: создание, PATCH, отправка, проверки ролей, 3 события и действующие сессии сохранены после рестарта |
| Публичный health и Swagger | HTTP 200; сценарий недоступной БД/503 также входит в backend-тесты |

Восемь предупреждений — одно о deprecation httpx в Starlette TestClient и
повторяющиеся предупреждения Alembic о незаданном path_separator. Они не являются
восемью упавшими проверками. Отдельных frontend-тестов в package.json нет:
проверена сборка, полноценное браузерное E2E в этой подготовке не выполнялось.
HTTP-smoke создаёт одну синтетическую проверочную заявку в локальном стенде;
автотесты используют отдельные БД, которые удаляются после прогона.

## Какие проблемы и ограничения остались

- Документы проектирования хранятся в другой ветке и содержат первоначальные
  BANK/права компании и устаревший раздел текущего состояния. Для T01 актуальны
  уточнения пользователя и этот отчёт; требуется последующее согласованное
  обновление/объединение документации. Архив раскрывает происхождение копий.
- PostgreSQL NUMERIC/Decimal сохраняет точность; однако базовые Docker-теги
  изменяемые и транзитивные Python-зависимости зафиксированы не полностью.
  Сборка требует интернет для публичных пакетов/образов, runtime T01 внешних API не требует.
- POST создания не идемпотентен: автоматический retry после потери ответа может
  создать вторую заявку. Для повторов PATCH/submit заявленные гарантии проверены.
- Row lock сериализует команды, но клиентской проверки ожидаемой version нет:
  два разных последовательных изменения одного поля работают по last-write-wins.
- Журнал append-only только через API приложения. Нет DB-триггера запрета UPDATE/DELETE,
  криптографической защиты или отдельного ограниченного runtime-пользователя БД.
- Нет аудита входов/просмотров/отказов доступа, UI входа, управления пользователями,
  rate limiting для login, фоновой очистки истёкших сессий, восстановления паролей.
- Неизвестные legacy-владельцы остаются NULL; нет endpoint их назначения.
  Существующие companies/company_id/created_by оставлены как совместимые данные,
  полноценная модель обслуживания организаций не реализована.
- В событие не копируются пароли и токены из auth/request. Если пользователь
  сам введёт секрет в название или цель, он сохранится как бизнес-данные old/new;
  автоматического распознавания секретов в свободном тексте нет.
- Демо-пароли из .env.example и seed публичные синтетические значения, пригодные
  только для локальной проверки. Настоящие .env, cookie, сессии и дампы БД в ZIP не входят.
- Swagger не описывает X-CSRF-Token отдельным security scheme; для полного ручного
  сценария удобнее curl ниже. Нет коллекции запросов и полного комплекта финальной сдачи хакатона.
- T01 не является полным кредитным MVP или промышленным security-аудитом.
  Продукты, скоринг, решения сотрудника, уточнения, оформление и выдача не добавлялись.

## Как вручную проверить T01

### Подготовка из ZIP

Распаковать архив и перейти в `credit-pilot/`. Требуются Docker/Compose и
доступ к публичным реестрам при первой сборке. Для примеров ниже также нужен
Python 3 на машине проверяющего. Никаких реальных API-ключей не требуется.

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend python seed.py
docker compose exec backend alembic current
curl --fail http://localhost:8000/api/health
```

Дождаться health 200. Frontend: http://localhost:5173; Swagger:
http://localhost:8000/docs. При изменении портов обновить ALLOWED_ORIGINS.
В существующем рабочем каталоге использовать уже подготовленный .env.

### Вход, создание и ошибка отправки

```bash
CREDIT_REVIEW_DIR=$(mktemp -d)
CREDIT_API=http://localhost:8000
CREDIT_CSRF=$(curl --fail --silent --show-error -c "$CREDIT_REVIEW_DIR/a.cookies" \
  -H 'Content-Type: application/json' \
  -d '{"login":"client-a","password":"demo-client-a-local"}' \
  "$CREDIT_API/api/auth/login" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])')

curl --fail --silent --show-error -b "$CREDIT_REVIEW_DIR/a.cookies" \
  -H "X-CSRF-Token: $CREDIT_CSRF" -H 'Content-Type: application/json' \
  -d '{"company_name":"Синтетическая компания для ревью"}' \
  "$CREDIT_API/api/applications" > "$CREDIT_REVIEW_DIR/draft.json"
CREDIT_APPLICATION_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$CREDIT_REVIEW_DIR/draft.json")
CREDIT_APPLICATION_URL="$CREDIT_API/api/applications/$CREDIT_APPLICATION_ID"

curl -sS -o /dev/null -w 'Expected 422: %{http_code}\n' \
  -b "$CREDIT_REVIEW_DIR/a.cookies" -H "X-CSRF-Token: $CREDIT_CSRF" \
  -X POST "$CREDIT_APPLICATION_URL/submit"
```

Должен остаться DRAFT, в истории — только DRAFT_CREATED.

### Изменение, повтор и отправка

```bash
CREDIT_PATCH='{"inn":"1234567890","credit_purpose":"Закупка оборудования","amount":"125000.25","term":12}'
curl --fail -b "$CREDIT_REVIEW_DIR/a.cookies" -H "X-CSRF-Token: $CREDIT_CSRF" \
  -H 'Content-Type: application/json' -X PATCH -d "$CREDIT_PATCH" "$CREDIT_APPLICATION_URL"
# Тот же PATCH повторно: нового события и новой версии не должно быть.
curl --fail -b "$CREDIT_REVIEW_DIR/a.cookies" -H "X-CSRF-Token: $CREDIT_CSRF" \
  -H 'Content-Type: application/json' -X PATCH -d "$CREDIT_PATCH" "$CREDIT_APPLICATION_URL"
curl --fail -b "$CREDIT_REVIEW_DIR/a.cookies" -H "X-CSRF-Token: $CREDIT_CSRF" \
  -X POST "$CREDIT_APPLICATION_URL/submit"
curl -sS -o /dev/null -w 'Expected 409: %{http_code}\n' \
  -b "$CREDIT_REVIEW_DIR/a.cookies" -H "X-CSRF-Token: $CREDIT_CSRF" \
  -X POST "$CREDIT_APPLICATION_URL/submit"
curl --fail --silent -b "$CREDIT_REVIEW_DIR/a.cookies" "$CREDIT_APPLICATION_URL/events" | python3 -m json.tool
```

Ожидаются ровно три события в порядке DRAFT_CREATED, DRAFT_UPDATED, SUBMITTED,
версии 1/2/3, actor_id текущего пользователя; переход отправки DRAFT → SUBMITTED.

### Чужой пользователь и сотрудник

```bash
CREDIT_OTHER_CSRF=$(curl --fail --silent --show-error -c "$CREDIT_REVIEW_DIR/b.cookies" \
  -H 'Content-Type: application/json' -d '{"login":"client-b","password":"demo-client-b-local"}' \
  "$CREDIT_API/api/auth/login" | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])')
curl -sS -o /dev/null -w 'Expected 404: %{http_code}\n' -b "$CREDIT_REVIEW_DIR/b.cookies" "$CREDIT_APPLICATION_URL"
curl -sS -o /dev/null -w 'Expected 404: %{http_code}\n' -b "$CREDIT_REVIEW_DIR/b.cookies" "$CREDIT_APPLICATION_URL/events"
curl -sS -o /dev/null -w 'Expected 404: %{http_code}\n' -b "$CREDIT_REVIEW_DIR/b.cookies" \
  -H "X-CSRF-Token: $CREDIT_OTHER_CSRF" -X POST "$CREDIT_APPLICATION_URL/submit"

CREDIT_BANK_CSRF=$(curl --fail --silent --show-error -c "$CREDIT_REVIEW_DIR/bank.cookies" \
  -H 'Content-Type: application/json' -d '{"login":"bank","password":"demo-bank-local"}' \
  "$CREDIT_API/api/auth/login" | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])')
curl --fail -b "$CREDIT_REVIEW_DIR/bank.cookies" "$CREDIT_API/api/me"
curl --fail -b "$CREDIT_REVIEW_DIR/bank.cookies" "$CREDIT_APPLICATION_URL/events"
curl -sS -o /dev/null -w 'Expected 403: %{http_code}\n' -b "$CREDIT_REVIEW_DIR/bank.cookies" \
  -H "X-CSRF-Token: $CREDIT_BANK_CSRF" -X POST "$CREDIT_APPLICATION_URL/submit"
curl -sS -o /dev/null -w 'Expected 401: %{http_code}\n' "$CREDIT_APPLICATION_URL/events"
```

У bank роль BANK_EMPLOYEE, история читается. Другому владельцу и анониму
данные не раскрываются. Изоляция клиентов одной компании проверена автотестом.

### Рестарт, тесты и завершение

```bash
docker compose restart backend
# После готовности health прежняя cookie должна читать те же три события.
curl --fail --silent -b "$CREDIT_REVIEW_DIR/a.cookies" "$CREDIT_APPLICATION_URL/events" | python3 -m json.tool
docker compose run --rm --build backend sh -c 'pip install -r requirements-dev.txt && pytest -q'
```

Для автотестов пользователь PostgreSQL должен иметь CREATEDB; стандартный
демопользователь Compose его имеет. Тесты создают отдельные БД и удаляют только их.
Сессию можно отозвать POST /api/auth/logout с соответствующей cookie и CSRF.
После проверки удалить созданный временный каталог с cookie. `docker compose down`
останавливает стенд с сохранением volume; удаление volume для ревью не требуется.

### Состав ZIP

Архив содержит корневой каталог `credit-pilot/`, текущие исходники (включая
untracked T01), миграции 0001–0003, тесты, lock-файл frontend, Docker-конфигурацию,
.env.example, README, этот отчёт, исходный PDF и копии AGENTS/проектных документов
из указанного commit ветки korobov/docs. `REVIEW_MANIFEST.sha256` содержит хеши
всех вложенных файлов, кроме самого манифеста.

Исключены .git, настоящий .env и другие локальные env-файлы, .aws/.codex/.agents,
node_modules, .venv, Python/npm-кэши, frontend/dist, .dist, архивы, логи, cookie,
дампы и данные PostgreSQL. Публичные синтетические демо-пароли намеренно остаются
в .env.example/seed/тестах для воспроизводимости. Архив не содержит Docker-образов:
проверяющий собирает их по исходникам. Это снимок рабочей копии, не новый commit.

Контроль упаковки: 44 файла, успешная CRC-проверка ZIP, сверка SHA-256 всех файлов
после распаковки, проверка исключённых путей и символических ссылок, поиск типовых
приватных ключей/токенов и совпадений с непубличными секретами локального .env.
Проверены ссылки в документации и `docker compose config --quiet` из распакованного
каталога с .env.example. Отдельный полный запуск второго стенда из ZIP не выполнялся;
исходники backend/frontend сверены побайтово с проверенной рабочей копией.
Поиск шаблонов не заменяет экспертную проверку произвольных секретов в тексте.
