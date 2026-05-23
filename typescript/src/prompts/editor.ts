import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EditorError } from "../errors.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface EditorConfig extends BaseConfig<string> {
  postfix?: string;
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
    const editor = process.env.VISUAL || process.env.EDITOR || "vi";
    const dir = mkdtempSync(join(tmpdir(), "inquirer-"));
    const tmpPath = join(dir, `edit${this.postfix}`);

    try {
      writeFileSync(tmpPath, this.defaultValue ?? "");
      const parts = editor.split(/\s+/);
      const cmd = parts[0]!;
      const args = [...parts.slice(1), tmpPath];
      const result = spawnSync(cmd, args, {
        stdio: "inherit",
      });

      if (result.error) {
        throw new EditorError(`Editor not found: ${JSON.stringify(editor)}. Set $VISUAL or $EDITOR.`);
      }
      if (result.status !== 0) {
        throw new EditorError(`Editor exited with code ${result.status}`);
      }

      return readFileSync(tmpPath, "utf8");
    } finally {
      try {
        unlinkSync(tmpPath);
      } catch {
        // ignore cleanup errors
      }
    }
  }
}
