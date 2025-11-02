import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { executeCommand } from "../commands";
import { selectFilteredCommands } from "../../selectors/commandSelectors";
import { CommandPaletteKeybinds } from "../palette/CommandPaletteKeyBindings";
import uiReducer from "../ui/uiSlice";
import {
  selectIsPaletteOpen,
  selectPaletteQuery,
  selectPaletteSelection,
  selectSearchHistory,
} from "../ui/uiSelectors";
import {
  closeCommandPalette,
  resetPalette,
  setPaletteQuery,
} from "../ui/uiSlice";
import { store, useAppDispatch, useAppSelector } from "../store";
import { injectReducer } from "../store/injectReducer";

const MAX_RESULTS = 20;


export function CommandPalette() {
  const dispatch = useAppDispatch();
  const isOpen = useAppSelector(selectIsPaletteOpen);
  const { commands } = useAppSelector(selectFilteredCommands);
  const query = useAppSelector(selectPaletteQuery);
  const selectedIndex = useAppSelector(selectPaletteSelection);
  const history = useAppSelector(selectSearchHistory);
  const [container, setContainer] = useState<HTMLElement | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const itemRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  useEffect(() => {
    injectReducer("ui", uiReducer);
  }, []);


  useEffect(() => {
    setContainer(document.getElementById("topbar-slot") as HTMLElement | null);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
    return () => cancelAnimationFrame(frame);
  }, [isOpen]);

  // useEffect(() => {
  //   persistPaletteHistory(history);
  // }, [history]);

  const visibleCommands = useMemo(
    () => commands.slice(0, MAX_RESULTS),
    [commands]
  );

  const activeIndex = useMemo(() => {
    if (visibleCommands.length === 0) {
      return -1;
    }
    return Math.min(selectedIndex, visibleCommands.length - 1);
  }, [visibleCommands, selectedIndex]);

  const handleClose = () => {
    dispatch(resetPalette());
    dispatch(closeCommandPalette());
  };

  const runCommand = (commandId: string) => {
    executeCommand(commandId, {
      dispatch,
      getState: store.getState,
    });
    handleClose();
  };

  useEffect(() => {
    if (!isOpen) return;
    if (!listRef.current) return;
    const command = visibleCommands[activeIndex];
    if (!command) return;
    const node = itemRefs.current.get(command.id);
    if (!node) return;
    // Ensure the selected command stays within view while navigating
    node.scrollIntoView({ block: "nearest" });
  }, [activeIndex, isOpen, visibleCommands]);

  const paletteContent =
    isOpen && container
      ? createPortal(
        <div className="pointer-events-auto flex w-full justify-center px-4">
          <div className="w-full max-w-xl overflow-hidden rounded-xl border border-slate-700/70 bg-slate-900/95 text-slate-100 shadow-2xl backdrop-blur-md transition">
            <input
              ref={inputRef}
              type="text"
              className="w-full rounded-t-xl border-b border-slate-700/60 bg-transparent px-4 py-3 text-base font-medium text-slate-100 outline-none focus:bg-slate-900 focus:ring-1 focus:ring-sky-400"
              placeholder="Search commands..."
              value={query}
              onChange={(event) => dispatch(setPaletteQuery(event.target.value))}
            />

            {history.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2 px-4 pb-3 text-sm text-slate-400">
                {history.slice(0, 5).map((entry) => (
                  <button
                    key={`${entry.query}-${entry.timestamp}`}
                    type="button"
                    className="rounded-md border border-slate-700/60 px-2 py-1 transition hover:border-slate-500 hover:bg-slate-800/70 hover:text-slate-200"
                    onClick={() => {
                      dispatch(setPaletteQuery(entry.query));
                      requestAnimationFrame(() => inputRef.current?.focus());
                    }}
                  >
                    {entry.query}
                  </button>
                ))}
              </div>
            )}

            <ul
              ref={listRef}
              className="max-h-72 overflow-y-auto divide-y divide-slate-800 px-2 py-2 mt-2"
            >
              {visibleCommands.length === 0 && (
                <li className="px-4 py-3 text-sm text-slate-400">
                  No commands match "{query}".
                </li>
              )}
              {visibleCommands.map((command, index) => {
                const isSelected = index === activeIndex;
                return (
                  <li key={command.id}>
                    <button
                      type="button"
                      ref={(element) => {
                        if (element) {
                          itemRefs.current.set(command.id, element);
                        } else {
                          itemRefs.current.delete(command.id);
                        }
                      }}
                      className={`w-full text-left px-4 py-3 transition ${isSelected
                        ? "bg-sky-500/20 text-slate-50"
                        : "hover:bg-slate-800/80"
                        }`}
                      onClick={() => runCommand(command.id)}
                    >
                      <div className="text-sm font-medium">
                        {command.title}
                      </div>
                      <div className="text-xs text-slate-400">{command.id}</div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>,
        container
      )
      : null;

  return (
    <>
      <CommandPaletteKeybinds
        commands={visibleCommands}
        activeIndex={activeIndex}
        onExecute={runCommand}
        onClose={handleClose}
      />
      {paletteContent}
    </>
  );
}
