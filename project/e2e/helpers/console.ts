import type { Page } from "@playwright/test";

const IGNORE_PATTERNS = [
  /favicon/i,
  /manifest/i,
  /Failed to load resource.*404/i,
  /Failed to load resource.*401/i,
  /net::ERR_/i,
];

export function attachConsoleCollector(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (err) => {
    errors.push(`pageerror: ${err.message}`);
  });
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (IGNORE_PATTERNS.some((re) => re.test(text))) return;
    errors.push(`console.error: ${text}`);
  });
  return errors;
}

export function assertNoCriticalConsoleErrors(errors: string[], context: string): void {
  if (errors.length) {
    throw new Error(`${context}: kritikus konzol hiba:\n${errors.join("\n")}`);
  }
}
