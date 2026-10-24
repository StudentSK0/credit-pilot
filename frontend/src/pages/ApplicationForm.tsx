import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Save,
  Send,
  ShieldCheck,
} from "lucide-react";
import { useSession } from "../auth/SessionProvider";
import { ApiError } from "../api/client";
import {
  type Application,
  type Fields,
  type Product,
  type Scenario,
  request,
  businessError,
  labels,
  money,
  number,
} from "../api/business";
import { Heading, ResourceState } from "../components/Business";

const empty: Record<keyof Fields, string> = {
  company_name: "",
  inn: "",
  credit_purpose: "",
  amount: "",
  term: "",
  product_code: "",
  monthly_revenue: "",
  monthly_operating_expenses: "",
  existing_monthly_debt_payments: "",
};
const steps = ["Задача бизнеса", "Компания", "Финансы", "Проверка"];
const financialKeys = [
  "monthly_revenue",
  "monthly_operating_expenses",
  "existing_monthly_debt_payments",
] as const;
const hints: Partial<Record<keyof Fields, string>> = {
  inn: "10 цифр для компании или 12 для ИП. Внешние проверки используют локальные синтетические записи.",
  company_name: "Название должно совпадать с синтетическим реестром.",
  credit_purpose:
    "Опишите покупку или задачу: это поможет сотруднику понять потребность.",
  monthly_revenue: "Поступления от обычной деятельности за один месяц.",
  monthly_operating_expenses:
    "Регулярные расходы: закупки, аренда, зарплаты. Без платежей по кредитам.",
  existing_monthly_debt_payments:
    "Сумма всех платежей по текущим кредитам за тот же месяц. Если их нет — 0.",
};

export function ApplicationForm({
  id,
  query,
}: {
  id?: number;
  query: URLSearchParams;
}) {
  const { csrfReady } = useSession();
  const [form, setForm] = useState({ ...empty });
  const [products, setProducts] = useState<Product[]>([]);
  const [current, setCurrent] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [step, setStep] = useState(
    Math.min(3, Math.max(0, Number(query.get("step")) || 0)),
  );
  const [estimate, setEstimate] = useState<string | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const initial = useRef({
    id,
    scenario: query.get("scenario"),
    product: query.get("product"),
  });
  const product = products.find((p) => p.code === form.product_code);
  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const p = await request<Product[]>("/api/products");
        let fields: Fields | undefined;
        if (initial.current.id) {
          const app = await request<Application>(
            `/api/applications/${initial.current.id}`,
          );
          if (app.status !== "DRAFT") {
            window.location.hash = `/applications/${app.id}`;
            return;
          }
          if (live) setCurrent(app);
          fields = app;
        } else if (initial.current.scenario) {
          const scenarios = await request<Scenario[]>("/api/demo-scenarios");
          const found = scenarios.find(
            (s) => s.code === initial.current.scenario,
          );
          fields = found?.fields;
          if (live) setScenario(found ?? null);
        }
        if (live) {
          setProducts(p);
          setForm(
            fields
              ? (Object.fromEntries(
                  Object.keys(empty).map((k) => [
                    k,
                    String(fields![k as keyof Fields] ?? ""),
                  ]),
                ) as typeof empty)
              : {
                  ...empty,
                  product_code: initial.current.product ?? p[0]?.code ?? "",
                },
          );
        }
      } catch (e) {
        if (live) setError(businessError(e));
      } finally {
        if (live) setLoading(false);
      }
    }
    void load();
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    const listener = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", listener);
    const click = (e: MouseEvent) => {
      const a = (e.target as Element).closest('a[href^="#/"]');
      if (
        dirty &&
        a &&
        !window.confirm("Есть несохранённые изменения. Покинуть анкету?")
      )
        e.preventDefault();
    };
    document.addEventListener("click", click);
    return () => {
      window.removeEventListener("beforeunload", listener);
      document.removeEventListener("click", click);
    };
  }, [dirty]);
  useEffect(() => {
    let live = true;
    setEstimate(null);
    if (
      !csrfReady ||
      !product ||
      !/^\d+([.,]\d{1,2})?$/.test(form.amount) ||
      !/^\d+$/.test(form.term)
    )
      return;
    const timeout = window.setTimeout(async () => {
      try {
        const r = await request<{ monthly_payment: string }>(
          "/api/products/estimate",
          {
            method: "POST",
            body: {
              product_code: form.product_code,
              amount: form.amount.replace(",", "."),
              term: Number(form.term),
            },
          },
        );
        if (live) setEstimate(r.monthly_payment);
      } catch {
        /* The form shows product boundaries; no speculative payment on invalid input. */
      }
    }, 400);
    return () => {
      live = false;
      clearTimeout(timeout);
    };
  }, [form.product_code, form.amount, form.term, csrfReady, product]);
  function change(key: keyof Fields, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    setDirty(true);
    setSaved(false);
    setError("");
  }
  function validate(targetStep?: number) {
    const keys: (keyof Fields)[] =
      targetStep === 0
        ? ["product_code", "amount", "term", "credit_purpose"]
        : targetStep === 1
          ? ["company_name", "inn"]
          : targetStep === 2
            ? [...financialKeys]
            : (Object.keys(empty) as (keyof Fields)[]);
    for (const key of keys)
      if (!form[key].trim()) return `Заполните поле «${labels[key]}».`;
    if (keys.includes("inn") && !/^\d{10}(\d{2})?$/.test(form.inn))
      return "ИНН должен содержать 10 или 12 цифр.";
    for (const key of ["amount", ...financialKeys] as const)
      if (keys.includes(key) && !/^\d+([.,]\d{1,2})?$/.test(form[key]))
        return `${labels[key]}: введите неотрицательное число, не более двух знаков после запятой.`;
    if (
      keys.includes("monthly_revenue") &&
      Number(form.monthly_revenue.replace(",", ".")) <= 0
    )
      return "Выручка должна быть больше нуля.";
    if (
      keys.includes("term") &&
      (!/^\d+$/.test(form.term) ||
        !product ||
        Number(form.term) < product.min_term ||
        Number(form.term) > product.max_term)
    )
      return `Срок должен быть целым числом от ${product?.min_term} до ${product?.max_term} месяцев.`;
    if (
      keys.includes("amount") &&
      (!product ||
        Number(form.amount.replace(",", ".")) < Number(product.min_amount) ||
        Number(form.amount.replace(",", ".")) > Number(product.max_amount))
    )
      return `Сумма должна быть от ${money(product?.min_amount)} до ${money(product?.max_amount)}.`;
    return "";
  }
  function payload(): Fields {
    if (form.term && !/^\d+$/.test(form.term))
      throw new Error("Срок: введите целое число месяцев.");
    for (const key of ["amount", ...financialKeys] as const)
      if (form[key] && !/^\d+([.,]\d{1,2})?$/.test(form[key]))
        throw new Error(`${labels[key]}: не более двух знаков после запятой.`);
    return {
      ...form,
      amount: form.amount.replace(",", ".") || null,
      term: form.term ? Number(form.term) : null,
      product_code: form.product_code || null,
      ...Object.fromEntries(
        financialKeys.map((k) => [k, form[k].replace(",", ".") || null]),
      ),
    } as Fields;
  }
  async function save(submit = false) {
    if (busy || !csrfReady || uncertain) return;
    const issue = submit ? validate() : "";
    if (issue) {
      setError(issue);
      return;
    }
    let body: Fields;
    try {
      body = payload();
    } catch (e) {
      setError((e as Error).message);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const app = await request<Application>(
        current ? `/api/applications/${current.id}` : "/api/applications",
        {
          method: current ? "PATCH" : "POST",
          body,
          expectedVersion: current?.version,
        },
      );
      setCurrent(app);
      setDirty(false);
      setSaved(true);
      if (submit) {
        const sent = await request<Application>(
          `/api/applications/${app.id}/submit`,
          { method: "POST", expectedVersion: app.version },
        );
        window.location.hash = `/applications/${sent.id}`;
      } else if (!id) {
        window.location.hash = `/applications/${app.id}/edit?step=${step}`;
      }
    } catch (e) {
      if (!current && e instanceof ApiError && e.reason === "network") {
        setUncertain(true);
        setError(
          "Сохранение не подтверждено. Откройте список заявок и проверьте, появился ли черновик, прежде чем создавать новый.",
        );
      } else setError(businessError(e));
    } finally {
      setBusy(false);
    }
  }
  const field = (
    key: keyof Fields,
    options: { area?: boolean; placeholder?: string } = {},
  ) => (
    <div className={`form-field ${options.area ? "field-wide" : ""}`} key={key}>
      <label htmlFor={key}>
        {labels[key]}
        {financialKeys.includes(key as (typeof financialKeys)[number]) ||
        key === "amount" ? (
          <span>₽</span>
        ) : null}
      </label>
      {options.area ? (
        <textarea
          id={key}
          value={form[key]}
          maxLength={1000}
          placeholder={options.placeholder}
          onChange={(e) => change(key, e.target.value)}
        />
      ) : (
        <input
          id={key}
          inputMode={
            key === "inn" || key === "term"
              ? "numeric"
              : key === "company_name"
                ? "text"
                : "decimal"
          }
          value={form[key]}
          maxLength={key === "company_name" ? 255 : 40}
          placeholder={options.placeholder}
          onChange={(e) => change(key, e.target.value)}
        />
      )}
      <small>{hints[key]}</small>
    </div>
  );
  if (loading)
    return (
      <ResourceState
        loading
        error={error}
        onRetry={() => window.location.reload()}
      />
    );
  return (
    <>
      <a className="back-link" href="#/applications">
        <ArrowLeft size={16} />К заявкам
      </a>
      <Heading
        eyebrow={current ? `ЧЕРНОВИК № ${current.id}` : "НОВАЯ ЗАЯВКА"}
        title="Расскажите о ваших планах"
        description="Четыре простых шага. Черновик можно сохранить в любой момент."
      />
      {scenario && (
        <div className="scenario-notice">
          <span>ДЕМО-СЦЕНАРИЙ</span>
          <strong>{scenario.title}</strong>
          <p>{scenario.description}</p>
        </div>
      )}
      <div className="form-progress">
        {steps.map((name, i) => (
          <button
            key={name}
            className={step === i ? "active" : step > i ? "complete" : ""}
            onClick={() => {
              if (i < step || !validate(step)) {
                setStep(i);
                setError("");
              } else setError(validate(step));
            }}
          >
            <span>{step > i ? <Check size={16} /> : i + 1}</span>
            {name}
          </button>
        ))}
      </div>
      <div className="form-layout">
        <form
          className="panel application-form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            if (step === 3) void save(true);
            else {
              const issue = validate(step);
              if (issue) setError(issue);
              else {
                setError("");
                setStep(step + 1);
              }
            }
          }}
        >
          <div className="form-section-title">
            <span>0{step + 1}</span>
            <div>
              <h2>{steps[step]}</h2>
              <p>
                {
                  [
                    "Для чего нужны деньги и на каких условиях",
                    "Сведения для проверки компании",
                    "Все показатели — в рублях за один и тот же месяц",
                    "Убедитесь, что данные верны. После отправки их проверит банк.",
                  ][step]
                }
              </p>
            </div>
          </div>
          {error && (
            <div className="notice notice-error" role="alert">
              {error}
            </div>
          )}
          {step === 0 && (
            <>
              <div className="product-choice">
                {products.map((p) => (
                  <label
                    key={p.code}
                    className={p.code === form.product_code ? "selected" : ""}
                  >
                    <input
                      type="radio"
                      name="product"
                      value={p.code}
                      checked={p.code === form.product_code}
                      onChange={() => change("product_code", p.code)}
                    />
                    <div>
                      <strong>
                        {p.code === "EQUIPMENT"
                          ? "Оборудование"
                          : "Оборотные средства"}
                      </strong>
                      <small>
                        {number(Number(p.annual_rate) * 100)}% · до {p.max_term}{" "}
                        мес.
                      </small>
                    </div>
                  </label>
                ))}
              </div>
              <div className="fields-grid">
                {field("amount", { placeholder: product?.min_amount })}
                {field("term", {
                  placeholder: `${product?.min_term}–${product?.max_term}`,
                })}
                {field("credit_purpose", {
                  area: true,
                  placeholder:
                    form.product_code === "EQUIPMENT"
                      ? "Какое оборудование и для какой задачи?"
                      : "Какие закупки или заказы планируете финансировать?",
                })}
              </div>
            </>
          )}
          {step === 1 && (
            <div className="fields-grid one-column">
              {field("company_name", {
                placeholder: "ООО «Название компании»",
              })}
              {field("inn", { placeholder: "10 или 12 цифр" })}
              <div className="inline-info">
                <ShieldCheck size={18} />
                <p>
                  Банк сверит сведения с локальным реестром. Для
                  воспроизводимого демо используйте один из четырёх сценариев на
                  главной.
                </p>
              </div>
            </div>
          )}
          {step === 2 && (
            <div className="fields-grid one-column">
              {field("monthly_revenue", { placeholder: "450000.00" })}
              {field("monthly_operating_expenses", {
                placeholder: "300000.00",
              })}
              {field("existing_monthly_debt_payments", { placeholder: "0.00" })}
            </div>
          )}
          {step === 3 && (
            <>
              <div className="review-summary">
                <h3>{form.company_name}</h3>
                <span>ИНН {form.inn}</span>
                <p>{form.credit_purpose}</p>
                <dl>
                  {(["amount", "term", ...financialKeys] as const).map((k) => (
                    <div key={k}>
                      <dt>{labels[k]}</dt>
                      <dd>
                        {k === "term"
                          ? `${form[k]} мес.`
                          : money(form[k].replace(",", "."))}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="inline-info">
                <CheckCircle2 size={19} />
                <p>
                  Отправка запускает рассмотрение сотрудником. Данные
                  синтетические; реальные проверки и денежные операции не
                  выполняются.
                </p>
              </div>
            </>
          )}
          <div className="form-actions">
            <button
              type="button"
              className="button button-secondary"
              disabled={busy || step === 0}
              onClick={() => {
                setStep(step - 1);
                setError("");
              }}
            >
              <ArrowLeft size={16} />
              Назад
            </button>
            <button
              className="button button-primary"
              type="submit"
              disabled={busy || (step === 3 && (!csrfReady || uncertain))}
            >
              {busy
                ? "Сохраняем…"
                : step === 3
                  ? "Отправить заявку"
                  : "Продолжить"}
              {step === 3 ? <Send size={16} /> : <ArrowRight size={16} />}
            </button>
          </div>
        </form>
        <aside className="application-aside">
          <div className="panel estimate-card">
            <span className="eyebrow">ВАШЕ ФИНАНСИРОВАНИЕ</span>
            <h3>
              {form.product_code === "EQUIPMENT"
                ? "Оборудование"
                : "Оборотные средства"}
            </h3>
            <div className="estimate-value">
              <small>Ежемесячный платёж</small>
              <strong>{estimate ? money(estimate) : "—"}</strong>
            </div>
            <dl>
              <div>
                <dt>Сумма</dt>
                <dd>
                  {form.amount ? money(form.amount.replace(",", ".")) : "—"}
                </dd>
              </div>
              <div>
                <dt>Срок</dt>
                <dd>{form.term ? `${form.term} мес.` : "—"}</dd>
              </div>
              <div>
                <dt>Учебная ставка</dt>
                <dd>
                  {product
                    ? `${number(Number(product.annual_rate) * 100)}%`
                    : "—"}
                </dd>
              </div>
            </dl>
            <p>
              Предварительный аннуитетный расчёт. Итоговые условия появятся
              после рассмотрения.
            </p>
          </div>
          <button
            className="button button-secondary save-draft"
            type="button"
            disabled={!csrfReady || busy || uncertain}
            onClick={() => void save()}
          >
            <Save size={17} />
            {saved ? "Черновик сохранён" : "Сохранить черновик"}
          </button>
          <p className="save-note">
            {dirty
              ? "Есть несохранённые изменения"
              : current
                ? "Черновик хранится в вашем кабинете"
                : "Сохраняйте прогресс, чтобы вернуться позже"}
          </p>
        </aside>
      </div>
    </>
  );
}
