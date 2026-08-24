import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";

// No StrictMode: it double-invokes effects and doubles every startup
// request. DOOF manages its own polling lifecycles explicitly.
createRoot(document.getElementById("root")!).render(<App />);
