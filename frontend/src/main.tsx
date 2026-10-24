import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { SessionProvider } from "./auth/SessionProvider";
import "./style.css";

createRoot(document.getElementById("root")!).render(
  <SessionProvider>
    <App />
  </SessionProvider>,
);

import "./workflow.css";
