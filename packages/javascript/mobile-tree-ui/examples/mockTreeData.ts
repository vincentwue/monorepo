import type { MobileTreeNode } from "../src/hooks/useMobileTreeNavigator"

export const vibrantTree: MobileTreeNode[] = [
    { id: "ideas", parentId: null, title: "Ideas", rank: 0 },
    { id: "projects", parentId: null, title: "Projects", rank: 1 },
    { id: "archive", parentId: null, title: "Archive", rank: 2 },
    { id: "idea-wellness", parentId: "ideas", title: "Wellness App", rank: 0 },
    { id: "idea-mentor", parentId: "ideas", title: "Mentor Platform", rank: 1 },
    { id: "idea-finance", parentId: "ideas", title: "Finance Tracker", rank: 2 },
    { id: "project-nova", parentId: "projects", title: "Project Nova", rank: 0 },
    { id: "project-echo", parentId: "projects", title: "Project Echo", rank: 1 },
    { id: "nova-design", parentId: "project-nova", title: "Design Sprint", rank: 0 },
    { id: "nova-build", parentId: "project-nova", title: "Build Phase", rank: 1 },
    { id: "archive-2023", parentId: "archive", title: "Ideas 2023", rank: 0 },
    { id: "archive-2022", parentId: "archive", title: "Ideas 2022", rank: 1 }
]
