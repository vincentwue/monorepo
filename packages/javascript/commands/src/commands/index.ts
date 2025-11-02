import type { CommandContext, CommandDescriptor } from "./types";

const registry: Record<string, CommandDescriptor> = {};

export function registerCommand(descriptor: CommandDescriptor) {
  registry[descriptor.id] = descriptor;
}

export function listCommands(): CommandDescriptor[] {
  return Object.values(registry);
}

export function executeCommand(id: string, ctx: CommandContext) {
  const cmd = registry[id];
  if (!cmd) return console.warn("[commands] Unknown command", id);
  cmd.handler(ctx);
}
