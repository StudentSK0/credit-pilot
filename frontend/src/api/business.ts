import { useCallback, useEffect, useState } from "react";
import { ApiError, apiRequest, errorMessage } from "./client";

export type Status =
  | "DRAFT"
  | "SUBMITTED"
  | "CHECKING"
  | "UNDER_REVIEW"
  | "NEEDS_INFO"
  | "OFFERED"
  | "REJECTED"
  | "SIGNED"
  | "DISBURSED";
export const statuses: Record<Status, string> = {
  DRAFT: "Черновик",
  SUBMITTED: "Отправлена",
  CHECKING: "Проверки",
  UNDER_REVIEW: "На рассмотрении",
  NEEDS_INFO: "Нужны сведения",
  OFFERED: "Есть предложение",
  REJECTED: "Отказ",
  SIGNED: "Условия приняты",
  DISBURSED: "Выдача смоделирована",
};
export type Fields = {
  company_name: string | null;
  inn: string | null;
  credit_purpose: string | null;
  amount: string | null;
  term: number | null;
  product_code: string | null;
  monthly_revenue: string | null;
  monthly_operating_expenses: string | null;
  existing_monthly_debt_payments: string | null;
};
export type Application = Fields & {
  id: number;
  status: Status;
  version: number;
  created_at: string;
  updated_at: string;
  product_version: string | null;
};
export type Product = {
  code: string;
  name: string;
  version: string;
  min_amount: string;
  max_amount: string;
  min_term: number;
  max_term: number;
  annual_rate: string;
};
export type Scenario = {
  code: string;
  title: string;
  label: string;
  description: string;
  fields: Fields;
};
export type AppList = {
  items: Application[];
  total: number;
  limit: number;
  offset: number;
};
export type Factor = {
  code: string;
  label: string;
  value: string;
  points: number;
  maximum: number;
};
export type Assessment = {
  factors: Factor[];
  score: number;
  risk: "LOW" | "MEDIUM" | "HIGH";
  score_version: string;
  policy_version: string;
  monthly_payment: string;
  dscr: string;
  margin: string;
  amount: string;
  term: number;
  annual_rate: string;
  eligible: boolean;
  blockers: string[];
  alternative?: Assessment | null;
  ml: {
    model_version: string;
    probability: number;
    target: string;
    intercept: number;
    factors: {
      code: string;
      label: string;
      value: number;
      contribution: number;
    }[];
  };
};
export type Run = {
  id: number;
  state: "RUNNING" | "COMPLETE" | "INCOMPLETE" | "FAILED";
  started_at: string;
  completed_at: string | null;
  error_code: string | null;
  input_snapshot: Fields;
  assessment: Assessment | null;
  checks: {
    code: string;
    label: string;
    result: string;
    detail: string;
    source: string;
    fixture_version: string;
    checked_at: string;
    evidence: Record<string, unknown> | null;
  }[];
};
export type InfoRequest = {
  id: number;
  message: string;
  fields: (keyof Fields)[];
  document_kind: string | null;
  created_at: string;
  answered_at: string | null;
  response: {
    explanation: string;
    fields: Partial<Fields>;
    document_ids: number[];
  } | null;
};
export type Terms = {
  amount: string;
  term: number;
  annual_rate: string;
  monthly_payment: string;
};
export type Decision = {
  id: number;
  kind: "OFFER" | "REJECT";
  reason_code: string;
  explanation: string;
  terms: Terms | null;
  assessment: Assessment | null;
  created_at: string;
};
export type Dossier = {
  application: Application;
  runs: Run[];
  information_requests: InfoRequest[];
  decision: Decision | null;
  contract: { id: number; document_text: string; signed_at: string } | null;
  disbursement: { amount: string; created_at: string } | null;
  documents: {
    id: number;
    name: string;
    created_at: string;
    request_id: number;
  }[];
  allowed_actions: string[];
  contract_preview: string | null;
};
export type Event = {
  id: number;
  event_type: string;
  occurred_at: string;
  actor_role: string;
  actor_id: number;
  application_version: number;
  new_status: Status;
  changes: Record<string, { old: unknown; new: unknown }>;
};
export type Analytics = {
  total: number;
  active: number;
  delayed: number;
  issued_amount: string;
  counts: { status: Status; count: number }[];
  funnel: { status: Status; count: number }[];
  bottlenecks: {
    status: Status;
    reason_code: string;
    count: number;
    oldest_hours: string;
  }[];
  decisions: (Decision & {
    application_id: number;
    company_name: string;
    actor: string;
  })[];
  reasons: { reason_code: string; count: number }[];
  delay_threshold_hours: number;
};
export type Article = { id: string; tag: string; title: string; body: string };

export const labels: Record<keyof Fields, string> = {
  company_name: "Название компании",
  inn: "ИНН",
  credit_purpose: "Цель финансирования",
  amount: "Сумма кредита",
  term: "Срок, месяцев",
  product_code: "Продукт",
  monthly_revenue: "Выручка за месяц",
  monthly_operating_expenses: "Операционные расходы",
  existing_monthly_debt_payments: "Платежи по действующим кредитам",
};
export const reasons: Record<string, string> = {
  STANDARD: "Исходные условия",
  COUNTER_OFFER: "Меньшая сумма",
  AFFORDABILITY: "Недостаточный денежный поток",
  CREDIT_HISTORY: "Кредитная история",
  INACTIVE_BUSINESS: "Неактивная регистрация",
  HIGH_RISK: "Высокий риск",
};
export const money = (value: string | number | null | undefined) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: "RUB",
        maximumFractionDigits: 2,
      }).format(Number(value));
export const number = (value: string | number, digits = 2) =>
  new Intl.NumberFormat("ru-RU", { maximumFractionDigits: digits }).format(
    Number(value),
  );
export const date = (value: string) =>
  new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Moscow",
  }).format(new Date(value));
export const request = <T>(
  path: `/api/${string}`,
  options: Parameters<typeof apiRequest>[1] = {},
) => apiRequest(path, options) as Promise<T>;
export function businessError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409)
      return typeof error.detail === "string"
        ? error.detail
        : "Данные изменились. Обновите страницу и проверьте заявку.";
    if (error.status === 422) {
      if (typeof error.detail === "string") return error.detail;
      if (Array.isArray(error.detail))
        return error.detail
          .map(
            (x: { loc?: string[]; msg?: string }) =>
              `${labels[x.loc?.at(-1) as keyof Fields] ?? "Поле"}: ${x.msg ?? "проверьте значение"}`,
          )
          .join(". ");
    }
    if (error.status === 404)
      return "Заявка не найдена или недоступна вашей учётной записи.";
  }
  return errorMessage(error);
}

export function useResource<T>(path: `/api/${string}`, poll = false) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((x) => x + 1), []);
  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const result = await request<T>(path);
        if (live) {
          setData(result);
          setError("");
        }
      } catch (e) {
        if (live) setError(businessError(e));
      } finally {
        if (live) {
          setLoading(false);
          if (poll) timer = window.setTimeout(load, 5000);
        }
      }
    }
    void load();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [path, poll, revision]);
  return { data, error, loading, refresh };
}

export function command(
  application: Application,
  action: string,
  payload: Record<string, unknown> = {},
) {
  return request<Application>(`/api/applications/${application.id}/${action}`, {
    method: "POST",
    body: {
      expected_version: application.version,
      command_id: crypto.randomUUID(),
      ...payload,
    },
  });
}
