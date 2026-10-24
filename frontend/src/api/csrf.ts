const STORAGE_KEY = "credit-pilot.csrf";

function readStoredToken(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

let token = readStoredToken();

export function getCsrfToken() {
  return token;
}

export function setCsrfToken(value: string | null) {
  token = value;
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, value);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Restricted storage: the in-memory token still works until reload.
  }
}
