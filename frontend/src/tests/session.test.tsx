// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../app/App';
import { SessionProvider } from '../auth/SessionProvider';
import { setCsrfToken } from '../api/csrf';
import type { Role, User } from '../api/auth';

const client: User = { id: 7, role: 'CLIENT', company_id: 3 };
const employee: User = { id: 9, role: 'BANK_EMPLOYEE', company_id: null };
const response = (body: unknown, status = 200) => new Response(body === null ? null : JSON.stringify(body), { status });

function backend(initial: User | null = null) {
  let current = initial;
  let logoutStatus = 204;
  let loginStatus = 200;
  const fetchMock = vi.fn(async (url: RequestInfo | URL, options?: RequestInit) => {
    if (url === '/api/health') return response({ status: 'ok', database: 'ok' });
    if (url === '/api/me') return current ? response(current) : response({}, 401);
    if (url === '/api/auth/login') {
      if (loginStatus !== 200) return response({}, loginStatus);
      const body = JSON.parse(String(options?.body));
      current = body.login === 'bank' ? employee : client;
      return response({ ...current, csrf_token: 'test-csrf' });
    }
    if (url === '/api/auth/logout') {
      if (logoutStatus === 204) { current = null; return response(null, 204); }
      return response({ detail: logoutStatus === 403 ? 'CSRF token is invalid' : 'error' }, logoutStatus);
    }
    throw new Error('Unexpected request');
  });
  vi.stubGlobal('fetch', fetchMock);
  return { fetchMock, expire: () => { current = null; }, failLogout: (status: number) => { logoutStatus = status; }, failLogin: (status: number) => { loginStatus = status; } };
}
function openApp() { return render(<SessionProvider><App /></SessionProvider>); }
async function signIn(login = 'client-a') {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('Логин'), login);
  await user.type(screen.getByLabelText('Пароль'), 'test-input');
  await user.click(screen.getByRole('button', { name: 'Войти в кабинет' }));
}

beforeEach(() => { window.location.hash = '/'; sessionStorage.clear(); localStorage.clear(); setCsrfToken(null); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('серверная сессия и навигация', () => {
  it.each(['CLIENT', 'BANK_EMPLOYEE'] as Role[])('вход %s использует серверную роль и cookie', async role => {
    const server = backend();
    localStorage.setItem('role', role === 'CLIENT' ? 'BANK_EMPLOYEE' : 'CLIENT');
    openApp();
    await signIn(role === 'CLIENT' ? 'client-a' : 'bank');
    const nav = await screen.findByRole('navigation', { name: role === 'CLIENT' ? 'Навигация предпринимателя' : 'Навигация сотрудника' });
    expect(within(nav).queryByText('Мои заявки') !== null).toBe(role === 'CLIENT');
    expect(within(nav).queryByText('Обработка заявок') !== null).toBe(role === 'BANK_EMPLOYEE');
    const login = server.fetchMock.mock.calls.find(([path]) => path === '/api/auth/login')!;
    expect(login[1]?.credentials).toBe('same-origin');
    expect(Object.keys(JSON.parse(String(login[1]?.body))).sort()).toEqual(['login', 'password']);
    expect(sessionStorage.getItem('credit-pilot.csrf')).toBe('test-csrf');
    expect(sessionStorage.length).toBe(1);
    expect(document.querySelector('input[type="password"]')).toBeNull();
  });

  it('восстанавливает кабинет через /me и отправляет сохранённый CSRF при выходе', async () => {
    const server = backend(client);
    sessionStorage.setItem('credit-pilot.csrf', 'persisted-token');
    setCsrfToken('persisted-token');
    openApp();
    await screen.findByRole('navigation');
    await userEvent.click(screen.getByRole('button', { name: 'Выйти из кабинета' }));
    await screen.findByLabelText('Логин');
    const logout = server.fetchMock.mock.calls.find(([path]) => path === '/api/auth/logout')!;
    expect(new Headers(logout[1]?.headers).get('X-CSRF-Token')).toBe('persisted-token');
    expect(logout[1]?.credentials).toBe('same-origin');
    expect(sessionStorage.getItem('credit-pilot.csrf')).toBeNull();
  });

  it('при пустом CSRF предлагает повторный вход и не отправляет logout', async () => {
    const server = backend(client);
    openApp();
    await screen.findByText('Для действий нужен повторный вход');
    await userEvent.click(screen.getByRole('button', { name: 'Выйти из кабинета' }));
    await screen.findByRole('heading', { name: 'Подтвердите вход' });
    expect(server.fetchMock.mock.calls.some(([path]) => path === '/api/auth/logout')).toBe(false);
    await signIn();
    await screen.findByRole('navigation');
    expect(screen.queryByText('Для действий нужен повторный вход')).toBeNull();
  });

  it('при неверном CSRF очищает токен и требует входа без повтора команды', async () => {
    const server = backend(client);
    setCsrfToken('stale-token'); server.failLogout(403);
    openApp(); await screen.findByRole('navigation');
    await userEvent.click(screen.getByRole('button', { name: 'Выйти из кабинета' }));
    await screen.findByText('Для действий нужен повторный вход');
    expect(sessionStorage.length).toBe(0);
    expect(server.fetchMock.mock.calls.filter(([path]) => path === '/api/auth/logout')).toHaveLength(1);
  });

  it('не изображает успешный выход при ошибке сервера', async () => {
    const server = backend(client); setCsrfToken('test-csrf'); server.failLogout(503);
    openApp(); await screen.findByRole('navigation');
    await userEvent.click(screen.getByRole('button', { name: 'Выйти из кабинета' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Не удалось подтвердить выход');
    expect(screen.queryByRole('navigation')).not.toBeNull();
    expect(sessionStorage.getItem('credit-pilot.csrf')).toBe('test-csrf');
  });

  it('401 после утраты сессии очищает локальное состояние', async () => {
    const server = backend(client); setCsrfToken('test-csrf');
    openApp(); await screen.findByRole('navigation');
    server.expire(); fireEvent(window, new Event('focus'));
    await screen.findByLabelText('Логин');
    expect(screen.queryByText('Сессия завершена. Войдите в кабинет снова.')).not.toBeNull();
    expect(sessionStorage.length).toBe(0);
    expect(screen.queryByRole('navigation')).toBeNull();
  });

  it('обновление страницы заново проверяет сессию на сервере', async () => {
    const server = backend(client); setCsrfToken('test-csrf');
    const view = openApp(); await screen.findByRole('navigation'); view.unmount();
    openApp(); await screen.findByRole('navigation');
    expect(server.fetchMock.mock.calls.filter(([path]) => path === '/api/me')).toHaveLength(2);
  });

  it('чужой маршрут роли недоступен и разделы явно отмечены', async () => {
    backend(employee); openApp(); await screen.findByRole('navigation');
    window.location.hash = '/products'; fireEvent(window, new HashChangeEvent('hashchange'));
    await screen.findByRole('heading', { name: 'Раздел недоступен' });
    await userEvent.click(within(screen.getByRole('navigation')).getByText('Обработка заявок'));
    await screen.findByText('Готовим обработку заявок');
    expect(screen.queryByText('В разработке')).not.toBeNull();
  });

  it('заготовки CLIENT не запрашивают ещё не подключённые API', async () => {
    const server = backend(client); openApp(); await screen.findByRole('navigation');
    await userEvent.click(within(screen.getByRole('navigation')).getByText('Кредитные продукты'));
    await screen.findByText('Готовим каталог продуктов');
    await userEvent.click(within(screen.getByRole('navigation')).getByText('Мои заявки'));
    await screen.findByText('Готовим раздел ваших заявок');
    expect(server.fetchMock.mock.calls.every(([path]) => path === '/api/me' || path === '/api/health')).toBe(true);
  });

  it('поздний 401 от старой проверки не сбрасывает новый вход', async () => {
    const server = backend(client); openApp(); await screen.findByRole('navigation');
    let finishOldRequest!: (value: Response) => void;
    server.fetchMock.mockImplementationOnce(() => new Promise<Response>(done => { finishOldRequest = done; }));
    fireEvent(window, new Event('focus'));
    await userEvent.click(screen.getByRole('button', { name: 'Повторный вход' }));
    await signIn(); await screen.findByRole('navigation');
    await act(async () => { finishOldRequest(response({}, 401)); });
    await waitFor(() => expect(sessionStorage.getItem('credit-pilot.csrf')).toBe('test-csrf'));
    expect(screen.queryByRole('navigation')).not.toBeNull();
  });

  it('мобильное меню закрывается клавишей Escape', async () => {
    backend(client); openApp(); await screen.findByRole('navigation');
    const open = screen.getByRole('button', { name: 'Открыть меню' });
    await userEvent.click(open);
    expect(open.getAttribute('aria-expanded')).toBe('true');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(open.getAttribute('aria-expanded')).toBe('false');
  });

  it.each([401, 403, 422])('понятно обрабатывает ошибку входа %i', async status => {
    const server = backend(); server.failLogin(status); openApp(); await signIn();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain(status === 401 ? 'Неверный логин' : status === 403 ? 'Сервер запретил' : 'Проверьте поля');
    expect((screen.getByLabelText('Пароль') as HTMLInputElement).value).toBe('');
    expect(sessionStorage.length).toBe(0);
  });

  it('показывает недоступность backend и позволяет повторить проверку', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    openApp(); await screen.findByRole('heading', { name: 'Не удалось открыть кабинет' });
    backend(client);
    await userEvent.click(screen.getByRole('button', { name: 'Повторить проверку' }));
    await screen.findByRole('navigation');
  });

  it('не принимает неизвестную серверную роль', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ id: 1, role: 'ADMIN', company_id: null })));
    openApp(); await screen.findByText('Сервер вернул неожиданные данные. Повторите проверку сессии.');
    expect(screen.queryByRole('navigation')).toBeNull();
  });

  it('показывает загрузку до ответа /me', async () => {
    let resolve!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn((path: string) => path === '/api/me'
      ? new Promise<Response>(done => { resolve = done; }) : Promise.resolve(response({ status: 'ok', database: 'ok' }))));
    openApp(); expect(screen.queryByText('Открываем кабинет')).not.toBeNull();
    resolve(response({}, 401));
    await waitFor(() => expect(screen.queryByLabelText('Логин')).not.toBeNull());
  });
});
