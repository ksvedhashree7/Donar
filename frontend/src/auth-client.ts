export type AuthRole = 'ADMIN' | 'BLOOD_BANK' | 'GENERAL_DONOR';
export type AuthChallengePurpose = 'EMAIL_VERIFY' | 'LOGIN' | 'TOTP_LOGIN';

export type AuthChallenge = {
  challenge_id: string;
  requires_otp: boolean;
  requires_totp?: boolean;
  message?: string;
};

export type AuthTokens = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type AuthenticatedSession = {
  role: AuthRole;
};

export type BloodBankRegistration = {
  institution_name: string;
  institution_type: string;
  representative_name: string;
  official_phone: string;
  address: string;
  locality: string;
  city: string;
  district: string;
  state: string;
  pincode: string;
  registration_number: string;
  issuing_authority: string;
};

type RegistrationPayload = {
  email: string;
  password: string;
  phone: string;
  role: Exclude<AuthRole, 'ADMIN'>;
  blood_bank?: BloodBankRegistration;
};

type LoginPayload = {
  password: string;
  role: AuthRole;
} & ({ email: string; username?: never } | { username: string; email?: never });

const apiUrl = (import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`).replace(/\/$/, '');

export class AuthApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'AuthApiError';
  }
}

async function request<T>(
  path: string,
  method: 'GET' | 'POST',
  body?: unknown,
  accessToken?: string,
): Promise<T> {
  const headers = new Headers();
  if (body !== undefined) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, {
      method,
      headers,
      credentials: 'include',
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error: unknown) {
    if (error instanceof TypeError) {
      throw new AuthApiError(
        `Cannot reach the Uthiram API at ${apiUrl}. Start the full app with start-uthiram.bat; the browser-only demo does not start the API.`,
        0,
      );
    }
    throw error;
  }
  const responseBody: unknown = response.status === 204 ? undefined : await response.json();

  if (!response.ok) {
    const detail = responseBody !== null && typeof responseBody === 'object' && 'detail' in responseBody
      ? responseBody.detail
      : undefined;
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item !== null && typeof item === 'object' && 'msg' in item ? String(item.msg) : '').filter(Boolean).join(' ')
        : `Authentication request failed (HTTP ${response.status}).`;
    throw new AuthApiError(message, response.status);
  }
  return responseBody as T;
}

export function registerAccount(payload: RegistrationPayload): Promise<AuthChallenge> {
  return request<AuthChallenge>('/auth/register', 'POST', payload);
}

export function startLogin(payload: LoginPayload): Promise<AuthChallenge> {
  return request<AuthChallenge>('/auth/login', 'POST', payload);
}

export function requestPasswordReset(email: string): Promise<AuthChallenge> {
  return request<AuthChallenge>('/auth/forgot-password', 'POST', { email });
}

export function resetPassword(challengeId: string, code: string, newPassword: string): Promise<void> {
  return request<void>('/auth/reset-password', 'POST', {
    challenge_id: challengeId,
    code,
    new_password: newPassword,
  });
}

export function refreshSession(): Promise<AuthTokens> {
  return request<AuthTokens>('/auth/refresh', 'POST');
}

export function getAuthenticatedSession(accessToken: string): Promise<AuthenticatedSession> {
  return request<AuthenticatedSession>('/auth/session', 'GET', undefined, accessToken);
}

export function verifyChallenge(
  challengeId: string,
  code: string,
  purpose: AuthChallengePurpose,
): Promise<AuthTokens> {
  const path = purpose === 'TOTP_LOGIN' ? '/auth/totp/challenge/verify' : '/auth/otp/verify';
  return request<AuthTokens>(path, 'POST', { challenge_id: challengeId, code });
}

export async function signOut(accessToken: string): Promise<void> {
  try {
    await request<void>('/auth/logout', 'POST', undefined, accessToken);
  } catch (error: unknown) {
    if (!(error instanceof AuthApiError && error.status === 401)) throw error;
    const refreshed = await refreshSession();
    await request<void>('/auth/logout', 'POST', undefined, refreshed.access_token);
  }
}
