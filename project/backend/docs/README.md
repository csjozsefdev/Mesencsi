# Mesencsi backend — documentation

FastAPI webshop API for [Mesencsi](https://mesencsi.hu): products, cart, guest checkout, Barion payments, admin CMS, email outbox.

**Alembic head:** `032_storybook_page_image_layout` · **Tests:** 347 pytest (SQLite in-memory)

---

## Start here

| Audience | Document |
|----------|----------|
| New developer | [DEVELOPMENT.md](./DEVELOPMENT.md) → [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Reviewer / handover | [../../HANDOVER.md](../../HANDOVER.md) · [../../REVIEW_CHECKLIST.md](../../REVIEW_CHECKLIST.md) |
| Production deploy | [deploy_readiness.md](./deploy_readiness.md) → [ops_runbook.md](./ops_runbook.md) |
| API reference | [API.md](./API.md) |
| Environment variables | [ENVIRONMENT.md](./ENVIRONMENT.md) |

---

## Core guides

| Document | Content |
|----------|---------|
| [DEVELOPMENT.md](./DEVELOPMENT.md) | Local setup, Docker, run scripts, testing |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | App structure, routers, services, database |
| [API.md](./API.md) | HTTP endpoints by area |
| [ENVIRONMENT.md](./ENVIRONMENT.md) | All env vars with defaults and production rules |
| [gate_commands.md](./gate_commands.md) | pytest / E2E gate scripts |

---

## Production & operations

| Document | Content |
|----------|---------|
| [deploy_readiness.md](./deploy_readiness.md) | Pre-deploy env checklist, smoke test order |
| [ops_runbook.md](./ops_runbook.md) | Email outbox cron, metrics, incidents, recovery |
| [pre_production_qa.md](./pre_production_qa.md) | Owner manual QA checklist |
| [migration_007_warning.md](./migration_007_warning.md) | Destructive migration 007 (legacy DBs) |
| [production_legal_todo.md](./production_legal_todo.md) | Legal pages before go-live (client task) |

---

## Email (SMTP)

| Document | Content |
|----------|---------|
| [render_smtp.md](./render_smtp.md) | SMTP on Render.com |
| [resend_smtp.md](./resend_smtp.md) | Resend SMTP setup |
| [local_auth_email_qa.md](./local_auth_email_qa.md) | Dev email verification QA |

---

## QA checklists

| Document | Content |
|----------|---------|
| [checkout_shipping_guest_qa.md](./checkout_shipping_guest_qa.md) | Guest checkout, GLS tiers, shipping |
| [mobile_storefront_smoke_checklist.md](./mobile_storefront_smoke_checklist.md) | Mobile UI smoke |
| [media_persistence_smoke.md](./media_persistence_smoke.md) | Upload persistence on deploy |
| [postgres_smoke.md](./postgres_smoke.md) | Optional real Postgres tests |
| [local_dev_cleanup.md](./local_dev_cleanup.md) | Dev user cleanup scripts |

---

## Project root (English)

| Document | Content |
|----------|---------|
| [../../HANDOVER.md](../../HANDOVER.md) | Handover & review guide |
| [../../REVIEW_CHECKLIST.md](../../REVIEW_CHECKLIST.md) | Pass/fail acceptance checklist |
| [../../PROJECT_CONTINUATION.md](../../PROJECT_CONTINUATION.md) | Current state & next steps |
| [../../E2E_TESTING.md](../../E2E_TESTING.md) | Playwright E2E tests |
| [../../BARION_SANDBOX_TESTING.md](../../BARION_SANDBOX_TESTING.md) | Barion sandbox payment testing |
| [../../CHANGELOG.md](../../CHANGELOG.md) | Release history |

---

## Quick commands

```powershell
cd backend
copy .env.example .env          # fill POSTGRES_PASSWORD, JWT secrets
docker compose up -d            # Postgres + Mailpit
.\run.bat                       # migrate + uvicorn on :8000
.\scripts\gate_pytest.ps1       # 347 tests
```

Store: http://127.0.0.1:8000/ · Admin: http://127.0.0.1:8000/admin/login · API docs: http://127.0.0.1:8000/docs (hidden when `MESENCSI_PRODUCTION=true`)
