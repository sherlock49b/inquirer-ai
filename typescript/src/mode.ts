import * as tty from "node:tty";

export function isAgentMode(): boolean {
  const env = (process.env["INQUIRER_AI_MODE"] ?? "").toLowerCase();
  if (env === "agent") return true;
  if (env === "human") return false;
  return !tty.isatty(0);
}
