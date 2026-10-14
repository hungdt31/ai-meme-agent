"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { PostCard } from "@/components/PostCard";
import { api, type Post } from "@/lib/api";

/** Bài đăng của một người trên trang hồ sơ (tải ở trình duyệt để trạng thái tim đúng với người xem). */
export function UserPosts({ username }: { username: string }) {
  const { user, loading } = useAuth();
  const [posts, setPosts] = useState<Post[] | null>(null);

  useEffect(() => {
    if (loading) return;
    api
      .userPosts(username)
      .then((r) => setPosts(r.items))
      .catch(() => setPosts([]));
  }, [username, loading, user?.id]);

  if (!posts || posts.length === 0) return null;
  return (
    <section className="flex flex-col">
      <h2 className="border-b border-line pb-2 font-serif text-xl">Bài đã đăng</h2>
      {posts.map((p) => (
        <PostCard key={p.id} post={p} onDeleted={() => setPosts((list) => list?.filter((x) => x.id !== p.id) ?? null)} />
      ))}
    </section>
  );
}
