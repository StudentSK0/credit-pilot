import { getCsrfToken } from './csrf';

export class ApiError extends Error {
  constructor(public status: number, public reason: 'http' | 'network' | 'csrf' | 'contract' = 'http') {
    super('API request failed');
  }
}

type AuthFailure = 'expired' | 'csrf';
const listeners = new Set<(reason: AuthFailure) => void>();
export function onAuthFailure(listener: (reason: AuthFailure) => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
function authFailure(reason: AuthFailure) { listeners.forEach(listener => listener(reason)); }

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  public?: boolean;
};

export async function apiRequest(path: `/api/${string}`, options: RequestOptions = {}): Promise<unknown> {
  const method = options.method ?? 'GET';
  const headers = new Headers({ Accept: 'application/json' });
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  if (method !== 'GET' && !options.public) {
    const csrf = getCsrfToken();
    if (!csrf) {
      authFailure('csrf');
      throw new ApiError(403, 'csrf');
    }
    headers.set('X-CSRF-Token', csrf);
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(path, {
      method, headers, credentials: 'same-origin', cache: 'no-store',
      signal: controller.signal,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const payload: unknown = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const isCsrf = response.status === 403 && payload !== null && typeof payload === 'object'
        && 'detail' in payload && payload.detail === 'CSRF token is invalid';
      if (!options.public && response.status === 401) authFailure('expired');
      if (!options.public && isCsrf) authFailure('csrf');
      throw new ApiError(response.status, isCsrf ? 'csrf' : 'http');
    }
    return payload;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'network');
  } finally { window.clearTimeout(timeout); }
}

export function errorMessage(error: unknown, action: 'login' | 'logout' | 'session' = 'session'): string {
  if (!(error instanceof ApiError)) return 'Не удалось обработать ответ сервера. Попробуйте ещё раз.';
  if (error.reason === 'csrf') return 'Для продолжения войдите повторно. Защитный токен этой вкладки больше недействителен.';
  if (error.reason === 'contract') return 'Сервер вернул неожиданные данные. Повторите проверку сессии.';
  if (error.status === 401) return action === 'login'
    ? 'Неверный логин или пароль. Проверьте данные и попробуйте ещё раз.'
    : 'Сессия завершена. Войдите в кабинет снова.';
  if (error.status === 403) return 'Сервер запретил действие. Проверьте адрес приложения или обратитесь к команде прототипа.';
  if (error.status === 422) return 'Проверьте поля: логин — от 1 до 255 символов, пароль — от 1 до 1024 символов.';
  if (error.status === 0 || error.status >= 500) return action === 'logout'
    ? 'Не удалось подтвердить выход на сервере. Проверьте соединение и повторите выход.'
    : 'Нет соединения с сервером или сервер временно недоступен. Попробуйте ещё раз.';
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.';
}
