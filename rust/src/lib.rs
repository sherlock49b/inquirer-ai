#![deny(warnings)]

pub mod agent;
pub mod choice;
pub mod errors;
pub mod mode;
pub mod prompts;
pub mod socket;
pub mod terminal;
pub mod theme;

pub use agent::{agent_send_error, agent_send_validation_error};
pub use choice::{Choice, ChoiceItem, Separator};
pub use errors::{InquirerError, Result};
pub use mode::is_agent_mode;
pub use socket::get_socket_transport;
pub use theme::{Theme, DEFAULT_THEME};

pub use prompts::autocomplete::{autocomplete, AutocompleteConfig};
pub use prompts::checkbox::{checkbox, CheckboxConfig};
pub use prompts::confirm::{confirm, ConfirmConfig};
pub use prompts::editor::{editor, EditorConfig};
pub use prompts::expand::{expand, ExpandChoice, ExpandConfig};
pub use prompts::number::{number, NumberConfig};
pub use prompts::password::{password, PasswordConfig};
pub use prompts::path::{path, PathConfig};
pub use prompts::rawlist::{rawlist, RawlistConfig};
pub use prompts::search::{search, SearchConfig};
pub use prompts::select::{select, SelectConfig};
pub use prompts::text::{text, TextConfig};
