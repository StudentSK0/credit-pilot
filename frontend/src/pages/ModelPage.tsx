import {
  Activity,
  ArrowUpRight,
  Database,
  GitBranch,
  ShieldCheck,
} from "lucide-react";
import { useResource, number } from "../api/business";
import { Heading, Metric, ResourceState } from "../components/Business";

type Metrics = {
  n: number;
  positive_rate: number;
  roc_auc: number;
  average_precision: number;
  brier: number;
  confusion_matrix: { tp: number; fp: number; tn: number; fn: number };
  calibration_bins: {
    bin: number;
    count: number;
    predicted: number;
    observed: number;
  }[];
};
type Model = {
  model_version: string;
  target: string;
  features: string[];
  limitation: string;
  report: {
    seed: number;
    train_n: number;
    validation_n: number;
    test_n: number;
    threshold: number;
    test: Metrics;
    constant_baseline: Metrics;
  };
};
export function ModelPage() {
  const result = useResource<Model>("/api/bank/model");
  const m = result.data;
  const t = m?.report.test;
  return (
    <>
      <Heading
        eyebrow="ОБЪЯСНИМЫЙ РИСК"
        title="Модель, которую можно проверить"
        description="Открытые веса, воспроизводимое обучение и сохранённые входы каждой оценки."
      />
      <ResourceState {...result} onRetry={result.refresh} />
      {m && t && (
        <>
          <section className="model-hero">
            <Activity size={34} />
            <div>
              <span className="eyebrow">{m.model_version}</span>
              <h2>Логистическая регрессия</h2>
              <p>
                {m.target}. Четыре признака, локальное выполнение, вклад каждого
                признака в оценку.
              </p>
            </div>
            <span className="badge">Только синтетические данные</span>
          </section>
          <div className="metrics-grid">
            <Metric
              label="ROC-AUC"
              value={number(t.roc_auc, 3)}
              detail="Разделение классов на тесте"
            />
            <Metric
              label="Average precision"
              value={number(t.average_precision, 3)}
              detail={`Доля просрочек: ${number(t.positive_rate * 100, 1)}%`}
            />
            <Metric
              label="Brier score"
              value={number(t.brier, 3)}
              detail={`Константный baseline: ${number(m.report.constant_baseline.brier, 3)}`}
            />
            <Metric
              label="Отложенный тест"
              value={m.report.test_n}
              detail="Независимых синтетических компаний"
            />
          </div>
          <div className="dashboard-grid">
            <section className="panel">
              <div className="panel-heading">
                <h2>Как обучена модель</h2>
                <GitBranch size={22} />
              </div>
              <ol className="model-steps">
                <li>
                  <span>01</span>
                  <div>
                    <h3>Генерация данных</h3>
                    <p>
                      6 000 независимых вымышленных компаний. Метки — случайные
                      исходы синтетического механизма с шумом, а не копия
                      балльного скоринга.
                    </p>
                  </div>
                </li>
                <li>
                  <span>02</span>
                  <div>
                    <h3>Разделение до обучения</h3>
                    <p>
                      {m.report.train_n} — обучение, {m.report.validation_n} —
                      подбор порога, {m.report.test_n} — финальная проверка.
                      Нормализация рассчитана только на обучении.
                    </p>
                  </div>
                </li>
                <li>
                  <span>03</span>
                  <div>
                    <h3>Воспроизводимость</h3>
                    <p>
                      Фиксированный seed {m.report.seed}, генератор и веса в
                      репозитории. Модель не использует решение сотрудника,
                      статус или другие признаки из будущего.
                    </p>
                  </div>
                </li>
              </ol>
              <div className="feature-pills">
                {m.features.map((f) => (
                  <span key={f}>{f}</span>
                ))}
              </div>
            </section>
            <section className="panel">
              <div className="panel-heading">
                <h2>Калибровка на синтетическом тесте</h2>
                <Database size={22} />
              </div>
              <p className="panel-description">
                Средний прогноз и наблюдаемая доля событий по группам. Малые
                группы менее устойчивы.
              </p>
              <div className="calibration-chart" aria-label="Калибровка модели">
                {t.calibration_bins.map((b) => (
                  <div className="calibration-bin" key={b.bin}>
                    <div className="calibration-bars">
                      <span
                        style={{ height: `${b.predicted * 100}%` }}
                        title={`Прогноз ${number(b.predicted * 100)}%`}
                      />
                      <span
                        style={{ height: `${b.observed * 100}%` }}
                        title={`Факт ${number(b.observed * 100)}%`}
                      />
                    </div>
                    <strong>
                      {b.bin * 10}–{(b.bin + 1) * 10}%
                    </strong>
                    <small>n={b.count}</small>
                  </div>
                ))}
              </div>
              <div className="chart-legend">
                <span>
                  <i />
                  Прогноз
                </span>
                <span>
                  <i />
                  Наблюдаемый исход
                </span>
              </div>
            </section>
          </div>
          <section className="panel model-limitations">
            <ShieldCheck size={23} />
            <div>
              <h2>Граница применимости</h2>
              <p>{m.limitation}</p>
              <p>
                Эти метрики показывают, насколько модель воспроизводит заданный
                синтетический механизм. Для реального применения нужны данные с
                исходами, внешняя валидация, проверка стабильности и калибровки.
                Порог {number(m.report.threshold)} выбран на валидации для
                отчёта и не используется для автоматического решения.
              </p>
            </div>
          </section>
          <a className="text-button" href="#/review">
            Посмотреть оценку в реальном досье прототипа
            <ArrowUpRight size={17} />
          </a>
        </>
      )}
    </>
  );
}
