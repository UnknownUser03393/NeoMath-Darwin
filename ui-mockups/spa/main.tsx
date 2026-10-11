import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { NeoMathApp } from "../components/NeoMathApp";
/* Tailwind/app first, KaTeX last so formula styles win over resets. */
import "../app/globals.css";
import "katex/dist/katex.min.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("NeoMath SPA root element #root is missing");
}

createRoot(root).render(
  <StrictMode>
    <NeoMathApp />
  </StrictMode>,
);
