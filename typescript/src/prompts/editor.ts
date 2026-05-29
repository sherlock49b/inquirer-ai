import { spawnSync } from "node:child_process";
import { closeSync, mkdtempSync, openSync, readFileSync, rmSync, writeSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EditorError } from "../errors.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface EditorConfig extends BaseConfig<string> {
  postfix?: string;
}

/**
 * Quote-aware shell-word split for $VISUAL/$EDITOR (R9). Honors single and
 * double quotes and backslash escapes; argv is exec'd WITHOUT a shell so there
 * is no injection surface. Mirrors the behavior of Python's shlex.split.
 */
export function splitCommand(input: string): string[] {
  const args: string[] = [];
  let current = "";
  let hasToken = false;
  let i = 0;
  const n = input.length;
  while (i < n) {
    const ch = input[i]!;
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r" || ch === "\f" || ch === "\v") {
      if (hasToken) {
        args.push(current);
        current = "";
        hasToken = false;
      }
      i++;
      continue;
    }
    hasToken = true;
    if (ch === "'") {
      i++;
      while (i < n && input[i] !== "'") {
        current += input[i];
        i++;
      }
      i++; // skip closing quote
    } else if (ch === '"') {
      i++;
      while (i < n && input[i] !== '"') {
        if (input[i] === "\\" && i + 1 < n) {
          const next = input[i + 1]!;
          // In double quotes, backslash escapes only " \ $ ` (POSIX); otherwise literal.
          if (next === '"' || next === "\\" || next === "$" || next === "`") {
            current += next;
            i += 2;
            continue;
          }
        }
        current += input[i];
        i++;
      }
      i++; // skip closing quote
    } else if (ch === "\\" && i + 1 < n) {
      current += input[i + 1];
      i += 2;
    } else {
      current += ch;
      i++;
    }
  }
  if (hasToken) args.push(current);
  return args;
}

export class EditorPrompt extends BasePrompt<string> {
  private postfix: string;

  constructor(config: EditorConfig) {
    super(config);
    this.postfix = config.postfix ?? ".txt";
  }

  get promptType(): string {
    return "editor";
  }

  protected validateAnswer(value: unknown): string {
    if (value == null) return this.defaultValue ?? "";
    return String(value);
  }

  protected override toAgentDict(): Record<string, unknown> {
    return { ...super.toAgentDict(), postfix: this.postfix };
  }

  protected async executeTerminal(): Promise<string> {
    const editorCmd = process.env.VISUAL || process.env.EDITOR || "vi";
    const parts = splitCommand(editorCmd);
    const cmd = parts[0] ?? "vi";
    const cmdArgs = parts.slice(1);

    // Secure temp file: randomized directory (0700) + randomized file name
    // created with O_EXCL | O_CREAT (no symlink follow, no clobber) at mode
    // 0600, removed on EVERY exit path (R9).
    const dir = mkdtempSync(join(tmpdir(), "inquirer-"));
    const rand = Math.random().toString(36).slice(2) + Date.now().toString(36);
    const tmpPath = join(dir, `edit-${rand}${this.postfix}`);

    try {
      // "wx" = O_WRONLY | O_CREAT | O_EXCL — fails if the path already exists
      // and does not follow a symlink to clobber another file.
      const fd = openSync(tmpPath, "wx", 0o600);
      try {
        writeSync(fd, this.defaultValue ?? "");
      } finally {
        closeSync(fd);
      }

      const result = spawnSync(cmd, [...cmdArgs, tmpPath], { stdio: "inherit" });

      if (result.error) {
        throw new EditorError(`Editor not found: ${JSON.stringify(editorCmd)}. Set $VISUAL or $EDITOR.`);
      }
      if (result.status !== 0) {
        throw new EditorError(`Editor exited with code ${result.status}`);
      }

      return readFileSync(tmpPath, "utf8");
    } finally {
      // Remove the temp dir + file on success, editor-not-found, and non-zero exit.
      try {
        rmSync(dir, { recursive: true, force: true });
      } catch {
        // ignore cleanup errors
      }
    }
  }
}
