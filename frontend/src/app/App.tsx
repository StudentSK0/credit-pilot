import { useState } from "react";
import { useSession } from "../auth/SessionProvider";
import { BackendStatus } from "../components/BackendStatus";
import { Brand } from "../components/Brand";
import { LoadingState, UnavailableState } from "../components/Feedback";
import { Layout } from "../components/Layout";
import { LoginPage } from "../pages/LoginPage";
import { ClientDashboard } from "../pages/ClientDashboard";
import { BankDashboard } from "../pages/BankDashboard";
import { ProductsPage } from "../pages/ProductsPage";
import { ApplicationsPage } from "../pages/ApplicationsPage";
import { ApplicationForm } from "../pages/ApplicationForm";
import { DossierPage } from "../pages/DossierPage";
import { ModelPage } from "../pages/ModelPage";
import { useNavigation } from "./navigation";

export function App() {
  const session = useSession();
  if (session.status === "loading" || session.status === "unavailable") {
    return (
      <div className="bootstrap-shell">
        <header>
          <Brand />
          <BackendStatus />
        </header>
        {session.status === "loading" ? (
          <LoadingState />
        ) : (
          <UnavailableState
            message={session.notice}
            onRetry={() => void session.refresh()}
          />
        )}
      </div>
    );
  }
  if (session.status === "guest") {
    return (
      <>
        <LoginPage />
        <div className="login-connection">
          <BackendStatus />
        </div>
      </>
    );
  }
  return <AuthenticatedApp key={session.user!.id} />;
}

function AuthenticatedApp() {
  const { user } = useSession();
  const [reauthenticate, setReauthenticate] = useState(false);
  const { path, current } = useNavigation(user!.role);
  if (reauthenticate)
    return (
      <LoginPage reauthenticate onCancel={() => setReauthenticate(false)} />
    );

  let content;
  const [route, search = ""] = path.split("?");
  const bank = user!.role === "BANK_EMPLOYEE";
  const detail = route.match(/^\/(applications|review)\/(\d+)(\/edit)?$/);
  if (!current)
    content = (
      <div className="center-state">
        <h1>Раздел недоступен</h1>
        <p>Такого раздела нет в вашем кабинете.</p>
        <a href="#/" className="button button-secondary">
          На главную
        </a>
      </div>
    );
  else if (path === "/")
    content = user!.role === "CLIENT" ? <ClientDashboard /> : <BankDashboard />;
  else if (route === "/products") content = <ProductsPage />;
  else if (route === "/model") content = <ModelPage />;
  else if (route === "/applications/new")
    content = (
      <ApplicationForm key={path} query={new URLSearchParams(search)} />
    );
  else if (detail && detail[3] && !bank)
    content = (
      <ApplicationForm
        key={path}
        id={Number(detail[2])}
        query={new URLSearchParams(search)}
      />
    );
  else if (detail)
    content = <DossierPage key={path} id={Number(detail[2])} bank={bank} />;
  else content = <ApplicationsPage bank={bank} />;
  return (
    <Layout onReauthenticate={() => setReauthenticate(true)}>{content}</Layout>
  );
}
