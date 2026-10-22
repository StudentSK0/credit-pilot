import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { authApi, type User } from '../api/auth';
import { ApiError, errorMessage, onAuthFailure } from '../api/client';
import { getCsrfToken, setCsrfToken } from '../api/csrf';

type Session = {
  status: 'loading' | 'guest' | 'authenticated' | 'unavailable';
  user: User | null;
  csrfReady: boolean;
  notice: string;
};
type SessionContextValue = Session & {
  login: (login: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};
const SessionContext = createContext<SessionContextValue | null>(null);
const guest: Session = { status: 'guest', user: null, csrfReady: false, notice: '' };

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ ...guest, status: 'loading' });
  const generation = useRef(0);
  const mutating = useRef(false);
  const clear = useCallback((notice?: string) => {
    generation.current++;
    setCsrfToken(null);
    setSession(current => ({
      ...guest,
      notice: notice ?? (current.status === 'authenticated' ? 'Сессия завершена. Войдите в кабинет снова.' : ''),
    }));
  }, []);

  const refresh = useCallback(async () => {
    if (mutating.current) return;
    const request = ++generation.current;
    try {
      const user = await authApi.me();
      if (request === generation.current) setSession({ status: 'authenticated', user, csrfReady: !!getCsrfToken(), notice: '' });
    } catch (error) {
      if (request !== generation.current) return;
      if (error instanceof ApiError && error.status === 401) clear();
      else setSession({ ...guest, status: 'unavailable', notice: errorMessage(error) });
    }
  }, [clear]);

  useEffect(() => {
    const unsubscribe = onAuthFailure(reason => {
      if (reason === 'expired') clear('Сессия завершена. Войдите в кабинет снова.');
      else {
        setCsrfToken(null);
        setSession(current => ({ ...current, csrfReady: false }));
      }
    });
    void refresh();
    const onFocus = () => { void refresh(); };
    window.addEventListener('focus', onFocus);
    return () => { unsubscribe(); window.removeEventListener('focus', onFocus); generation.current++; };
  }, [clear, refresh]);

  async function login(login: string, password: string) {
    if (mutating.current) return;
    mutating.current = true;
    generation.current++;
    try {
      const result = await authApi.login(login, password);
      setCsrfToken(result.csrf);
      setSession({ status: 'authenticated', user: result.user, csrfReady: true, notice: '' });
    } finally { mutating.current = false; }
  }

  async function logout() {
    if (mutating.current) return;
    mutating.current = true;
    generation.current++;
    try { await authApi.logout(); clear('Вы вышли из кабинета. Серверная сессия отозвана.'); }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) clear('Сессия уже завершена.');
      else throw error;
    } finally { mutating.current = false; }
  }

  return <SessionContext.Provider value={{ ...session, login, logout, refresh }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error('SessionProvider is required');
  return context;
}
