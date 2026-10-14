"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Avatar } from "@/components/Avatar";
import { AuthorName, PostCard } from "@/components/PostCard";
import { api, ApiError, type PostComment, type PostDetail } from "@/lib/api";
import { timeAgo } from "@/lib/time";

export function PostDetailView({ postId }: { postId: string }) {
  const { user, loading: authLoading } = useAuth();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [comments, setComments] = useState<PostComment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    api
      .post(postId)
      .then((p) => {
        setPost(p);
        setComments(p.comments);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được bài viết"));
  }, [postId, authLoading, user?.id]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setSending(true);
    try {
      const c = await api.comment(postId, body);
      setComments((list) => [...list, c]);
      setBody("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không gửi được bình luận");
    } finally {
      setSending(false);
    }
  }

  async function removeComment(id: string) {
    if (!confirm("Xoá bình luận này?")) return;
    await api.deleteComment(id);
    setComments((list) => list.filter((c) => c.id !== id));
  }

  if (error && !post) return <p className="py-8 text-center text-muted">{error}</p>;
  if (!post) return <p className="py-8 text-center text-muted">Đang tải…</p>;

  return (
    <div className="flex flex-col pt-2">
      <Link href="/feed" className="flex min-h-11 items-center gap-1 text-sm text-muted">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M15 5l-7 7 7 7" />
        </svg>
        Cộng đồng
      </Link>
      <PostCard post={post} commentCount={comments.length} linkToDetail={false} />

      <section className="flex flex-col" aria-label="Bình luận">
        {comments.length === 0 && <p className="py-6 text-center text-sm text-muted">Chưa có bình luận nào. Mở màn đi!</p>}
        {comments.map((c) => (
          <div key={c.id} className="flex gap-3 border-b border-line py-3">
            <Avatar name={c.author.display_name} url={c.author.avatar_url} size={32} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-sm">
                <AuthorName author={c.author} />
                <span className="text-faint">{timeAgo(c.created_at)}</span>
                {c.can_delete && (
                  <button type="button" onClick={() => removeComment(c.id)} className="ml-auto min-h-9 px-2 text-xs text-faint underline">
                    Xoá
                  </button>
                )}
              </div>
              <p className="whitespace-pre-line text-[15px] leading-relaxed break-words">{c.body}</p>
            </div>
          </div>
        ))}
      </section>

      {user ? (
        <form onSubmit={send} className="sticky bottom-0 flex items-end gap-2 border-t border-line bg-ivory py-3">
          <Avatar name={user.display_name} url={user.avatar_url} size={32} />
          <label htmlFor="comment" className="sr-only">
            Viết bình luận
          </label>
          <textarea
            id="comment"
            rows={1}
            maxLength={500}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={`Trả lời ${post.author.display_name}…`}
            className="min-h-11 flex-1 resize-none rounded-2xl border border-line-strong bg-white px-3.5 py-2.5 text-base"
          />
          <button type="submit" disabled={sending || !body.trim()} className="min-h-11 rounded-2xl bg-clay-dark px-4 text-sm font-semibold text-white disabled:opacity-40">
            Gửi
          </button>
        </form>
      ) : (
        <p className="py-4 text-center text-sm text-muted">
          <Link href={`/login?next=/p/${postId}`} className="font-semibold underline">
            Đăng nhập
          </Link>{" "}
          để bình luận.
        </p>
      )}
      {error && post && <p className="pb-4 text-sm text-clay-dark">{error}</p>}
    </div>
  );
}
