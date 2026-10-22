import { useState } from 'react';
import { useSession } from '../auth/SessionProvider';
import { BackendStatus } from '../components/BackendStatus';
import { Brand } from '../components/Brand';
import { LoadingState, UnavailableState } from '../components/Feedback';
import { Layout } from '../components/Layout';
import { LoginPage } from '../pages/LoginPage';
import { ClientDashboard } from '../pages/ClientDashboard';
import { BankDashboard } from '../pages/BankDashboard';
import { SectionPage } from '../pages/SectionPage';
import { useNavigation } from './navigation';

export function App() {
  const session = useSession();
  if (session.status === 'loading' || session.status === 'unavailable') {
    return <div className="bootstrap-shell">
      <header><Brand /><BackendStatus /></header>
      {session.status === 'loading'
        ? <LoadingState />
        : <UnavailableState message={session.notice} onRetry={() => void session.refresh()} />}
    </div>;
  }
  if (session.status === 'guest') {
    return <><LoginPage /><div className="login-connection"><BackendStatus /></div></>;
  }
  return <AuthenticatedApp key={session.user!.id} />;
}

function AuthenticatedApp() {
  const { user } = useSession();
  const [reauthenticate, setReauthenticate] = useState(false);
  const { path, current } = useNavigation(user!.role);
  if (reauthenticate) return <LoginPage reauthenticate onCancel={() => setReauthenticate(false)} />;

  let content;
  if (!current) content = <div className="center-state"><h1>Раздел недоступен</h1><p>Такого раздела нет в вашем кабинете.</p><a href="#/" className="button button-secondary">На главную</a></div>;
  else if (path === '/') content = user!.role === 'CLIENT' ? <ClientDashboard /> : <BankDashboard />;
  else content = <SectionPage path={path} title={current.title} isClient={user!.role === 'CLIENT'} />;
  return <Layout onReauthenticate={() => setReauthenticate(true)}>{content}</Layout>;
}
