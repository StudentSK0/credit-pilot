import { ArrowUpRight, BriefcaseBusiness, Factory, Check } from "lucide-react";
import { useResource, type Product, money, number } from "../api/business";
import { Heading, ResourceState } from "../components/Business";

export function ProductsPage() {
  const products = useResource<Product[]>("/api/products");
  return (
    <>
      <Heading
        eyebrow="ФИНАНСИРОВАНИЕ БИЗНЕСА"
        title="Деньги под ваши задачи"
        description="Два продукта. Понятные условия. Выберите, что поможет вашему бизнесу сейчас."
      />
      <ResourceState {...products} onRetry={products.refresh} />
      <div className="products-grid">
        {products.data?.map((p) => (
          <article
            className={`product-card ${p.code === "WORKING_CAPITAL" ? "product-working" : ""}`}
            key={p.code}
          >
            <div className="product-top">
              <span className="product-icon">
                {p.code === "EQUIPMENT" ? (
                  <Factory size={30} />
                ) : (
                  <BriefcaseBusiness size={30} />
                )}
              </span>
              <span className="badge">Для малого бизнеса</span>
            </div>
            <h2>
              {p.code === "EQUIPMENT"
                ? "Оборудование для роста"
                : "Оборотные средства"}
            </h2>
            <p>
              {p.code === "EQUIPMENT"
                ? "Новый станок, техника или производственная линия. Инвестируйте в возможности бизнеса."
                : "Закупки, сырьё и новые заказы. Поддержите ежедневную работу и расширьте ассортимент."}
            </p>
            <div className="product-amount">
              <small>Финансирование до</small>
              <strong>{money(p.max_amount)}</strong>
            </div>
            <dl className="product-terms">
              <div>
                <dt>Учебная ставка</dt>
                <dd>{number(Number(p.annual_rate) * 100)}% годовых</dd>
              </div>
              <div>
                <dt>Срок</dt>
                <dd>
                  {p.min_term}–{p.max_term} месяцев
                </dd>
              </div>
              <div>
                <dt>От</dt>
                <dd>{money(p.min_amount)}</dd>
              </div>
            </dl>
            <div className="product-benefits">
              <span>
                <Check size={16} />
                Заявка и решение в одном кабинете
              </span>
              <span>
                <Check size={16} />
                Понятное объяснение условий
              </span>
            </div>
            <a
              className="button button-primary"
              href={`#/applications/new?product=${p.code}`}
            >
              Выбрать продукт
              <ArrowUpRight size={17} />
            </a>
          </article>
        ))}
      </div>
      <p className="fineprint">
        Условия предложены командой для учебного прототипа. Это синтетические
        продукты; реальные кредитные предложения не формируются.
      </p>
    </>
  );
}
