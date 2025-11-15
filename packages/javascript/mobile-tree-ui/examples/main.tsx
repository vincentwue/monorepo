import React from "react"
import ReactDOM from "react-dom/client"
import { MobileTreeNavigator } from "../src"
import { vibrantTree } from "./mockTreeData"
import "./styles.css"
import "../src/styles.css"

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
        <div className="example-shell">
            <MobileTreeNavigator initialNodes={vibrantTree} />
        </div>
    </React.StrictMode>,
)
