import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_EXACT_ROUTES = new Set([
  '/',
  '/signin',
  '/signup',
  '/login',
  '/register',
  '/privacy',
  '/terms',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
  '/invitations/accept',
]);

function isJwtExpired(token: string | undefined): boolean {
  if (!token) return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(base64);
    const payload = JSON.parse(json);
    if (!payload.exp) return true;
    // Check if expired (exp is in seconds, Date.now() in ms)
    return payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow static assets, images, next internals, and API routes
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/favicon.ico') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Normalize path without trailing slash (preserving root '/')
  const cleanPath = pathname.length > 1 && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;

  // Legacy route aliases: always redirect /login to /signin and /register to /signup
  if (cleanPath === '/login') {
    const signinUrl = new URL('/signin', request.url);
    request.nextUrl.searchParams.forEach((val, key) => signinUrl.searchParams.set(key, val));
    return NextResponse.redirect(signinUrl);
  }
  if (cleanPath === '/register') {
    const signupUrl = new URL('/signup', request.url);
    request.nextUrl.searchParams.forEach((val, key) => signupUrl.searchParams.set(key, val));
    return NextResponse.redirect(signupUrl);
  }

  const accessToken = request.cookies.get('contractly_access_token')?.value;
  const refreshToken = request.cookies.get('contractly_refresh_token')?.value;
  const hasAccessToken = Boolean(accessToken);
  const isAccessExpired = isJwtExpired(accessToken);
  const hasRefreshToken = Boolean(refreshToken);

  // A potential session exists if access token is unexpired OR a refresh token exists for silent refresh
  const hasPotentialSession = (!isAccessExpired && hasAccessToken) || hasRefreshToken;

  const isAuthRoute =
    cleanPath === '/signin' ||
    cleanPath === '/signup';

  const isPublicRoute =
    PUBLIC_EXACT_ROUTES.has(cleanPath) ||
    cleanPath.startsWith('/invitations/accept/');

  // Auth routes (/signin, /signup) handling
  if (isAuthRoute) {
    const hasReturnUrl = request.nextUrl.searchParams.has('returnUrl');

    // If redirected to sign-in with returnUrl, NEVER bounce to dashboard!
    // Stale cookies led to this redirect; clear them to break loops and display the form.
    if (hasReturnUrl) {
      const response = NextResponse.next();
      if (hasAccessToken) response.cookies.delete('contractly_access_token');
      if (hasRefreshToken) response.cookies.delete('contractly_refresh_token');
      return response;
    }

    // Only redirect to dashboard if the access token is genuinely VALID and UNEXPIRED
    if (hasAccessToken && !isAccessExpired) {
      const dashboardUrl = new URL('/dashboard', request.url);
      return NextResponse.redirect(dashboardUrl);
    }

    // If access token is expired, clean it up and allow the sign-in / sign-up page to render
    const response = NextResponse.next();
    if (hasAccessToken && isAccessExpired) {
      response.cookies.delete('contractly_access_token');
    }
    return response;
  }

  // Unauthenticated user attempting to access protected dashboard routes
  if (!hasPotentialSession && !isPublicRoute) {
    const signinUrl = new URL('/signin', request.url);
    if (cleanPath && cleanPath !== '/') {
      signinUrl.searchParams.set('returnUrl', cleanPath);
    }
    const response = NextResponse.redirect(signinUrl);
    if (hasAccessToken) response.cookies.delete('contractly_access_token');
    if (hasRefreshToken) response.cookies.delete('contractly_refresh_token');
    return response;
  }

  const response = NextResponse.next();

  // If visiting a protected page, prevent caching to ensure Back button navigation revalidates
  if (!isPublicRoute) {
    response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    response.headers.set('Pragma', 'no-cache');
    response.headers.set('Expires', '0');
  }

  return response;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};

