use std::env;
use std::io::IsTerminal;

/// Returns true when `INQUIRER_AI_MODE` equals "human" (case-insensitive).
pub fn is_human_mode() -> bool {
    env::var("INQUIRER_AI_MODE")
        .unwrap_or_default()
        .eq_ignore_ascii_case("human")
}

/// Returns true when a socket transport has been explicitly requested:
/// either `INQUIRER_AI_SOCKET` is set and non-empty, or
/// `INQUIRER_AI_MODE` equals "agent" (case-insensitive).
pub fn is_socket_requested() -> bool {
    let socket_set = env::var("INQUIRER_AI_SOCKET")
        .map(|v| !v.is_empty())
        .unwrap_or(false);
    if socket_set {
        return true;
    }
    env::var("INQUIRER_AI_MODE")
        .unwrap_or_default()
        .eq_ignore_ascii_case("agent")
}

/// Agent mode is active when NOT human AND (a socket was requested OR stdin
/// is not a TTY).
///
/// This implements the unified mode-detection contract (R3): a plain piped
/// non-TTY with no MODE/SOCKET stays in agent (stdio) mode for backwards
/// compatibility, while `INQUIRER_AI_SOCKET` (even on a TTY) activates agent
/// mode.
pub fn is_agent_mode() -> bool {
    if is_human_mode() {
        return false;
    }
    is_socket_requested() || !std::io::stdin().is_terminal()
}
