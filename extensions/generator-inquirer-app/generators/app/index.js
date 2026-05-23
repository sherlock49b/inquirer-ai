import Generator from "yeoman-generator";
import {
  text,
  select,
  checkbox,
  confirm,
  number,
} from "inquirer-ai";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export default class InquirerAppGenerator extends Generator {
  #answers = {};

  async prompting() {
    const name = await text({
      message: "Project name",
      default: this.appname.replace(/\s+/g, "-"),
      validate: (s) => {
        if (!s.trim()) return "Project name is required";
        if (!/^[a-z0-9_-]+$/i.test(s.trim()))
          return "Use only letters, numbers, hyphens, dashes";
        return true;
      },
      filter: (s) => s.trim().toLowerCase(),
    });

    const language = await select({
      message: "Language",
      choices: [
        {
          name: "Python",
          value: "python",
          description: "pip install inquirer-ai",
        },
        {
          name: "TypeScript",
          value: "typescript",
          description: "npm install inquirer-ai",
        },
        {
          name: "Go",
          value: "go",
          description:
            "go get github.com/sherlock49b/inquirer-ai/go/prompt",
        },
        {
          name: "Rust",
          value: "rust",
          description: "cargo add inquirer-ai",
        },
      ],
    });

    const promptTypes = await checkbox({
      message: "Which prompt types to include in the demo?",
      choices: [
        { name: "text", value: "text" },
        { name: "confirm", value: "confirm" },
        { name: "select", value: "select" },
        { name: "checkbox", value: "checkbox" },
        { name: "password", value: "password" },
        { name: "number", value: "number" },
      ],
      default: ["text", "confirm", "select"],
    });

    const agentExample = await confirm({
      message: "Include agent mode usage in README?",
      default: true,
    });

    this.#answers = { name, language, promptTypes, agentExample };
  }

  writing() {
    const { name, language, promptTypes, agentExample } = this.#answers;
    const dest = this.destinationPath(name);

    const gen = generators[language];
    if (gen) gen(dest, name, promptTypes, agentExample);
  }

  end() {
    const { name, language } = this.#answers;
    const steps = {
      python: `cd ${name} && pip install inquirer-ai && python main.py`,
      typescript: `cd ${name} && npm install && node main.js`,
      go: `cd ${name} && go mod tidy && go run .`,
      rust: `cd ${name} && cargo run`,
    };
    this.log("");
    this.log(`  ✓ Created ${language} project in ${name}/`);
    this.log("");
    this.log("  Next steps:");
    this.log(`    ${steps[language]}`);
    this.log("");
  }
}

const generators = { python: genPython, typescript: genTS, go: genGo, rust: genRust };

function genPython(dest, name, types, agentExample) {
  mkdirSync(dest, { recursive: true });

  const imports = types.join(", ");
  const demos = types.map((t) => pyDemo[t] || "").join("\n\n");

  writeFileSync(
    join(dest, "main.py"),
    `#!/usr/bin/env python3
from inquirer_ai import ${imports}


def main():
    print(f"Welcome to ${name}!\\n")

${indent(demos, "    ")}

    print("\\nDone!")


if __name__ == "__main__":
    main()
`,
  );

  writeFileSync(
    join(dest, "pyproject.toml"),
    `[project]
name = "${name}"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["inquirer-ai>=0.1.0"]
`,
  );

  if (agentExample) writeReadme(dest, name, "python main.py");
}

function genTS(dest, name, types, agentExample) {
  mkdirSync(dest, { recursive: true });

  const imports = types.join(", ");
  const demos = types.map((t) => tsDemo[t] || "").join("\n\n");

  writeFileSync(
    join(dest, "main.js"),
    `import { ${imports} } from "inquirer-ai";

async function main() {
  console.log("Welcome to ${name}!\\n");

${indent(demos, "  ")}

  console.log("\\nDone!");
}

main();
`,
  );

  writeFileSync(
    join(dest, "package.json"),
    JSON.stringify(
      { name, version: "0.1.0", type: "module", dependencies: { "inquirer-ai": "^0.1.0" } },
      null,
      2,
    ) + "\n",
  );

  if (agentExample) writeReadme(dest, name, "node main.js");
}

function genGo(dest, name, types, agentExample) {
  mkdirSync(dest, { recursive: true });

  const demos = types.map((t) => goDemo[t] || "").join("\n\n");

  writeFileSync(
    join(dest, "main.go"),
    `package main

import (
\t"fmt"
\t"os"

\t"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
\tfmt.Println("Welcome to ${name}!\\n")

${indent(demos, "\t")}

\tfmt.Println("\\nDone!")
}

func fatal(err error) {
\tfmt.Fprintf(os.Stderr, "Error: %v\\n", err)
\tos.Exit(1)
}
`,
  );

  writeFileSync(
    join(dest, "go.mod"),
    `module ${name}

go 1.22

require github.com/sherlock49b/inquirer-ai v0.1.0
`,
  );

  if (agentExample) writeReadme(dest, name, "go run .");
}

function genRust(dest, name, types, agentExample) {
  mkdirSync(join(dest, "src"), { recursive: true });

  const demos = types.map((t) => rustDemo[t] || "").join("\n\n");

  writeFileSync(
    join(dest, "src", "main.rs"),
    `use inquirer_ai::*;

fn main() -> Result<()> {
    println!("Welcome to ${name}!\\n");

${indent(demos, "    ")}

    println!("\\nDone!");
    Ok(())
}
`,
  );

  writeFileSync(
    join(dest, "Cargo.toml"),
    `[package]
name = "${name}"
version = "0.1.0"
edition = "2021"

[dependencies]
inquirer-ai = "0.1.0"
`,
  );

  if (agentExample) writeReadme(dest, name, "cargo run");
}

function writeReadme(dest, name, runCmd) {
  writeFileSync(
    join(dest, "README.md"),
    `# ${name}

## Run interactively
\`\`\`bash
${runCmd}
\`\`\`

## Run with AI agent
\`\`\`bash
INQUIRER_AI_MODE=agent ${runCmd}
\`\`\`
`,
  );
}

const pyDemo = {
  text: 'name = text("What is your name?")\nprint(f"Hello, {name}!")',
  confirm: 'ok = confirm("Continue?")\nprint(f"Answer: {ok}")',
  select: 'lang = select("Pick a language", choices=["Python", "Go", "TypeScript", "Rust"])\nprint(f"Selected: {lang}")',
  checkbox: 'features = checkbox("Features?", choices=["Docker", "CI/CD", "Tests"])\nprint(f"Selected: {features}")',
  password: 'token = password("API token?")\nprint(f"Token length: {len(token)}")',
  number: 'port = number("Port?", default=8080, min=1024, max=65535)\nprint(f"Port: {port}")',
};

const tsDemo = {
  text: 'const name = await text({ message: "What is your name?" });\nconsole.log(`Hello, ${name}!`);',
  confirm: 'const ok = await confirm({ message: "Continue?" });\nconsole.log(`Answer: ${ok}`);',
  select: 'const lang = await select({ message: "Pick a language", choices: ["Python", "Go", "TypeScript", "Rust"] });\nconsole.log(`Selected: ${lang}`);',
  checkbox: 'const features = await checkbox({ message: "Features?", choices: ["Docker", "CI/CD", "Tests"] });\nconsole.log(`Selected: ${features}`);',
  password: 'const token = await password({ message: "API token?" });\nconsole.log(`Token length: ${token.length}`);',
  number: 'const port = await number({ message: "Port?", default: 8080, min: 1024, max: 65535 });\nconsole.log(`Port: ${port}`);',
};

const goDemo = {
  text: 'name, err := prompt.Text(prompt.TextConfig{Message: "What is your name?"})\nif err != nil { fatal(err) }\nfmt.Printf("Hello, %s!\\n", name)',
  confirm: 'ok, err := prompt.Confirm(prompt.ConfirmConfig{Message: "Continue?"})\nif err != nil { fatal(err) }\nfmt.Printf("Answer: %v\\n", ok)',
  select: 'lang, err := prompt.Select(prompt.SelectConfig{\n\tMessage: "Pick a language",\n\tChoices: []prompt.ChoiceItem{\n\t\tprompt.Choice{Name: "Python", Value: "python"},\n\t\tprompt.Choice{Name: "Go", Value: "go"},\n\t\tprompt.Choice{Name: "TypeScript", Value: "typescript"},\n\t\tprompt.Choice{Name: "Rust", Value: "rust"},\n\t},\n})\nif err != nil { fatal(err) }\nfmt.Printf("Selected: %v\\n", lang)',
  checkbox: 'features, err := prompt.Checkbox(prompt.CheckboxConfig{\n\tMessage: "Features?",\n\tChoices: []prompt.ChoiceItem{\n\t\tprompt.Choice{Name: "Docker", Value: "docker"},\n\t\tprompt.Choice{Name: "CI/CD", Value: "ci"},\n\t\tprompt.Choice{Name: "Tests", Value: "tests"},\n\t},\n})\nif err != nil { fatal(err) }\nfmt.Printf("Selected: %v\\n", features)',
  password: 'token, err := prompt.Password(prompt.PasswordConfig{Message: "API token?"})\nif err != nil { fatal(err) }\nfmt.Printf("Token length: %d\\n", len(token))',
  number: 'port, err := prompt.Number(prompt.NumberConfig{Message: "Port?", Default: float64Ptr(8080), Min: float64Ptr(1024), Max: float64Ptr(65535)})\nif err != nil { fatal(err) }\nfmt.Printf("Port: %v\\n", port)',
};

const rustDemo = {
  text: 'let name = text(TextConfig::new("What is your name?"))?;\nprintln!("Hello, {name}!");',
  confirm: 'let ok = confirm(ConfirmConfig::new("Continue?"))?;\nprintln!("Answer: {ok}");',
  select: 'let lang = select(SelectConfig::new("Pick a language", vec![\n    ChoiceItem::Choice(Choice::new("Python", "python")),\n    ChoiceItem::Choice(Choice::new("Go", "go")),\n    ChoiceItem::Choice(Choice::new("TypeScript", "typescript")),\n    ChoiceItem::Choice(Choice::new("Rust", "rust")),\n]))?;\nprintln!("Selected: {lang}");',
  checkbox: 'let features = checkbox(CheckboxConfig::new("Features?", vec![\n    ChoiceItem::Choice(Choice::new("Docker", "docker")),\n    ChoiceItem::Choice(Choice::new("CI/CD", "ci")),\n    ChoiceItem::Choice(Choice::new("Tests", "tests")),\n]))?;\nprintln!("Selected: {features:?}");',
  password: 'let token = password(PasswordConfig::new("API token?"))?;\nprintln!("Token length: {}", token.len());',
  number: 'let port = number(NumberConfig { message: "Port?".into(), default: Some(8080.0), min: Some(1024.0), max: Some(65535.0), float_allowed: false })?;\nprintln!("Port: {port}");',
};

function indent(text, prefix) {
  return text
    .split("\n")
    .map((line) => (line.trim() ? prefix + line : line))
    .join("\n");
}
