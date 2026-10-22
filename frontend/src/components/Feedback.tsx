import { AlertCircle, LoaderCircle, ServerOff, Wrench } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from './ui/button';

export function ErrorNotice({ children }: { children: ReactNode }) {
  return <div className="notice notice-error" role="alert"><AlertCircle size={18} aria-hidden="true" /><span>{children}</span></div>;
}

export function LoadingState() {
  return <div className="center-state" role="status"><LoaderCircle className="animate-spin" size={26} aria-hidden="true" /><h1>Открываем кабинет</h1><p>Проверяем вашу сессию на сервере…</p></div>;
}

export function UnavailableState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="center-state"><ServerOff size={32} aria-hidden="true" /><h1>Не удалось открыть кабинет</h1><p role="alert">{message}</p><Button onClick={onRetry}>Повторить проверку</Button></div>;
}

export function DevelopmentState({ title, description }: { title: string; description: string }) {
  return <section className="development-state"><span className="development-icon"><Wrench size={26} aria-hidden="true" /></span><span className="badge">В разработке</span><h2>{title}</h2><p>{description}</p><p className="muted text-sm">Раздел появится на следующем этапе прототипа.</p></section>;
}
