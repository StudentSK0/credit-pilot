import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  const [status, setStatus] = useState('Проверяем соединение…');

  useEffect(() => {
    const controller = new AbortController();

    async function checkHealth() {
      try {
        const response = await fetch('/api/health', {
          signal: controller.signal,
          cache: 'no-store',
        });
        const health = await response.json();

        if (response.ok && health.status === 'ok' && health.database === 'ok') {
          setStatus('Backend работает. PostgreSQL доступен.');
        } else if (response.status === 503) {
          setStatus('Backend доступен. PostgreSQL недоступен.');
        } else {
          setStatus('Backend вернул ошибку.');
        }
      } catch {
        if (!controller.signal.aborted) {
          setStatus('Нет соединения с backend.');
        }
      }
    }

    void checkHealth();
    const timer = window.setInterval(() => void checkHealth(), 5000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  return (
    <main>
      <h1>Credit Pilot</h1>
      <p>Умный кабинет предпринимателя</p>
      <p role="status" aria-live="polite">{status}</p>
      <small>Статус обновляется каждые 5 секунд.</small>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
