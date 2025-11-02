import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

import { store } from "@monorepo/store";
import { Provider as ReduxProvider } from "react-redux";
import App from "./App";

console.debug("[boot] main.tsx loaded; Redux store connected");

const root = document.getElementById("root")!;
ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <ReduxProvider store={store}>
      <App />
    </ReduxProvider>
  </React.StrictMode>
);
