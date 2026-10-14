"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Avatar } from "@/components/Avatar";
import { api, ApiError, type Post } from "@/lib/api";
import { timeAgo } from "@/lib/time";

export function AuthorName({ author }: { author: Post["author"] }) {
  if (author.username && author.profile_public) {
    return (
      <Link href={`/u/${author.username}`} className="truncate font-semibold hover:underline">
        {author.display_name}
      </Link>
    );
  }
  return <span className="truncate font-semibold">{author.display_name}</span>;
}

/** Một bài trong bảng tin: người đăng, caption, ảnh meme, tim, bình luận. */
export function PostCard({
  post: initial,
  linkToDetail = true,
  onDeleted,
  commentCount,
}: {
  post: Post;
  linkToDetail?: boolean;
  onDeleted?: () => void;
  commentCount?: number;
}) {
  const router = useRouter();
  const { user } = useAuth();
  const [post, setPost] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(initial.caption);
  const [menu, setMenu] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggleLike() {
    if (!user) {
      router.push(`/login?next=${encodeURIComponent(linkToDetail ? "/feed" : `/p/${post.id}`)}`);
      return;
    }
    const liked = !post.liked;
    setPost({ ...post, liked, like_count: post.like_count + (liked ? 1 : -1) }); // cập nhật ngay, máy chủ xác nhận sau
    try {
      const res = liked ? await api.like(post.id) : await api.unlike(post.id);
      setPost((p) => ({ ...p, liked: res.liked, like_count: res.like_count }));
    } catch {
      setPost((p) => ({ ...p, liked: !liked, like_count: p.like_count + (liked ? -1 : 1) }));
    }
  }

  async function saveCaption() {
    try {
      setPost(await api.editPost(post.id, draft));
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được");
    }
  }

  async function remove() {
    setMenu(false);
    if (!confirm("Xoá bài này? Tim và bình luận cũng sẽ mất.")) return;
    await api.deletePost(post.id);
    if (onDeleted) onDeleted();
    else router.push("/feed");
  }

  async function report() {
    setMenu(false);
    if (!confirm("Báo cáo bài này có nội dung không phù hợp?")) return;
    await api.reportPost(post.id, "user_report").catch(() => undefined);
    setError("Đã gửi báo cáo, cảm ơn bạn");
  }

  const image = <img src={post.meme.image_url} alt={Object.values(post.meme.captions).join(" / ")} loading="lazy" className="block w-full rounded-2xl border border-line" />;

  return (
    <article className="flex gap-3 border-b border-line py-4">
      <Avatar name={post.author.display_name} url={post.author.avatar_url} size={40} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <header className="flex items-center gap-2 text-[15px]">
          <AuthorName author={post.author} />
          <span className="shrink-0 text-sm text-faint">
            {timeAgo(post.created_at)}
            {post.edited && " · đã sửa"}
          </span>
          <div className="relative ml-auto">
            <button type="button" onClick={() => setMenu(!menu)} aria-label="Tuỳ chọn" className="flex size-9 items-center justify-center rounded-full text-faint hover:bg-sand">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <circle cx="5" cy="12" r="1.8" />
                <circle cx="12" cy="12" r="1.8" />
                <circle cx="19" cy="12" r="1.8" />
              </svg>
            </button>
            {menu && (
              <div className="absolute right-0 z-10 mt-1 w-40 overflow-hidden rounded-xl border border-line bg-white text-sm shadow-lg">
                {post.mine ? (
                  <>
                    <button type="button" onClick={() => { setMenu(false); setDraft(post.caption); setEditing(true); }} className="block min-h-11 w-full px-4 text-left hover:bg-sand">
                      Sửa caption
                    </button>
                    <button type="button" onClick={remove} className="block min-h-11 w-full px-4 text-left text-clay-dark hover:bg-sand">
                      Xoá bài
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={report} className="block min-h-11 w-full px-4 text-left hover:bg-sand">
                    Báo cáo
                  </button>
                )}
              </div>
            )}
          </div>
        </header>

        {editing ? (
          <div className="flex flex-col gap-2">
            <textarea value={draft} maxLength={500} rows={3} onChange={(e) => setDraft(e.target.value)} className="resize-none rounded-xl border border-line-strong px-3 py-2 text-base" aria-label="Caption" />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setEditing(false)} className="min-h-10 px-3 text-sm text-muted">
                Huỷ
              </button>
              <button type="button" onClick={saveCaption} className="min-h-10 rounded-xl bg-clay-dark px-4 text-sm font-semibold text-white">
                Lưu
              </button>
            </div>
          </div>
        ) : (
          post.caption && <p className="whitespace-pre-line text-[15px] leading-relaxed">{post.caption}</p>
        )}

        {linkToDetail ? <Link href={`/p/${post.id}`}>{image}</Link> : image}

        <footer className="flex items-center gap-1 text-sm text-body">
          <button
            type="button"
            onClick={toggleLike}
            aria-pressed={post.liked}
            aria-label={post.liked ? "Bỏ tim" : "Thả tim"}
            className={`flex min-h-10 items-center gap-1.5 rounded-full px-3 hover:bg-sand ${post.liked ? "text-[#E5484D]" : ""}`}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill={post.liked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z" />
            </svg>
            {post.like_count > 0 && post.like_count}
          </button>
          <Link href={`/p/${post.id}`} className="flex min-h-10 items-center gap-1.5 rounded-full px-3 hover:bg-sand" aria-label="Bình luận">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-.9L3 20l1.1-4.5A8.4 8.4 0 0 1 12 3a8.5 8.5 0 0 1 9 8.5z" />
            </svg>
            {(commentCount ?? post.comment_count) > 0 && (commentCount ?? post.comment_count)}
          </Link>
        </footer>
        {error && <p className="text-sm text-muted">{error}</p>}
      </div>
    </article>
  );
}
