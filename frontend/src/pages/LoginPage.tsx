import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  Eye,
  EyeOff,
  FileText,
  Layers3,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { useSession } from "../auth/SessionProvider";
import { errorMessage } from "../api/client";
import { Brand } from "../components/Brand";
import { ErrorNotice } from "../components/Feedback";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

export function LoginPage({
  reauthenticate = false,
  onCancel,
}: {
  reauthenticate?: boolean;
  onCancel?: () => void;
}) {
  const session = useSession();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    setBusy(true);
    try {
      await session.login(login.trim(), password);
      window.location.hash = "/";
      onCancel?.();
    } catch (error) {
      setError(errorMessage(error, "login"));
    } finally {
      setPassword("");
      setBusy(false);
    }
  }

  return (
    <main className="login-shell" id="main-content">
      <section className="login-story">
        <Brand />
        <div className="story-content">
          <span className="eyebrow">
            <span className="tiny-line" />
            ФИНАНСЫ С ПОНЯТНЫМ МАРШРУТОМ
          </span>
          <h1>
            Большие планы.
            <br />
            <span>Понятный путь.</span>
          </h1>
          <p>От идеи для бизнеса до кредитного решения — в одном кабинете.</p>
          <div className="journey" aria-label="Путь заявки">
            <div className="journey-node">
              <Layers3 size={20} aria-hidden="true" />
              <span>Выбор продукта</span>
              <span className="journey-number">01</span>
            </div>
            <div className="journey-line" />
            <div className="journey-node">
              <FileText size={20} aria-hidden="true" />
              <span>Заявка и сведения</span>
              <span className="journey-number">02</span>
            </div>
            <div className="journey-line" />
            <div className="journey-node">
              <ShieldCheck size={20} aria-hidden="true" />
              <span>Рассмотрение</span>
              <span className="journey-number">03</span>
            </div>
          </div>
          <span className="story-caption">
            От заявки до моделируемой выдачи
          </span>
        </div>
        <div className="story-footer">
          <span className="prototype-dot" />
          Учебный прототип для хакатона Альфа-Банка
        </div>
      </section>
      <section className="login-panel" aria-label="Вход в кабинет">
        <span className="badge login-badge">ДЕМОНСТРАЦИОННАЯ ВЕРСИЯ</span>
        <div className="login-form-wrap">
          <span className="login-lock">
            <LockKeyhole size={22} aria-hidden="true" />
          </span>
          <h2>{reauthenticate ? "Подтвердите вход" : "Добро пожаловать"}</h2>
          <p className="login-description">
            {reauthenticate
              ? "Сессия активна, но для действий в этой вкладке нужно войти ещё раз."
              : "Войдите, чтобы открыть свой кабинет."}
          </p>
          {session.notice && !reauthenticate && (
            <p className="notice notice-info" role="status">
              {session.notice}
            </p>
          )}
          {error && <ErrorNotice>{error}</ErrorNotice>}
          <form onSubmit={submit} aria-busy={busy} autoComplete="off">
            <label htmlFor="login">Логин</label>
            <Input
              id="login"
              name="login"
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              placeholder="Введите логин"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              required
              maxLength={255}
              disabled={busy}
            />
            <label htmlFor="password">Пароль</label>
            <div className="password-field">
              <Input
                id="password"
                name="password"
                type={visible ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Введите пароль"
                autoComplete="off"
                required
                maxLength={1024}
                disabled={busy}
              />
              <button
                type="button"
                className="password-toggle"
                aria-label={visible ? "Скрыть пароль" : "Показать пароль"}
                aria-pressed={visible}
                onClick={() => setVisible(!visible)}
              >
                {visible ? <EyeOff size={19} /> : <Eye size={19} />}
              </button>
            </div>
            <Button
              type="submit"
              className="w-full mt-7"
              disabled={busy || !login.trim() || !password}
            >
              {busy ? "Входим…" : "Войти в кабинет"}
              {!busy && <ArrowRight size={18} aria-hidden="true" />}
            </Button>
            <span className="sr-only" role="status">
              {busy ? "Проверяем данные на сервере" : ""}
            </span>
          </form>
          {reauthenticate && (
            <Button className="w-full mt-3" variant="ghost" onClick={onCancel}>
              Вернуться в кабинет
            </Button>
          )}
          <div className="login-help">
            <ShieldCheck size={18} aria-hidden="true" />
            <p>
              Кабинет откроется по роли вашей учётной записи. Используйте
              тестовый аккаунт команды.
            </p>
          </div>
        </div>
        <p className="login-disclaimer">
          Credit Pilot — учебный прототип.
          <br />
          Не является официальным продуктом банка.
        </p>
      </section>
    </main>
  );
}
