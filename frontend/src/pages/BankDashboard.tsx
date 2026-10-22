import { ArrowUpRight, ClipboardList, ShieldCheck } from 'lucide-react';
import { useSession } from '../auth/SessionProvider';
import { DevelopmentState } from '../components/Feedback';

export function BankDashboard() {
  const { user } = useSession();
  return <><div className="page-heading"><div><span className="eyebrow">КАБИНЕТ СОТРУДНИКА</span><h1>Рабочее пространство</h1><p>Единый маршрут рассмотрения заявок бизнеса.</p></div><span className="badge">Прототип T06</span></div>
    <section className="bank-intro"><span className="feature-icon"><ClipboardList size={27} aria-hidden="true" /></span><div><h2>Подготовка к работе с заявками</h2><p>Очередь, досье и история рассмотрения появятся на следующих этапах.</p></div><a href="#/review" className="button button-secondary">К обработке<ArrowUpRight size={17} aria-hidden="true" /></a></section>
    <DevelopmentState title="Рабочий кабинет в разработке" description="Очередь заявок пока не подключена. Здесь нет демонстрационных заявок, показателей или кредитных решений." />
    <section className="profile-card"><div className="profile-title"><ShieldCheck size={23} aria-hidden="true" /><div><h2>Доступ сотрудника</h2><p>Права определяет сервер</p></div></div><dl className="profile-data"><div><dt>Пользователь</dt><dd>№ {user!.id}</dd></div><div><dt>Роль</dt><dd>Сотрудник банка</dd></div><div><dt>Текущий доступ API</dt><dd>Чтение заявки и истории</dd></div></dl></section>
  </>;
}
