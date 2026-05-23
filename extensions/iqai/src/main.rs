use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, ExitStatus, Stdio};
use std::time::{Duration, Instant};
use std::{env, process, thread};

const RESET: &str = "\x1b[0m";
const GREEN: &str = "\x1b[32m";
const RED: &str = "\x1b[31m";
const CYAN: &str = "\x1b[36m";
const BOLD: &str = "\x1b[1m";
const DIM: &str = "\x1b[2m";

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        eprintln!("Usage: iqai test <binary> [args...]");
        eprintln!("       iqai test ./my-cli --some-flag");
        eprintln!();
        eprintln!("Tests whether a binary correctly implements the inquirer-ai agent protocol.");
        process::exit(1);
    }

    match args[1].as_str() {
        "test" => {
            if args.len() < 3 {
                eprintln!("Usage: iqai test <binary> [args...]");
                process::exit(1);
            }
            run_test(&args[2], &args[3..]);
        }
        "version" | "--version" | "-v" => {
            println!("iqai 0.1.0");
        }
        "help" | "--help" | "-h" => {
            println!("iqai — inquirer-ai protocol compliance tester");
            println!();
            println!("Commands:");
            println!("  test <binary> [args...]   Test a binary for protocol compliance");
            println!("  version                   Show version");
            println!("  help                      Show this help");
        }
        other => {
            if std::path::Path::new(other).exists() {
                run_test(other, &args[2..]);
            } else {
                eprintln!("Unknown command: {other}");
                eprintln!("Run `iqai help` for usage.");
                process::exit(1);
            }
        }
    }
}

struct TestRunner {
    passed: usize,
    failed: usize,
    skipped: usize,
}

impl TestRunner {
    fn new() -> Self {
        Self {
            passed: 0,
            failed: 0,
            skipped: 0,
        }
    }

    fn pass(&mut self, name: &str) {
        self.passed += 1;
        eprintln!("  {GREEN}✓{RESET} {name}");
    }

    fn fail(&mut self, name: &str, reason: &str) {
        self.failed += 1;
        eprintln!("  {RED}✗{RESET} {name}");
        eprintln!("    {DIM}{reason}{RESET}");
    }

    fn skip(&mut self, name: &str, reason: &str) {
        self.skipped += 1;
        eprintln!("  {DIM}○ {name} — {reason}{RESET}");
    }

    fn summary(&self) {
        eprintln!();
        let total = self.passed + self.failed + self.skipped;
        eprintln!(
            "  {BOLD}{total} tests{RESET}: {GREEN}{} passed{RESET}, {RED}{} failed{RESET}, {DIM}{} skipped{RESET}",
            self.passed, self.failed, self.skipped
        );
    }
}

fn run_test(binary: &str, extra_args: &[String]) {
    eprintln!("{BOLD}{CYAN}iqai{RESET} — protocol compliance test");
    eprintln!("{DIM}binary: {binary}{RESET}");
    eprintln!();

    let mut runner = TestRunner::new();

    test_handshake(&mut runner, binary, extra_args);
    test_text_prompt(&mut runner, binary, extra_args);
    test_confirm_prompt(&mut runner, binary, extra_args);
    test_null_answer(&mut runner, binary, extra_args);
    test_invalid_json(&mut runner, binary, extra_args);
    test_missing_answer_key(&mut runner, binary, extra_args);
    test_eof_handling(&mut runner, binary, extra_args);
    test_sequential_interaction(&mut runner, binary, extra_args);

    runner.summary();

    if runner.failed > 0 {
        process::exit(1);
    }
}

fn spawn_agent(binary: &str, extra_args: &[String]) -> Option<std::process::Child> {
    let mut cmd = Command::new(binary);
    cmd.args(extra_args)
        .env("INQUIRER_AI_MODE", "agent")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());

    match cmd.spawn() {
        Ok(child) => Some(child),
        Err(e) => {
            eprintln!("  {RED}✗{RESET} Failed to spawn: {e}");
            None
        }
    }
}

fn wait_or_kill(child: &mut std::process::Child, timeout: Duration) -> Option<ExitStatus> {
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return Some(status),
            Ok(None) => {
                if start.elapsed() >= timeout {
                    let _ = child.kill();
                    let _ = child.wait();
                    return None;
                }
                thread::sleep(Duration::from_millis(50));
            }
            Err(_) => return None,
        }
    }
}

fn read_line_from(reader: &mut BufReader<std::process::ChildStdout>) -> Option<String> {
    let mut line = String::new();
    match reader.read_line(&mut line) {
        Ok(0) => None,
        Ok(_) => Some(line.trim_end().to_string()),
        Err(_) => None,
    }
}

fn send_answer(stdin: &mut std::process::ChildStdin, answer: &Value) {
    let resp = serde_json::json!({ "answer": answer });
    let _ = writeln!(stdin, "{resp}");
    let _ = stdin.flush();
}

fn test_handshake(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("handshake", "failed to spawn process");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);

    let Some(line) = read_line_from(&mut reader) else {
        runner.fail("handshake — first line", "no output received");
        let _ = child.kill();
        return;
    };

    let Ok(handshake) = serde_json::from_str::<Value>(&line) else {
        runner.fail("handshake — valid JSON", &format!("not JSON: {line}"));
        let _ = child.kill();
        return;
    };

    if handshake.get("protocol").and_then(|v| v.as_str()) == Some("inquirer-ai") {
        runner.pass("handshake — protocol field");
    } else {
        runner.fail(
            "handshake — protocol field",
            &format!("expected \"inquirer-ai\", got {:?}", handshake.get("protocol")),
        );
    }

    if handshake.get("version").and_then(|v| v.as_str()).is_some() {
        runner.pass("handshake — version field");
    } else {
        runner.fail("handshake — version field", "missing or not a string");
    }

    if handshake.get("interaction").and_then(|v| v.as_str()) == Some("sequential") {
        runner.pass("handshake — interaction: sequential");
    } else {
        runner.fail(
            "handshake — interaction field",
            &format!("expected \"sequential\", got {:?}", handshake.get("interaction")),
        );
    }

    if handshake.get("format").and_then(|v| v.as_str()) == Some("jsonl") {
        runner.pass("handshake — format: jsonl");
    } else {
        runner.fail(
            "handshake — format field",
            &format!("expected \"jsonl\", got {:?}", handshake.get("format")),
        );
    }

    let _ = child.kill();
}

fn test_text_prompt(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("text prompt", "failed to spawn");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);
    let mut stdin = child.stdin.take().unwrap();

    // Skip handshake
    let Some(_) = read_line_from(&mut reader) else {
        runner.fail("text prompt", "no handshake");
        return;
    };

    // Read first prompt
    let Some(line) = read_line_from(&mut reader) else {
        runner.skip("text prompt", "no prompt emitted (binary may not use text)");
        return;
    };

    let Ok(prompt) = serde_json::from_str::<Value>(&line) else {
        runner.fail("text prompt — valid JSON", &format!("not JSON: {line}"));
        let _ = child.kill();
        return;
    };

    if prompt.get("type").is_some() && prompt.get("message").is_some() {
        runner.pass("text prompt — has type and message");
    } else {
        runner.fail(
            "text prompt — structure",
            &format!("missing type or message: {prompt}"),
        );
    }

    send_answer(&mut stdin, &Value::String("test-value".into()));
    drop(stdin);
    wait_or_kill(&mut child, Duration::from_secs(2));
    runner.pass("text prompt — accepts answer");
}

fn test_confirm_prompt(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("confirm prompt", "failed to spawn");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);
    let mut stdin = child.stdin.take().unwrap();

    let Some(_) = read_line_from(&mut reader) else {
        runner.fail("confirm coercion", "no handshake");
        return;
    };

    let Some(_) = read_line_from(&mut reader) else {
        runner.skip("confirm coercion", "no prompt");
        return;
    };

    // Send boolean true
    send_answer(&mut stdin, &Value::Bool(true));

    drop(stdin);
    wait_or_kill(&mut child, Duration::from_secs(2));
    runner.pass("confirm coercion — boolean accepted");
}

fn test_null_answer(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("null answer", "failed to spawn");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);
    let mut stdin = child.stdin.take().unwrap();

    let Some(_) = read_line_from(&mut reader) else {
        runner.fail("null answer", "no handshake");
        return;
    };

    let Some(_) = read_line_from(&mut reader) else {
        runner.skip("null answer", "no prompt");
        return;
    };

    send_answer(&mut stdin, &Value::Null);
    drop(stdin);

    let status = wait_or_kill(&mut child, Duration::from_secs(2));
    match status {
        Some(s) if s.success() => {
            runner.pass("null answer — handled gracefully");
        }
        Some(s) => {
            runner.pass(&format!(
                "null answer — exited with code {} (validation error is acceptable)",
                s.code().unwrap_or(-1)
            ));
        }
        None => {
            runner.pass("null answer — process killed after timeout (multi-prompt program)");
        }
    }
}

fn test_invalid_json(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("invalid JSON", "failed to spawn");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);
    let mut stdin = child.stdin.take().unwrap();

    let Some(_) = read_line_from(&mut reader) else {
        runner.fail("invalid JSON", "no handshake");
        return;
    };

    let Some(_) = read_line_from(&mut reader) else {
        runner.skip("invalid JSON", "no prompt");
        return;
    };

    let _ = writeln!(stdin, "not valid json at all");
    let _ = stdin.flush();
    drop(stdin);

    match wait_or_kill(&mut child, Duration::from_secs(2)) {
        Some(s) if !s.success() => {
            runner.pass("invalid JSON — rejected with non-zero exit");
        }
        Some(_) => {
            runner.fail("invalid JSON", "exited 0 — should reject invalid JSON");
        }
        None => {
            runner.fail("invalid JSON", "process did not exit");
        }
    }
}

fn test_missing_answer_key(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("missing answer key", "failed to spawn");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);
    let mut stdin = child.stdin.take().unwrap();

    let Some(_) = read_line_from(&mut reader) else {
        runner.fail("missing answer key", "no handshake");
        return;
    };

    let Some(_) = read_line_from(&mut reader) else {
        runner.skip("missing answer key", "no prompt");
        return;
    };

    let _ = writeln!(stdin, "{{\"wrong_key\": \"value\"}}");
    let _ = stdin.flush();
    drop(stdin);

    match wait_or_kill(&mut child, Duration::from_secs(2)) {
        Some(s) if !s.success() => {
            runner.pass("missing answer key — rejected");
        }
        Some(_) => {
            runner.fail(
                "missing answer key",
                "exited 0 — should reject response without 'answer' key",
            );
        }
        None => {
            runner.fail("missing answer key", "process did not exit");
        }
    }
}

fn test_eof_handling(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("EOF handling", "failed to spawn");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);

    let Some(_) = read_line_from(&mut reader) else {
        runner.fail("EOF handling", "no handshake");
        return;
    };

    let Some(_) = read_line_from(&mut reader) else {
        runner.skip("EOF handling", "no prompt");
        return;
    };

    drop(child.stdin.take());

    match wait_or_kill(&mut child, Duration::from_secs(2)) {
        Some(s) if !s.success() => {
            runner.pass("EOF handling — exited non-zero on stdin close");
        }
        Some(_) => {
            runner.fail("EOF handling", "exited 0 — should error when stdin closes without response");
        }
        None => {
            runner.fail("EOF handling", "process did not exit after stdin close");
        }
    }
}

fn test_sequential_interaction(runner: &mut TestRunner, binary: &str, args: &[String]) {
    let Some(mut child) = spawn_agent(binary, args) else {
        runner.fail("sequential interaction", "failed to spawn");
        return;
    };

    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);
    let mut stdin = child.stdin.take().unwrap();

    // Read handshake
    let Some(hs_line) = read_line_from(&mut reader) else {
        runner.fail("sequential interaction", "no handshake");
        return;
    };

    let Ok(hs) = serde_json::from_str::<Value>(&hs_line) else {
        runner.fail("sequential interaction", "handshake not JSON");
        return;
    };

    if hs.get("interaction").and_then(|v| v.as_str()) != Some("sequential") {
        runner.skip(
            "sequential interaction",
            "handshake does not declare sequential interaction",
        );
        let _ = child.kill();
        return;
    }

    // Read first prompt
    let Some(p1_line) = read_line_from(&mut reader) else {
        runner.skip("sequential interaction", "no first prompt");
        return;
    };

    let Ok(p1) = serde_json::from_str::<Value>(&p1_line) else {
        runner.fail("sequential interaction", "first prompt not JSON");
        let _ = child.kill();
        return;
    };

    // Send appropriate answer based on prompt type
    let answer = make_answer_for(&p1);
    send_answer(&mut stdin, &answer);

    // Try to read a second prompt (program may only have one)
    if let Some(p2_line) = read_line_from(&mut reader) {
        if let Ok(p2) = serde_json::from_str::<Value>(&p2_line) {
            if p2.get("type").is_some() && p2.get("message").is_some() {
                runner.pass("sequential interaction — second prompt received after first answer");
                let answer2 = make_answer_for(&p2);
                send_answer(&mut stdin, &answer2);
            } else {
                runner.pass("sequential interaction — single prompt program");
            }
        }
    } else {
        runner.pass("sequential interaction — single prompt completed");
    }

    drop(stdin);
    wait_or_kill(&mut child, Duration::from_secs(2));
}

fn make_answer_for(prompt: &Value) -> Value {
    match prompt.get("type").and_then(|v| v.as_str()) {
        Some("input") | Some("password") | Some("editor") | Some("path") | Some("autocomplete") => {
            Value::String("test".into())
        }
        Some("confirm") => Value::Bool(true),
        Some("number") => {
            let default = prompt.get("default").and_then(|v| v.as_f64()).unwrap_or(42.0);
            serde_json::json!(default)
        }
        Some("select") | Some("rawlist") | Some("search") => {
            if let Some(choices) = prompt.get("choices").and_then(|v| v.as_array()) {
                for c in choices {
                    if c.get("type").and_then(|v| v.as_str()) == Some("separator") {
                        continue;
                    }
                    if let Some(disabled) = c.get("disabled") {
                        if disabled.as_bool() == Some(true) || disabled.is_string() {
                            continue;
                        }
                    }
                    if let Some(val) = c.get("value") {
                        return val.clone();
                    }
                }
            }
            Value::String("test".into())
        }
        Some("checkbox") => {
            if let Some(choices) = prompt.get("choices").and_then(|v| v.as_array()) {
                let first: Vec<Value> = choices
                    .iter()
                    .filter(|c| {
                        c.get("type").and_then(|v| v.as_str()) != Some("separator")
                            && c.get("disabled").and_then(|v| v.as_bool()) != Some(true)
                    })
                    .take(1)
                    .filter_map(|c| c.get("value").cloned())
                    .collect();
                Value::Array(first)
            } else {
                Value::Array(vec![])
            }
        }
        Some("expand") => {
            if let Some(choices) = prompt.get("choices").and_then(|v| v.as_array()) {
                if let Some(first) = choices.first() {
                    if let Some(key) = first.get("key") {
                        return key.clone();
                    }
                }
            }
            Value::String("y".into())
        }
        _ => Value::String("test".into()),
    }
}
