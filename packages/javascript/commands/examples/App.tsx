import { registerCommand } from "@/commands";
import { store } from "@/store";
import { CommandPalette } from "@/ui/CommandPalette";
import { useEffect } from "react";
import { Provider } from "react-redux";

export function App() {
  useEffect(() => {
    registerCommand({
      id: "demo.hello",
      title: "Say Hello",
      handler: () => alert("🎵 Hello from Command Orchestra Example!"),
    });
    registerCommand({
      id: "demo.log",
      title: "Log Time",
      handler: () => console.log("🕐", new Date().toLocaleTimeString()),
    });
  }, []);

  return (
    <Provider store={store}>
      <div id="topbar-slot" className="fixed top-4 left-0 w-full z-50" />
      <CommandPalette />
      <div className="p-6 text-center text-slate-200">
        <h1 className="text-2xl font-semibold mb-3">Command Orchestra Example</h1>
        <p className="text-slate-400">
          Press <kbd>Ctrl+Enter</kbd> or <kbd>Ctrl+P</kbd> to open the palette.
        </p>
      </div>
    </Provider>
  );
}
