import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "../src/index.ts"; // ensure source commands loaded
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
