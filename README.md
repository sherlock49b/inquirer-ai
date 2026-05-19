# inquirer-ai

Interactive CLI prompts for both humans and AI agents.

A dual-mode library that lets developers build CLI tools operable by both humans (terminal UI) and AI agents (structured JSON protocol). When a human runs the tool, they get arrow-key navigation, checkboxes, etc. When an agent calls it via subprocess, the same prompts are exchanged as JSON over stdin/stdout.

## Packages

| Package | Language | Status |
|---------|----------|--------|
| [python/](./python/) | Python | Available |
| [typescript/](./typescript/) | TypeScript | Planned |

## Agent Protocol

All implementations share the same JSON line protocol:

```
CLI stdout → {"type": "select", "message": "Choose DB:", "choices": [...]}
Agent stdin → {"answer": "PostgreSQL"}
```

See each package's README for language-specific usage.

## License

MIT
