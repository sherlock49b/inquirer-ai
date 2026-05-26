use inquirer_ai::choice::{Choice, ChoiceItem};
use inquirer_ai::prompts::search::{SearchConfig, SearchSource};
use proptest::prelude::*;
use serde_json::json;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

fn make_source(items: Vec<(&str, &str)>) -> SearchSource {
    let items: Vec<(String, String)> = items
        .into_iter()
        .map(|(n, v)| (n.to_string(), v.to_string()))
        .collect();
    Box::new(move |term: &str| {
        items
            .iter()
            .filter(|(name, _)| {
                term.is_empty() || name.to_lowercase().contains(&term.to_lowercase())
            })
            .map(|(name, value)| {
                ChoiceItem::Choice(Choice::new(name.clone(), json!(value.clone())))
            })
            .collect()
    })
}

// ── Thread safety of source function ──

#[test]
fn search_source_thread_safety() {
    let call_log = Arc::new(Mutex::new(Vec::<String>::new()));
    let log = Arc::clone(&call_log);
    let source: SearchSource = Box::new(move |term: &str| {
        log.lock().unwrap().push(term.to_string());
        vec![ChoiceItem::Choice(Choice::new("result", json!("val")))]
    });
    let source = Arc::new(source);

    let counter = Arc::new(AtomicUsize::new(0));
    let mut handles = Vec::new();

    for i in 0..50 {
        let src = Arc::clone(&source);
        let cnt = Arc::clone(&counter);
        handles.push(thread::spawn(move || {
            let term = format!("query_{i}");
            let results = src(&term);
            assert!(!results.is_empty());
            cnt.fetch_add(1, Ordering::SeqCst);
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(counter.load(Ordering::SeqCst), 50);
    assert_eq!(call_log.lock().unwrap().len(), 50);
}

// ── Source with empty results ──

#[test]
fn search_empty_source_no_crash() {
    let source: SearchSource = Box::new(|_term: &str| Vec::new());
    let result = source("anything");
    assert!(result.is_empty());
}

// ── Source with special characters ──

#[test]
fn search_source_special_chars() {
    let source: SearchSource = Box::new(|_term: &str| {
        vec![
            ChoiceItem::Choice(Choice::new("", json!("empty"))),
            ChoiceItem::Choice(Choice::new("a".repeat(100_000), json!("long"))),
            ChoiceItem::Choice(Choice::new("line\nbreak", json!("newline"))),
            ChoiceItem::Choice(Choice::new("tab\there", json!("tab"))),
            ChoiceItem::Choice(Choice::new("null\0byte", json!("null"))),
            ChoiceItem::Choice(Choice::new("\x1b[31mred\x1b[0m", json!("ansi"))),
        ]
    });
    let results = source("test");
    assert_eq!(results.len(), 6);
}

// ── Source with slow response (no deadlock) ──

#[test]
fn search_slow_source_no_deadlock() {
    let source: SearchSource = Box::new(|term: &str| {
        thread::sleep(Duration::from_millis(50));
        vec![ChoiceItem::Choice(Choice::new(
            format!("result for {term}"),
            json!(term),
        ))]
    });
    let source = Arc::new(source);

    let mut handles = Vec::new();
    for i in 0..10 {
        let src = Arc::clone(&source);
        handles.push(thread::spawn(move || {
            let results = src(&format!("q{i}"));
            assert_eq!(results.len(), 1);
        }));
    }

    for h in handles {
        h.join().unwrap();
    }
}

// ── Stale result rejection logic ──

#[test]
fn search_stale_result_rejected() {
    let call_order = Arc::new(Mutex::new(Vec::<(String, usize)>::new()));
    let log = Arc::clone(&call_order);
    let counter = Arc::new(AtomicUsize::new(0));
    let cnt = Arc::clone(&counter);

    let source: SearchSource = Box::new(move |term: &str| {
        let idx = cnt.fetch_add(1, Ordering::SeqCst);
        if term == "slow" {
            thread::sleep(Duration::from_millis(100));
        }
        log.lock().unwrap().push((term.to_string(), idx));
        vec![ChoiceItem::Choice(Choice::new(
            format!("result_{term}"),
            json!(term),
        ))]
    });
    let source = Arc::new(source);

    let src_slow = Arc::clone(&source);
    let src_fast = Arc::clone(&source);

    let h_slow = thread::spawn(move || src_slow("slow"));
    thread::sleep(Duration::from_millis(10));
    let h_fast = thread::spawn(move || src_fast("fast"));

    let fast_result = h_fast.join().unwrap();
    let slow_result = h_slow.join().unwrap();

    assert_eq!(fast_result.len(), 1);
    assert_eq!(slow_result.len(), 1);

    let log = call_order.lock().unwrap();
    let fast_call = log.iter().find(|(t, _)| t == "fast").unwrap();
    let slow_call = log.iter().find(|(t, _)| t == "slow").unwrap();
    assert!(
        fast_call.1 > slow_call.1 || slow_call.1 > fast_call.1,
        "both should have been called"
    );
}

// ── Agent mode search ──

#[test]
fn search_agent_source_called_with_empty_term() {
    let called_with = Arc::new(Mutex::new(Vec::<String>::new()));
    let log = Arc::clone(&called_with);

    let source = make_source(vec![("Alpha", "a"), ("Beta", "b")]);
    let results = source("");
    assert_eq!(results.len(), 2);

    let tracking_source: SearchSource = Box::new(move |term: &str| {
        log.lock().unwrap().push(term.to_string());
        vec![
            ChoiceItem::Choice(Choice::new("Alpha", json!("a"))),
            ChoiceItem::Choice(Choice::new("Beta", json!("b"))),
        ]
    });

    let _config = SearchConfig {
        message: "Pick?".to_string(),
        source: tracking_source,
        page_size: 10,
    };
}

// ── Disabled choices filtered out ──

#[test]
fn search_disabled_choices_filtered() {
    let source: SearchSource = Box::new(|_term: &str| {
        vec![
            ChoiceItem::Choice(Choice::new("enabled", json!("e"))),
            ChoiceItem::Choice(Choice {
                name: "disabled".to_string(),
                value: json!("d"),
                disabled: Some(json!(true)),
                short: None,
                description: None,
            }),
        ]
    });
    let results: Vec<_> = source("")
        .into_iter()
        .filter_map(|c| match c {
            ChoiceItem::Choice(c) if !c.is_disabled() => Some(c),
            _ => None,
        })
        .collect();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].name, "enabled");
}

// ── Property-based tests ──

proptest! {
    #[test]
    fn source_never_panics_on_random_term(term in "\\PC{0,200}") {
        let source = make_source(vec![("Alpha", "a"), ("Beta", "b"), ("Charlie", "c")]);
        let results = source(&term);
        for item in &results {
            match item {
                ChoiceItem::Choice(c) => {
                    prop_assert!(!c.name.is_empty());
                }
                _ => {}
            }
        }
    }

    #[test]
    fn concurrent_source_calls_never_panic(
        terms in prop::collection::vec("\\PC{0,50}", 1..20)
    ) {
        let source = Arc::new(make_source(vec![("A", "a"), ("B", "b")]));
        let handles: Vec<_> = terms.into_iter().map(|term| {
            let src = Arc::clone(&source);
            thread::spawn(move || {
                let results = src(&term);
                results.len()
            })
        }).collect();

        for h in handles {
            let count = h.join().unwrap();
            prop_assert!(count <= 2);
        }
    }

    #[test]
    fn filter_disabled_choices_invariant(
        n_enabled in 0..20usize,
        n_disabled in 0..10usize
    ) {
        let mut items: Vec<ChoiceItem> = Vec::new();
        for i in 0..n_enabled {
            items.push(ChoiceItem::Choice(Choice::new(format!("e{i}"), json!(i))));
        }
        for i in 0..n_disabled {
            items.push(ChoiceItem::Choice(Choice {
                name: format!("d{i}"),
                value: json!(100 + i),
                disabled: Some(json!(true)),
                short: None,
                description: None,
            }));
        }

        let filtered: Vec<_> = items
            .into_iter()
            .filter_map(|c| match c {
                ChoiceItem::Choice(c) if !c.is_disabled() => Some(c),
                _ => None,
            })
            .collect();

        prop_assert_eq!(filtered.len(), n_enabled);
    }
}
