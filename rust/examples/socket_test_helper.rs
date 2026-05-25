//! Test helper binary for socket transport integration tests.
//!
//! This binary is launched by tests/socket.rs. It reads the TEST_SCENARIO
//! environment variable to decide which prompts to execute.

use inquirer_ai::prompts::confirm::{confirm, ConfirmConfig};
use inquirer_ai::prompts::number::{number, NumberConfig};
use inquirer_ai::prompts::text::{text, TextConfig};

fn main() {
    let scenario = std::env::var("TEST_SCENARIO").unwrap_or_else(|_| "single_text".to_string());

    match scenario.as_str() {
        "single_text" => {
            let result = text(TextConfig::new("What is your name?")).unwrap();
            eprintln!("Got: {result}");
        }
        "number_min10" => {
            let mut config = NumberConfig::new("Enter a number >= 10");
            config.min = Some(10.0);
            let result = number(config).unwrap();
            eprintln!("Got: {result}");
        }
        "multi_prompt" => {
            let name = text(TextConfig::new("What is your name?")).unwrap();
            eprintln!("Name: {name}");

            let confirmed = confirm(ConfirmConfig::new("Continue?")).unwrap();
            eprintln!("Confirmed: {confirmed}");

            let mut config = NumberConfig::new("Pick a number");
            config.float_allowed = true;
            let num = number(config).unwrap();
            eprintln!("Number: {num}");
        }
        other => {
            eprintln!("Unknown scenario: {other}");
            std::process::exit(1);
        }
    }
}
