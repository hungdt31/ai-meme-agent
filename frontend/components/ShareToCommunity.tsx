"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError } from "@/lib/api";

const MAX = 500;

/** Chia sẻ meme của mình lên cộng đồng, kèm caption tuỳ chọn. Chỉ hiện với chủ meme đã đăng nhập. */
export function ShareToCommunity({
  memeId,
  ownerId,
  initialPostId,
}: {
  memeId: string;
  ownerId: string | null;
  initialPostId: string | null;
}) {
  const { user, loading } = useAuth();
  const [postId, setPostId] = useState(initialPostId);
  const [open, setOpen] = useState(false);
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading || !user || !ownerId || ownerId !== user.id) return null;

  if (postId) {
    return (
      <p className="flex min-h-11 items-center justify-center gap-1 rounded-2xl bg-good-tint px-4 text-sm text-good">
        Đã đăng lên cộng đồng ·{" "}
        <Link href={`/p/${postId}`} className="font-semibold underline">
          Xem bài
        </Link>
      </p>
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex min-h-12 items-center justify-center gap-2 rounded-2xl border border-clay bg-clay-tint text-[15px] font-semibold text-clay-dark"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
        Chia sẻ lên cộng đồng
      </button>
    );
  }

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      const post = await api.createPost(memeId, caption);
      setPostId(post.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đăng được, thử lại nhé");
    } finally {
      setBusy(false);
    }
  }

  const id = `share-caption-${memeId}`;
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-line-strong bg-ivory p-3">
      <label htmlFor={id} className="text-sm font-medium text-body">
        Viết gì đó kèm meme (tuỳ chọn)
      </label>
      <textarea
        id={id}
        rows={3}
        maxLength={MAX}
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        placeholder="Ai đi làm thứ 2 cũng hiểu cảm giác này…"
        className="resize-none rounded-xl border border-line-strong bg-white px-3 py-2 text-base"
      />
      <div className="flex items-center justify-between text-xs text-faint">
        <span>Mọi người trong cộng đồng sẽ thấy tên bạn và bài này.</span>
        <span>
          {caption.length}/{MAX}
        </span>
      </div>
      {error && <p className="text-sm text-clay-dark">{error}</p>}
      <div className="grid grid-cols-2 gap-2">
        <button type="button" onClick={() => setOpen(false)} className="min-h-11 rounded-xl text-sm text-muted">
          Huỷ
        </button>
        <button
          type="button"
          onClick={publish}
          disabled={busy}
          className="min-h-11 rounded-xl bg-clay-dark text-sm font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Đang đăng…" : "Đăng"}
        </button>
      </div>
    </div>
  );
}
