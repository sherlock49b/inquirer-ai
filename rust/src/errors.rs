use std::fmt;

#[derive(Debug)]
pub enum InquirerError {
    Validation(String),
    InvalidChoice(String),
    PromptAborted(String),
    Editor(String),
    Io(std::io::Error),
}

impl fmt::Display for InquirerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Validation(msg) => write!(f, "Validation error: {msg}"),
            Self::InvalidChoice(msg) => write!(f, "Invalid choice: {msg}"),
            Self::PromptAborted(msg) => write!(f, "Prompt aborted: {msg}"),
            Self::Editor(msg) => write!(f, "Editor error: {msg}"),
            Self::Io(err) => write!(f, "I/O error: {err}"),
        }
    }
}

impl std::error::Error for InquirerError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(err) => Some(err),
            _ => None,
        }
    }
}

impl From<std::io::Error> for InquirerError {
    fn from(err: std::io::Error) -> Self {
        Self::Io(err)
    }
}

impl From<serde_json::Error> for InquirerError {
    fn from(err: serde_json::Error) -> Self {
        Self::Validation(format!(
            "Invalid JSON: {err}. Expected JSON like: {{\"answer\": \"<value>\"}}"
        ))
    }
}

pub type Result<T> = std::result::Result<T, InquirerError>;
