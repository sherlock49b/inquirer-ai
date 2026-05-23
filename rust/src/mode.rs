use std::env;
use std::io::IsTerminal;

pub fn is_agent_mode() -> bool {
    match env::var("INQUIRER_AI_MODE")
        .unwrap_or_default()
        .to_lowercase()
        .as_str()
    {
        "agent" => true,
        "human" => false,
        _ => !std::io::stdin().is_terminal(),
    }
}
