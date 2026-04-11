# Authentication Spec

KIS Open API OAuth-based authentication system for Stockquare.

## 1. Token Management

### KIS OAuth Token Lifecycle

KIS Open API uses OAuth 2.0 with client credentials grant. The access token is issued via `POST /oauth2/tokenP` and is valid for **24 hours** (real account) or **24 hours** (mock account).

| Action | KIS Endpoint | Method | tr_id |
|--------|-------------|--------|-------|
| Issue token | `/oauth2/tokenP` | POST | — |
| Revoke token | `/oauth2/revokeP` | POST | — |

### Token Issue Request

```
POST {base_url}/oauth2/tokenP
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "appkey": "<app_key>",
  "appsecret": "<app_secret>"
}
```

### Token Issue Response

```json
{
  "access_token": "eyJ0eXAiOi...",
  "access_token_token_expired": "2026-04-12 10:30:00",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

### Auto-Refresh Strategy

- Store `access_token` and `expires_at` in memory via `TokenManager`.
- Refresh **5 minutes before expiry** to avoid mid-request failures.
- On startup, issue a new token immediately (do not persist tokens across restarts).
- If token refresh fails, retry up to 3 times with exponential backoff.
- After all retries fail, raise `TokenExpiredError` and log the failure.

### Internal Token State

```python
class TokenState:
    access_token: str
    expires_at: datetime
    account_mode: AccountMode  # REAL or MOCK
```

## 2. Account Mode

### Real vs Mock Trading

KIS Open API provides separate environments for real and mock trading. The base URL and `tr_id` prefixes differ by mode.

| Mode | Base URL | tr_id Prefix | Description |
|------|----------|-------------|-------------|
| REAL | `https://openapi.koreainvestment.com:9443` | `T` (e.g., `TTTC8434R`) | Real trading |
| MOCK | `https://openapivts.koreainvestment.com:29443` | `V` (e.g., `VTTC8434R`) | Mock trading |

### AccountMode Enum

```python
class AccountMode(str, Enum):
    REAL = "real"
    MOCK = "mock"
```

### Mode Switching Rules

- Each mode requires its own `appkey` / `appsecret` pair (KIS issues separate keys per environment).
- Tokens are mode-specific. Switching mode requires issuing a new token.
- The active mode is set at application startup via environment variable `KIS_ACCOUNT_MODE`.
- Runtime mode switching is **not supported** in Phase 1 (requires restart).

## 3. Credentials Storage

### Environment Variables

All credentials are stored as environment variables. Never hardcode or commit secrets.

| Variable | Description | Required |
|----------|-------------|----------|
| `KIS_APP_KEY` | KIS app key | Yes |
| `KIS_APP_SECRET` | KIS app secret | Yes |
| `KIS_ACCOUNT_NO` | Account number (8-digit) | Yes |
| `KIS_ACCOUNT_PRODUCT_CODE` | Account product code (2-digit, e.g., `01`) | Yes |
| `KIS_ACCOUNT_MODE` | `real` or `mock` (default: `mock`) | No |
| `KIS_HTS_ID` | HTS ID (reserved for Phase 2 WebSocket). Phase 1 does not require this. | No |

### Config Model

```python
class KISConfig(BaseModel):
    app_key: str
    app_secret: str
    account_no: str
    account_product_code: str = "01"
    account_mode: AccountMode = AccountMode.MOCK
    hts_id: str | None = None  # Phase 2 WebSocket use

    @property
    def base_url(self) -> str:
        if self.account_mode == AccountMode.REAL:
            return "https://openapi.koreainvestment.com:9443"
        return "https://openapivts.koreainvestment.com:29443"

    @property
    def ws_url(self) -> str:
        if self.account_mode == AccountMode.REAL:
            return "ws://ops.koreainvestment.com:21000"
        return "ws://ops.koreainvestment.com:31000"
```

### .env.example

```env
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NO=12345678
KIS_ACCOUNT_PRODUCT_CODE=01
KIS_ACCOUNT_MODE=mock
# Phase 2 only - leave blank in Phase 1
KIS_HTS_ID=
```

## 4. API Endpoints

Stockquare backend exposes the following auth-related endpoints.

### POST /api/v1/auth/token

Issue a new access token. Called on application startup or when the frontend needs to verify auth status.

**Request**: None (uses server-side credentials)

**Response**:
```json
{
  "authenticated": true,
  "account_mode": "mock",
  "expires_at": "2026-04-12T10:30:00"
}
```

**Response Model**:
```python
class AuthStatusResponse(BaseModel):
    authenticated: bool
    account_mode: AccountMode
    expires_at: datetime
```

### GET /api/v1/auth/status

Check the current authentication status, token validity, and which (if any)
KIS credentials are still missing. The frontend uses `missing_credentials`
to drive specific onboarding hints (e.g., "Add KIS_ACCOUNT_NO to enable
account summary").

**Response (fully configured, token cached)**:
```json
{
  "authenticated": true,
  "account_mode": "mock",
  "expires_at": "2026-04-12T10:30:00",
  "remaining_seconds": 72000,
  "credentials_complete": true,
  "missing_credentials": []
}
```

**Response (partial configuration)**:
```json
{
  "authenticated": false,
  "account_mode": "mock",
  "expires_at": null,
  "remaining_seconds": 0,
  "credentials_complete": false,
  "missing_credentials": ["KIS_ACCOUNT_NO"]
}
```

**Response Model**:
```python
class AuthDetailResponse(BaseModel):
    authenticated: bool
    account_mode: AccountMode
    expires_at: datetime | None
    remaining_seconds: int
    credentials_complete: bool
    missing_credentials: list[str]
```

### POST /api/v1/auth/revoke

Revoke the current access token.

**Response**:
```json
{
  "revoked": true
}
```

## 5. Error Handling

### Error Scenarios

| Scenario | Exception | HTTP Status | Code | Recovery |
|----------|-----------|-------------|------|----------|
| Token issuance failed (transient) | `KISAPIError` | 502 | `KIS_API_ERROR` | Retry with exponential backoff (3 tries) |
| Token expired / refresh exhausted | `TokenExpiredError` | 401 | `TOKEN_EXPIRED` | Auto-refresh and retry the failed request exactly once |
| KIS credentials missing at request time | `KISNotConfiguredError` | 503 | `KIS_NOT_CONFIGURED` | Fail-fast before hitting the network; response lists missing env vars |
| Invalid credentials rejected by KIS | `KISAPIError` | 502 | `KIS_API_ERROR` | Log and surface to caller — requires config fix |
| KIS server 5xx | `KISAPIError` | 502 | `KIS_API_ERROR` | Logged with `rt_cd`/`msg_cd`/`msg1` for diagnostics |

### Exception Classes

```python
class ConfigError(StockquareError):
    """Generic configuration error — reserved for future use."""
    code: ClassVar[str] = "CONFIG_ERROR"
    http_status: ClassVar[int] = 500


class KISNotConfiguredError(StockquareError):
    """KIS credentials missing — raised at request time, fail-fast.

    Preferred over startup crash so DB-only endpoints (empty watchlist,
    /health, /auth/status) remain serviceable while KIS-dependent routes
    degrade cleanly with a 503.
    """
    code: ClassVar[str] = "KIS_NOT_CONFIGURED"
    http_status: ClassVar[int] = 503

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
```

`TokenExpiredError` and `KISAPIError` are defined in the Error Handling
pattern (`ERROR_HANDLING.md`).

### Startup Credential Behavior

Missing KIS credentials at startup do **not** crash the app. `Settings` is
loaded with empty-string defaults for KIS fields, and `log_credential_status(settings)`
emits a WARNING listing each missing variable. Individual KIS calls then
fail-fast with `KISNotConfiguredError` → HTTP 503 until the operator fills
in the env vars and restarts the container.

### Auto-Recovery Flow

```
Request fails with 401
  → TokenManager.refresh()
    → Success → Retry original request (once)
    → Failure → Raise TokenExpiredError to caller
```

If the refresh itself hits `KISNotConfiguredError` (credentials empty),
the retry loop is bypassed and the caller receives 503 immediately —
there is no transient state that retry could fix.

## 6. Security

### Token Storage

- Access tokens are stored **in-memory only** (never persisted to disk or database).
- Tokens are bound to a single process lifecycle. Restart = new token.
- Never log access tokens. Use structured logging with token metadata only (e.g., expiry time).

### Credential Protection

- All secrets loaded from environment variables via `KISConfig`.
- `.env` file is listed in `.gitignore` — never commit.
- `.env.example` contains placeholder values only.

### Request Security

- All KIS API calls use HTTPS (TLS).
- `appkey` and `appsecret` are sent in headers per KIS API specification, not in query strings.
- WebSocket connections use the `approval_key` (separate from access token), obtained via `/oauth2/Approval`.

### WebSocket Approval Key

The WebSocket approval key is a separate credential for real-time data subscriptions.

| Action | KIS Endpoint | Method |
|--------|-------------|--------|
| Issue approval key | `/oauth2/Approval` | POST |

```
POST {base_url}/oauth2/Approval
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "appkey": "<app_key>",
  "secretkey": "<app_secret>"
}
```

Response:
```json
{
  "approval_key": "abc123..."
}
```

- The approval key does not expire on a fixed schedule but should be re-obtained on WebSocket reconnect.
- Store in memory alongside the access token.

### Rate Limiting

- KIS enforces per-second API call limits (approximately 20 calls/sec).
- The `RateLimiter` (defined in `API_INTEGRATION.md`) must be applied to all authenticated requests.
- Token issuance calls are exempt from rate limiting but should not be called excessively.

## Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| KIS HTTP client | `app/kis/client.py` | kis |
| Token manager | `app/kis/token.py` | kis |
| KIS config | `app/config.py` | core |
| Auth endpoints | `app/api/v1/auth.py` | api |
| Exception classes | `app/core/exceptions.py` | core |
| KIS response models | `app/kis/models.py` | kis |
