# Short-Term Cloud Handoff Design

## Purpose and Constraints

Run the existing recommendation console for two or three days on the user's existing Tencent Cloud Linux server (2 CPU cores, 4 GiB RAM), primarily from mobile browsers. The existing bookkeeping application on public port 8080 remains independent. The local Windows installation stays usable without a login after the cloud period. No production model, signal, scoring, or stake rule changes are part of this work.

The cloud installation uses plain HTTP as explicitly chosen for this short period. HTTP exposes credentials and application data to anyone able to observe the connection. The design limits the public surface and lifetime but does not claim to make HTTP confidential. No domain, TLS certificate, Tailscale client, or separate application account database is required.

## Considered Approaches

1. **Recommended: separate Nginx entry on port 8081 with per-device Basic Auth.** Nginx serves the built frontend and proxies `/api` to one localhost-only FastAPI process. This protects both static pages and every API route without adding login state to the application. Authentication is enabled by deploying the cloud entry; the existing local startup remains unauthenticated.
2. **Application-managed device tokens.** This needs a login screen, token storage and forwarding in every frontend request, server-side token validation, and revocation behavior. Plain HTTP still exposes the token, so the extra code does not solve the principal transport risk for this short deployment.
3. **Reuse the bookkeeping application's entry and authentication.** This couples two unrelated applications and complicates rollback. The new application therefore gets its own service and port.

## Cloud Runtime and Access

- A dedicated systemd service runs `uvicorn icewine_web:app` from the repository root with `PYTHONPATH=src`, one worker, and a Python 3.11-or-newer virtual environment. It binds only to `127.0.0.1` on a port selected after checking existing listeners. The paper automation scheduler consequently has only one instance.
- Build the Vite frontend once and serve `web/dist` through Nginx; do not run the Vite development server continuously. Nginx listens on public port 8081, authenticates every route including `/api`, and proxies API requests to FastAPI. The cloud firewall/security group exposes only that new public port for this application; the FastAPI port stays closed externally. Existing port 8080 and its service are untouched.
- Give each device a distinct, easy-to-type lowercase username such as `iphone`, `android`, `laptop`, or `tablet`. Generate a 12-character password with a cryptographically secure random generator from letters and digits excluding visually ambiguous `0`, `O`, `1`, `I`, and `l`. The user can change the labels, but duplicate usernames are rejected. Each account has the same application access; a username labels a credential, not a hardware-bound device.
- Store only password hashes in the Nginx credential file outside the repository. Generate and display each plaintext password once during interactive setup; do not place it in command arguments, shell history, the deployment manifest, URL, or application logs. A device can be revoked by removing its entry and reloading Nginx. No separate administrator password is added for this short period.
- The project `.env` is transferred separately over SSH, stored with restricted permissions, and never placed under the Nginx document root. The browser does not receive provider API keys, but a stolen browser credential could invoke write and paid-sync endpoints. Stop exposing port 8081 and revoke the credentials at the end of the cloud period.

## Data Boundary

`local_data/icewine_prediction.sqlite3` is the authoritative application database. Only one installation may write it at a time. The local-to-cloud cutover finishes before the cloud service starts; the cloud-to-local cutover stops cloud writers before the local service resumes. Scripts reject a handoff if training, paper automation, or a separate odds worker is still active. They do not silently stop an active worker.

The initial package includes a consistent SQLite backup, the latest successful training run's three CSV artifacts, the older baseline CSVs used by fallback/default paths, generated training reports under `docs/数据审计` and `docs/模型实验`, mutable display-name and translation-status YAML, and required configuration. The cloud `.env` is handled as a separate secret. Code and built frontend are included. Old database copies, `local_data/reports`, `local_data/research_deps`, historical training snapshots, `web/node_modules`, and development caches are not part of the minimum recommendation runtime. The preflight checks the latest recommendation CSV and training-page artifact paths before packaging.

Cloud training writes new CSVs under `local_data/training` and reports under the generated audit/model-report directories. Display-name editing writes `config/display_names.yaml`; translation completion writes `config/display_translation_status.yaml`. These files, the cloud database, and operational odds logs are included in the return bundle. Existing local historical artifacts are retained. The local `.env` is not overwritten on return.

Existing `training_runs` rows store relative Windows-style paths. Resolve persisted artifact paths as project-relative paths with either slash convention, without rewriting historical database values. Linux-created relative paths must likewise remain readable on Windows after return. Absolute or escaping paths are not accepted from a transfer manifest.

## Handoff Workflow

1. **Preflight:** record the code revision and file checksums; inspect the Linux distribution, CPU architecture, free disk, Python availability, ports, and security-group access. Require at least 15 GiB free before transfer so the live database, staged copy, backups, dependencies, and new training outputs can coexist. Verify the current local database with SQLite `integrity_check` and identify the latest successful training files. Do not require a clean Git tree or include unrelated local files.
2. **Initial cutover:** wait for local workers and training to finish, stop the local Web service, and create a consistent SQLite snapshot with the backup API. Stage the selected files and SHA-256 manifest locally; upload over SSH to a new cloud staging directory. Verify checksums on the server, install dependencies, configure the isolated services and credentials, then start cloud FastAPI and Nginx. Keep the local original as a rollback copy and leave local automation stopped.
3. **Daily operation:** systemd restarts the Web process after failure. Keep a daily checked SQLite backup outside the public web root with limited retention. Monitor health, worker status, database integrity, disk space, and API-provider errors. Avoid concurrent full training and bulk historical-odds backfill on 4 GiB RAM. A cloud full-training run must be tested before depending on it.
4. **Return cutover:** wait for cloud tasks/workers to finish and stop cloud FastAPI. Create and integrity-check a final SQLite backup; stage all cloud-created training/report files, mutable YAML, and relevant logs with a checksum manifest. Download over SSH into a new local staging directory. Refuse restoration if the local database or mutable files changed after initial cutover. Preserve the pre-cloud local data, verify all downloads, replace active files, start the local Web service, and validate recommendations and recent records. Only then close cloud port 8081 and disable the cloud service.
5. **Failure behavior:** any failed transfer, checksum, integrity, or readiness check leaves the receiving installation stopped and keeps its previous active data intact. Do not delete a verified source or backup automatically. A failed cloud deployment resumes local operation from the retained local copy; a failed return keeps the cloud copy available until repair.

The handoff is a full-database ownership transfer, not row-level bidirectional synchronization. That avoids SQLite primary-key and update conflicts across matches, odds, training, and paper recommendations.

## User Interface and Validation

The production frontend must report API failures rather than silently replacing real data with mock matches or recommendations. Local development may retain its existing mock fallback behind an explicit development-only setting. Mobile acceptance covers login, match list filtering, match detail and wide odds-table scrolling, paper recommendations, training status, and record actions at common iPhone and Android widths.

Automated checks cover cross-platform training path resolution, transfer-manifest selection and checksum rejection, SQLite backup/restore on a temporary database, and frontend production API-failure behavior. Server acceptance checks verify unauthenticated requests receive `401`, each configured device credential reaches the page and API, revoked credentials stop working, the backend port is not publicly reachable, and the existing 8080 application continues to operate. Verify one cloud recommendation against the same database and training CSV before enabling normal use.

## Cost and Limits

The existing server is the only compute instance; Nginx, systemd, SSH, and Python add no license fee. The current main database is about 1.86 GiB and the minimum selected training artifacts are measured during packaging, so the initial transfer is expected to be roughly 2 GiB plus code and configuration. The return transfer is primarily the then-current database and new artifacts. Cloud outbound traffic or extra block storage may incur charges under the user's existing Tencent Cloud plan; the script reports actual package sizes before transfer.

This design does not implement TLS, real hardware binding, multiuser permissions, automatic row merging, or changes to the existing bookkeeping application. Cloud API reachability and full-training memory usage must be measured on the actual Linux server before the final cutover.
