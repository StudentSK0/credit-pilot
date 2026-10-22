// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest';

beforeEach(() => { vi.resetModules(); sessionStorage.clear(); });
it('после загрузки модуля восстанавливает CSRF той же вкладки', async () => {
  sessionStorage.setItem('credit-pilot.csrf', 'stored-token');
  const csrf = await import('../api/csrf');
  expect(csrf.getCsrfToken()).toBe('stored-token');
  csrf.setCsrfToken(null);
  expect(sessionStorage.length).toBe(0);
});
it('при запрете sessionStorage работает с токеном в памяти', async () => {
  const storage = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new DOMException('Denied'); });
  const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Denied'); });
  const csrf = await import('../api/csrf');
  expect(csrf.getCsrfToken()).toBeNull();
  csrf.setCsrfToken('memory-token');
  expect(csrf.getCsrfToken()).toBe('memory-token');
  storage.mockRestore(); write.mockRestore();
});
