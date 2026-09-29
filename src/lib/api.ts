import type { ApiError } from "./types";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = error.code;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  query?: Query;
  retry?: boolean;
}

let refreshing: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch("/api/auth/refresh", { method: "POST", credentials: "include" })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

function buildUrl(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const data = await res.json();
    if (data?.error?.code) return data.error as ApiError;
    if (Array.isArray(data?.detail)) {
      const first = data.detail[0];
      const field = Array.isArray(first?.loc) ? first.loc.slice(1).join(".") : "";
      return {
        code: "validation_error",
        message: field ? `${field}: ${first.msg}` : String(first?.msg ?? "Invalid input"),
      };
    }
    if (typeof data?.detail === "string") return { code: "error", message: data.detail };
  } catch {
    /* non-JSON body */
  }
  return { code: `http_${res.status}`, message: res.statusText || "Request failed" };
}

const AUTH_RETRY_CODES = new Set(["token_expired", "unauthenticated", "token_invalid"]);

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, retry = true } = options;
  const res = await fetch(buildUrl(path, query), {
    method,
    credentials: "include",
    headers: body !== undefined ? { "content-type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (res.status === 204) return undefined as T;
  if (res.ok) return (await res.json()) as T;

  const error = await parseError(res);
  const isAuthPath = path.startsWith("/api/auth/refresh") || path.startsWith("/api/auth/login");
  if (res.status === 401 && retry && !isAuthPath && AUTH_RETRY_CODES.has(error.code)) {
    if (await refreshSession()) {
      return api<T>(path, { ...options, retry: false });
    }
  }
  throw new ApiRequestError(res.status, error);
}

export function errorMessage(err: unknown, fallback = "Something went wrong"): string {
  if (err instanceof ApiRequestError) return err.message;
  if (err instanceof Error) return err.message;
  return fallback;
}
