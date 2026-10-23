import { ArrowUpRight, FileText, LoaderCircle, RefreshCw } from "lucide-react";
import {
  type Application,
  type Status,
  statuses,
  money,
  date,
} from "../api/business";
import type { ReactNode } from "react";

export function Heading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children}
    </div>
  );
}
export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`status-badge status-${status.toLowerCase()}`}>
      <span />
      {statuses[status]}
    </span>
  );
}
export function ResourceState({
  loading,
  error,
  onRetry,
}: {
  loading: boolean;
  error: string;
  onRetry: () => void;
}) {
  if (error)
    return (
      <div className="notice notice-error" role="alert">
        <span>{error}</span>
        <button className="text-button" onClick={onRetry}>
          <RefreshCw size={15} />
          Повторить
        </button>
      </div>
    );
  if (loading)
    return (
      <div className="loading-inline" role="status">
        <LoaderCircle className="spin" size={20} />
        Загружаем данные…
      </div>
    );
  return null;
}
export function Empty({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="feature-icon">
        <FileText size={24} />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {children}
    </div>
  );
}
export function ApplicationRows({
  items,
  bank = false,
}: {
  items: Application[];
  bank?: boolean;
}) {
  return (
    <div className="application-table">
      <div className="table-labels">
        <span>Компания / заявка</span>
        <span>Финансирование</span>
        <span>Статус</span>
        <span>Обновлена · МСК</span>
        <span />
      </div>
      {items.map((a) => (
        <a
          key={a.id}
          className="application-row"
          href={`#/${bank ? "review" : "applications"}/${a.id}`}
        >
          <div className="company-cell">
            <span className="company-monogram">
              {(a.company_name ?? "Н")
                .replace(/ООО|ИП|«|»/g, "")
                .trim()
                .slice(0, 1)}
            </span>
            <div>
              <strong>{a.company_name || "Новая заявка"}</strong>
              <small>
                № {String(a.id).padStart(4, "0")} ·{" "}
                {a.product_code === "EQUIPMENT"
                  ? "Оборудование"
                  : "Оборотные средства"}
              </small>
            </div>
          </div>
          <div>
            <strong>{money(a.amount)}</strong>
            <small>{a.term ? `${a.term} мес.` : "Срок не указан"}</small>
          </div>
          <StatusBadge status={a.status} />
          <span className="row-date">{date(a.updated_at)}</span>
          <ArrowUpRight size={18} />
        </a>
      ))}
    </div>
  );
}
export function Metric({
  label,
  value,
  detail,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  detail: string;
  accent?: boolean;
}) {
  return (
    <div className={`metric ${accent ? "metric-accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
