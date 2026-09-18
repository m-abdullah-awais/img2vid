// The one door to the img2vid engine. Every request goes through here so the
// base URL, the error shape and the "engine is not running" case are handled
// once.

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8765").replace(
  /\/+$/,
  "",
);

export const ENGINE_DOWN = "The img2vid engine is not running. Start it with Run.bat.";

/** Absolute URL for a path the API handed back, which always starts /api/. */
export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return API_BASE + (path.startsWith("/") ? path : `/${path}`);
}

/** /api/projects/{id}/... with every segment URL encoded. */
export function projectPath(id: string, ...segments: (string | number)[]): string {
  const rest = segments.map((part) => encodeURIComponent(String(part))).join("/");
  return `/api/projects/${encodeURIComponent(id)}${rest ? `/${rest}` : ""}`;
}

export type ErrorDetails = Record<string, unknown> | null;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetails;

  constructor(status: number, code: string, message: string, details: ErrorDetails = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isUnreachable(error: unknown): boolean {
  return error instanceof ApiError && error.code === "unreachable";
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError(0, "aborted", "Stopped.");
  }
  if (error instanceof TypeError) return new ApiError(0, "unreachable", ENGINE_DOWN);
  const message = error instanceof Error ? error.message : String(error);
  return new ApiError(0, "internal", message);
}

function errorFromBody(status: number, text: string): ApiError {
  try {
    const parsed = JSON.parse(text) as {
      error?: { code?: string; message?: string; details?: ErrorDetails };
    };
    if (parsed && parsed.error && typeof parsed.error.message === "string") {
      return new ApiError(
        status,
        parsed.error.code || "internal",
        parsed.error.message,
        parsed.error.details ?? null,
      );
    }
  } catch {
    // Not JSON: fall through to a plain description of the status.
  }
  return new ApiError(
    status,
    status === 404 ? "not_found" : "internal",
    `The engine answered ${status} without saying why. Try again, and if it repeats, restart Run.bat.`,
  );
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  json?: unknown;
  signal?: AbortSignal;
  ifNoneMatch?: string | null;
};

export type RawResponse<T> = {
  status: number;
  data: T | null;
  etag: string | null;
};

/** Low level: returns the status, so callers can see a 304. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<RawResponse<T>> {
  const headers: Record<string, string> = {};
  let body: string | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }
  if (options.ifNoneMatch) headers["If-None-Match"] = options.ifNoneMatch;

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: options.method || "GET",
      headers,
      body,
      signal: options.signal,
      cache: "no-store",
    });
  } catch (error) {
    throw toApiError(error);
  }

  const etag = response.headers.get("ETag");
  if (response.status === 304) return { status: 304, data: null, etag };

  const text = await response.text();
  if (!response.ok) throw errorFromBody(response.status, text);
  const data = (text ? JSON.parse(text) : {}) as T;
  return { status: response.status, data, etag };
}

/** The usual call: resolves to the JSON body, throws ApiError otherwise. */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const result = await request<T>(path, options);
  return result.data as T;
}

export const post = <T>(path: string, json: unknown = {}, signal?: AbortSignal) =>
  api<T>(path, { method: "POST", json, signal });

export const patch = <T>(path: string, json: unknown) => api<T>(path, { method: "PATCH", json });

export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });

type UploadOptions = {
  query?: Record<string, string | number | boolean | undefined | null>;
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
};

function withQuery(path: string, query: UploadOptions["query"]): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === false) continue;
    params.set(key, value === true ? "1" : String(value));
  }
  const text = params.toString();
  return text ? `${path}${path.includes("?") ? "&" : "?"}${text}` : path;
}

/**
 * PUT a file as the raw request body. XMLHttpRequest rather than fetch,
 * because only XHR reports upload progress. The browser sets Content-Length.
 */
export function upload<T>(path: string, file: Blob, options: UploadOptions = {}): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", apiUrl(withQuery(path, options.query)));
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && options.onProgress) {
        options.onProgress(event.total ? event.loaded / event.total : 0);
      }
    };
    xhr.onload = () => {
      const text = xhr.responseText || "";
      if (xhr.status >= 200 && xhr.status < 300) {
        options.onProgress?.(1);
        try {
          resolve((text ? JSON.parse(text) : {}) as T);
        } catch {
          resolve({} as T);
        }
      } else {
        reject(errorFromBody(xhr.status, text));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "unreachable", ENGINE_DOWN));
    xhr.onabort = () => reject(new ApiError(0, "aborted", "Upload stopped."));

    if (options.signal) {
      if (options.signal.aborted) {
        reject(new ApiError(0, "aborted", "Upload stopped."));
        return;
      }
      options.signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(file);
  });
}

/** Run async work over items, at most `limit` at a time. */
export async function pool<T>(items: T[], limit: number, work: (item: T, index: number) => Promise<void>) {
  let cursor = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor++;
      await work(items[index], index);
    }
  });
  await Promise.all(runners);
}
