import * as tty from "node:tty";

/** True if INQUIRER_AI_MODE == "human" (case-insensitive). */
export function isHumanMode(): boolean {
  return (process.env.INQUIRER_AI_MODE ?? "").toLowerCase() === "human";
}

/**
 * A socket transport is requested when INQUIRER_AI_SOCKET is set & non-empty,
 * OR INQUIRER_AI_MODE == "agent" (case-insensitive) (R3).
 */
export function isSocketRequested(): boolean {
  const sock = process.env.INQUIRER_AI_SOCKET;
  if (sock !== undefined && sock !== "") return true;
  return (process.env.INQUIRER_AI_MODE ?? "").toLowerCase() === "agent";
}

/**
 * Agent (non-interactive) mode. is_agent = (not human) AND
 * (socket_requested OR stdin-is-not-a-TTY). A plain piped non-TTY with no
 * MODE/SOCKET stays in agent (stdio) mode for backwards compatibility (R3).
 */
export function isAgentMode(): boolean {
  if (isHumanMode()) return false;
  if (isSocketRequested()) return true;
  return !tty.isatty(0);
}
