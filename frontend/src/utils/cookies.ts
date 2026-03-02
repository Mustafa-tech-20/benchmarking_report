/**
 * Cookie Management for Session Persistence
 */

const SESSION_COOKIE_NAME = 'car_agent_session';
const COOKIE_EXPIRY_DAYS = 7;

export interface SessionData {
  userId: string | null;
  sessionId: string | null;
}

/**
 * Save session to cookies
 */
export function saveSessionToCookies(session: SessionData): void {
  const expires = new Date();
  expires.setDate(expires.getDate() + COOKIE_EXPIRY_DAYS);

  const sessionJson = JSON.stringify(session);
  document.cookie = `${SESSION_COOKIE_NAME}=${encodeURIComponent(sessionJson)}; expires=${expires.toUTCString()}; path=/; SameSite=Strict`;
}

/**
 * Load session from cookies
 */
export function getSessionFromCookies(): SessionData {
  const name = SESSION_COOKIE_NAME + '=';
  const decodedCookie = decodeURIComponent(document.cookie);
  const cookies = decodedCookie.split(';');

  for (let cookie of cookies) {
    cookie = cookie.trim();
    if (cookie.indexOf(name) === 0) {
      try {
        const sessionJson = cookie.substring(name.length);
        return JSON.parse(sessionJson);
      } catch (error) {
        console.error('Error parsing session cookie:', error);
        return { userId: null, sessionId: null };
      }
    }
  }

  return { userId: null, sessionId: null };
}

/**
 * Clear session cookies
 */
export function clearSessionCookies(): void {
  document.cookie = `${SESSION_COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}
