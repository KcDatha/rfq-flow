export interface LineItem {
  item_id: string;
  rfq_id: string;
  raw_line_text: string;
  product_category: string | null;
  extracted_material: string | null;
  extracted_size: string | null;
  extracted_schedule: string | null;
  quantity: number | null;
  unit_of_measure: string;
  confidence_score: number | null;
  requires_human_review: boolean;
  validation_notes: string[];
  reviewed: boolean;
  unit_price: number | null;
  customer_name?: string | null;
}

export interface Submission {
  rfq_id: string;
  customer_name: string | null;
  raw_text: string;
  status: string;
  extractor_used: string | null;
  created_at: string;
  source_filename: string | null;
  line_items: LineItem[];
}

export interface QuoteLine {
  item_id: string;
  description: string;
  quantity: number | null;
  unit_of_measure: string;
  unit_price: number;
  line_total: number;
}

export interface Quote {
  rfq_id: string;
  customer_name: string | null;
  lines: QuoteLine[];
  total: number;
}

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function request<T>(
  path: string,
  init?: RequestInit,
  opts?: { retries?: number; retryOn404?: boolean }
): Promise<T> {
  const retries = opts?.retries ?? (init?.method && init.method !== "GET" ? 0 : 2);
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(path, init);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const err = new ApiError(body.detail || `Request failed (${res.status})`, res.status);
        // Demo data lives in per-instance serverless storage, so a 404
        // can just mean "wrong instance" — retrying often lands on the
        // instance that actually holds the record.
        if (opts?.retryOn404 && res.status === 404 && attempt < retries) {
          await sleep(400 * (attempt + 1));
          continue;
        }
        throw err;
      }
      return res.json();
    } catch (e) {
      lastErr = e;
      // Network-level failures (cold start in flight, connection reset)
      // are worth retrying on reads; a definitive HTTP error is not.
      if (e instanceof ApiError || attempt >= retries) throw e;
      await sleep(400 * (attempt + 1));
    }
  }
  throw lastErr;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// --- Local mirror of submissions -------------------------------------------
//
// On Vercel each serverless instance keeps its own throwaway SQLite file
// in /tmp, so the same GET can return a submission on one request and an
// empty list on the next (verified live). Until the app runs on a shared
// database (set DATABASE_URL), the browser keeps a mirror of everything
// it submitted and merges it with whatever the server returns, so data
// never visibly disappears between tabs or refreshes.

const CACHE_KEY = "rfqflow.submissions.v1";
const CACHE_LIMIT = 50;

function readCache(): Submission[] {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeCache(subs: Submission[]) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(subs.slice(0, CACHE_LIMIT)));
  } catch {
    // Storage full or unavailable (private mode) — mirror is best-effort.
  }
}

export function cacheSubmission(sub: Submission) {
  const rest = readCache().filter((s) => s.rfq_id !== sub.rfq_id);
  writeCache([sub, ...rest]);
}

export function getCachedSubmissions(): Submission[] {
  return readCache();
}

function updateCachedSubmission(rfqId: string, fn: (sub: Submission) => Submission) {
  writeCache(readCache().map((s) => (s.rfq_id === rfqId ? fn(s) : s)));
}

export function markCachedItemReviewed(updated: LineItem) {
  updateCachedSubmission(updated.rfq_id, (sub) => ({
    ...sub,
    line_items: sub.line_items.map((i) =>
      i.item_id === updated.item_id ? { ...i, ...updated, reviewed: true } : i
    ),
  }));
}

export function markCachedQuoted(rfqId: string) {
  updateCachedSubmission(rfqId, (sub) => ({ ...sub, status: "QUOTED" }));
}

/** Server rows win; cached rows fill in anything the server missed. */
export function mergeSubmissions(server: Submission[], cached: Submission[]): Submission[] {
  const seen = new Set(server.map((s) => s.rfq_id));
  return [...server, ...cached.filter((s) => !seen.has(s.rfq_id))];
}

export const api = {
  submitText: async (raw_text: string, customer_name?: string) => {
    const sub = await request<Submission>("/rfqs", json("POST", { raw_text, customer_name }));
    cacheSubmission(sub);
    return sub;
  },

  submitFile: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const sub = await request<Submission>("/rfqs/upload", { method: "POST", body: form });
    cacheSubmission(sub);
    return sub;
  },

  listRfqs: () => request<Submission[]>("/rfqs"),
  reviewQueue: () => request<LineItem[]>("/review-queue"),

  reviewItem: async (itemId: string, patch: Partial<LineItem>) => {
    const item = await request<LineItem>(`/review/${itemId}`, json("PATCH", patch), {
      retries: 4,
      retryOn404: true,
    });
    markCachedItemReviewed(item);
    return item;
  },

  generateQuote: async (rfqId: string) => {
    const quote = await request<Quote>(`/rfqs/${rfqId}/quote`, { method: "POST" }, {
      retries: 4,
      retryOn404: true,
    });
    markCachedQuoted(rfqId);
    return quote;
  },

  materials: () =>
    request<{ grade_id: string; category: string; is_exotic: boolean }[]>(
      "/catalog/materials"
    ),
};
