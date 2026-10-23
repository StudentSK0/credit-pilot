import {
  Plus,
  Search,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import {
  type AppList,
  type Status,
  statuses,
  useResource,
} from "../api/business";
import {
  ApplicationRows,
  Empty,
  Heading,
  ResourceState,
} from "../components/Business";

export function ApplicationsPage({ bank = false }: { bank?: boolean }) {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const result = useResource<AppList>(
    `/api/applications?limit=12&offset=${offset}&status=${status}&q=${encodeURIComponent(search)}`.replace(
      "&status=&",
      "&",
    ) as `/api/${string}`,
    true,
  );
  return (
    <>
      <Heading
        eyebrow={bank ? "КРЕДИТНЫЙ КОНВЕЙЕР" : "МОЙ БИЗНЕС"}
        title={bank ? "Очередь заявок" : "Мои заявки"}
        description={
          bank
            ? "От первичной проверки до решения. Каждой заявке — следующий шаг."
            : "Сохраняйте черновики, отвечайте на вопросы и следите за решением."
        }
      >
        {!bank && (
          <a href="#/applications/new" className="button button-primary">
            <Plus size={18} />
            Новая заявка
          </a>
        )}
      </Heading>
      <div className="queue-toolbar">
        <form
          className="search-field"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(q.trim());
            setOffset(0);
          }}
        >
          <Search size={18} />
          <input
            aria-label="Поиск заявок"
            placeholder="Компания, ИНН или номер заявки"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button type="submit">Найти</button>
        </form>
        <select
          aria-label="Фильтр по статусу"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все статусы</option>
          {Object.entries(statuses)
            .filter(([key]) => !bank || key !== "DRAFT")
            .map(([key, label]) => (
              <option value={key} key={key}>
                {label}
              </option>
            ))}
        </select>
        <button
          className="icon-button"
          aria-label="Обновить заявки"
          onClick={result.refresh}
        >
          <RefreshCw size={18} />
        </button>
      </div>
      <ResourceState {...result} onRetry={result.refresh} />
      {result.data &&
        (result.data.items.length ? (
          <ApplicationRows items={result.data.items} bank={bank} />
        ) : (
          <Empty
            title={search || status ? "Ничего не найдено" : "Заявок пока нет"}
            description={
              search || status
                ? "Попробуйте другой запрос или снимите фильтр."
                : bank
                  ? "Отправленные клиентами заявки появятся здесь."
                  : "Выберите продукт и создайте свою первую заявку."
            }
          />
        ))}
      {result.data && (
        <div className="pagination">
          <span>
            {result.data.total
              ? `${offset + 1}–${Math.min(offset + 12, result.data.total)} из ${result.data.total}`
              : "0 заявок"}
          </span>
          <div>
            <button
              className="button button-secondary button-small"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 12))}
            >
              <ChevronLeft size={16} />
              Назад
            </button>
            <button
              className="button button-secondary button-small"
              disabled={offset + 12 >= result.data.total}
              onClick={() => setOffset(offset + 12)}
            >
              Далее
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
      {bank && (
        <div className="queue-legend">
          {(
            ["SUBMITTED", "NEEDS_INFO", "UNDER_REVIEW", "SIGNED"] as Status[]
          ).map((s, i) => (
            <div key={s}>
              <span>0{i + 1}</span>
              <strong>{statuses[s]}</strong>
              <p>
                {s === "SUBMITTED"
                  ? "Выполните локальные проверки"
                  : s === "NEEDS_INFO"
                    ? "Ожидается ответ клиента"
                    : s === "SIGNED"
                      ? "Завершите симуляцию выдачи"
                      : "Изучите досье и выберите решение"}
              </p>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
