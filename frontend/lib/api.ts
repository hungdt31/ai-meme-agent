export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

export type Style = "gen_z" | "van_phong" | "mua_thi" | "choi_chu";

export const STYLES: { id: Style; label: string }[] = [
  { id: "gen_z", label: "Gen Z" },
  { id: "van_phong", label: "Dân văn phòng" },
  { id: "mua_thi", label: "Mùa thi" },
  { id: "choi_chu", label: "Chơi chữ" },
];

export type MemeBox = { id: string; style: string; max_chars: number; hint: string };

export type Meme = {
  id: string;
  job_id: string;
  image_url: string;
  og_image_url: string;
  template_id: string | null;
  captions: Record<string, string>;
  boxes: MemeBox[];
  scores: Record<string, number> | null;
  rank: number | null;
  parent_id: string | null;
  owner: Owner | null;
  owner_id: string | null;
  post_id: string | null;
  created_at: string;
  topic?: string | null;
  overflow?: boolean;
};

export type Owner = { username: string; display_name: string; avatar_url: string | null };

export type Quota = { limit: number; used: number; left: number };

export type Me = Owner & {
  id: string;
  email: string;
  profile_public: boolean;
  created_at: string;
  stats: { memes: number; posts: number; likes: number };
  quota: Quota;
};

export type MemePage = { items: Meme[]; next_before: string | null };

export type Author = Owner & { username: string | null; profile_public: boolean };

export type Post = {
  id: string;
  created_at: string;
  edited: boolean;
  caption: string;
  author: Author;
  meme: { id: string; image_url: string; captions: Record<string, string> };
  like_count: number;
  comment_count: number;
  liked: boolean;
  mine: boolean;
};

export type PostComment = { id: string; created_at: string; body: string; author: Author; can_delete: boolean };

export type PostDetail = Post & { comments: PostComment[] };

export type Profile = Owner & { joined_at: string; meme_count: number; memes: MemePage };

export type Job = {
  id: string;
  status: "created" | "running" | "done" | "refused" | "failed";
  topic: string | null;
  style: Style | null;
  error: string | null;
  memes: Meme[];
};

export type TemplateItem = { id: string; name: string; when_to_use: string; thumb_url: string };

export type JobEvent =
  | { type: "node_start"; node: string }
  | { type: "node_end"; node: string; summary: string }
  | { type: "candidate"; candidate_id: string; image_url: string; template_id: string | null; overflow: boolean }
  | { type: "scored"; candidate_id: string; scores: Record<string, number>; feedback: string }
  | { type: "result"; memes: Meme[] }
  | { type: "refused"; message: string; suggestions: string[] }
  | { type: "error"; code: string; message: string }
  | { type: "done" };

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

/** Token phiên lưu trong localStorage (backend khác domain nên không dùng được cookie). */
const TOKEN_KEY = "chememe.token";
export const tokenStore = {
  get(): string | null {
    if (typeof window === "undefined") return null; // server component: luôn là khách
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // trình duyệt chặn lưu trữ: chỉ đăng nhập được trong tab này
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      // bỏ qua
    }
  },
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (res.status === 401 && token) tokenStore.clear(); // phiên hết hạn hoặc đã đăng xuất ở nơi khác
    throw new ApiError(res.status, body.code ?? "error", body.message ?? "Có lỗi xảy ra, thử lại nhé");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  templates: () => request<TemplateItem[]>("/api/templates"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ upload_id: string }>("/api/uploads", { method: "POST", body: form });
  },
  createJob: (body: { topic?: string; upload_id?: string; template_id?: string; style?: Style; consent?: boolean }) =>
    request<{ job_id: string }>("/api/jobs", json(body)),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  meme: (id: string) => request<Meme>(`/api/memes/${id}`),
  rerender: (id: string, captions: Record<string, string>) =>
    request<Meme & { overflow: boolean }>(`/api/memes/${id}/rerender`, json({ captions })),
  report: (id: string, reason: string) => request<void>(`/api/memes/${id}/report`, json({ reason })),
  feed: (sort: "new" | "hot", before?: string) =>
    request<{ items: Post[]; next_before: string | null }>(
      `/api/feed?sort=${sort}${before ? `&before=${encodeURIComponent(before)}` : ""}`,
    ),
  userPosts: (username: string) => request<{ items: Post[] }>(`/api/users/${encodeURIComponent(username)}/posts`),
  post: (id: string) => request<PostDetail>(`/api/posts/${id}`),
  createPost: (meme_id: string, caption: string) => request<Post>("/api/posts", json({ meme_id, caption })),
  editPost: (id: string, caption: string) => request<Post>(`/api/posts/${id}`, json({ caption }, "PATCH")),
  deletePost: (id: string) => request<void>(`/api/posts/${id}`, { method: "DELETE" }),
  reportPost: (id: string, reason: string) => request<void>(`/api/posts/${id}/report`, json({ reason })),
  like: (id: string) => request<{ liked: boolean; like_count: number }>(`/api/posts/${id}/like`, { method: "POST" }),
  unlike: (id: string) => request<{ liked: boolean; like_count: number }>(`/api/posts/${id}/like`, { method: "DELETE" }),
  comment: (id: string, body: string) => request<PostComment>(`/api/posts/${id}/comments`, json({ body })),
  deleteComment: (id: string) => request<void>(`/api/comments/${id}`, { method: "DELETE" }),

  loginGoogle: (credential: string) =>
    request<{ token: string; expires_at: string; user: Me }>("/api/auth/google", json({ credential })),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  me: () => request<Me>("/api/me"),
  quota: () => request<Quota & { signed_in: boolean }>("/api/me/quota"),
  updateMe: (body: { display_name?: string; username?: string; profile_public?: boolean }) =>
    request<Me>("/api/me", json(body, "PATCH")),
  deleteMe: () => request<void>("/api/me", { method: "DELETE" }),
  myMemes: (page = 1, pageSize = 12) =>
    request<{ items: Meme[]; page: number; pages: number; total: number }>(`/api/me/memes?page=${page}&page_size=${pageSize}`),
  deleteMeme: (id: string) => request<void>(`/api/memes/${id}`, { method: "DELETE" }),
  profile: (username: string) => request<Profile>(`/api/users/${encodeURIComponent(username)}`),
};

/** Đọc SSE từ POST /api/jobs/{id}/run (EventSource chỉ hỗ trợ GET nên tự parse). */
export async function streamJob(jobId: string, onEvent: (e: JobEvent) => void, signal?: AbortSignal) {
  const res = await fetch(`${API_URL}/api/jobs/${jobId}/run`, { method: "POST", signal });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.code ?? "error", body.message ?? "Không chạy được");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
      }
    }
  }
}

export function shareUrl(memeId: string) {
  return `${SITE_URL}/m/${memeId}`;
}
