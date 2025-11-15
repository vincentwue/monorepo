export interface IdeaNodeView {
  id: string;
  parentId: string | null;
  title: string;
  note?: string;
  rank: number;
}

/**
 * Direction for reordering a node among its siblings.
 * For now we support simple "up"/"down" moves.
 */
export type ReorderDirection = "up" | "down";

export interface IdeasTreeState {
  nodes: IdeaNodeView[];
  loading: boolean;
  error: string | null;
}
