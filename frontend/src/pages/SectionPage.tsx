import { DevelopmentState } from '../components/Feedback';

const sections: Record<string, { subtitle: string; title: string; description: string }> = {
  '/products': {
    subtitle: 'Финансирование для следующего шага.',
    title: 'Готовим каталог продуктов',
    description: 'Условия и выбор продукта появятся после подключения каталога. Кредитные предложения пока недоступны.',
  },
  '/applications': {
    subtitle: 'Все этапы заявки в одном месте.',
    title: 'Готовим раздел ваших заявок',
    description: 'Список, создание и отправка заявок появятся на следующем этапе. Данные заявок сейчас не загружаются.',
  },
  '/review': {
    subtitle: 'Единое пространство для рассмотрения.',
    title: 'Готовим обработку заявок',
    description: 'Очередь и досье будут подключены позже. Банковские решения и скоринг пока недоступны.',
  },
};

export function SectionPage({ path, title, isClient }: { path: string; title: string; isClient: boolean }) {
  const section = sections[path];
  return <>
    <div className="page-heading">
      <div>
        <span className="eyebrow">{isClient ? 'КАБИНЕТ БИЗНЕСА' : 'КАБИНЕТ СОТРУДНИКА'}</span>
        <h1>{title}</h1>
        <p>{section.subtitle}</p>
      </div>
    </div>
    <DevelopmentState title={section.title} description={section.description} />
  </>;
}
