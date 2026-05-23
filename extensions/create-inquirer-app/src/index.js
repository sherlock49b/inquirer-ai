#!/usr/bin/env node

import { text, select, checkbox, confirm } from "inquirer-ai";
import { mkdirSync, writeFileSync, existsSync } from "node:fs";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEMPLATES_DIR = join(__dirname, "..", "templates");

async function main() {
  console.error("\n  create-inquirer-app — scaffold a new interactive CLI\n");

  const name = await text({
    message: "Project name",
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
      { name: "Python", value: "python", description: "pip install inquirer-ai" },
      { name: "TypeScript", value: "typescript", description: "npm install inquirer-ai" },
      { name: "Go", value: "go", description: "go get github.com/sherlock49b/inquirer-ai/go/prompt" },
      { name: "Rust", value: "rust", description: "cargo add inquirer-ai" },
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
      { name: "editor", value: "editor" },
      { name: "path", value: "path" },
    ],
    default: ["text", "confirm", "select"],
  });

  const agentMode = await confirm({
    message: "Include agent mode example?",
    default: true,
  });

  const targetDir = join(process.cwd(), name);
  if (existsSync(targetDir)) {
    const overwrite = await confirm({
      message: `Directory "${name}" already exists. Overwrite?`,
    });
    if (!overwrite) {
      console.error("Aborted.");
      process.exit(0);
    }
  }

  const proceed = await confirm({
    message: `Create ${language} project "${name}" with ${promptTypes.length} prompt types?`,
    default: true,
  });

  if (!proceed) {
    console.error("Aborted.");
    process.exit(0);
  }

  mkdirSync(targetDir, { recursive: true });

  const generator = generators[language];
  if (!generator) {
    console.error(`Generator for ${language} not found.`);
    process.exit(1);
  }

  generator(targetDir, name, promptTypes, agentMode);

  console.error(`\n  ✓ Created ${language} project in ./${name}/`);
  console.error(`\n  Next steps:`);
  console.error(`    cd ${name}`);

  const nextSteps = {
    python: "    uv sync && uv run python main.py",
    typescript: "    npm install && node main.js",
    go: "    go run .",
    rust: "    cargo run",
  };
  console.error(nextSteps[language]);
  console.error();
}

const generators = {
  python: generatePython,
  typescript: generateTypeScript,
  go: generateGo,
  rust: generateRust,
};

function generatePython(dir, name, types, agentMode) {
  const imports = types.map((t) => `    ${t}`).join(",\n");
  const demos = types.map((t) => pythonDemo(t)).join("\n\n");

  writeFileSync(
    join(dir, "main.py"),
    `#!/usr/bin/env python3
from inquirer_ai import (
${imports},
)


def main():
    print(f"Welcome to {name}!\\n")

${indent(demos, 4)}

    print("\\nDone!")


if __name__ == "__main__":
    main()
`,
  );

  writeFileSync(
    join(dir, "pyproject.toml"),
    `[project]
name = "${name}"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["inquirer-ai>=0.1.0"]
`,
  );

  if (agentMode) {
    writeFileSync(
      join(dir, "README.md"),
      `# ${name}

## Run interactively
\`\`\`bash
python main.py
\`\`\`

## Run with AI agent
\`\`\`bash
INQUIRER_AI_MODE=agent python main.py
\`\`\`
`,
    );
  }
}

function generateTypeScript(dir, name, types, agentMode) {
  const imports = types.join(", ");
  const demos = types.map((t) => tsDemo(t)).join("\n\n");

  writeFileSync(
    join(dir, "main.js"),
    `import { ${imports} } from "inquirer-ai";

async function main() {
  console.log("Welcome to ${name}!\\n");

${indent(demos, 2)}

  console.log("\\nDone!");
}

main();
`,
  );

  writeFileSync(
    join(dir, "package.json"),
    JSON.stringify(
      {
        name,
        version: "0.1.0",
        type: "module",
        dependencies: { "inquirer-ai": "^0.1.0" },
      },
      null,
      2,
    ) + "\n",
  );

  if (agentMode) {
    writeFileSync(
      join(dir, "README.md"),
      `# ${name}

## Run interactively
\`\`\`bash
node main.js
\`\`\`

## Run with AI agent
\`\`\`bash
INQUIRER_AI_MODE=agent node main.js
\`\`\`
`,
    );
  }
}

function generateGo(dir, name, types, agentMode) {
  const demos = types.map((t) => goDemo(t)).join("\n\n");

  writeFileSync(
    join(dir, "main.go"),
    `package main

import (
\t"fmt"
\t"os"

\t"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
\tfmt.Println("Welcome to ${name}!\\n")

${indent(demos, 1, "\t")}

\tfmt.Println("\\nDone!")
}

func fatal(err error) {
\tfmt.Fprintf(os.Stderr, "Error: %v\\n", err)
\tos.Exit(1)
}
`,
  );

  writeFileSync(
    join(dir, "go.mod"),
    `module ${name}

go 1.22

require github.com/sherlock49b/inquirer-ai v0.1.0
`,
  );

  if (agentMode) {
    writeFileSync(
      join(dir, "README.md"),
      `# ${name}

## Run interactively
\`\`\`bash
go run .
\`\`\`

## Run with AI agent
\`\`\`bash
INQUIRER_AI_MODE=agent go run .
\`\`\`
`,
    );
  }
}

function generateRust(dir, name, types, agentMode) {
  const demos = types.map((t) => rustDemo(t)).join("\n\n");

  mkdirSync(join(dir, "src"), { recursive: true });

  writeFileSync(
    join(dir, "src", "main.rs"),
    `use inquirer_ai::*;

fn main() -> Result<()> {
    println!("Welcome to ${name}!\\n");

${indent(demos, 4)}

    println!("\\nDone!");
    Ok(())
}
`,
  );

  writeFileSync(
    join(dir, "Cargo.toml"),
    `[package]
name = "${name}"
version = "0.1.0"
edition = "2021"

[dependencies]
inquirer-ai = "0.1.0"
`,
  );

  if (agentMode) {
    writeFileSync(
      join(dir, "README.md"),
      `# ${name}

## Run interactively
\`\`\`bash
cargo run
\`\`\`

## Run with AI agent
\`\`\`bash
INQUIRER_AI_MODE=agent cargo run
\`\`\`
`,
    );
  }
}

function pythonDemo(type) {
  const demos = {
    text: 'name = text("What is your name?")\nprint(f"Hello, {name}!")',
    confirm: 'ok = confirm("Continue?")\nprint(f"Answer: {ok}")',
    select: 'lang = select("Language?", choices=["Python", "Go", "TypeScript", "Rust"])\nprint(f"Selected: {lang}")',
    checkbox: 'features = checkbox("Features?", choices=["Docker", "CI/CD", "Tests"])\nprint(f"Selected: {features}")',
    password: 'token = password("API token?")\nprint(f"Token length: {len(token)}")',
    number: 'port = number("Port?", default=8080, min=1024, max=65535)\nprint(f"Port: {port}")',
    editor: 'desc = editor("Description?")\nprint(f"Lines: {len(desc.splitlines())}")',
    path: 'p = path("Output directory?")\nprint(f"Path: {p}")',
  };
  return demos[type] || "";
}

function tsDemo(type) {
  const demos = {
    text: 'const name = await text({ message: "What is your name?" });\nconsole.log(`Hello, ${name}!`);',
    confirm: 'const ok = await confirm({ message: "Continue?" });\nconsole.log(`Answer: ${ok}`);',
    select: 'const lang = await select({ message: "Language?", choices: ["Python", "Go", "TypeScript", "Rust"] });\nconsole.log(`Selected: ${lang}`);',
    checkbox: 'const features = await checkbox({ message: "Features?", choices: ["Docker", "CI/CD", "Tests"] });\nconsole.log(`Selected: ${features}`);',
    password: 'const token = await password({ message: "API token?" });\nconsole.log(`Token length: ${token.length}`);',
    number: 'const port = await number({ message: "Port?", default: 8080, min: 1024, max: 65535 });\nconsole.log(`Port: ${port}`);',
    editor: 'const desc = await editor({ message: "Description?" });\nconsole.log(`Lines: ${desc.split("\\n").length}`);',
    path: 'const p = await path({ message: "Output directory?" });\nconsole.log(`Path: ${p}`);',
  };
  return demos[type] || "";
}

function goDemo(type) {
  const demos = {
    text: 'name, err := prompt.Text(prompt.TextConfig{Message: "What is your name?"})\nif err != nil { fatal(err) }\nfmt.Printf("Hello, %s!\\n", name)',
    confirm: 'ok, err := prompt.Confirm(prompt.ConfirmConfig{Message: "Continue?"})\nif err != nil { fatal(err) }\nfmt.Printf("Answer: %v\\n", ok)',
    select: 'lang, err := prompt.Select(prompt.SelectConfig{\n\tMessage: "Language?",\n\tChoices: []prompt.ChoiceItem{\n\t\tprompt.Choice{Name: "Python", Value: "python"},\n\t\tprompt.Choice{Name: "Go", Value: "go"},\n\t\tprompt.Choice{Name: "TypeScript", Value: "typescript"},\n\t\tprompt.Choice{Name: "Rust", Value: "rust"},\n\t},\n})\nif err != nil { fatal(err) }\nfmt.Printf("Selected: %v\\n", lang)',
    checkbox: 'features, err := prompt.Checkbox(prompt.CheckboxConfig{\n\tMessage: "Features?",\n\tChoices: []prompt.ChoiceItem{\n\t\tprompt.Choice{Name: "Docker", Value: "docker"},\n\t\tprompt.Choice{Name: "CI/CD", Value: "ci"},\n\t\tprompt.Choice{Name: "Tests", Value: "tests"},\n\t},\n})\nif err != nil { fatal(err) }\nfmt.Printf("Selected: %v\\n", features)',
    password: 'token, err := prompt.Password(prompt.PasswordConfig{Message: "API token?"})\nif err != nil { fatal(err) }\nfmt.Printf("Token length: %d\\n", len(token))',
    number: 'port, err := prompt.Number(prompt.NumberConfig{Message: "Port?", Default: float64Ptr(8080), Min: float64Ptr(1024), Max: float64Ptr(65535)})\nif err != nil { fatal(err) }\nfmt.Printf("Port: %v\\n", port)',
    editor: 'desc, err := prompt.Editor(prompt.EditorConfig{Message: "Description?"})\nif err != nil { fatal(err) }\nfmt.Printf("Lines: %d\\n", len(strings.Split(desc, "\\n")))',
    path: 'p, err := prompt.Path(prompt.PathConfig{Message: "Output directory?"})\nif err != nil { fatal(err) }\nfmt.Printf("Path: %s\\n", p)',
  };
  return demos[type] || "";
}

function rustDemo(type) {
  const demos = {
    text: 'let name = text(TextConfig::new("What is your name?"))?;\nprintln!("Hello, {name}!");',
    confirm: 'let ok = confirm(ConfirmConfig::new("Continue?"))?;\nprintln!("Answer: {ok}");',
    select:
      'let lang = select(SelectConfig::new("Language?", vec![\n    ChoiceItem::Choice(Choice::new("Python", "python")),\n    ChoiceItem::Choice(Choice::new("Go", "go")),\n    ChoiceItem::Choice(Choice::new("TypeScript", "typescript")),\n    ChoiceItem::Choice(Choice::new("Rust", "rust")),\n]))?;\nprintln!("Selected: {lang}");',
    checkbox:
      'let features = checkbox(CheckboxConfig::new("Features?", vec![\n    ChoiceItem::Choice(Choice::new("Docker", "docker")),\n    ChoiceItem::Choice(Choice::new("CI/CD", "ci")),\n    ChoiceItem::Choice(Choice::new("Tests", "tests")),\n]))?;\nprintln!("Selected: {features:?}");',
    password: 'let token = password(PasswordConfig::new("API token?"))?;\nprintln!("Token length: {}", token.len());',
    number: 'let port = number(NumberConfig { message: "Port?".into(), default: Some(8080.0), min: Some(1024.0), max: Some(65535.0), float_allowed: false })?;\nprintln!("Port: {port}");',
    editor: 'let desc = editor(EditorConfig::new("Description?"))?;\nprintln!("Lines: {}", desc.lines().count());',
    path: 'let p = path(PathConfig::new("Output directory?"))?;\nprintln!("Path: {p}");',
  };
  return demos[type] || "";
}

function indent(text, level, char = "    ") {
  const prefix = char.repeat(level);
  return text
    .split("\n")
    .map((line) => (line.trim() ? prefix + line : line))
    .join("\n");
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
