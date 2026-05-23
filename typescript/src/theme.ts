export interface Theme {
  question: string;
  success: string;
  pointer: string;
  highlight: string;
  selected: string;
  answer: string;
  error: string;
  muted: string;
  symQuestion: string;
  symSuccess: string;
  symPointer: string;
  symChecked: string;
  symUnchecked: string;
}

export const defaultTheme: Theme = {
  question: "#9fa4e3",
  success: "#62bfa1",
  pointer: "#9c99ec",
  highlight: "#90bbe9",
  selected: "#59bca4",
  answer: "#9db9dd",
  error: "#d77780",
  muted: "#84858f",
  symQuestion: "?",
  symSuccess: "✓",
  symPointer: "❯",
  symChecked: "◉",
  symUnchecked: "◯",
};

let currentTheme: Theme = { ...defaultTheme };

export function setTheme(theme: Partial<Theme>): void {
  currentTheme = { ...currentTheme, ...theme };
}

export function getTheme(): Theme {
  return currentTheme;
}

export const RESET = "\x1b[0m";
export const BOLD = "\x1b[1m";

export function ansi(hexColor: string): string {
  const h = hexColor.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `\x1b[38;2;${r};${g};${b}m`;
}
