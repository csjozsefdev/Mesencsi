export const E2E_BASE_URL = process.env.E2E_BASE_URL || "http://127.0.0.1:8000";
export const E2E_API_URL = process.env.E2E_API_URL || E2E_BASE_URL;

export const E2E_USER_EMAIL = process.env.E2E_USER_EMAIL || "e2e-buyer@mesencsi.test";
export const E2E_USER_PASSWORD = process.env.E2E_USER_PASSWORD || "E2eTest1234!";

export const E2E_ADMIN_USER = process.env.E2E_ADMIN_USER || "owner";
export const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "jelszó";

import path from "path";

export const BACKEND_ROOT = process.env.E2E_BACKEND_ROOT || path.join(__dirname, "../../backend");
