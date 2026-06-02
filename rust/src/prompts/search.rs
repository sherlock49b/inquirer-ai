use crate::agent::agent_prompt_with_retry;
use crate::choice::{Choice, ChoiceItem};
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{format_success, poll_key, KeyInput, ListRenderer};
use crate::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use serde_json::{json, Value};
use std::sync::mpsc;
use std::sync::Arc;
use std::time::{Duration, Instant};

/// Debounce delay before calling the source function after a keystroke.
/// Prevents hammering a slow source (HTTP, DB, etc.) on every character
/// while the user is still typing.
const SEARCH_DEBOUNCE: Duration = Duration::from_millis(150);

/// Timeout used when polling for terminal events inside the render loop.
/// Short enough to feel responsive, long enough to avoid busy-spinning.
const POLL_TIMEOUT: Duration = Duration::from_millis(50);

/// A synchronous search source function that receives a search term and
/// returns matching choices.
///
/// The source is called in a background thread so that slow sources
/// (HTTP requests, database queries, file-system walks, etc.) do not
/// block the terminal render loop. The closure must therefore be
/// `Send + Sync`.
pub type SearchSource = Box<dyn Fn(&str) -> Vec<ChoiceItem> + Send + Sync>;

pub struct SearchConfig {
    pub message: String,
    pub source: SearchSource,
    pub page_size: usize,
}

impl SearchConfig {
    pub fn new(
        message: impl Into<String>,
        source: impl Fn(&str) -> Vec<ChoiceItem> + Send + Sync + 'static,
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
        search_terminal(config)
    }
}

fn search_agent(config: &SearchConfig) -> Result<Value> {
    // Resolve the initial (empty-term) choices once: these are advertised in
    // the payload AND used to resolve the answer (match -> value).
    let initial_choices: Vec<Choice> = (config.source)("")
        .into_iter()
        .filter_map(|c| match c {
            ChoiceItem::Choice(c) if !c.is_disabled() => Some(c),
            _ => None,
        })
        .collect();

    let initial: Vec<Value> = initial_choices
        .iter()
        .map(|c| ChoiceItem::Choice(c.clone()).to_json())
        .collect();

    let payload = json!({
        "type": "search",
        "message": config.message,
        "default": null,
        "searchable": true,
        "choices": initial,
    });

    agent_prompt_with_retry(&payload, move |answer| {
        // Type-aware value match OR exact name match against an advertised
        // choice -> return that choice's value. Otherwise return the answer
        // verbatim (dynamic-source-safe).
        for c in &initial_choices {
            if answer == c.value || answer.as_str() == Some(c.name.as_str()) {
                return Ok(c.value.clone());
            }
        }
        Ok(answer)
    })
}

/// Message sent from a background search thread back to the render loop.
struct SearchResult {
    term: String,
    choices: Vec<Choice>,
}

fn search_terminal(config: SearchConfig) -> Result<Value> {
    let t = &DEFAULT_THEME;
    let source = Arc::new(config.source);

    // Channel for receiving results from background search threads.
    let (tx, rx) = mpsc::channel::<SearchResult>();

    // State
    let mut input = String::new();
    let mut filtered: Vec<Choice> = Vec::new();
    let mut cursor: usize = 0;
    let mut loading = true;
    let mut last_queried = String::new();
    let mut last_keystroke: Option<Instant> = None;
    let mut pending_term: Option<String> = None;

    ListRenderer::enable_raw()?;
    let mut renderer = ListRenderer::new();

    // Kick off the initial (empty-term) source fetch in a background thread.
    {
        let src = Arc::clone(&source);
        let sender = tx.clone();
        std::thread::spawn(move || {
            let choices = get_filtered(&*src, "");
            let _ = sender.send(SearchResult {
                term: String::new(),
                choices,
            });
        });
    }

    loop {
        // --- drain channel: pick up any results from background threads ---
        while let Ok(result) = rx.try_recv() {
            // Only accept results that match the latest query we issued.
            if result.term == last_queried {
                filtered = result.choices;
                loading = false;
                cursor = 0;
            }
        }

        // --- debounce: if enough time has passed since the last keystroke,
        //     fire off a new search ---
        if let Some(ref term) = pending_term.clone() {
            if let Some(ts) = last_keystroke {
                if ts.elapsed() >= SEARCH_DEBOUNCE {
                    last_queried = term.clone();
                    loading = true;
                    pending_term = None;

                    let search_term = term.clone();
                    let src = Arc::clone(&source);
                    let sender = tx.clone();
                    std::thread::spawn(move || {
                        let choices = get_filtered(&*src, &search_term);
                        let _ = sender.send(SearchResult {
                            term: search_term,
                            choices,
                        });
                    });
                }
            }
        }

        // --- render ---
        let header = format!(
            "{}{}{}  {BOLD}{}{RESET}",
            ansi_color(t.question),
            t.sym_question,
            RESET,
            config.message,
        );

        let input_line = format!(
            "  {}{}{}_{}",
            ansi_color(t.answer),
            input,
            RESET,
            ansi_color(t.muted),
        );

        let mut items: Vec<(String, String)> = Vec::new();
        items.push((String::new(), input_line));

        if loading {
            items.push((ansi_color(t.muted), "  Searching...".to_string()));
        } else if filtered.is_empty() {
            items.push((ansi_color(t.muted), "  No results".to_string()));
        } else {
            let end = filtered.len().min(config.page_size);
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

        // --- poll for key events (non-blocking with short timeout) ---
        let key = match poll_key(POLL_TIMEOUT) {
            Ok(Some(k)) => k,
            Ok(None) => continue, // timeout — loop back to drain channel + re-render
            Err(e) => {
                renderer.clear();
                ListRenderer::disable_raw()?;
                return Err(InquirerError::Io(e));
            }
        };

        match key {
            KeyInput::Up if !filtered.is_empty() && !loading => {
                let end = filtered.len().min(config.page_size);
                cursor = (cursor + end - 1) % end;
            }
            KeyInput::Down if !filtered.is_empty() && !loading => {
                let end = filtered.len().min(config.page_size);
                cursor = (cursor + 1) % end;
            }
            KeyInput::Backspace if !input.is_empty() => {
                input.pop();
                last_keystroke = Some(Instant::now());
                pending_term = Some(input.clone());
            }
            KeyInput::Char(c) => {
                input.push(c);
                last_keystroke = Some(Instant::now());
                pending_term = Some(input.clone());
            }
            KeyInput::Enter => {
                renderer.clear();
                ListRenderer::disable_raw()?;
                if loading || filtered.is_empty() {
                    return Err(InquirerError::PromptAborted("No selection made".into()));
                }
                let end = filtered.len().min(config.page_size);
                let safe_cursor = cursor.min(end.saturating_sub(1));
                if let Some(choice) = filtered.get(safe_cursor) {
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
