# SaaS Billing System API

A FastAPI-based backend for ISP (Internet Service Provider) registration, billing, subscriptions, and hotspot management. Integrates with Mikrotik RouterOS for router and hotspot operations, and supports email verification, JWT authentication, and package/subscription lifecycle management.

## Features

- **Authentication** — ISP registration, login (password + OTP), JWT access/refresh tokens, logout, email verification
- **ISP Profile** — ISP management and profile (with optional image upload via Cloudinary)
- **Routers** — Router CRUD, Mikrotik integration, status monitoring, VPN/SSH utilities
- **Packages** — Package types and plans, seeding on startup
- **Customers** — Customer management
- **Subscriptions** — Subscription lifecycle, expiry monitoring, Mikrotik actions
- **Hotspot** — Hotspot voucher management and expiry monitoring
- **Email** — Verification emails via Brevo (Sendinblue)
- **Background tasks** — Router status monitor (every 10s), subscription expiry monitor, hotspot voucher expiry monitor

## Tech Stack

- **Framework:** FastAPI
- **Database:** PostgreSQL with SQLAlchemy
- **Auth:** JWT (access + refresh), bcrypt
- **Email:** Brevo API
- **Storage:** Cloudinary (images)
- **Integrations:** Mikrotik RouterOS API, OpenVPN status, SSH

## Prerequisites

- Python 3.10+
- PostgreSQL
- (Optional) Mikrotik router for RouterOS/hotspot features
- (Optional) Brevo account for email; Cloudinary for images

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "billing system api"
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   # source venv/bin/activate   # Linux/macOS
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment variables**  
   Create a `.env` file in the project root. Example:

   ```env
   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/billing_system

   # JWT
   JWT_SECRET_KEY=your-secret-key
   JWT_REFRESH_SECRET_KEY=your-refresh-secret-key
   JWT_ALGORITHM=HS256
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
   JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

   # Email (Brevo)
   BREVO_API_KEY=your-brevo-api-key
   BREVO_SENDER_EMAIL=noreply@yourdomain.com
   BREVO_SENDER_NAME=Billing System

   # Frontend (for verification links)
   FRONTEND_VERIFY_URL=http://localhost:3000/verify-email

   # Optional: Cloudinary
   CLOUDINARY_CLOUD_NAME=your-cloud-name
   CLOUDINARY_API_KEY=your-api-key
   CLOUDINARY_API_SECRET=your-api-secret

   # Optional: Mikrotik / SSH / OpenVPN (for router & hotspot features)
   SSH_HOST=your-server-ip
   SSH_USER=root
   SSH_PASSWORD=your-password
   SSH_PORT=22
   OPENVPN_SERVER_IP=your-vpn-ip
   OPENVPN_SERVER_PORT=1194
   OPENVPN_STATUS_LOG=/var/log/openvpn-status.log

   # FreeRADIUS (separate PostgreSQL database for radcheck, radreply, radusergroup, nas)
   RADIUS_DATABASE_URL=postgresql://radius_user:password@localhost:5432/radius
   RADIUS_DEFAULT_GROUP=users
   # FreeRADIUS server IP (for auto-configuring MikroTik as RADIUS client when router comes online)
   RADIUS_SERVER_IP=10.0.0.1
   RADIUS_SERVER_AUTH_PORT=1812
   RADIUS_SERVER_ACCT_PORT=1813

   # App
   DEBUG=false
   ```

5. **Database**  
   Ensure PostgreSQL is running and the database in `DATABASE_URL` exists. The app creates tables on startup (for production, consider using Alembic migrations instead).

6. **FreeRADIUS**  
   Customer and subscription authentication use a **separate** PostgreSQL database (`RADIUS_DATABASE_URL`). The app writes to `radcheck`, `radreply`, and `radusergroup` in that database only. Billing tables stay in `DATABASE_URL`. RADIUS tables must already exist (e.g. from a FreeRADIUS install). MikroTik should be configured to use FreeRADIUS for PPPoE/hotspot auth.

## Running the Application

From the project root:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health: `http://localhost:8000/health`

## API Endpoints

Base URL: `http://localhost:8000` (when running locally). Endpoints under `/auth` that do not require a token are marked with *(public)*. All other endpoints require a valid JWT in the `Authorization: Bearer <token>` header unless noted.

### Root & Health

| Method | Endpoint   | Description                    |
|--------|------------|--------------------------------|
| GET    | `/`        | API info and version           |
| GET    | `/health`  | Health check                   |

### Authentication (`/auth`)

| Method | Endpoint         | Description                                      |
|--------|------------------|--------------------------------------------------|
| POST   | `/auth/register` | Register a new ISP; sends verification email *(public)* |
| GET    | `/auth/verify-email` | Verify email with token from email *(public)* |
| POST   | `/auth/login`    | Step 1: validate credentials, send OTP *(public)* |
| POST   | `/auth/verify-otp` | Step 2: verify OTP, return access & refresh tokens *(public)* |
| POST   | `/auth/refresh-token` | Get new access token from refresh token *(public)* |
| POST   | `/auth/logout`   | Revoke refresh token(s)                          |

### ISP Profile (`/isps`)

| Method | Endpoint                 | Description                          |
|--------|--------------------------|--------------------------------------|
| GET    | `/isps/profile`         | Get authenticated ISP profile        |
| POST   | `/isps/profile/complete`| Complete profile (phone, location, logo) |
| PUT    | `/isps/profile`         | Update profile (partial; logo optional) |

### Routers (`/routers`)

| Method | Endpoint                          | Description                              |
|--------|-----------------------------------|------------------------------------------|
| GET    | `/routers`                        | List routers for the ISP                 |
| POST   | `/routers`                        | Create router + VPN user; returns config |
| GET    | `/routers/{router_id}/config`     | Get OpenVPN config (only right after create) |
| PUT    | `/routers/{router_id}`            | Update router (name, API port, credentials) |
| DELETE | `/routers/{router_id}`           | Delete router and VPN user               |
| GET    | `/routers/{router_id}/status-history` | Router status history (query: `limit`) |

### Packages (`/packages`)

| Method | Endpoint                                | Description                        |
|--------|-----------------------------------------|------------------------------------|
| GET    | `/packages/package-types`               | List package types (e.g. pppoe, static) *(no auth)* |
| POST   | `/packages`                             | Create package for a router        |
| GET    | `/packages/routers/{router_id}/packages`| List packages for a router         |
| PUT    | `/packages/{package_id}`                | Update package                     |
| PATCH  | `/packages/{package_id}/disable`        | Disable package                    |
| PATCH  | `/packages/{package_id}/enable`         | Enable package                     |
| DELETE | `/packages/{package_id}`                | Delete package (query: `force`)    |
| POST   | `/packages/{package_id}/sync`           | Sync package to MikroTik           |

### Customers (`/customers`)

| Method | Endpoint                              | Description                |
|--------|---------------------------------------|----------------------------|
| POST   | `/customers`                          | Create customer            |
| GET    | `/customers`                          | List customers (skip, limit, status, search) |
| GET    | `/customers/{customer_id}`            | Get customer by ID         |
| PUT    | `/customers/{customer_id}`            | Update customer            |
| DELETE | `/customers/{customer_id}`            | Soft delete (status terminated) |
| POST   | `/customers/{customer_id}/activate`   | Activate terminated customer |
| POST   | `/customers/{customer_id}/change-password` | Change customer password |

### Subscriptions (`/subscriptions`)

| Method | Endpoint                                    | Description                    |
|--------|---------------------------------------------|--------------------------------|
| POST   | `/subscriptions`                            | Create subscription (pending)  |
| GET    | `/subscriptions/`                           | List subscriptions (filters, pagination) |
| GET    | `/subscriptions/{subscription_id}`          | Get subscription by ID         |
| POST   | `/subscriptions/{subscription_id}/activate` | Activate on MikroTik           |
| POST   | `/subscriptions/{subscription_id}/suspend`  | Suspend subscription           |
| POST   | `/subscriptions/{subscription_id}/resume`   | Resume suspended subscription  |
| POST   | `/subscriptions/{subscription_id}/terminate` | Terminate and remove from router |

### Hotspot (`/hotspot`)

| Method | Endpoint                                  | Description                    |
|--------|-------------------------------------------|--------------------------------|
| POST   | `/hotspot/packages`                       | Create hotspot package         |
| GET    | `/hotspot/packages`                      | List hotspot packages          |
| GET    | `/hotspot/packages/{package_id}`         | Get hotspot package by ID      |
| PATCH  | `/hotspot/packages/{package_id}/toggle`  | Enable/disable package         |
| POST   | `/hotspot/mac-vouchers`                  | Create MAC-based voucher       |
| GET    | `/hotspot/mac-vouchers`                  | List MAC vouchers (package_id, active_only) |

## Project Structure

```
app/
├── main.py              # FastAPI app, routers, exception handlers, startup tasks
├── config.py            # Settings from environment
├── database.py          # SQLAlchemy engine and session
├── auth/                # Auth routes, JWT, login history
├── isps/                # ISP models and routes
├── routers/             # Router CRUD, Mikrotik, status monitor, VPN/SSH
├── packages/            # Packages and package types
├── customers/           # Customer management
├── subscriptions/       # Subscriptions, expiry monitor, Mikrotik actions
├── hotspot/             # Hotspot vouchers and expiry monitor
├── email_verification/  # Email verification models
├── otp/                 # OTP models
├── email/               # Email sending (Brevo)
└── cloudinary/          # Image upload service
```

## License

Use and modify as needed for your project.
