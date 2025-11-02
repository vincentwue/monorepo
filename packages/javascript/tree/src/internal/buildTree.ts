// src/internal/buildTree.ts

/**
 * Build a recursive tree from a flat array of items.
 *
 * Generic — works for any record with id / parent_id / rank.
 *
 * @param items  Flat array of records
 * @param opts.idKey      property name for id (default "_id")
 * @param opts.parentKey  property name for parent id (default "parent_id")
 * @param opts.rankKey    property name for ordering (default "rank")
 * @param opts.sort       whether to recursively sort children
 */
export function buildTree<T extends Record<string, any>>(
  items: T[],
  opts: {
    idKey?: keyof T;
    parentKey?: keyof T;
    rankKey?: keyof T;
    sort?: boolean;
  } = {},
): (T & { children: (T & { children: any[] })[] })[] {
  const {
    idKey = "_id" as keyof T,
    parentKey = "parent_id" as keyof T,
    rankKey = "rank" as keyof T,
    sort = true,
  } = opts;

  const map: Record<string, T & { children: any[] }> = {};
  for (const item of items) {
    const id = String(item[idKey]);
    map[id] = { ...(item as any), children: [] };
  }

  const roots: (T & { children: any[] })[] = [];
  for (const item of Object.values(map)) {
    const parentId = item[parentKey];
    if (parentId && map[parentId as any]) {
      map[parentId as any].children.push(item);
    } else {
      roots.push(item);
    }
  }

  if (sort) {
    const sortRecursively = (nodes: (T & { children: any[] })[]) => {
      nodes.sort(
        (a, b) => ((a[rankKey] as number) ?? 0) - ((b[rankKey] as number) ?? 0),
      );
      for (const n of nodes) if (n.children.length) sortRecursively(n.children);
    };
    sortRecursively(roots);
  }

  return roots;
}
