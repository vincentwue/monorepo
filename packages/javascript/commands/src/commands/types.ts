import type { AppDispatch, RootState } from "../store";

export interface CommandContext {
  dispatch: AppDispatch;
  getState: () => RootState;
}

export interface CommandDescriptor {
  id: string;
  title: string;
  handler: (ctx: CommandContext, args?: any) => void;
}
