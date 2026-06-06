export const E2E_BASE_URL = process.env.E2E_BASE_URL || "http://127.0.0.1:8000";
export const E2E_API_URL = process.env.E2E_API_URL || E2E_BASE_URL;

export const E2E_USER_EMAIL = process.env.E2E_USER_EMAIL || "e2e-buyer@example.com";
export const E2E_USER_PASSWORD = process.env.E2E_USER_PASSWORD || "E2eTest1234!";

import fs from "fs";
import path from "path";

export const BACKEND_ROOT = process.env.E2E_BACKEND_ROOT || path.join(__dirname, "../../backend");

function readBackendEnvValue(key: string): string {
  const envPath = path.join(BACKEND_ROOT, ".env");
  if (!fs.existsSync(envPath)) return "";
  const text = fs.readFileSync(envPath, "utf8");
  const re = new RegExp(`^${key}=(.*)$`, "m");
  const m = text.match(re);
  if (!m) return "";
  return m[1].trim().replace(/^["']|["']$/g, "");
}

const backendOwnerUser = readBackendEnvValue("OWNER_USERNAME");

export const E2E_ADMIN_USER =
  process.env.E2E_ADMIN_USER || backendOwnerUser || "owner";
export const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "jelszó";

export const E2E_AUTH_DIR = path.join(__dirname, "../.auth");
export const E2E_ADMIN_READY_FILE = path.join(E2E_AUTH_DIR, ".admin-ready");

export function hasAdminE2eSession(): boolean {
  return fs.existsSync(path.join(E2E_AUTH_DIR, "admin-owner.json"));
}
