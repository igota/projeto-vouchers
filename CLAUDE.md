# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project layout

The live system is **`vouchers/`** (Flask + MySQL) **+ `frontend/`** (React/Vite SPA), talking to each other only over HTTP — no SSR, no shared build. Both run as Docker containers via `vouchers/docker-compose.yml` (see "Deploy" below) — that's the primary way to run this locally too, not `python app.py` directly.

`projetoTeste/` is an earlier, pre-React prototype (plain Node/Python scripts, no UI) used to validate the same external integrations. It's kept for reference but is **not** part of the running system — don't assume code there matches the current backend.

## Running

### Everything, via Docker Compose (primary path)

```powershell
cd vouchers
copy .env.example .env            # fill in real credentials/keys first
docker compose up -d --build
```

This starts four containers (names match the tech, not the compose service key — see `container_name:` in the compose file):
- `mysql` — MySQL 8, schema auto-created from `../deploy/mysql/init.sql` on first run only (a fresh volume). `vouchers/docker-compose.yml` sets `name: vouchers` explicitly so the data volume (`vouchers_mysql_data`) doesn't depend on the folder name.
- `flask` — the Gunicorn+Flask API (service key `api` in the compose file), built from `vouchers/Dockerfile`.
- `nginx` — built from `frontend/Dockerfile` (multi-stage: `npm run build` then copies the result into an Nginx image along with `deploy/nginx/vouchers.conf`); this is what publishes port 80 to the host and is what you open in a browser.
- `scheduler` — a small Alpine+cron container (`deploy/scheduler/`) that `curl`s `flask`'s `/api/repor-estoque` and `/api/limpar-expirados` daily — see "Voucher stock" below.

To rebuild just one service after a code change: `docker compose up -d --build <service>` (service keys are `mysql`, `api`, `scheduler`, `frontend` — not the container names above).

### Backend outside Docker (quick local debugging only)

```powershell
cd vouchers
pip install -r requirements.txt
copy .env.example .env
python app.py                     # Flask's own dev server, host 0.0.0.0:5000, needs a reachable MySQL
```

All secrets and environment-specific config live in `vouchers/.env` (see `.env.example` for the full list: DB credentials, Omada/iControl credentials, `KIOSK_API_KEY`, `FLASK_DEBUG`, `ALLOWED_ORIGINS`, `TIPOS_USUARIO_PERMITIDO`, printer and stock-replenishment settings). Never hardcode credentials back into the Python files. The daily job schedule is **not** in `.env` — it's the crontab baked into the `scheduler` container at startup (`deploy/scheduler/entrypoint.sh`).

The allowlist of usernames who can log into `/gerencia` lives in `vouchers/json/usuarios_permitidos.json` — not committed (same treatment as `.env`), copy `usuarios_permitidos.json.example` to `usuarios_permitidos.json` and fill in real usernames.

### Frontend outside Docker (quick local debugging only)

```powershell
cd frontend
npm install
copy .env.example .env   # dev: sets VITE_API_BASE (absolute) and VITE_KIOSK_API_KEY
npm run dev               # vite --host
npm run build              # tsc -b && vite build — reads .env.production, not .env
npm run lint
```

For a production-shaped build outside Docker, copy `.env.production.example` to `.env.production` first — it sets `VITE_API_BASE=` (empty) because Nginx serves the build and proxies `/api`/`/gerencia` from the same origin. The Docker build of `frontend/Dockerfile` passes these as build args instead of reading this file — see "Deploy" below.

There are no automated tests for either side; frontend has ESLint + a TS build check, backend has none.

### Legacy prototype (`projetoTeste/`)

```powershell
cd projetoTeste
npm install
node projetoTeste/app.js           # voucher generation test (JS)
node projetoTeste/seguranca.js     # NTI email automation (Puppeteer)
python projetoTeste/seguranca.py   # NTI email automation (Selenium)
node projetoTeste/icontrol.js      # credential search
```

## Architecture

Three external systems are involved, each with its own client module in `vouchers/`:

- **TP-Link Omada Controller** (address in `OMADA_BASE_URL`/`OMADA_SITE_ID`, see `.env.example`) — `omada.py` (voucher CRUD, client lookup/cancel) and `voucherService.py` (bulk voucher generation for stock replenishment). Both log in with `OMADA_USERNAME`/`OMADA_PASSWORD` and skip TLS verification (self-signed cert).
- **iControl** (address in `ICONTROL_BASE_URL`, see `.env.example`; ASP.NET/DataTables) — `icontrol.py`'s `BuscaCredencial` class looks up RFID cards/credentials by card number, name, or identifier.
- **Vitae / NTI** (address in `VITAE_URL`, see `.env.example`; JSF) — `vitae_auth.py` validates a coordinator's real login against this system (scrapes the JSF login form); there is no separate password store for `/gerencia`.

### Two frontend flows, two backend auth models

**Kiosk flow** (`frontend/src/pages/LeitorCartao.tsx` → `VoucherUsuario.tsx`, routes `/` and `/voucher`) — no user login. An RFID reader emulates a keyboard; the page buffers keystrokes and calls the unauthenticated-by-login (but key-protected) endpoints in `vouchers/app.py`: `buscar-cartao`, `liberar-voucher`, `substituir-voucher`, `cancelar-voucher`, `verificar-estoque`, `repor-estoque`, `limpar-expirados`, `imprimir-etiqueta`. All of them require the header `X-Kiosk-Key`, checked by the `kiosk_key_obrigatoria` decorator with no bypass — the daily jobs call these same endpoints over HTTP too (see "Voucher stock" below), so there's no in-process caller that needs to skip the check. Only iControl users whose `tipo_usuario` matches `TIPOS_USUARIO_PERMITIDO` (env) can pull a voucher. The frontend sends this key via `frontend/src/kioskApi.ts`'s `kioskFetch` — note the key ships in the public JS bundle, so it only screens out casual/off-network access, not a determined attacker with DevTools on the kiosk itself.

**Gerência (admin) flow** (`GerenciaLogin.tsx` → `GerenciaDashboard.tsx`, routes `/gerencia` and `/gerencia/consulta`, backend blueprint `gerencia.py`) — real login: username must be in `vouchers/json/usuarios_permitidos.json`, password is validated live against Vitae. On success the backend issues a random session token (2h TTL) stored in the `gerencia_sessoes` MySQL table (**not** an in-memory dict — Gunicorn runs multiple worker processes, and a dict in one worker's memory is invisible to the others, which caused intermittent "Não autenticado" errors until this was fixed) and the frontend stores it in `localStorage`, sending it as `X-Gerencia-Token` (`gerenciaApi.ts`'s `gerenciaFetch`), checked by the `login_obrigatorio` decorator. Dashboard features: search a person in iControl, check/generate/replace/deactivate a voucher (arbitrary duration), view stock and issuance history.

### Voucher stock

Three MySQL tables (schema in `deploy/mysql/init.sql`, applied automatically to a fresh `mysql` container; pool config in `conexao.py`). `banco de dados/script_vouchers.sql` is an older scratch/reference copy of the first two tables with ad-hoc maintenance commands mixed in — don't mount it as an init script, it's not idempotent.
- `vouchers_disponiveis` — stock: voucher code, `periodo` (bucket label, e.g. `1dia`), `status` (`disponivel`/`usado`).
- `vouchers_impressos` — issuance history, FK to `vouchers_disponiveis`, keyed by `numero_cartao`/`id_credencial`.
- `gerencia_sessoes` — `/gerencia` login sessions (see above).

There is no in-process scheduler. The `scheduler` container (`deploy/scheduler/`) runs busybox `crond` — its `entrypoint.sh` writes `/etc/crontabs/root` at startup with `$KIOSK_API_KEY` substituted in, then two daily cron entries `curl` the corresponding endpoint on `flask:8000`. This reuses the exact same logic the API already exposes instead of duplicating it elsewhere, and avoids the classic "duplicate job per Gunicorn worker" bug an in-process background thread would hit:
- **Repor estoque** (`/api/repor-estoque`) — if available `1dia` stock drops to/under `ESTOQUE_LIMITE_MINIMO`, tops back up to `ESTOQUE_LIMITE_MAXIMO` by generating new Omada vouchers (duration `VOUCHER_REPOSICAO_DURACAO_MINUTOS`) via `voucherService.gerar_e_inserir_vouchers` (parallel `ThreadPoolExecutor`) and bulk-inserting them.
- **Limpar expirados** (`/api/limpar-expirados`) — walks `vouchers_impressos`, checks each voucher's `valid` state in Omada, deletes the DB record for ones no longer valid (frees that card/credential to receive a new voucher).

To change the schedule, edit the cron lines in `deploy/scheduler/entrypoint.sh` and rebuild that one container (`docker compose up -d --build scheduler`).

Note: `alpine`'s separate `dcron` package crashes with `setpgid: Operation not permitted` when run as PID 1 in a container — the entrypoint deliberately uses the busybox-builtin `crond` instead (no extra `apk add` needed for it).

### Printing

Network-only: `imprimir-etiqueta` sends an EPL label over a raw TCP socket (port 9100) to a networked Godex BPE300, gated by `IMPRESSORA_REDE_HABILITADA`/`IMPRESSORA_REDE_IP` in `.env`. USB printing (`win32print`) was removed along with the Windows-only deployment path — there's no local-printer fallback anymore.

## Deploy

Runs as four Docker containers via `vouchers/docker-compose.yml` — see "Running" above for the commands. `flask` needs `cryptography` installed (in `requirements.txt`) because PyMySQL requires it for MySQL 8's default `caching_sha2_password` auth — easy to forget since it's an indirect/optional dependency, not something imported directly.

`flask` connects as `DB_USER`/`DB_PASSWORD` (a dedicated `vouchers_app` MySQL user, `ALL PRIVILEGES` scoped to `vouchers_db` only — no access to other databases, no admin grants), never as root. `DB_ROOT_PASSWORD` is a separate `.env` value used only by the `mysql` container itself (its healthcheck, and `MYSQL_ROOT_PASSWORD` at first init) — the app never reads it. `MYSQL_USER`/`MYSQL_PASSWORD` in `docker-compose.yml` make the official MySQL image create that app user automatically, but **only on a brand-new empty volume** — on a volume that already has data (e.g. after this change was made), the user has to be created once by hand:
```sql
CREATE USER 'vouchers_app'@'%' IDENTIFIED BY '<DB_PASSWORD>';
GRANT ALL PRIVILEGES ON vouchers_db.* TO 'vouchers_app'@'%';
```

All four services share the `x-logging` anchor (`json-file`, `max-size: 10m`, `max-file: 3`) — without it Docker's default log driver has no size limit, and a container logging for months straight can fill the VM's disk. No HTTPS on purpose: this only runs on the internal LAN, not exposed externally, so a self-signed cert was judged not worth the hassle of installing it as trusted on every device that hits `/gerencia`.

Target host is a Debian VM: install Docker there, copy the repo (or just `vouchers/`, `frontend/`, `deploy/`, and `banco de dados/` if you want it for reference), fill in `vouchers/.env`, and run the same `docker compose up -d --build` from `vouchers/`. Nothing in the compose file is Windows/Docker-Desktop-specific. Containers use `restart: unless-stopped`, so as long as the Docker daemon itself is enabled on boot (`systemctl enable docker`, standard on Debian), the stack comes back after a VM reboot without any extra systemd unit.

`deploy/nginx/vouchers.conf` is baked into the `nginx` image at build time (see `frontend/Dockerfile`) — don't expect to hand-edit it on a running container; change the file and rebuild that service. Its `location ~ ^/gerencia/(login|logout|api/)` regex is deliberately narrow: a bare `location /gerencia/` would also swallow the frontend's own `/gerencia` and `/gerencia/consulta` SPA routes (both served by the same Nginx, same path prefix as the Flask blueprint) and proxy them to Flask, which 404s since those aren't Flask routes.

There is no Windows production path anymore — `run.py` (Waitress + pystray tray icon) was removed when the target moved to Debian, and bare-metal systemd units (Gunicorn/Nginx installed directly on the host, no Docker) were tried first but replaced by the Docker Compose setup described here.
