use inquirer_ai::choice::{Choice, ChoiceItem};
use inquirer_ai::errors::InquirerError;
use inquirer_ai::prompts::checkbox::CheckboxConfig;
use inquirer_ai::prompts::confirm::ConfirmConfig;
use inquirer_ai::prompts::select::SelectConfig;
use inquirer_ai::prompts::text::TextConfig;
use inquirer_ai::{checkbox, confirm, select, text};
use serde::Deserialize;
use serde_json::Value;
use std::path::PathBuf;
use std::{env, fs, process};
use toml_edit::DocumentMut;

fn main() {
    // cargo subcommand convention: `cargo deps` passes ["cargo-deps", "deps", ...]
    let args: Vec<String> = env::args().collect();
    let args: Vec<&str> = args
        .iter()
        .map(|s| s.as_str())
        .filter(|s| *s != "deps")
        .collect();

    match args.get(1).copied() {
        Some("search") => {
            let query = args.get(2).copied().unwrap_or("");
            cmd_search(query);
        }
        Some("add") => {
            let query = args.get(2).copied().unwrap_or("");
            cmd_add(query);
        }
        Some("remove") => cmd_remove(),
        Some("list") => cmd_list(),
        Some("help") | Some("--help") | Some("-h") => print_help(),
        Some("--version") | Some("-V") => println!("cargo-deps 0.1.0"),
        None => cmd_interactive(),
        Some(other) => {
            // Treat unknown arg as a search query
            cmd_add(other);
        }
    }
}

fn print_help() {
    eprintln!("cargo-deps — interactive dependency management for Cargo");
    eprintln!();
    eprintln!("Usage:");
    eprintln!("  cargo deps              Interactive menu");
    eprintln!("  cargo deps search <q>   Search crates.io");
    eprintln!("  cargo deps add [query]  Search and add a dependency");
    eprintln!("  cargo deps remove       Interactively remove dependencies");
    eprintln!("  cargo deps list         List current dependencies");
}

fn cmd_interactive() {
    let action = select(SelectConfig::new(
        "What would you like to do?",
        vec![
            ChoiceItem::Choice(Choice::new("Search & add a dependency", "add")),
            ChoiceItem::Choice(Choice::new("Remove a dependency", "remove")),
            ChoiceItem::Choice(Choice::new("List current dependencies", "list")),
        ],
    ));

    match action {
        Ok(v) => match v.as_str() {
            Some("add") => cmd_add(""),
            Some("remove") => cmd_remove(),
            Some("list") => cmd_list(),
            _ => {}
        },
        Err(InquirerError::PromptAborted(_)) => {}
        Err(e) => fatal(&e.to_string()),
    }
}

// --- Search ---

#[derive(Deserialize)]
struct CratesResponse {
    crates: Vec<CrateInfo>,
}

#[derive(Deserialize)]
struct CrateInfo {
    name: String,
    max_version: String,
    description: Option<String>,
    downloads: u64,
}

#[derive(Deserialize)]
struct CrateVersionsResponse {
    version: CrateVersionDetail,
}

#[derive(Deserialize)]
struct CrateVersionDetail {
    features: std::collections::HashMap<String, Vec<String>>,
}

fn search_crates(query: &str) -> Vec<CrateInfo> {
    let url = format!(
        "https://crates.io/api/v1/crates?q={}&per_page=10&sort=downloads",
        urlencoded(query)
    );
    let body = match ureq::get(&url)
        .header("User-Agent", "cargo-deps/0.1.0 (inquirer-ai)")
        .call()
        .and_then(|mut r| r.body_mut().read_to_string())
    {
        Ok(s) => s,
        Err(e) => {
            eprintln!("Failed to search crates.io: {e}");
            return vec![];
        }
    };

    match serde_json::from_str::<CratesResponse>(&body) {
        Ok(data) => data.crates,
        Err(e) => {
            eprintln!("Failed to parse response: {e}");
            vec![]
        }
    }
}

fn get_crate_features(name: &str, version: &str) -> Vec<String> {
    let url = format!("https://crates.io/api/v1/crates/{name}/{version}");
    let body = match ureq::get(&url)
        .header("User-Agent", "cargo-deps/0.1.0 (inquirer-ai)")
        .call()
        .and_then(|mut r| r.body_mut().read_to_string())
    {
        Ok(s) => s,
        Err(_) => return vec![],
    };

    match serde_json::from_str::<CrateVersionsResponse>(&body) {
        Ok(data) => {
            let mut features: Vec<String> = data
                .version
                .features
                .keys()
                .filter(|k| *k != "default")
                .cloned()
                .collect();
            features.sort();
            features
        }
        Err(_) => vec![],
    }
}

fn cmd_search(initial_query: &str) {
    let query = if initial_query.is_empty() {
        match text(TextConfig::new("Search crates.io")) {
            Ok(q) => q,
            Err(_) => return,
        }
    } else {
        initial_query.to_string()
    };

    if query.is_empty() {
        eprintln!("No search query provided.");
        return;
    }

    let results = search_crates(&query);
    if results.is_empty() {
        eprintln!("No crates found for \"{query}\".");
        return;
    }

    for c in &results {
        let desc = c.description.as_deref().unwrap_or("");
        let downloads = format_downloads(c.downloads);
        eprintln!(
            "  {} {} ({}) — {}",
            c.name, c.max_version, downloads, desc
        );
    }
}

// --- Add ---

fn cmd_add(initial_query: &str) {
    let query = if initial_query.is_empty() {
        match text(TextConfig::new("Search crates.io")) {
            Ok(q) => q,
            Err(_) => return,
        }
    } else {
        initial_query.to_string()
    };

    if query.is_empty() {
        eprintln!("No search query provided.");
        return;
    }

    let results = search_crates(&query);
    if results.is_empty() {
        eprintln!("No crates found for \"{query}\".");
        return;
    }

    let choices: Vec<ChoiceItem> = results
        .iter()
        .map(|c| {
            let desc: String = c.description.as_deref().unwrap_or("")
                .chars().filter(|c| !matches!(c, '\n' | '\r')).take(60).collect();
            let downloads = format_downloads(c.downloads);
            ChoiceItem::Choice(Choice {
                name: format!("{} v{} ({})", c.name, c.max_version, downloads),
                value: Value::String(c.name.clone()),
                disabled: None,
                short: Some(c.name.clone()),
                description: Some(desc),
            })
        })
        .collect();

    let selected = match select(SelectConfig::new("Select a crate to add", choices)) {
        Ok(v) => v,
        Err(_) => return,
    };

    let crate_name = selected.as_str().unwrap_or("");
    let crate_info = results.iter().find(|c| c.name == crate_name).unwrap();

    // Ask about features
    let features = get_crate_features(&crate_info.name, &crate_info.max_version);
    let selected_features = if features.is_empty() {
        vec![]
    } else {
        let feature_choices: Vec<ChoiceItem> = features
            .iter()
            .map(|f| ChoiceItem::Choice(Choice::new(f.as_str(), Value::String(f.clone()))))
            .collect();

        match checkbox(CheckboxConfig::new(
            format!("Enable features for {}?", crate_info.name),
            feature_choices,
        )) {
            Ok(selected) => selected
                .into_iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect(),
            Err(_) => return,
        }
    };

    // Confirm
    let dep_str = if selected_features.is_empty() {
        format!("{} = \"{}\"", crate_info.name, crate_info.max_version)
    } else {
        format!(
            "{} = {{ version = \"{}\", features = {:?} }}",
            crate_info.name, crate_info.max_version, selected_features
        )
    };

    let ok = match confirm(ConfirmConfig {
        message: format!("Add {dep_str} ?"),
        default: true,
    }) {
        Ok(v) => v,
        Err(_) => return,
    };

    if !ok {
        eprintln!("Cancelled.");
        return;
    }

    // Write to Cargo.toml
    let cargo_toml = find_cargo_toml();
    add_dependency(&cargo_toml, &crate_info.name, &crate_info.max_version, &selected_features);
    eprintln!("✓ Added {} to {}", crate_info.name, cargo_toml.display());
}

// --- Remove ---

fn cmd_remove() {
    let cargo_toml = find_cargo_toml();
    let content = fs::read_to_string(&cargo_toml).unwrap_or_else(|_| {
        fatal("Could not read Cargo.toml");
        unreachable!()
    });

    let doc = content.parse::<DocumentMut>().unwrap_or_else(|e| {
        fatal(&format!("Invalid Cargo.toml: {e}"));
        unreachable!()
    });

    let deps = collect_dep_names(&doc);
    if deps.is_empty() {
        eprintln!("No dependencies to remove.");
        return;
    }

    let choices: Vec<ChoiceItem> = deps
        .iter()
        .map(|(name, table)| {
            ChoiceItem::Choice(Choice {
                name: name.clone(),
                value: Value::String(name.clone()),
                disabled: None,
                short: None,
                description: Some(format!("[{table}]")),
            })
        })
        .collect();

    let to_remove = match checkbox(CheckboxConfig::new("Select dependencies to remove", choices)) {
        Ok(v) => v,
        Err(_) => return,
    };

    if to_remove.is_empty() {
        eprintln!("Nothing selected.");
        return;
    }

    let names: Vec<&str> = to_remove
        .iter()
        .filter_map(|v| v.as_str())
        .collect();

    let ok = match confirm(ConfirmConfig {
        message: format!("Remove {}?", names.join(", ")),
        default: true,
    }) {
        Ok(v) => v,
        Err(_) => return,
    };

    if !ok {
        eprintln!("Cancelled.");
        return;
    }

    let mut doc = content.parse::<DocumentMut>().unwrap();
    for name in &names {
        for table in ["dependencies", "dev-dependencies", "build-dependencies"] {
            if let Some(section) = doc.get_mut(table).and_then(|t| t.as_table_like_mut()) {
                section.remove(*name);
            }
        }
    }

    fs::write(&cargo_toml, doc.to_string()).unwrap_or_else(|e| {
        fatal(&format!("Failed to write Cargo.toml: {e}"));
    });

    eprintln!("✓ Removed {} from {}", names.join(", "), cargo_toml.display());
}

// --- List ---

fn cmd_list() {
    let cargo_toml = find_cargo_toml();
    let content = fs::read_to_string(&cargo_toml).unwrap_or_else(|_| {
        fatal("Could not read Cargo.toml");
        unreachable!()
    });

    let doc = content.parse::<DocumentMut>().unwrap_or_else(|e| {
        fatal(&format!("Invalid Cargo.toml: {e}"));
        unreachable!()
    });

    for table_name in ["dependencies", "dev-dependencies", "build-dependencies"] {
        if let Some(table) = doc.get(table_name).and_then(|t| t.as_table_like()) {
            if table.is_empty() {
                continue;
            }
            eprintln!("[{table_name}]");
            for (key, value) in table.iter() {
                let version = extract_version(value);
                eprintln!("  {key} = {version}");
            }
            eprintln!();
        }
    }
}

// --- Helpers ---

fn find_cargo_toml() -> PathBuf {
    let mut dir = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    loop {
        let candidate = dir.join("Cargo.toml");
        if candidate.exists() {
            return candidate;
        }
        if !dir.pop() {
            fatal("No Cargo.toml found in current directory or any parent.");
            unreachable!()
        }
    }
}

fn add_dependency(path: &PathBuf, name: &str, version: &str, features: &[String]) {
    let content = fs::read_to_string(path).unwrap_or_else(|e| {
        fatal(&format!("Failed to read Cargo.toml: {e}"));
        unreachable!()
    });

    let mut doc = content.parse::<DocumentMut>().unwrap_or_else(|e| {
        fatal(&format!("Invalid Cargo.toml: {e}"));
        unreachable!()
    });

    if doc.get("dependencies").is_none() {
        doc["dependencies"] = toml_edit::table();
    }

    if features.is_empty() {
        doc["dependencies"][name] = toml_edit::value(version);
    } else {
        let mut inline = toml_edit::InlineTable::new();
        inline.insert("version", version.into());
        let mut arr = toml_edit::Array::new();
        for f in features {
            arr.push(f.as_str());
        }
        inline.insert("features", toml_edit::Value::Array(arr));
        doc["dependencies"][name] = toml_edit::value(toml_edit::Value::InlineTable(inline));
    }

    fs::write(path, doc.to_string()).unwrap_or_else(|e| {
        fatal(&format!("Failed to write Cargo.toml: {e}"));
    });
}

fn collect_dep_names(doc: &DocumentMut) -> Vec<(String, String)> {
    let mut deps = Vec::new();
    for table_name in ["dependencies", "dev-dependencies", "build-dependencies"] {
        if let Some(table) = doc.get(table_name).and_then(|t| t.as_table_like()) {
            for (key, _) in table.iter() {
                deps.push((key.to_string(), table_name.to_string()));
            }
        }
    }
    deps
}

fn extract_version(value: &toml_edit::Item) -> String {
    if let Some(s) = value.as_str() {
        return format!("\"{s}\"");
    }
    if let Some(table) = value.as_inline_table() {
        if let Some(v) = table.get("version").and_then(|v| v.as_str()) {
            let features = table
                .get("features")
                .and_then(|f| f.as_array())
                .map(|arr| {
                    let items: Vec<&str> = arr.iter().filter_map(|v| v.as_str()).collect();
                    format!(", features = {:?}", items)
                })
                .unwrap_or_default();
            return format!("{{ version = \"{v}\"{features} }}");
        }
    }
    if let Some(table) = value.as_table_like() {
        if let Some(v) = table.get("version").and_then(|v| v.as_str()) {
            return format!("{{ version = \"{v}\", ... }}");
        }
    }
    value.to_string()
}

fn format_downloads(n: u64) -> String {
    if n >= 1_000_000 {
        format!("{:.1}M dl", n as f64 / 1_000_000.0)
    } else if n >= 1_000 {
        format!("{:.0}K dl", n as f64 / 1_000.0)
    } else {
        format!("{n} dl")
    }
}

fn urlencoded(s: &str) -> String {
    s.replace(' ', "+")
        .replace('&', "%26")
        .replace('?', "%3F")
        .replace('#', "%23")
}

fn fatal(msg: &str) {
    eprintln!("Error: {msg}");
    process::exit(1);
}
