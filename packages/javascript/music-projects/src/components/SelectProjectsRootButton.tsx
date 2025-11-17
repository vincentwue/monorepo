import { useState } from "react";

export function SelectProjectsRootButton() {
    const [path, setPath] = useState<string | null>(null);

    async function handleSelect() {
        try {
            // Ask user to choose the music projects folder
            const dirHandle = await (window as any).showDirectoryPicker();

            // DirectoryHandle.name is only the folder name, not the full absolute path
            // Browsers do NOT reveal absolute paths for security reasons.
            // But we can store the handle itself OR a virtual id OR a permission grant.
            // For now, we store the handle in-memory and treat its name as the visible label.

            // EXAMPLE: using the directory name as “pseudo root path”
            // (you can replace this with real electron path resolution later)
            const pseudoPath = dirHandle.name;

            setPath(pseudoPath);
            // setProjectsRootPath(pseudoPath);

            console.log("Selected directory:", dirHandle);
        } catch (err) {
            console.warn("User cancelled directory selection", err);
        }
    }

    return (
        <div>
            <button onClick={handleSelect}>Select Music Projects Root</button>
            {path && <div>Selected: {path}</div>}
        </div>
    );
}
