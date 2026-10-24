import {
  ArrowRight,
  Activity,
  ArrowUpRight,
  Clock3,
  ShieldCheck,
} from "lucide-react";
import {
  type Analytics,
  statuses,
  money,
  date,
  reasons,
  useResource,
} from "../api/business";
import { Heading, Metric, ResourceState, Empty } from "../components/Business";

const bottleneckText: Record<string, string> = {
  CHECKS_NOT_STARTED: "Ожидают запуска проверок",
  CHECKS_FAILED: "Сбой проверки — нужен повтор",
  CHECKS_RUNNING: "Проверки ещё выполняются",
  DATA_INCOMPLETE: "Не хватает данных для оценки",
  BANK_DECISION: "Ожидают решения сотрудника",
  CLIENT_REPLY: "Ожидают уточнений или документов",
  CLIENT_SIGNATURE: "Ожидают принятия условий клиентом",
  BANK_DISBURSEMENT: "Ожидают моделируемой выдачи",
};
export function BankDashboard() {
  const resource = useResource<Analytics>("/api/bank/analytics", true);
  const a = resource.data;
  return (
    <>
      <Heading
        eyebrow="РАБОЧЕЕ ПРОСТРАНСТВО"
        title="Каждой заявке — движение"
        description="Кредитный процесс в цифрах. Данные обновляются каждые 5 секунд."
      >
        <a className="button button-primary" href="#/review">
          Открыть очередь
          <ArrowUpRight size={18} />
        </a>
      </Heading>
      <ResourceState {...resource} onRetry={resource.refresh} />
      {a && (
        <>
          <div className="metrics-grid">
            <Metric
              label="Заявок в работе"
              value={a.active}
              detail={`Всего отправлено: ${a.total}`}
            />
            <Metric
              label="Ждут решения"
              value={
                a.counts.find((c) => c.status === "UNDER_REVIEW")?.count ?? 0
              }
              detail="Проверки завершены"
            />
            <Metric
              label="Без движения >24 ч"
              value={a.delayed}
              detail="Учебный ориентир внимания"
            />
            <Metric
              label="Выдано · симуляция"
              value={money(a.issued_amount)}
              detail="Реальных переводов нет"
              accent
            />
          </div>
          <div className="dashboard-grid">
            <section className="panel funnel-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">ВЕСЬ ПУТЬ</span>
                  <h2>Воронка финансирования</h2>
                </div>
                <Activity size={21} />
              </div>
              <p className="panel-description">
                Уникальные заявки, достигшие этапа. Повторные проверки не
                увеличивают счётчик.
              </p>
              <div className="funnel">
                {(
                  [
                    "SUBMITTED",
                    "UNDER_REVIEW",
                    "OFFERED",
                    "SIGNED",
                    "DISBURSED",
                  ] as const
                ).map((s, i) => {
                  const count =
                    a.funnel.find((c) => c.status === s)?.count ?? 0;
                  const width = a.total
                    ? Math.max(3, (count / a.total) * 100)
                    : 0;
                  return (
                    <div className="funnel-row" key={s}>
                      <span className="funnel-index">0{i + 1}</span>
                      <div>
                        <div className="funnel-label">
                          <span>
                            {s === "SUBMITTED"
                              ? "Поступили"
                              : s === "UNDER_REVIEW"
                                ? "Рассмотрены"
                                : s === "OFFERED"
                                  ? "Получили предложение"
                                  : s === "SIGNED"
                                    ? "Приняли условия"
                                    : "Выдача смоделирована"}
                          </span>
                          <strong>{count}</strong>
                        </div>
                        <div className="funnel-track">
                          <div
                            style={{
                              width: `${width}%`,
                              opacity: 1 - i * 0.12,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">ГДЕ НУЖНО ВНИМАНИЕ</span>
                  <h2>Что удерживает заявки</h2>
                </div>
                <Clock3 size={21} />
              </div>
              <div className="bottleneck-list">
                {a.bottlenecks.length ? (
                  a.bottlenecks.map((b) => (
                    <a
                      href="#/review"
                      className="bottleneck"
                      key={b.reason_code}
                    >
                      <span
                        className={`bottleneck-dot ${b.status === "NEEDS_INFO" ? "amber" : ""}`}
                      />
                      <div>
                        <strong>{bottleneckText[b.reason_code]}</strong>
                        <small>
                          Дольше всего:{" "}
                          {Number(b.oldest_hours) < 1
                            ? "менее часа"
                            : `${Math.floor(Number(b.oldest_hours))} ч`}{" "}
                          без изменений
                        </small>
                      </div>
                      <b>{b.count}</b>
                    </a>
                  ))
                ) : (
                  <p className="muted">В очереди нет незавершённых заявок.</p>
                )}
              </div>
              <a href="#/review" className="text-button">
                Перейти к обработке
                <ArrowRight size={16} />
              </a>
            </section>
          </div>
          <div className="section-heading">
            <h2>Журнал решений</h2>
            <span>Последние 20 · время МСК</span>
          </div>
          {a.decisions.length ? (
            <div className="decision-table">
              {a.decisions.map((d) => (
                <a
                  key={d.id}
                  href={`#/review/${d.application_id}`}
                  className="decision-row"
                >
                  <span
                    className={`decision-icon ${d.kind === "REJECT" ? "rejected" : ""}`}
                  >
                    <ShieldCheck size={20} />
                  </span>
                  <div>
                    <strong>{d.company_name}</strong>
                    <small>
                      № {d.application_id} · {date(d.created_at)} · {d.actor}
                    </small>
                    <p>{d.explanation}</p>
                  </div>
                  <div className="decision-result">
                    <strong>
                      {d.kind === "OFFER" ? money(d.terms?.amount) : "Отказ"}
                    </strong>
                    <span>{reasons[d.reason_code]}</span>
                  </div>
                  <ArrowUpRight size={18} />
                </a>
              ))}
            </div>
          ) : (
            <Empty
              title="Первое решение — впереди"
              description="После рассмотрения здесь появятся условия, основания и автор каждого решения."
            />
          )}
          <section className="model-link">
            <span className="feature-icon">
              <Activity size={25} />
            </span>
            <div>
              <h3>Два взгляда на кредитный риск</h3>
              <p>
                Прозрачная балльная модель и локальный ML. Снимки данных,
                факторы и версии доступны в каждом досье.
              </p>
            </div>
            <a href="#/model" className="button button-secondary">
              О модели
              <ArrowUpRight size={17} />
            </a>
          </section>
        </>
      )}
    </>
  );
}
