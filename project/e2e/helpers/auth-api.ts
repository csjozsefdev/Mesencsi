import { APIRequestContext } from "@playwright/test";
import { execSync } from "child_process";
import path from "path";
import { BACKEND_ROOT, E2E_ADMIN_PASSWORD, E2E_ADMIN_USER, E2E_USER_EMAIL, E2E_USER_PASSWORD } from "./env";

export async function ensureVerifiedShopUser(request: APIRequestContext): Promise<void> {
  const reg = await request.post("/auth/register", {
    data: {
      email: E2E_USER_EMAIL,
      password: E2E_USER_PASSWORD,
      password_confirm: E2E_USER_PASSWORD,
      terms_accepted: true,
      privacy_acknowledged: true,
    },
  });
  if (reg.status() !== 201 && reg.status() !== 409) {
    throw new Error(`E2E register failed: ${reg.status()} ${await reg.text()}`);
  }
  const script = path.join(BACKEND_ROOT, "scripts", "dev_manual_verify_shop_user.py");
  execSync(`"${process.platform === "win32" ? path.join(BACKEND_ROOT, ".venv", "Scripts", "python.exe") : path.join(BACKEND_ROOT, ".venv", "bin", "python")}" "${script}" "${E2E_USER_EMAIL}"`, {
    cwd: BACKEND_ROOT,
    stdio: "inherit",
  });
}

export async function shopLogin(request: APIRequestContext): Promise<{ token: string; user: object }> {
  const res = await request.post("/auth/login", {
    data: { email: E2E_USER_EMAIL, password: E2E_USER_PASSWORD },
  });
  if (!res.ok()) throw new Error(`E2E shop login failed: ${res.status()} ${await res.text()}`);
  const data = await res.json();
  return { token: data.access_token as string, user: data.user as object };
}

export async function adminLogin(request: APIRequestContext): Promise<{ token: string }> {
  const res = await request.post("/admin/login", {
    data: { username: E2E_ADMIN_USER, password: E2E_ADMIN_PASSWORD },
  });
  if (!res.ok()) throw new Error(`E2E admin login failed: ${res.status()} ${await res.text()}`);
  const data = await res.json();
  const token = data.token as string;
  if (!token) throw new Error("E2E admin login: missing token in response");
  return { token };
}
