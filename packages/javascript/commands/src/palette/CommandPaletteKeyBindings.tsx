import { useEffect } from "react";
import { CommandDescriptor } from "../commands/types";
import { useAppDispatch } from "../store";
import { openCommandPalette, closeCommandPalette, setPaletteSelection } from "../ui/uiSlice";


interface Props {
    commands: CommandDescriptor[];
    activeIndex: number;
    onExecute: (id: string) => void;
    onClose: () => void;
}

/**
 * Handles global keyboard shortcuts for command palette
 */
export function CommandPaletteKeybinds({
    commands,
    activeIndex,
    onExecute,
    onClose,
}: Props) {
    const dispatch = useAppDispatch();

    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            // --- open palette
            if ((e.ctrlKey && e.key === "p") || (e.ctrlKey && e.key === "Enter")) {
                e.preventDefault();
                dispatch(openCommandPalette());
                return;
            }

            // --- close palette
            if (e.key === "Escape") {
                e.preventDefault();
                dispatch(closeCommandPalette());
                onClose();
                return;
            }

            // --- navigation
            if (e.key === "ArrowDown") {
                e.preventDefault();
                const next = Math.min(activeIndex + 1, commands.length - 1);
                dispatch(setPaletteSelection(next));
                return;
            }

            if (e.key === "ArrowUp") {
                e.preventDefault();
                const prev = Math.max(activeIndex - 1, 0);
                dispatch(setPaletteSelection(prev));
                return;
            }

            // --- execute
            if (e.key === "Enter" && commands[activeIndex]) {
                e.preventDefault();
                onExecute(commands[activeIndex].id);
                return;
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [dispatch, commands, activeIndex, onExecute, onClose]);

    return null;
}
