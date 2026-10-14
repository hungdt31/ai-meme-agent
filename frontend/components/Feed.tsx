"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { PostCard } from "@/components/PostCard";
import { api, type Post } from "@/lib/api";

type Sort = "new" | "hot";
const TABS: { id: Sort; label: string }[] = [
  { id: "new", label: "Mới nhất" },
  { id: "hot", label: "Nổi bật" },
];

export function Feed() {
  const { user, loading: authLoading } = useAuth();
  const [sort, setSort] = useState<Sort>("new");
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setPosts(null);
    setError(null);
    try {
      const page = await api.feed(sort);
      setPosts(page.items);
      setNextBefore(page.next_before);
    } catch {
      setError("Không tải được bảng tin");
    }
  }, [sort]);

  useEffect(() => {
    if (!authLoading) load(); // đợi biết đã đăng nhập chưa để trạng thái tim đúng
  }, [load, authLoading, user?.id]);

  async function more() {
    if (!nextBefore) return;
    const page = await api.feed(sort, nextBefore);
    setPosts((p) => [...(p ?? []), ...page.items]);
    setNextBefore(page.next_before);
  }

  return (
    <div className="flex flex-col pt-2">
      <div className="flex items-baseline justify-between pb-3">
        <h1 className="font-serif text-3xl font-normal">Cộng đồng</h1>
        <Link href="/" className="flex min-h-10 items-center rounded-full bg-clay-dark px-4 text-sm font-semibold text-white">
          Tạo meme
        </Link>
      </div>
      <div role="tablist" className="grid grid-cols-2 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={sort === t.id}
            onClick={() => setSort(t.id)}
            className={`min-h-11 border-b-2 text-[15px] ${sort === t.id ? "border-ink font-semibold text-ink" : "border-transparent text-muted"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <p className="py-6 text-center text-muted">{error}</p>}
      {posts === null && !error && <p className="py-6 text-center text-muted">Đang tải…</p>}
      {posts?.length === 0 && (
        <div className="flex flex-col items-center gap-3 py-10 text-center text-muted">
          <p>{sort === "hot" ? "Tuần này chưa có bài nào nổi bật." : "Chưa có ai đăng bài."}</p>
          <Link href="/" className="font-semibold text-clay-dark underline">
            Tạo meme và đăng bài đầu tiên
          </Link>
        </div>
      )}
      {posts?.map((p) => (
        <PostCard key={p.id} post={p} onDeleted={() => setPosts((list) => list?.filter((x) => x.id !== p.id) ?? null)} />
      ))}
      {nextBefore && (
        <button type="button" onClick={more} className="my-4 min-h-11 rounded-2xl border border-line-strong bg-white text-sm">
          Xem thêm
        </button>
      )}
      {!user && posts && posts.length > 0 && (
        <p className="py-4 text-center text-sm text-muted">
          <Link href="/login?next=/feed" className="underline">
            Đăng nhập
          </Link>{" "}
          để thả tim, bình luận và đăng meme của bạn.
        </p>
      )}
    </div>
  );
}
