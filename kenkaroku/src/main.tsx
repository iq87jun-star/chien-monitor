import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { applyTokens } from "./ui/theme/tokens";
import "./ui/theme/global.css";
import { App } from "./ui/App";

applyTokens();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
