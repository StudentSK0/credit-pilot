import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ChevronRight, LogOut, Menu, ShieldCheck, X } from 'lucide-react';
import { useSession } from '../auth/SessionProvider';
import { errorMessage } from '../api/client';
import { useNavigation } from '../app/navigation';
import { BackendStatus } from './BackendStatus';
import { Brand } from './Brand';
import { ErrorNotice } from './Feedback';
import { Button } from './ui/button';

export function Layout({ children, onReauthenticate }: { children: ReactNode; onReauthenticate: () => void }) {
  const session = useSession();
  const user = session.user!;
  const { items, path, current } = useNavigation(user.role);
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const menuButton = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const isClient = user.role === 'CLIENT';
  useEffect(() => {
    if (!menuOpen) return;
    closeButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      menuButton.current?.focus();
    };
  }, [menuOpen]);
  async function logout() {
    if (!session.csrfReady) { onReauthenticate(); return; }
    setBusy(true); setError('');
    try { await session.logout(); }
    catch (error) { setError(errorMessage(error, 'logout')); }
    finally { setBusy(false); }
  }

  return <div className="app-shell">
    <a href="#main-content" className="skip-link" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>К содержимому</a>
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-brand"><Brand /><button ref={closeButton} className="mobile-close icon-button" aria-label="Закрыть меню" onClick={() => setMenuOpen(false)}><X size={20} /></button></div>
      <div className="workspace-label"><span className="workspace-avatar">{isClient ? 'Б' : 'С'}</span><div><strong>{isClient ? 'Кабинет бизнеса' : 'Кабинет сотрудника'}</strong><small>Тестовая среда</small></div></div>
      <span className="nav-caption">{isClient ? 'МОЙ БИЗНЕС' : 'РАБОЧЕЕ ПРОСТРАНСТВО'}</span>
      <nav aria-label={isClient ? 'Навигация предпринимателя' : 'Навигация сотрудника'}>
        {items.map(({ path: href, title, icon: Icon }) => <a key={href} href={`#${href}`} aria-current={path === href ? 'page' : undefined} onClick={() => { setMenuOpen(false); setError(''); }}><Icon size={19} aria-hidden="true" /><span>{title}</span>{path === href && <span className="nav-active-dot" />}</a>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="demo-note"><ShieldCheck size={19} aria-hidden="true" /><strong>Без реальных операций</strong><p>Только синтетические данные и учебные сценарии.</p></div>
        <div className="user-summary"><span className="user-avatar">{isClient ? 'К' : 'Б'}</span><div><strong>{isClient ? 'Предприниматель' : 'Сотрудник банка'}</strong><small>Пользователь № {user.id}</small></div></div>
        <Button className="logout-button" variant="ghost" onClick={() => void logout()} disabled={busy}><LogOut size={17} aria-hidden="true" />{busy ? 'Выходим…' : 'Выйти из кабинета'}</Button>
      </div>
    </aside>
    {menuOpen && <button className="menu-backdrop" aria-label="Закрыть навигацию" onClick={() => setMenuOpen(false)} />}
    <div className="main-shell" inert={menuOpen}>
      <header className="topbar"><button ref={menuButton} className="mobile-menu icon-button" aria-label="Открыть меню" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Menu size={22} /></button><div className="breadcrumbs">Credit Pilot<ChevronRight size={14} aria-hidden="true" /><span>{current?.title ?? 'Страница не найдена'}</span></div><BackendStatus /></header>
      <main className="content" id="main-content" tabIndex={-1}>
        {!session.csrfReady && <div className="notice notice-warning" role="status"><ShieldCheck size={21} aria-hidden="true" /><div><strong>Для действий нужен повторный вход</strong><p>Сессия активна. Войдите ещё раз, чтобы восстановить защиту этой вкладки и выйти из кабинета.</p></div><Button size="small" variant="secondary" onClick={onReauthenticate}>Повторный вход</Button></div>}
        {error && <ErrorNotice>{error}</ErrorNotice>}
        {children}
      </main>
      <footer className="app-footer"><span>© 2026 Credit Pilot</span><span>Учебный прототип · Не является продуктом банка</span></footer>
    </div>
  </div>;
}
