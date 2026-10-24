import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  FileText,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Upload,
  X,
  AlertCircle,
  Activity,
} from "lucide-react";
import { useSession } from "../auth/SessionProvider";
import {
  type Dossier,
  type Application,
  type Assessment,
  type InfoRequest,
  type Event,
  type Fields,
  type Run,
  useResource,
  request,
  command,
  businessError,
  labels,
  statuses,
  reasons,
  money,
  number,
  date,
} from "../api/business";
import {
  Heading,
  StatusBadge,
  ResourceState,
  Metric,
} from "../components/Business";

const nextStep: Record<string, string> = {
  DRAFT: "Заполните анкету и отправьте её на рассмотрение.",
  SUBMITTED: "Заявка поступила в банк. Следующий шаг — проверка сведений.",
  CHECKING:
    "Выполняются локальные проверки. Сотрудник увидит результат или причину сбоя.",
  UNDER_REVIEW: "Проверки завершены. Сотрудник рассматривает данные и условия.",
  NEEDS_INFO:
    "Банк задал вопрос. Ответьте здесь, чтобы продолжить рассмотрение.",
  OFFERED:
    "Банк подготовил условия. Изучите предложение и подтвердите принятие.",
  REJECTED: "Рассмотрение завершено. Основание решения указано ниже.",
  SIGNED: "Вы приняли условия. Осталось смоделировать выдачу на стороне банка.",
  DISBURSED: "Демонстрационный путь завершён. Условия и история сохранены.",
};
const eventNames: Record<string, string> = {
  DRAFT_CREATED: "Создан черновик",
  DRAFT_UPDATED: "Обновлена анкета",
  SUBMITTED: "Заявка отправлена",
  CHECKS_STARTED: "Начаты проверки",
  CHECKS_COMPLETED: "Сохранены результаты проверок",
  CHECKS_FAILED: "Источник проверки недоступен",
  INFORMATION_REQUESTED: "Запрошены дополнительные сведения",
  INFORMATION_PROVIDED: "Получен ответ клиента",
  OFFER_ISSUED: "Подготовлено предложение",
  REJECTED: "Принято решение об отказе",
  SIGNED_SIMULATED: "Смоделировано подписание",
  DISBURSED_SIMULATED: "Смоделирована выдача",
};

export function DossierPage({ id, bank }: { id: number; bank: boolean }) {
  const session = useSession();
  const result = useResource<Dossier>(`/api/applications/${id}/dossier`, true);
  const [tab, setTab] = useState("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const d = result.data;
  const a = d?.application;
  const latest = d?.runs[0];
  async function act(action: string, payload: Record<string, unknown> = {}) {
    if (!a || busy || !session.csrfReady) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await command(a, action, payload);
      setSuccess("Действие сохранено. Досье обновлено.");
      result.refresh();
    } catch (e) {
      setError(businessError(e));
      result.refresh();
      throw e;
    } finally {
      setBusy(false);
    }
  }
  const safeAct = (action: string, payload: Record<string, unknown> = {}) => {
    void act(action, payload).catch(() => {});
  };
  const disabled = busy || !session.csrfReady;
  return (
    <>
      <a className="back-link" href={bank ? "#/review" : "#/applications"}>
        <ArrowLeft size={16} />
        {bank ? "К очереди заявок" : "К моим заявкам"}
      </a>
      <ResourceState
        loading={result.loading && !d}
        error={result.error}
        onRetry={result.refresh}
      />
      {a && d && (
        <>
          <Heading
            eyebrow={`ЗАЯВКА № ${String(a.id).padStart(4, "0")} · ${a.product_code === "EQUIPMENT" ? "ОБОРУДОВАНИЕ" : "ОБОРОТНЫЕ СРЕДСТВА"}`}
            title={a.company_name || "Новая заявка"}
            description={`ИНН ${a.inn ?? "не указан"} · Создана ${date(a.created_at)} МСК`}
          >
            <StatusBadge status={a.status} />
          </Heading>
          <div className={`journey-banner journey-${a.status.toLowerCase()}`}>
            <span className="journey-symbol">
              {a.status === "DISBURSED" ? (
                <CheckCircle2 size={26} />
              ) : a.status === "NEEDS_INFO" ? (
                <FileText size={25} />
              ) : (
                <Activity size={25} />
              )}
            </span>
            <div>
              <strong>{statuses[a.status]}</strong>
              <p>{nextStep[a.status]}</p>
            </div>
            {bank && d.allowed_actions.includes("checks") && (
              <button
                className="button button-primary"
                disabled={disabled}
                onClick={() => safeAct("checks")}
              >
                <Play size={16} />
                {busy
                  ? "Проверяем…"
                  : latest
                    ? "Повторить проверки"
                    : "Запустить проверки"}
              </button>
            )}
            {!bank && a.status === "DRAFT" && (
              <a
                className="button button-primary"
                href={`#/applications/${a.id}/edit`}
              >
                Продолжить заполнение
                <ArrowRight size={16} />
              </a>
            )}
            {bank && a.status === "SIGNED" && (
              <button
                className="button button-primary"
                disabled={disabled}
                onClick={() => safeAct("disburse")}
              >
                Смоделировать выдачу
                <ArrowRight size={16} />
              </button>
            )}
          </div>
          {error && (
            <div className="notice notice-error" role="alert">
              {error}
              <button
                className="text-button"
                onClick={() => {
                  setError("");
                  result.refresh();
                }}
              >
                <RefreshCw size={15} />
                Обновить
              </button>
            </div>
          )}
          {success && (
            <div className="notice notice-success" role="status">
              <Check size={17} />
              {success}
            </div>
          )}
          <div className="dossier-stats">
            <Metric
              label="Запрошенная сумма"
              value={money(a.amount)}
              detail="Исходный запрос сохранён"
            />
            <Metric
              label="Срок финансирования"
              value={a.term ? `${a.term} мес.` : "—"}
              detail={
                a.product_code === "EQUIPMENT"
                  ? "Приобретение оборудования"
                  : "Пополнение оборотных средств"
              }
            />
            <Metric
              label={
                d.decision?.terms ? "Платёж по предложению" : "Расчётный платёж"
              }
              value={money(
                d.decision?.terms?.monthly_payment ??
                  latest?.assessment?.monthly_payment,
              )}
              detail="Учебный аннуитетный расчёт"
            />
          </div>
          <div className="tabs" role="tablist" aria-label="Разделы досье">
            {[
              ["overview", "Обзор заявки"],
              ["checks", "Проверки и риск"],
              ["history", "История действий"],
            ].map(([key, title]) => (
              <button
                role="tab"
                aria-selected={tab === key}
                key={key}
                onClick={() => setTab(key)}
              >
                {title}
                {key === "checks" && latest && (
                  <span className="count-badge">{latest.checks.length}</span>
                )}
              </button>
            ))}
          </div>
          <div role="tabpanel">
            {tab === "overview" && (
              <div className="dossier-layout">
                <div className="dossier-main">
                  {d.decision && (
                    <DecisionResult
                      dossier={d}
                      bank={bank}
                      disabled={disabled}
                      onSign={(payload) => act("sign", payload)}
                    />
                  )}
                  {d.information_requests
                    .filter((r) => !r.answered_at)
                    .map((r) => (
                      <section className="panel request-panel" key={r.id}>
                        <div className="panel-heading">
                          <div>
                            <span className="eyebrow">
                              ЗАПРОС БАНКА · {date(r.created_at)}
                            </span>
                            <h2>Уточним детали</h2>
                          </div>
                          <FileText size={22} />
                        </div>
                        <p className="request-message">{r.message}</p>
                        {bank ? (
                          <div className="inline-info">
                            <ClockIcon />
                            <p>
                              Ожидается ответ клиента
                              {r.document_kind
                                ? " и синтетический документ"
                                : ""}
                              . После ответа понадобится новая проверка.
                            </p>
                          </div>
                        ) : (
                          <ReplyForm
                            requestInfo={r}
                            application={a}
                            disabled={disabled}
                            onReply={(payload) =>
                              act(`information-requests/${r.id}/reply`, payload)
                            }
                          />
                        )}
                      </section>
                    ))}
                  <section className="panel">
                    <div className="panel-heading">
                      <h2>Потребность бизнеса</h2>
                      <span className="badge">Анкета клиента</span>
                    </div>
                    <p className="purpose-text">
                      {a.credit_purpose || "Цель пока не указана"}
                    </p>
                    <dl className="data-list">
                      {(
                        [
                          "monthly_revenue",
                          "monthly_operating_expenses",
                          "existing_monthly_debt_payments",
                        ] as const
                      ).map((k) => (
                        <div key={k}>
                          <dt>
                            {labels[k]}
                            <small>₽ в месяц</small>
                          </dt>
                          <dd>{money(a[k])}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                  {d.information_requests.some((r) => r.answered_at) && (
                    <section className="panel">
                      <h2>Уточнения клиента</h2>
                      {d.information_requests
                        .filter((r) => r.answered_at)
                        .map((r) => (
                          <div className="answered-request" key={r.id}>
                            <span className="eyebrow">
                              ОТВЕТ · {date(r.answered_at!)}
                            </span>
                            <h3>{r.message}</h3>
                            <p>{r.response?.explanation}</p>
                            {r.response &&
                              Object.entries(r.response.fields).map(
                                ([k, v]) => (
                                  <p key={k}>
                                    <strong>
                                      {labels[k as keyof Fields]}:
                                    </strong>{" "}
                                    {String(v)}
                                  </p>
                                ),
                              )}
                          </div>
                        ))}
                    </section>
                  )}
                  {d.documents.length > 0 && (
                    <section className="panel">
                      <h2>Документы</h2>
                      <p className="panel-description">
                        Синтетические материалы, предоставленные клиентом.
                      </p>
                      {d.documents.map((doc) => (
                        <a
                          className="document-link"
                          href={`/api/applications/${a.id}/documents/${doc.id}`}
                          key={doc.id}
                        >
                          <FileText size={20} />
                          <div>
                            <strong>{doc.name}</strong>
                            <small>{date(doc.created_at)} МСК</small>
                          </div>
                          <span>Скачать ↓</span>
                        </a>
                      ))}
                    </section>
                  )}
                </div>
                <aside className="dossier-aside">
                  {bank && a.status === "UNDER_REVIEW" ? (
                    <BankActions
                      key={latest?.id}
                      dossier={d}
                      disabled={disabled}
                      onAct={act}
                    />
                  ) : (
                    <section className="panel next-step-card">
                      <span className="eyebrow">ПОНЯТНЫЙ МАРШРУТ</span>
                      <h2>Что дальше</h2>
                      <p>{nextStep[a.status]}</p>
                      <ol>
                        {[
                          "Анкета и отправка",
                          "Проверки и рассмотрение",
                          "Предложение и принятие",
                          "Выдача · симуляция",
                        ].map((s, i) => (
                          <li key={s}>
                            <span>{i + 1}</span>
                            {s}
                          </li>
                        ))}
                      </ol>
                    </section>
                  )}
                  {latest?.assessment && (
                    <section className="panel compact-risk">
                      <span className="eyebrow">
                        ОЦЕНКА ПО ЗАПРОШЕННЫМ УСЛОВИЯМ
                      </span>
                      <div>
                        <strong>
                          {latest.assessment.score}
                          <small>/100</small>
                        </strong>
                        <span>{riskLabel(latest.assessment.risk)}</span>
                      </div>
                      <p>
                        {latest.assessment.eligible
                          ? "Условия проходят учебную кредитную политику."
                          : "Перед предложением нужно рассмотреть ограничения."}
                      </p>
                      <button
                        className="text-button"
                        onClick={() => setTab("checks")}
                      >
                        Посмотреть факторы
                        <ArrowRight size={15} />
                      </button>
                    </section>
                  )}
                </aside>
              </div>
            )}
            {tab === "checks" && <Checks runs={d.runs} />}
            {tab === "history" && (
              <History key={a.version} applicationId={a.id} />
            )}
          </div>
        </>
      )}
    </>
  );
}
function ClockIcon() {
  return <RefreshCw size={18} />;
}
function riskLabel(risk: string) {
  return (
    { LOW: "Низкий риск", MEDIUM: "Средний риск", HIGH: "Высокий риск" }[
      risk
    ] ?? risk
  );
}

function BankActions({
  dossier: d,
  disabled,
  onAct,
}: {
  dossier: Dossier;
  disabled: boolean;
  onAct: (action: string, payload: Record<string, unknown>) => Promise<void>;
}) {
  const score = d.runs[0]?.assessment;
  const candidate = score?.eligible ? score : score?.alternative;
  const [mode, setMode] = useState("offer");
  const [amount, setAmount] = useState(
    candidate?.amount ?? d.application.amount ?? "",
  );
  const [explanation, setExplanation] = useState("");
  const [fields, setFields] = useState<(keyof Fields)[]>([
    "monthly_operating_expenses",
  ]);
  const [documentKind, setDocumentKind] = useState("FINANCIAL_REPORT");
  const [reason, setReason] = useState("AFFORDABILITY");
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (mode === "info")
        await onAct("information-requests", {
          message: explanation,
          fields,
          document_kind: documentKind || null,
        });
      else
        await onAct("decisions", {
          kind: mode === "offer" ? "OFFER" : "REJECT",
          reason_code:
            mode === "offer"
              ? Number(amount.replace(",", ".")) < Number(d.application.amount)
                ? "COUNTER_OFFER"
                : "STANDARD"
              : reason,
          explanation,
          ...(mode === "offer"
            ? { offered_amount: amount.replace(",", ".") }
            : {}),
        });
    } catch {
      /* Parent displays server errors without losing the entered explanation. */
    }
  }
  return (
    <section className="panel bank-actions">
      <span className="eyebrow">СЛЕДУЮЩЕЕ ДЕЙСТВИЕ</span>
      <h2>Решение сотрудника</h2>
      <div className="action-mode">
        <button
          className={mode === "offer" ? "active" : ""}
          onClick={() => setMode("offer")}
        >
          Предложить
        </button>
        <button
          className={mode === "info" ? "active" : ""}
          onClick={() => setMode("info")}
        >
          Уточнить
        </button>
        <button
          className={mode === "reject" ? "active" : ""}
          onClick={() => setMode("reject")}
        >
          Отказать
        </button>
      </div>
      <form onSubmit={submit}>
        {mode === "offer" && (
          <>
            {!candidate ? (
              <div className="inline-info warning">
                <AlertCircle size={19} />
                <p>
                  Текущие данные не позволяют предложить кредит. Изучите
                  проверки или запросите уточнение.
                </p>
              </div>
            ) : (
              <>
                <label className="field-label" htmlFor="offered-amount">
                  Предлагаемая сумма, ₽
                </label>
                <input
                  id="offered-amount"
                  className="input"
                  inputMode="decimal"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                  pattern="[0-9]+([.,][0-9]{1,2})?"
                />
                <p className="field-hint">
                  {score?.alternative
                    ? "Рассчитана меньшая сумма с покрытием платежей не ниже 1,20."
                    : "Исходная сумма проходит правила. Можно предложить меньшую."}{" "}
                  Срок — {d.application.term} мес.
                </p>
              </>
            )}
          </>
        )}
        {mode === "reject" && (
          <>
            <label className="field-label" htmlFor="reason">
              Основание решения
            </label>
            <select
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            >
              {[
                "AFFORDABILITY",
                "CREDIT_HISTORY",
                "HIGH_RISK",
                "INACTIVE_BUSINESS",
              ].map((r) => (
                <option value={r} key={r}>
                  {reasons[r]}
                </option>
              ))}
            </select>
            <p className="field-hint">
              Сервер проверит, что основание подтверждается результатами
              проверки.
            </p>
          </>
        )}
        {mode === "info" && (
          <>
            <span className="field-label">Какие поля уточнить</span>
            <div className="checkbox-list">
              {(
                [
                  "monthly_revenue",
                  "monthly_operating_expenses",
                  "existing_monthly_debt_payments",
                  "company_name",
                  "credit_purpose",
                ] as const
              ).map((k) => (
                <label key={k}>
                  <input
                    type="checkbox"
                    checked={fields.includes(k)}
                    onChange={(e) =>
                      setFields(
                        e.target.checked
                          ? [...fields, k]
                          : fields.filter((f) => f !== k),
                      )
                    }
                  />
                  {labels[k]}
                </label>
              ))}
            </div>
            <label className="field-label" htmlFor="document-kind">
              Запросить документ
            </label>
            <select
              id="document-kind"
              value={documentKind}
              onChange={(e) => setDocumentKind(e.target.value)}
            >
              <option value="">Достаточно пояснения</option>
              <option value="FINANCIAL_REPORT">
                Финансовый отчёт · TXT / CSV
              </option>
              <option value="PURPOSE_EVIDENCE">
                Подтверждение цели · TXT / CSV
              </option>
            </select>
          </>
        )}
        <label className="field-label" htmlFor="decision-explanation">
          {mode === "info" ? "Вопрос клиенту" : "Объяснение для клиента"}
        </label>
        <textarea
          id="decision-explanation"
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
          minLength={10}
          maxLength={1800}
          required
          placeholder={
            mode === "info"
              ? "Что нужно уточнить и почему?"
              : "Объясните основание и дальнейшие действия."
          }
        />
        <p className="field-hint">
          Не менее 10 символов. Клиент увидит этот текст.
        </p>
        <button
          className="button button-primary"
          disabled={disabled || (mode === "offer" && !candidate)}
          type="submit"
        >
          {disabled
            ? "Подождите…"
            : mode === "info"
              ? "Запросить сведения"
              : mode === "offer"
                ? "Отправить предложение"
                : "Подтвердить отказ"}
          <Send size={15} />
        </button>
      </form>
    </section>
  );
}

function ReplyForm({
  requestInfo: r,
  application: a,
  disabled,
  onReply,
}: {
  requestInfo: InfoRequest;
  application: Application;
  disabled: boolean;
  onReply: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [fields, setFields] = useState<Record<string, string>>(
    Object.fromEntries(r.fields.map((k) => [k, String(a[k] ?? "")])),
  );
  const [explanation, setExplanation] = useState("");
  const [documents, setDocuments] = useState<
    { name: string; content: string }[]
  >([]);
  const [error, setError] = useState("");
  const [reading, setReading] = useState(false);
  async function readFiles(files: FileList | null) {
    if (!files) return;
    setError("");
    setReading(true);
    try {
      if (files.length > 3)
        throw new Error("Можно приложить не более трёх документов.");
      const docs = [];
      for (const file of Array.from(files)) {
        if (!/\.(txt|csv)$/.test(file.name) || file.size > 65536)
          throw new Error("Нужен TXT или CSV до 64 КиБ.");
        docs.push({ name: file.name, content: await file.text() });
      }
      setDocuments(docs);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReading(false);
    }
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const values = Object.fromEntries(
      Object.entries(fields).map(([k, v]) => [
        k,
        k.startsWith("monthly_") || k === "existing_monthly_debt_payments"
          ? v.replace(",", ".")
          : v,
      ]),
    );
    try {
      await onReply({ fields: values, explanation, documents });
    } catch {
      /* Error is displayed above the dossier. */
    }
  }
  function exampleDocument() {
    const text = `СИНТЕТИЧЕСКИЙ ДОКУМЕНТ CREDIT PILOT\nКомпания: ${a.company_name}\nИНН: ${a.inn}\n${Object.entries(
      fields,
    )
      .map(([k, v]) => `${labels[k as keyof Fields]}: ${v}`)
      .join(
        "\n",
      )}\nПояснение: ${explanation || "Учебные данные для демонстрации"}\nНе является финансовой отчётностью реальной организации.`;
    setDocuments([{ name: "synthetic-report.txt", content: text }]);
  }
  return (
    <form onSubmit={submit} className="reply-form">
      <div className="fields-grid">
        {r.fields.map((k) => (
          <div className="form-field" key={k}>
            <label htmlFor={`reply-${k}`}>{labels[k]}</label>
            <input
              id={`reply-${k}`}
              value={fields[k]}
              onChange={(e) => setFields({ ...fields, [k]: e.target.value })}
              required
            />
          </div>
        ))}
      </div>
      <label className="field-label" htmlFor="reply-explanation">
        Ваше пояснение
      </label>
      <textarea
        id="reply-explanation"
        value={explanation}
        onChange={(e) => setExplanation(e.target.value)}
        minLength={10}
        maxLength={1800}
        required
        placeholder="Что изменилось и чем подтверждаются данные?"
      />
      <div className="upload-area">
        <Upload size={24} />
        <div>
          <strong>
            {r.document_kind
              ? "Приложите запрошенный документ"
              : "Документы к ответу"}
          </strong>
          <p>Только синтетические TXT / CSV, до 64 КиБ, не более 3 файлов.</p>
          <input
            type="file"
            aria-label="Приложить документы"
            accept=".txt,.csv"
            multiple
            onChange={(e) => void readFiles(e.target.files)}
          />
        </div>
      </div>
      <button className="text-button" type="button" onClick={exampleDocument}>
        Сформировать учебный пример из введённых данных
      </button>
      {documents.map((doc, i) => (
        <div className="attached-document" key={i}>
          <FileText size={17} />
          <span>{doc.name}</span>
          <button
            type="button"
            className="icon-button"
            aria-label={`Убрать ${doc.name}`}
            onClick={() => setDocuments(documents.filter((_, j) => i !== j))}
          >
            <X size={15} />
          </button>
        </div>
      ))}
      {error && (
        <div className="notice notice-error" role="alert">
          {error}
        </div>
      )}
      <button
        className="button button-primary"
        type="submit"
        disabled={
          disabled || reading || (!!r.document_kind && !documents.length)
        }
      >
        Отправить ответ
        <Send size={16} />
      </button>
    </form>
  );
}

function DecisionResult({
  dossier: d,
  bank,
  disabled,
  onSign,
}: {
  dossier: Dossier;
  bank: boolean;
  disabled: boolean;
  onSign: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const decision = d.decision!;
  const [confirmed, setConfirmed] = useState(false);
  const t = decision.terms;
  return (
    <section
      className={`panel decision-card ${decision.kind === "REJECT" ? "rejection-card" : ""}`}
    >
      <span className="eyebrow">
        {d.disbursement
          ? "ПУТЬ ЗАВЕРШЁН"
          : decision.kind === "OFFER"
            ? "РЕШЕНИЕ ПО ВАШЕЙ ЗАЯВКЕ"
            : "РЕЗУЛЬТАТ РАССМОТРЕНИЯ"}
      </span>
      <h2>
        {d.disbursement
          ? "Финансирование смоделировано"
          : decision.kind === "REJECT"
            ? "Почему банк отказал"
            : decision.reason_code === "COUNTER_OFFER"
              ? "Больше запаса. Комфортнее платёж."
              : "Вашему бизнесу — новые возможности"}
      </h2>
      <p>{decision.explanation}</p>
      {t && (
        <>
          <div className="offer-amount">
            {money(t.amount)}
            {decision.reason_code === "COUNTER_OFFER" && (
              <small>Вы запрашивали {money(d.application.amount)}</small>
            )}
          </div>
          <div className="offer-terms">
            <div>
              <span>Срок</span>
              <strong>{t.term} месяцев</strong>
            </div>
            <div>
              <span>Учебная ставка</span>
              <strong>{number(Number(t.annual_rate) * 100)}%</strong>
            </div>
            <div>
              <span>Платёж в месяц</span>
              <strong>{money(t.monthly_payment)}</strong>
            </div>
          </div>
          <details className="contract-preview">
            <summary>
              <FileText size={17} />
              Открыть демонстрационный договор
              <ChevronDown size={16} />
            </summary>
            <pre>{d.contract?.document_text ?? d.contract_preview}</pre>
          </details>
          {!bank && d.application.status === "OFFERED" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void onSign({
                  decision_id: decision.id,
                  confirmed: true,
                }).catch(() => {});
              }}
            >
              <label className="confirmation">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                Я прочитал(а) условия и подтверждаю моделируемое подписание.
                Реальных обязательств и перевода денег нет.
              </label>
              <button
                type="submit"
                className="button button-primary"
                disabled={disabled || !confirmed}
              >
                Принять условия и подписать · демо
                <CheckCircle2 size={17} />
              </button>
            </form>
          )}
          {d.contract && (
            <div className="inline-info">
              <ShieldCheck size={19} />
              <p>
                Подписание смоделировано {date(d.contract.signed_at)} МСК.{" "}
                {d.disbursement
                  ? `Выдача ${money(d.disbursement.amount)} смоделирована ${date(d.disbursement.created_at)} МСК.`
                  : "Ожидается моделируемая выдача сотрудником."}
              </p>
            </div>
          )}
        </>
      )}
      <p className="fineprint">
        {decision.kind === "OFFER"
          ? "Учебное предложение. Реальные операции и юридически значимая подпись не выполняются."
          : "Основание относится к синтетическим данным этой заявки и учебной политике."}
      </p>
    </section>
  );
}

function Checks({ runs }: { runs: Run[] }) {
  const latest = runs[0];
  if (!latest)
    return (
      <div className="empty-state">
        <ShieldCheck size={32} />
        <h2>Проверки ещё не начались</h2>
        <p>После отправки сотрудник запустит сверку сведений и оценку риска.</p>
      </div>
    );
  return (
    <div className="checks-page">
      <div className="check-run-heading">
        <span>
          Проверка №{latest.id} · {date(latest.started_at)} МСК
        </span>
        <span className="badge">
          {latest.state === "COMPLETE"
            ? "Завершена"
            : latest.state === "INCOMPLETE"
              ? "Нужен разбор данных"
              : latest.state === "FAILED"
                ? "Проверка не завершена"
                : "Выполняется"}
        </span>
      </div>
      {latest.error_code && (
        <div className="notice notice-error">
          <AlertCircle size={20} />
          <p>
            {latest.error_code === "SOURCE_UNAVAILABLE"
              ? "Локальный источник недоступен."
              : latest.error_code === "SOURCE_INVALID"
                ? "Источник вернул некорректные данные."
                : latest.error_code === "INTERRUPTED"
                  ? "Предыдущая попытка была прервана."
                  : "Во время обработки произошла ошибка."}{" "}
            Результат не считается успешным. Сотрудник может повторить проверку;
            прерванная попытка доступна для повтора через 30 секунд.
          </p>
        </div>
      )}
      <div className="check-cards">
        {latest.checks.map((c) => (
          <article
            className={`check-card check-${c.result.toLowerCase()}`}
            key={c.code}
          >
            <span className="check-icon">
              {c.result === "PASS" ? (
                <CheckCircle2 size={20} />
              ) : (
                <AlertCircle size={20} />
              )}
            </span>
            <div>
              <h3>{c.label}</h3>
              <p>{c.detail}</p>
              <small>
                {c.source === "LOCAL_SIMULATOR"
                  ? "Локальный симулятор"
                  : "Проверка анкеты"}{" "}
                · {c.fixture_version}
              </small>
              {c.evidence && (
                <details>
                  <summary>Сведения источника</summary>
                  <dl className="source-evidence">
                    {Object.entries(c.evidence).map(([k, v]) => (
                      <div key={k}>
                        <dt>
                          {{
                            legal_name: "Название в реестре",
                            registration_active: "Активная регистрация",
                            business_age_months: "Возраст бизнеса, мес.",
                            max_overdue_days: "Максимальная просрочка, дн.",
                          }[k] ?? k}
                        </dt>
                        <dd>
                          {typeof v === "boolean"
                            ? v
                              ? "Да"
                              : "Нет"
                            : String(v)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </details>
              )}
            </div>
          </article>
        ))}
      </div>
      {latest.assessment ? (
        <ScoreDetails assessment={latest.assessment} />
      ) : (
        !latest.error_code && (
          <div className="notice notice-warning">
            <AlertCircle size={20} />
            <p>
              Оценка риска не рассчитана: сведения неполны или противоречат друг
              другу. Неизвестные признаки не заменяются положительными
              значениями.
            </p>
          </div>
        )
      )}
      {runs.length > 1 && (
        <section className="panel">
          <h2>Предыдущие проверки</h2>
          <p className="panel-description">
            Каждая попытка хранит собственный снимок. Новые сведения не
            переписывают историю.
          </p>
          {runs.slice(1).map((r) => (
            <details className="previous-run" key={r.id}>
              <summary>
                Проверка №{r.id} · {date(r.started_at)} · {r.state}
                <ChevronDown size={15} />
              </summary>
              {r.assessment && (
                <p>
                  Оценка: {r.assessment.score}/100 ·{" "}
                  {riskLabel(r.assessment.risk)} · покрытие{" "}
                  {number(r.assessment.dscr)}
                </p>
              )}
              <dl className="data-list">
                {Object.entries(r.input_snapshot).map(([k, v]) => (
                  <div key={k}>
                    <dt>{labels[k as keyof Fields]}</dt>
                    <dd>{String(v ?? "—")}</dd>
                  </div>
                ))}
              </dl>
            </details>
          ))}
        </section>
      )}
    </div>
  );
}
function ScoreDetails({ assessment: s }: { assessment: Assessment }) {
  return (
    <>
      <div className="scoring-grid">
        <section className="panel score-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">ПРОЗРАЧНЫЕ ПРАВИЛА</span>
              <h2>Из чего складывается оценка</h2>
            </div>
            <span className="badge">{s.score_version}</span>
          </div>
          <div className="score-overview">
            <div
              className={`score-ring risk-${s.risk.toLowerCase()}`}
              style={{ "--score": `${s.score}%` } as React.CSSProperties}
            >
              <strong>
                {s.score}
                <small>из 100</small>
              </strong>
            </div>
            <div>
              <h3>{riskLabel(s.risk)}</h3>
              <p>
                Покрытие платежей: <strong>{number(s.dscr)}×</strong>
                <br />
                Операционная маржа:{" "}
                <strong>{number(Number(s.margin) * 100)}%</strong>
              </p>
            </div>
          </div>
          <div className="factor-list">
            {s.factors.map((f) => (
              <div className="factor" key={f.code}>
                <div>
                  <span>{f.label}</span>
                  <strong>
                    {f.points}
                    <small> / {f.maximum}</small>
                  </strong>
                </div>
                <div className="factor-track">
                  <span style={{ width: `${(f.points / f.maximum) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <p className="fineprint">
            DSCR = (выручка − операционные расходы) / (текущие платежи + новый
            платёж). Учебные пороги команды.
          </p>
        </section>
        <section className="panel ml-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">ДОПОЛНИТЕЛЬНЫЙ ВЗГЛЯД</span>
              <h2>ML-оценка риска</h2>
            </div>
            <span className="ml-chip">ML</span>
          </div>
          <div className="ml-probability">
            <strong>
              {number(s.ml.probability * 100, 1)}
              <span>%</span>
            </strong>
            <p>
              Учебная вероятность просрочки
              <br />
              &gt;30 дней за следующие 12 месяцев
            </p>
          </div>
          <div className="ml-contributions">
            {s.ml.factors.map((f) => (
              <div key={f.code}>
                <span>{f.label}</span>
                <strong
                  className={
                    f.contribution > 0 ? "risk-increase" : "risk-decrease"
                  }
                >
                  {f.contribution > 0 ? "↑" : "↓"}{" "}
                  {number(Math.abs(f.contribution))}
                </strong>
              </div>
            ))}
          </div>
          <p className="field-hint">
            Вклад в логарифм шансов: ↑ повышает оценку риска, ↓ снижает
            относительно среднего обучающей выборки.
          </p>
          <div className="ml-limitation">
            <ShieldCheck size={17} />
            <p>
              Обучено на синтетических данных. Модель помогает анализировать
              риск; решение принимает сотрудник с учётом правил.
            </p>
          </div>
          <small className="muted">
            {s.ml.model_version} · локальный inference
          </small>
        </section>
      </div>
      <section
        className={`panel policy-panel ${s.eligible ? "policy-pass" : ""}`}
      >
        <div>
          <span className="eyebrow">
            КРЕДИТНАЯ ПОЛИТИКА · {s.policy_version}
          </span>
          <h2>
            {s.eligible
              ? "Исходные условия допустимы"
              : "Исходные условия требуют изменения или отказа"}
          </h2>
          {s.blockers.map((b) => (
            <p key={b}>• {b}</p>
          ))}
          {s.eligible && (
            <p>
              Проверки и учебные ограничения допускают предложение. Сотрудник
              подтверждает его отдельным решением.
            </p>
          )}
        </div>
        {s.alternative && (
          <div className="alternative">
            <small>Рассчитанная альтернатива</small>
            <strong>{money(s.alternative.amount)}</strong>
            <span>
              {money(s.alternative.monthly_payment)} / мес. · DSCR{" "}
              {number(s.alternative.dscr)}
            </span>
          </div>
        )}
      </section>
    </>
  );
}

function History({ applicationId }: { applicationId: number }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  async function load(after = 0) {
    setBusy(true);
    setError("");
    try {
      const next = await request<Event[]>(
        `/api/applications/${applicationId}/events?limit=100&after_id=${after}`,
      );
      setEvents((old) => (after ? [...old, ...next] : next));
      setMore(next.length === 100);
    } catch (e) {
      setError(businessError(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void load();
  }, [applicationId]);
  return (
    <section className="panel history-panel">
      <div className="panel-heading">
        <h2>История заявки</h2>
        <span className="badge">Время МСК · версия и автор</span>
      </div>
      {error && (
        <div className="notice notice-error" role="alert">
          {error}
        </div>
      )}
      <ol className="timeline">
        {[...events].reverse().map((e) => (
          <li key={e.id}>
            <span className="timeline-dot" />
            <div className="timeline-event">
              <div>
                <h3>{eventNames[e.event_type] ?? e.event_type}</h3>
                <time>{date(e.occurred_at)}</time>
              </div>
              <p>
                {e.actor_role === "CLIENT"
                  ? "Предприниматель"
                  : "Сотрудник банка"}{" "}
                №{e.actor_id} · версия {e.application_version}
              </p>
              {!!Object.keys(e.changes).length && (
                <details>
                  <summary>
                    Подробности изменения
                    <ChevronDown size={14} />
                  </summary>
                  <dl>
                    {Object.entries(e.changes).map(([k, v]) => (
                      <div key={k}>
                        <dt>
                          {labels[k as keyof Fields] ??
                            {
                              explanation: "Пояснение",
                              message: "Вопрос",
                              reason_code: "Основание",
                              terms: "Условия",
                              run_id: "Проверка",
                              result: "Результат",
                              request_id: "Запрос",
                              decision_id: "Решение",
                              contract_id: "Договор",
                              disbursement_id: "Выдача",
                              document_ids: "Документы",
                              product_version: "Версия продукта",
                              fields: "Запрошенные поля",
                              document_kind: "Вид документа",
                            }[k] ??
                            k}
                        </dt>
                        <dd>
                          {v.old !== null && (
                            <>
                              <span className="old-value">
                                {typeof v.old === "object"
                                  ? JSON.stringify(v.old)
                                  : String(v.old)}
                              </span>{" "}
                              →{" "}
                            </>
                          )}
                          {typeof v.new === "object"
                            ? JSON.stringify(v.new)
                            : String(v.new ?? "—")}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </details>
              )}
            </div>
          </li>
        ))}
      </ol>
      {more && (
        <button
          className="button button-secondary"
          disabled={busy}
          onClick={() => void load(events.at(-1)?.id)}
        >
          Загрузить следующие события
        </button>
      )}
      {busy && <p className="muted">Загружаем историю…</p>}
    </section>
  );
}
