import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
// theme.gen.css 可选存在(ShadeApp(theme=...) 才发射):glob 命中零个是合法 no-op
import.meta.glob("./generated/theme.gen.css", { eager: true });
import App from "./generated/app.gen";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
