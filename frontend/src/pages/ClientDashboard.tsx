import {
  ArrowUpRight,
  ArrowRight,
  Sparkles,
  CircleCheck,
  Clock3,
} from "lucide-react";
import { useState } from "react";
import {
  useResource,
  type AppList,
  type Article,
  type Scenario,
} from "../api/business";
import {
  ApplicationRows,
  Empty,
  Heading,
  ResourceState,
} from "../components/Business";

export function ClientDashboard() {
  const applications = useResource<AppList>("/api/applications?limit=4", true);
  const scenarios = useResource<Scenario[]>("/api/demo-scenarios");
  const feed = useResource<Article[]>("/api/feed", true);
  const [article, setArticle] = useState<string | null>(null);
  return (
    <>
      <Heading
        eyebrow="КАБИНЕТ ПРЕДПРИНИМАТЕЛЯ"
        title="Ваш бизнес. Следующий шаг."
        description="Финансирование, которое помогает двигаться вперёд."
      >
        <span className="environment-pill">
          <span />
          Демонстрационная среда
        </span>
      </Heading>
      <section className="welcome-card live-hero">
        <div className="welcome-content">
          <span className="welcome-kicker">ОТ ПЛАНА К ВОЗМОЖНОСТЯМ</span>
          <h2>
            У больших планов
            <br />
            есть понятный маршрут.
          </h2>
          <p>
            Выберите финансирование для бизнеса. Все этапы, вопросы банка и
            решение — здесь, в вашем кабинете.
          </p>
          <a className="button button-light" href="#/products">
            Подобрать финансирование
            <ArrowUpRight size={18} />
          </a>
          <div className="hero-trust">
            <span>
              <CircleCheck size={14} />
              Сохранение черновика
            </span>
            <span>
              <Clock3 size={14} />
              Статус онлайн
            </span>
          </div>
        </div>
        <div className="growth-art" aria-hidden="true">
          <span className="growth-ring" />
          <span className="growth-bar bar-one" />
          <span className="growth-bar bar-two" />
          <span className="growth-bar bar-three" />
          <span className="growth-arrow">
            <ArrowUpRight size={66} strokeWidth={1.3} />
          </span>
          <span className="growth-label">ПРОСТРАНСТВО ДЛЯ РОСТА</span>
        </div>
      </section>
      <div className="section-heading">
        <h2>
          Ваши заявки{" "}
          <span className="count-badge">{applications.data?.total ?? "—"}</span>
        </h2>
        <a className="text-button" href="#/applications">
          Все заявки
          <ArrowRight size={16} />
        </a>
      </div>
      <ResourceState {...applications} onRetry={applications.refresh} />
      {applications.data &&
        (applications.data.items.length ? (
          <ApplicationRows items={applications.data.items} />
        ) : (
          <Empty
            title="Здесь начнётся ваша история"
            description="Создайте первую заявку или познакомьтесь с процессом на готовом сценарии."
          >
            <a className="button button-primary" href="#/applications/new">
              Создать заявку
              <ArrowUpRight size={16} />
            </a>
          </Empty>
        ))}
      <div className="section-heading">
        <h2>
          <Sparkles size={18} /> Попробуйте весь процесс
        </h2>
        <span>Четыре синтетических сценария</span>
      </div>
      <div className="scenario-grid">
        {scenarios.data?.map((s, i) => (
          <a
            href={`#/applications/new?scenario=${s.code}`}
            className="scenario-card"
            key={s.code}
          >
            <span className="scenario-index">
              0{i + 1}
              <ArrowUpRight size={16} />
            </span>
            <span className="eyebrow">{s.label}</span>
            <h3>{s.title}</h3>
            <p>{s.description}</p>
          </a>
        ))}
      </div>
      {scenarios.error && (
        <ResourceState {...scenarios} onRetry={scenarios.refresh} />
      )}
      <div className="section-heading">
        <h2>Полезно для вашего бизнеса</h2>
        <span>Материалы под продукт и этап заявки</span>
      </div>
      <div className="article-grid">
        {feed.data?.map((a) => (
          <article className="article-card" key={a.id}>
            <span className="eyebrow">{a.tag}</span>
            <h3>{a.title}</h3>
            <p>{article === a.id ? a.body : `${a.body.slice(0, 105)}…`}</p>
            <button
              className="text-button"
              onClick={() => setArticle(article === a.id ? null : a.id)}
              aria-expanded={article === a.id}
            >
              {article === a.id ? "Свернуть" : "Читать материал"}
              <ArrowRight size={15} />
            </button>
          </article>
        ))}
      </div>
    </>
  );
}
