import { ArrowDown, ArrowUpRight, BriefcaseBusiness, FileText, LayoutGrid, ShieldCheck } from 'lucide-react';
import { useSession } from '../auth/SessionProvider';

export function ClientDashboard() {
  const { user } = useSession();
  return <>
    <div className="page-heading"><div><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Ваш бизнес. Ваши возможности.</h1><p>Всё для следующего шага — в одном месте.</p></div><span className="badge"><span className="prototype-dot" />Прототип T06</span></div>
    <section className="welcome-card"><div className="welcome-content"><span className="welcome-kicker">НА ПУТИ К РАЗВИТИЮ</span><h2>Бизнес растёт.<br />Кабинет готовится к старту.</h2><p>Скоро здесь можно будет выбрать кредитный продукт, подать заявку и следить за её рассмотрением.</p><a className="button button-light" href="#/products">Кредитные продукты<ArrowUpRight size={18} aria-hidden="true" /></a></div><div className="growth-art" aria-hidden="true"><span className="growth-ring" /><span className="growth-bar bar-one" /><span className="growth-bar bar-two" /><span className="growth-bar bar-three" /><span className="growth-arrow"><ArrowUpRight size={66} strokeWidth={1.3} /></span><span className="growth-label">СЛЕДУЮЩИЙ ШАГ</span></div></section>
    <div className="section-heading"><h2>Разделы кабинета</h2><span>Постепенно открываем возможности</span></div>
    <div className="section-cards">
      <a href="#/products" className="section-card"><div className="card-top"><span className="feature-icon"><BriefcaseBusiness size={23} aria-hidden="true" /></span><ArrowUpRight size={20} aria-hidden="true" /></div><h3>Кредитные продукты</h3><p>Каталог и условия финансирования для задач вашего бизнеса.</p><span className="badge">В разработке</span></a>
      <a href="#/applications" className="section-card"><div className="card-top"><span className="feature-icon feature-icon-peach"><FileText size={23} aria-hidden="true" /></span><ArrowUpRight size={20} aria-hidden="true" /></div><h3>Мои заявки</h3><p>Заявки, текущие этапы рассмотрения и история изменений.</p><span className="badge">В разработке</span></a>
    </div>
    <section className="profile-card"><div className="profile-title"><span className="feature-icon feature-icon-neutral"><LayoutGrid size={21} aria-hidden="true" /></span><div><h2>Ваша учётная запись</h2><p>Данные подтверждены серверной сессией</p></div><ShieldCheck size={22} className="profile-shield" aria-hidden="true" /></div><dl className="profile-data"><div><dt>Пользователь</dt><dd>№ {user!.id}</dd></div><div><dt>Роль</dt><dd>Предприниматель</dd></div><div><dt>Идентификатор компании</dt><dd>{user!.company_id ?? 'Не указан'}</dd></div><div><dt>Среда</dt><dd>Демонстрационная</dd></div></dl></section>
    <p className="bottom-hint"><ArrowDown size={15} aria-hidden="true" />Каталог и формы заявок появятся после подключения следующих этапов.</p>
  </>;
}
