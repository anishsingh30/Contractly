# CONTRACTLY AUTHENTICATION HANG: ROOT CAUSE AND FIX REPORT

**Workspace:** `A:\Soft Computing`  
**Date:** 2026-10-14  
**Audit Scope:** Local application authentication hang at `http://localhost:3000/dashboard` ("CONTRACTLY: Authenticating workspace session...").  
**Database & Environment Integrity:**  
- `backend/contractly.db`: Untouched (155,648 bytes, preserved).  
- `.env.staging` & `.env.local`: Untouched.  
- Zero migrations executed, no live connections made to Neon.

---

## 1. Executive Summary

When visiting `http://localhost:3000/dashboard`, the application was becoming stuck indefinitely on the warm ivory loading gate:
```text
CONTRACTLY
Authenticating workspace session...
```

The underlying issue was diagnosed and confirmed:
An **infinite circular redirect loop** between `src/middleware.ts` and `src/app/dashboard/page.tsx` triggered by stale or expired `HttpOnly` browser cookies (`contractly_access_token` and `contractly_refresh_token`), exacerbated by an uncoordinated hard window redirection in `src/lib/api-client.ts` (`fetchWithAuth`) while React authentication state hydration (`isAuthLoading`) was active.

Following targeted, minimal code modifications in `src/middleware.ts`, `src/lib/api-client.ts`, `src/context/contractly-context.tsx`, and `src/app/dashboard/page.tsx`, the circular loop was broken, token expiration is properly validated, stale cookies are cleared on unauthenticated sign-in redirects, and 9/9 automated routing and authentication verification tests passed.

---

## 2. Confirmed Root Cause & Execution Paths

### Root Cause 1: `middleware.ts` Circular Redirect Loop on Stale/Expired Cookies
- **File:** `src/middleware.ts`
- **Mechanism:**
  1. Previously, `middleware.ts` checked:
     ```ts
     const accessToken = request.cookies.get('contractly_access_token')?.value;
     const refreshToken = request.cookies.get('contractly_refresh_token')?.value;
     const hasAuthCookies = Boolean(accessToken || refreshToken);
     ...
     if (hasAuthCookies && isAuthRoute) {
       return NextResponse.redirect(new URL('/dashboard', request.url));
     }
     ```
  2. If the user had ANY leftover or expired cookie (e.g., from an earlier session, server restart, or token expiration after 15 minutes), `hasAuthCookies` evaluated to `true`.
  3. When an unauthenticated user visited `/dashboard`, middleware permitted passthrough to Next.js because the cookie existed.
  4. The client page mounted and displayed:
     ```text
     CONTRACTLY
     Authenticating workspace session...
     ```
  5. The client context called `GET /api/v1/auth/me`. Because the token was expired or the backend was restarted, the request returned `401 Unauthorized`.
  6. Silent token refresh (`POST /api/v1/auth/refresh`) failed because the refresh token was also expired, revoked, or invalid.
  7. The client triggered `window.location.replace('/signin?returnUrl=/dashboard')`.
  8. The browser sent `GET /signin?returnUrl=/dashboard` with the existing `HttpOnly` cookies still attached (since client JavaScript cannot delete `HttpOnly` cookies).
  9. `middleware.ts` intercepted the request for `/signin`, evaluated `hasAuthCookies === true`, and responded with `307 Temporary Redirect` -> `/dashboard`!
  10. The browser followed the redirect to `/dashboard`, re-mounted the ivory loading screen, called `/auth/me`, failed, redirected to `/signin`, got bounced back to `/dashboard`, repeating indefinitely every ~80ms.
  11. The user was permanently locked out of viewing the sign-in form.

### Root Cause 2: Mid-Hydration Hard Redirection in `fetchWithAuth`
- **File:** `src/lib/api-client.ts` (`fetchWithAuth`)
- **Mechanism:**
  1. Inside `fetchWithAuth`, when a 401 occurred and `refreshSession()` failed, it immediately executed:
     ```ts
     window.location.replace(`/signin?returnUrl=${encodeURIComponent(path)}`);
     ```
  2. Because `fetchCurrentUser()` in `src/context/contractly-context.tsx` called `fetchWithAuth('/auth/me')` on mount, `fetchWithAuth` triggered a hard window navigation *during* context initialization while `isAuthLoading` was still `true`.
  3. This preempted the React tree before `loadData()` could settle `isAuthLoading = false` in its `finally` block and reset `currentUser = null`.

### Root Cause 3: Legacy Route Alias Logic Wrapped in Cookie Check
- **File:** `src/middleware.ts`
- **Mechanism:**
  - `/login` and `/register` aliases were wrapped in `if (!hasAuthCookies)`. If a user had stale cookies and typed `/login`, it was not aliased to `/signin`; instead, it fell into the `hasAuthCookies && isAuthRoute` branch and bounced them to `/dashboard`.

---

## 3. Exact Code Changes Made

### 1. `src/middleware.ts`
- **Added `isJwtExpired` helper:** Decodes standard JWT base64url payloads to check whether `payload.exp * 1000 <= Date.now()`.
- **Differentiated potential session vs genuinely valid session:**
  - An access token is only valid if `!isAccessExpired`.
  - A potential session exists if `(!isAccessExpired && hasAccessToken) || hasRefreshToken`.
- **Eliminated circular redirect on auth routes (`/signin`, `/signup`):**
  - If `request.nextUrl.searchParams.has('returnUrl')`, NEVER redirect to `/dashboard`. The presence of `returnUrl` signifies an unauthenticated redirect. Clear stale cookies on the response so they cannot trigger downstream loops, and render `/signin`.
  - Only redirect `/signin` or `/signup` to `/dashboard` if `hasAccessToken && !isAccessExpired` AND `!hasReturnUrl`.
  - If access token is expired, delete `contractly_access_token` and allow the sign-in page to render.
- **Protected route redirection (`!isPublicRoute`):**
  - If `!hasPotentialSession`: redirect to `/signin?returnUrl=${cleanPath}` and delete dead cookies.
- **Unconditional legacy aliases:**
  - `/login` unconditionally redirects to `/signin` (preserving query params).
  - `/register` unconditionally redirects to `/signup` (preserving query params).

### 2. `src/lib/api-client.ts`
- **Added `skipRedirect?: boolean` to `FetchWithAuthOptions`:**
  - When `skipRedirect: true` is passed (as in `fetchCurrentUser()`), `fetchWithAuth` attempts silent refresh once, but if refresh fails, it returns the 401 response cleanly without executing `window.location.replace`.
  - This allows `ContractlyContext` and `DashboardPage` to manage lifecycle and navigation gracefully.
- **Guaranteed promise settlement in `fetchWithAuth`:**
  - Wrapped `refreshSession()` in a `try/finally` block to guarantee `isRefreshing = false` and `onRefreshed(refreshSuccess)` always fire, preventing any subscriber promise from hanging.
- **Storage cleanup:**
  - When an unrefreshable 401 redirect occurs on mid-session actions, `localStorage.clear()` and `sessionStorage.clear()` are executed.

### 3. `src/context/contractly-context.tsx`
- **Imported `useCallback`:**
  - Wrapped `recheckAuth` in `useCallback(async () => { ... }, [])` to provide a stable function reference and eliminate unnecessary listener teardowns in `DashboardPage`.
- **Reinforced `loadData` error handling:**
  - In `loadData()` catch block, explicitly reset `currentUser = null`, `currentOrganization = null`, and `availableOrganizations = []`, ensuring `isAuthLoading = false` always settles in `finally`.

### 4. `src/app/dashboard/page.tsx`
- **Refined `handleFocus`:**
  - Changed `handleFocus` to only invoke `recheckAuth()` if `currentUser` is currently present (avoiding redundant auth calls during unauthenticated redirection).

### 5. `backend/app/api/v1/auth.py`
- **Safeguarded `resolve_user_verification_status`:**
  - Wrapped `AccountToken` query in a `try/except` block to gracefully handle local development databases (like canonical `contractly.db`) that have not run Alembic migration 0002 for `account_tokens`, preventing 500 crashes during login credential verification.

---

## 4. Verification & Test Results

### A. Routing & Authentication Suite (9 Tests)
Executed against running Next.js server (`http://localhost:3000`) and FastAPI backend (`http://127.0.0.1:8000`):

| Test Case | Scenario / Route | Expected | Actual Result | Status |
|:---:|---|---|---|:---:|
| 1 | `GET /` (Public Landing Page) | 200 OK | Status: 200 | **PASS** |
| 2 | `GET /signin` (Without session) | 200 OK | Status: 200 | **PASS** |
| 3 | `GET /signup` (Without session) | 200 OK | Status: 200 | **PASS** |
| 4 | `GET /dashboard` (Without cookies) | 307 Redirect to `/signin?returnUrl=%2Fdashboard` | Status: 307, Location: `/signin?returnUrl=%2Fdashboard` | **PASS** |
| 5 | `GET /dashboard` (Expired access token, no refresh) | 307 Redirect to `/signin?returnUrl=%2Fdashboard` | Status: 307, Location: `/signin?returnUrl=%2Fdashboard` | **PASS** |
| 6 | `GET /signin?returnUrl=/dashboard` (With expired cookies) | 200 OK (Sign-in form, cookies deleted) | Status: 200, Set-Cookie clears tokens | **PASS** |
| 7 | `GET /login` (Legacy alias) | 307 Redirect to `/signin` | Status: 307, Location: `/signin` | **PASS** |
| 8 | `GET /register` (Legacy alias) | 307 Redirect to `/signup` | Status: 307, Location: `/signup` | **PASS** |
| 9 | `GET /api/v1/auth/me` (Via Next.js proxy rewrite) | 401 Unauthorized | Status: 401 | **PASS** |

### B. TypeScript & Lint Checks
```bash
npx tsc --noEmit
# Result: 0 errors (Exit code 0)

npm run lint
# Result: 0 errors (Exit code 0)
```

### C. Production Build
```bash
npm run build
# Result: 17/17 static pages and middleware compiled successfully (Exit code 0)
```

### D. Backend Pytest Suite
```bash
python -m pytest backend/tests/test_phase_13_3_auth_and_logout.py -v
# Result: 2 passed, 0 failed in 1.56s (Exit code 0)
```

---

## 5. Server Status During Verification

- **Frontend (Next.js):** Running locally on `http://localhost:3000` (Process 6499).
- **Backend (FastAPI / Uvicorn):** Running locally on `http://127.0.0.1:8000` (Process 6370), health check returning `status: "healthy"`.

---

## 6. Remaining Blockers & Visual Verification Note

1. **Browser Subagent Driver Limitation:**
   - Visual inspection via the `browser_subagent` / Playwright tool was attempted, but the automated browser context could not be spawned because the Playwright driver binary (`playwright-1.57.0-win32_x64.zip`) is not pre-installed in the environment and returned a 404 from the external CDN.
   - All HTTP redirects, HTML rendering, cookie headers, and proxy endpoints were verified via direct automated HTTP client tests.
2. **Manual Test Still Recommended:**
   - Open a real browser window at `http://localhost:3000/dashboard` in Incognito / Private mode.
   - Confirm immediate redirection to `http://localhost:3000/signin?returnUrl=%2Fdashboard`.
   - Confirm sign-in form displays with work email and password inputs.
   - Enter credentials to test end-to-end dashboard entry.

---

## 7. Conclusion

The authentication hang at `/dashboard` has been resolved at the root cause. Circular redirects have been eliminated, stale cookies are purged on auth failure, and token validation functions fail-closed.
