# OpsLens &mdash; Smart IT Helpdesk & Incident Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.12%20|%203.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-green.svg)](https://palletsprojects.com/p/flask/)
[![SQLite](https://img.shields.io/badge/SQLite-3-lightgrey.svg)](https://sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-41%20Passed%20(94%25%20Coverage)-brightgreen.svg)](https://pytest.org/)
[![Security](https://img.shields.io/badge/Security-RBAC%20%7C%20CSRF%20%7C%20Audit%20Logs-red.svg)](#security-architecture--cyber-security-focus)

**OpsLens** is a modern, security-hardened IT Service Management (ITSM) and Incident Analytics platform. Built with Python, Flask, SQLite, and vanilla ES6/Chart.js, OpsLens mirrors real-world enterprise incident response systems (e.g., Jira Service Management, ServiceNow, PagerDuty) while maintaining clean, readable architecture designed for technical portfolio defense and software engineering interviews.

---

## ⚡ Key Highlights & Features

1. **Executive Incident Dashboard & KPIs**:
   - Real-time incident counts (Total, Open, In Progress, Resolved, Critical).
   - **Mean Time to Resolution (MTTR)** computed natively in SQLite using Julian day arithmetic.
   - Interactive visualizations powered by **Chart.js**: Incident status doughnut, priority severity distribution, and category breakdown.
   - **Pattern Telemetry & Recurring Issue Detection**: Algorithmic clustering of repeated incidents (e.g. VPN timeouts, IAM desyncs, DLP alerts).

2. **Incident Lifecycle Management (CRUD)**:
   - Full ticket submission, editing, searching, and filtering.
   - Multi-faceted query filters (keyword search across title/description, status, priority, and category).
   - Collaborative timeline supporting public user discussions and **confidential internal support notes** (strictly hidden from requesters).
   - Dynamic lifecycle transitions (`open` &rarr; `in_progress` &rarr; `resolved` &rarr; `closed`) with automated timestamp tracking (`resolved_at`).

3. **Enterprise Role-Based Access Control (RBAC)**:
   - **Admin**: Full visibility, system audit log inspection, ticket management, and user configuration.
   - **Support Agent**: Triage queue, update status/priority/assignee, view and author confidential internal notes.
   - **Requester**: Least-privilege access &mdash; isolated strictly to viewing and managing tickets they submitted.

4. **Defense-in-Depth Cyber Security**:
   - **100% Parameterized SQL Queries**: Complete protection against SQL Injection (`?` placeholders).
   - **Work-Factored Password Hashing**: `scrypt` / `PBKDF2-SHA256` salted password derivation (via `Werkzeug`).
   - **CSRF Defense**: Synchronizer Token Pattern enforced on all state-changing HTTP requests (`POST`, `PUT`, `DELETE`).
   - **Session Security**: Signed cookies with `HttpOnly=True`, `SameSite='Lax'`, and session fixation defenses (session ID regenerated upon login).
   - **Open Redirect Protection**: Relative destination validation preventing external phishing redirects.
   - **Tamper-Evident Audit Logging**: Dedicated relational logging capturing user ID, event action, client IP, timestamp, and metadata.
   - **Security Headers**: Standard defense against Clickjacking (`X-Frame-Options: SAMEORIGIN`) and MIME-sniffing (`X-Content-Type-Options: nosniff`).

5. **Automated Test Suite**:
   - **41 automated tests** with **94% test coverage** via `pytest` and `pytest-cov`.
   - Comprehensive test suites for CRUD, RBAC, input validation, SQL injection resilience, CSRF enforcement, and MTTR zero-division edge cases.

---

## 🏗️ Architecture & Technology Stack

```
+---------------------------------------------------------------------------------+
|                               Presentation Layer                                |
|  - Semantic HTML5 + Jinja2 (Context-aware auto-escaping against XSS)            |
|  - Modern, responsive CSS3 (Clean IT Operations UI, accessible contrast)       |
|  - Vanilla JavaScript (ES6) + Chart.js (Incident trends & MTTR visualization)   |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
|                           Application Layer (Flask)                             |
|  - Application Factory pattern (`create_app`) with modular Blueprints           |
|  - Blueprints: `auth`, `tickets`, `analytics`, `errors`                         |
|  - Server-Side Role-Based Access Control (RBAC): Admin, Agent, Requester        |
|  - Synchronizer Token CSRF protection for state-changing HTTP methods           |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
|                           Security & Audit Layer                                |
|  - Password Hashing: PBKDF2-SHA256 / scrypt (Salted, work-factored)             |
|  - Session Cookies: HttpOnly (mitigates XSS), SameSite=Lax (mitigates CSRF)     |
|  - Tamper-Evident Audit Logs: Captures IP, user ID, action, timestamp           |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
|                            Data Persistence Layer                               |
|  - SQLite3 with Foreign Key enforcement (`PRAGMA foreign_keys = ON`)            |
|  - 100% Parameterized queries (`?`) — Zero SQL Injection risk                   |
|  - Indexes on filter hotspots (status, priority, category, created_at)          |
+---------------------------------------------------------------------------------+
```

### Tech Stack Breakdown
- **Backend**: Python 3 (3.12+ / 3.14 compatible), Flask 3.1.3
- **Database**: SQLite3 with strict relational integrity (`PRAGMA foreign_keys = ON`)
- **Frontend**: HTML5, Modern CSS3 (Grid/Flexbox, Custom Properties), Vanilla JavaScript (ES6)
- **Data Visualization**: Chart.js 4.4.1
- **Testing & Quality**: pytest 9.1.1, pytest-cov 7.1.0

---

## 🗄️ Database Schema & Normalization (3NF)

The schema enforces Third Normal Form (3NF) and strict referential integrity.

```
       +------------------+
       |      roles       |
       +------------------+
       | id (PK)          |<----------+
       | name             |           |
       | description      |           |
       +------------------+           |
                 |                    |
                 | 1:N                |
                 v                    |
       +------------------+           |
       |      users       |           |
       +------------------+           |
       | id (PK)          |           |
       | username         |           |
       | email            |           |
       | password_hash    |           |
       | role_id (FK) ----+           |
       | is_active        |           |
       | created_at       |           |
       +------------------+           |
         |         |                  |
     1:N |     1:N |                  |
         |         +--------------+   |
         v                        v   |
+------------------+    +----------------------+
|     tickets      |    |     ticket_comments  |
+------------------+    +----------------------+
| id (PK)          |<---| id (PK)              |
| title            |    | ticket_id (FK)       |
| description      |    | user_id (FK)         |
| category_id (FK)-+    | comment              |
| priority         |    | is_internal          |
| status           |    | created_at           |
| requester_id(FK) |    +----------------------+
| assignee_id (FK) |
| created_at       |    +----------------------+
| updated_at       |    |      audit_logs      |
| resolved_at      |    +----------------------+
+------------------+    | id (PK)              |
         |              | user_id (FK)         |
     N:1 |              | action               |
         v              | target_type          |
+------------------+    | target_id            |
|    categories    |    | ip_address           |
+------------------+    | details              |
| id (PK)          |    | created_at           |
| name             |    +----------------------+
| description      |
+------------------+
```

### Relational Hotspot Indexes
- `idx_tickets_status` ON `tickets(status)`
- `idx_tickets_priority` ON `tickets(priority)`
- `idx_tickets_category` ON `tickets(category_id)`
- `idx_tickets_requester` ON `tickets(requester_id)`
- `idx_tickets_assignee` ON `tickets(assignee_id)`
- `idx_tickets_created_at` ON `tickets(created_at)`
- `idx_audit_logs_action` ON `audit_logs(action)`

---

## 🛡️ Security Architecture & Cyber Security Focus

When presenting OpsLens in technical and cybersecurity interviews, emphasize these concrete implementations:

| Threat / Vulnerability | Defense Implemented in OpsLens | Code Location |
|---|---|---|
| **SQL Injection (CWE-89)** | 100% Parameterized queries using SQLite `?` placeholders. Zero string concatenation. | [`app/tickets/routes.py`](file:///Users/abhinavchaudhary/opslens/app/tickets/routes.py) |
| **Credential Cracking (CWE-307)** | Salted, work-factored hashes using `scrypt` / `PBKDF2-SHA256` (600,000 iterations). | [`app/auth/routes.py`](file:///Users/abhinavchaudhary/opslens/app/auth/routes.py) |
| **Cross-Site Request Forgery (CWE-352)** | Synchronizer Token Pattern with cryptographically secure tokens (`secrets.token_hex(32)`) validated via constant-time comparison (`secrets.compare_digest`). | [`app/security/csrf.py`](file:///Users/abhinavchaudhary/opslens/app/security/csrf.py) |
| **Broken Object Level Authorization (BOLA / IDOR)** | Server-side validation ensuring Requesters can only access/query tickets where `requester_id == g.user['id']`. | [`app/tickets/routes.py`](file:///Users/abhinavchaudhary/opslens/app/tickets/routes.py) |
| **Session Fixation (CWE-384)** | Session cleared and re-issued upon successful authentication (`session.clear()`). | [`app/auth/routes.py`](file:///Users/abhinavchaudhary/opslens/app/auth/routes.py) |
| **Session Hijacking via XSS (CWE-1004)** | Cookie flags: `HttpOnly=True` prevents JavaScript access; `SameSite='Lax'` prevents cross-site leakage. | [`app/__init__.py`](file:///Users/abhinavchaudhary/opslens/app/__init__.py) |
| **Open Redirect (CWE-601)** | `is_safe_redirect_url()` verifies redirect targets share scheme and netloc with application host. | [`app/auth/routes.py`](file:///Users/abhinavchaudhary/opslens/app/auth/routes.py) |
| **Information Disclosure (Internal Notes)** | Requesters query with filter `WHERE is_internal = 0`; internal notes only loaded for agents/admins. | [`app/tickets/routes.py`](file:///Users/abhinavchaudhary/opslens/app/tickets/routes.py) |
| **Non-Repudiation & Forensic Audit** | Immutable `audit_logs` table tracking security events, actor ID, client IP, action name, and metadata. | [`app/audit/logger.py`](file:///Users/abhinavchaudhary/opslens/app/audit/logger.py) |

---

## 🚀 Quickstart Guide (macOS / Linux)

### 1. Prerequisites
- Python 3.12 or newer
- Git

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone https://github.com/your-username/opslens.git
cd opslens

# Create a clean virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the sample environment variables:
```bash
cp .env.example .env
```
*(Optional)* Generate your own cryptographic secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Initialize Database Schema & Seed Data
Initialize the database and populate realistic enterprise sample data:
```bash
flask --app run.py init-db
flask --app run.py seed-db
```

### 5. Launch the Application
```bash
python run.py
```
Open your browser and navigate to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 👥 Pre-Seeded Demo Accounts

For convenient demonstration and role walkthroughs, click the quick-fill buttons on the login page or use these credentials:

| Persona | Username | Password | Role & Permissions |
|---|---|---|---|
| **System Administrator** | `admin` | `Password123!` | Full admin access, security audit log inspection, queue management |
| **Support Specialist** | `sarah_agent` | `Password123!` | Ticket triage, status/priority assignment, internal agent notes |
| **Support Specialist** | `alex_agent` | `Password123!` | Ticket triage and incident handling |
| **Standard Requester** | `john_requester` | `Password123!` | Raises and tracks own tickets; restricted from other users' tickets |
| **Standard Requester** | `emily_requester` | `Password123!` | Raises tickets; can close own resolved tickets |

---

## 🧪 Automated Testing & Coverage

Run the complete test suite with coverage reporting:
```bash
python -m pytest -v --cov=app --cov-report=term-missing
```

### Actual Benchmark Results
```text
============================= test session starts ==============================
collected 41 items

tests/test_analytics.py ................................... [  7%]
tests/test_auth.py ........................................ [ 31%]
tests/test_coverage_edge_cases.py ......................... [ 56%]
tests/test_rbac.py ........................................ [ 75%]
tests/test_security_audit.py .............................. [ 85%]
tests/test_tickets.py ..................................... [100%]

================================ tests coverage ================================
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
app/__init__.py                44      4    91%   27, 35-36, 83
app/analytics/__init__.py       0      0   100%
app/analytics/routes.py        36      0   100%
app/audit/__init__.py           0      0   100%
app/audit/logger.py            14      2    86%   33-35
app/auth/__init__.py            0      0   100%
app/auth/decorators.py         23      0   100%
app/auth/routes.py             72      6    92%   39-40, 48, 68, 70, 117
app/db.py                      36      0   100%
app/security/__init__.py        0      0   100%
app/security/csrf.py           15      0   100%
app/tickets/__init__.py         0      0   100%
app/tickets/routes.py         159      9    94%   53-54, 106, 110, 261, 303, 312, 333-334
---------------------------------------------------------
TOTAL                         399     21    94%
============================== 41 passed in 3.19s ==============================
```

---

## 🎓 Technical Interview Talking Points (Student Guide)

As a Cyber Security student, here is how you can explain OpsLens during interviews:

1. **Why SQLite with parameterized raw SQL instead of an ORM?**
   > *"I intentionally chose raw SQL queries with parameterization over an ORM to demonstrate mastery of relational fundamentals (3NF normalization, foreign key cascade constraints, indexing strategies, and aggregate math for MTTR). From a security perspective, it shows that I understand how SQL injection attacks function at the database driver protocol level and how prepared statements separate executable SQL logic from user-supplied data."*

2. **How does your Role-Based Access Control (RBAC) work?**
   > *"I built server-side decorators (`@login_required` and `@roles_required`). Access control is never enforced merely by hiding UI buttons in HTML; the server validates the user's role on every state-changing route and queries user identity from server-signed session storage. If an unauthorized requester attempts to query another employee's ticket ID or submit an internal note, the backend logs an `UNAUTHORIZED_ACCESS_ATTEMPT` audit event and aborts with HTTP 403 Forbidden."*

3. **How does OpsLens defend against Cross-Site Request Forgery (CSRF)?**
   > *"OpsLens implements the Synchronizer Token Pattern. The server generates a high-entropy cryptographically secure token using Python's `secrets` module and binds it to the authenticated session. When submitting forms, the token is sent in the payload and verified on every non-idempotent HTTP request (`POST`, `PUT`, `DELETE`) using constant-time comparison (`secrets.compare_digest`) to avoid timing attacks."*

4. **How do you calculate MTTR (Mean Time to Resolution)?**
   > *"I utilize SQLite's `julianday()` function: `(julianday(resolved_at) - julianday(created_at)) * 24.0`. This computes the duration in fractional hours entirely within the database engine, avoiding the overhead of loading thousands of timestamp objects into Python memory. I also handled edge cases in the test suite where zero tickets have been resolved to prevent division-by-zero crashes."*

---

## 🗺️ Future Roadmap & Enhancements

- **OAuth 2.0 / OpenID Connect (OIDC)**: Integration with enterprise identity providers (Okta, Google Workspace, Azure AD).
- **Webhook Incident Integrations**: Automated incident notifications dispatched to Slack or Microsoft Teams webhook channels.
- **Rate Limiting & Brute-Force Throttling**: Leaky bucket IP rate limiting on `/auth/login` using Redis.
- **REST / OpenAPI Spec**: Exposing a versioned RESTful API (`/api/v1/tickets`) with Bearer token authentication for CI/CD integration.
