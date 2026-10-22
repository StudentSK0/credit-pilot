import { useSyncExternalStore } from 'react';
import { FileText, LayoutDashboard, BriefcaseBusiness, Inbox } from 'lucide-react';
import type { Role } from '../api/auth';

export const navigation = {
  CLIENT: [
    { path: '/', title: 'Обзор кабинета', icon: LayoutDashboard },
    { path: '/products', title: 'Кредитные продукты', icon: BriefcaseBusiness },
    { path: '/applications', title: 'Мои заявки', icon: FileText },
  ],
  BANK_EMPLOYEE: [
    { path: '/', title: 'Рабочий кабинет', icon: LayoutDashboard },
    { path: '/review', title: 'Обработка заявок', icon: Inbox },
  ],
};

function subscribe(callback: () => void) {
  window.addEventListener('hashchange', callback);
  return () => window.removeEventListener('hashchange', callback);
}
function getPath() { return window.location.hash.slice(1) || '/'; }

// Hash routes work with both the existing nginx and Vite without server changes.
export function useNavigation(role: Role) {
  const path = useSyncExternalStore(subscribe, getPath);
  const items = navigation[role];
  return { path, items, current: items.find(item => item.path === path) };
}
