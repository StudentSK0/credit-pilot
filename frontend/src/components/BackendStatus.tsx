import { useEffect, useState } from "react";
import { apiRequest, ApiError } from "../api/client";

export function BackendStatus() {
  const [status, setStatus] = useState<
    "checking" | "ok" | "database" | "offline"
  >("checking");
  useEffect(() => {
    let active = true;
    let timer: number;
    async function check() {
      let next: typeof status = "offline";
      try {
        const data = await apiRequest("/api/health", { public: true });
        if (
          data !== null &&
          typeof data === "object" &&
          "status" in data &&
          data.status === "ok" &&
          "database" in data &&
          data.database === "ok"
        )
          next = "ok";
      } catch (error) {
        if (error instanceof ApiError && error.status === 503)
          next = "database";
      }
      if (active) {
        setStatus(next);
        timer = window.setTimeout(() => void check(), 5000);
      }
    }
    void check();
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, []);
  const text = {
    checking: "Проверяем соединение",
    ok: "Сервер и БД доступны",
    database: "База данных недоступна",
    offline: "Сервер недоступен",
  }[status];
  return (
    <div
      className={`backend-status status-${status}`}
      role="status"
      title="Проверка /api/health каждые 5 секунд"
    >
      <span className="status-dot" />
      {text}
    </div>
  );
}
