//! Conformance driver (Rust) for inquirer-ai.
//!
//! Runs the 11-prompt conformance scenario through the REAL inquirer-ai
//! library in STDIO AGENT MODE. The library reads answers from stdin and
//! writes the JSONL protocol (handshake + prompts + validation_errors) to
//! stdout. Each prompt's RETURN VALUE is collected and written as a single
//! JSON array to the results file path given in argv[1].

use inquirer_ai::choice::{Choice, ChoiceItem, Separator};
use inquirer_ai::prompts::autocomplete::{autocomplete, AutocompleteConfig};
use inquirer_ai::prompts::checkbox::{checkbox, CheckboxConfig};
use inquirer_ai::prompts::confirm::{confirm, ConfirmConfig};
use inquirer_ai::prompts::expand::{expand, ExpandChoice, ExpandConfig};
use inquirer_ai::prompts::number::{number, NumberConfig};
use inquirer_ai::prompts::password::{password, PasswordConfig};
use inquirer_ai::prompts::path::{path, PathConfig};
use inquirer_ai::prompts::rawlist::{rawlist, RawlistConfig};
use inquirer_ai::prompts::search::{search, SearchConfig};
use inquirer_ai::prompts::select::{select, SelectConfig};
use inquirer_ai::prompts::text::{text, TextConfig};
use serde_json::{json, Value};

fn ch(name: &str, value: Value) -> ChoiceItem {
    ChoiceItem::Choice(Choice::new(name, value))
}

fn ch_disabled(name: &str, value: Value, disabled: Value) -> ChoiceItem {
    let mut c = Choice::new(name, value);
    c.disabled = Some(disabled);
    ChoiceItem::Choice(c)
}

fn main() {
    let results_file = std::env::args().nth(1).expect("usage: driver <results_file>");

    let mut results: Vec<Value> = Vec::new();

    // P1 text/input  message="Name" default="anon"
    let mut p1 = TextConfig::new("Name");
    p1.default = Some("anon".to_string());
    let r1 = text(p1).expect("P1 text failed");
    results.push(json!(r1));

    // P2 confirm  message="Proceed?" default=true
    let mut p2 = ConfirmConfig::new("Proceed?");
    p2.default = true;
    let r2 = confirm(p2).expect("P2 confirm failed");
    results.push(json!(r2));

    // P3 number  message="Count" default=10 min=1 max=1000 float_allowed=false
    let mut p3 = NumberConfig::new("Count");
    p3.default = Some(10.0);
    p3.min = Some(1.0);
    p3.max = Some(1000.0);
    p3.float_allowed = false;
    let r3 = number(p3).expect("P3 number failed");
    results.push(json!(r3));

    // P4 select  message="Lang"
    let p4 = SelectConfig::new(
        "Lang",
        vec![
            ch("Python", json!("py")),
            ch("Go", json!("go")),
            ChoiceItem::Separator(Separator::new("--")),
            ch_disabled("Rust", json!("rs"), json!("soon")),
        ],
    );
    let r4 = select(p4).expect("P4 select failed");
    results.push(r4);

    // P5 checkbox  message="Feat" default=["a"]
    let mut p5 = CheckboxConfig::new(
        "Feat",
        vec![
            ch("A", json!("a")),
            ch("B", json!("b")),
            ch("C", json!("c")),
        ],
    );
    p5.default = vec![json!("a")];
    let r5 = checkbox(p5).expect("P5 checkbox failed");
    results.push(json!(r5));

    // P6 rawlist  message="Ver"
    let p6 = RawlistConfig::new(
        "Ver",
        vec![
            ch("3.13", json!("313")),
            ChoiceItem::Separator(Separator::new("-")),
            ch_disabled("3.12", json!("312"), json!(true)),
            ch("3.11", json!("311")),
        ],
    );
    let r6 = rawlist(p6).expect("P6 rawlist failed");
    results.push(r6);

    // P7 search  message="Pkg" choices=[requests->req, httpx->hx]
    let p7 = SearchConfig::new("Pkg", |_term: &str| {
        vec![
            ch("requests", json!("req")),
            ch("httpx", json!("hx")),
        ]
    });
    let r7 = search(p7).expect("P7 search failed");
    results.push(r7);

    // P8 password  message="Token" default="def"
    let mut p8 = PasswordConfig::new("Token");
    p8.default = Some("def".to_string());
    let r8 = password(p8).expect("P8 password failed");
    results.push(json!(r8));

    // P9 expand  message="Conflict"  (key "Y" uppercase on purpose -> lowercased)
    let p9 = ExpandConfig::new(
        "Conflict",
        vec![
            ExpandChoice {
                key: "Y".to_string(),
                name: "Yes".to_string(),
                value: json!("yes"),
            },
            ExpandChoice {
                key: "n".to_string(),
                name: "No".to_string(),
                value: json!("no"),
            },
        ],
    );
    let r9 = expand(p9).expect("P9 expand failed");
    results.push(r9);

    // P10 autocomplete  message="Free" choices=["Python","Go"]
    let p10 = AutocompleteConfig::new("Free", vec!["Python".to_string(), "Go".to_string()]);
    let r10 = autocomplete(p10).expect("P10 autocomplete failed");
    results.push(json!(r10));

    // P11 path  message="Dir" default="."
    let mut p11 = PathConfig::new("Dir");
    p11.default = Some(".".to_string());
    let r11 = path(p11).expect("P11 path failed");
    results.push(json!(r11));

    // Write the results array to argv[1]. Protocol stays on stdout.
    let array = Value::Array(results);
    std::fs::write(&results_file, array.to_string())
        .unwrap_or_else(|e| panic!("failed to write results file {results_file}: {e}"));
}
