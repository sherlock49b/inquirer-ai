use crate::agent::{agent_receive, agent_send};
use crate::choice::{Choice, ChoiceItem};
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{format_success, KeyInput, ListRenderer};
use crate::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use serde_json::{json, Value};

pub type SearchSource = Box<dyn Fn(&str) -> Vec<ChoiceItem>>;

pub struct SearchConfig {
    pub message: String,
    pub source: SearchSource,
    pub page_size: usize,
}

impl SearchConfig {
    pub fn new(
        message: impl Into<String>,
        source: impl Fn(&str) -> Vec<ChoiceItem> + 'static,
    ) -> Self {
        Self {
            message: message.into(),
            source: Box::new(source),
            page_size: 10,
        }
    }
}

pub fn search(config: SearchConfig) -> Result<Value> {
    if is_agent_mode() {
        search_agent(&config)
    } else {
        search_terminal(&config)
    }
}

fn search_agent(config: &SearchConfig) -> Result<Value> {
    let initial: Vec<Value> = (config.source)("")
        .iter()
        .filter_map(|c| match c {
            ChoiceItem::Choice(c) if !c.is_disabled() => {
                Some(ChoiceItem::Choice(c.clone()).to_json())
            }
            _ => None,
        })
        .collect();

    let payload = json!({
        "type": "search",
        "message": config.message,
        "default": null,
        "searchable": true,
        "choices": initial,
    });
    agent_send(&payload)?;
    agent_receive()
}

fn search_terminal(config: &SearchConfig) -> Result<Value> {
    let t = &DEFAULT_THEME;
    let filtered = get_filtered(&config.source, "");
    let mut cursor: usize = 0;

    ListRenderer::enable_raw()?;
    let mut renderer = ListRenderer::new();

    loop {
        let header = format!(
            "{}{}{}  {BOLD}{}{RESET}",
            ansi_color(t.question),
            t.sym_question,
            RESET,
            config.message,
        );

        let end = filtered.len().min(config.page_size);
        let mut items: Vec<(String, String)> = Vec::new();
        if filtered.is_empty() {
            items.push((ansi_color(t.muted), "  No matches".to_string()));
        } else {
            for (i, f) in filtered.iter().enumerate().take(end) {
                if i == cursor {
                    items.push((
                        ansi_color(t.highlight),
                        format!("{} {}", t.sym_pointer, f.name),
                    ));
                } else {
                    items.push((String::new(), format!("  {}", f.name)));
                }
            }
        }

        renderer.render(&header, &items);

        match crate::terminal::read_key()? {
            KeyInput::Up if !filtered.is_empty() => {
                cursor = (cursor + filtered.len() - 1) % filtered.len();
            }
            KeyInput::Down if !filtered.is_empty() => {
                cursor = (cursor + 1) % filtered.len();
            }
            KeyInput::Enter => {
                renderer.clear();
                ListRenderer::disable_raw()?;
                if !filtered.is_empty() {
                    let choice = &filtered[cursor];
                    let display = choice.short.as_deref().unwrap_or(&choice.name);
                    eprintln!("{}", format_success(&config.message, display));
                    return Ok(choice.value.clone());
                }
                return Err(InquirerError::PromptAborted("No selection made".into()));
            }
            KeyInput::CtrlC => {
                renderer.clear();
                ListRenderer::disable_raw()?;
                return Err(InquirerError::PromptAborted(
                    "Prompt aborted by user".into(),
                ));
            }
            _ => {}
        }
    }
}

fn get_filtered(source: &dyn Fn(&str) -> Vec<ChoiceItem>, term: &str) -> Vec<Choice> {
    source(term)
        .into_iter()
        .filter_map(|c| match c {
            ChoiceItem::Choice(c) if !c.is_disabled() => Some(c),
            _ => None,
        })
        .collect()
}
