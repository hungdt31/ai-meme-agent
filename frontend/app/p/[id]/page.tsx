import type { Metadata } from "next";
import { PostDetailView } from "@/components/PostDetailView";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const post = await api.post((await params).id).catch(() => null);
  if (!post) return { title: "Bài viết", robots: { index: false } };
  const memeTitle = Object.values(post.meme.captions).find(Boolean)?.split("\n")[0] ?? "Meme";
  const title = `${post.author.display_name} trên Easy Meme`;
  const description = post.caption || memeTitle;
  // Ảnh JPEG cùng tên với ảnh WebP (backend lưu cả hai) để Messenger, Zalo hiện ảnh xem trước
  const ogImage = post.meme.image_url.replace(/\.webp$/, ".jpg");
  return {
    title,
    description,
    openGraph: { title, description, images: [{ url: ogImage }], type: "article", siteName: "Easy Meme" },
    twitter: { card: "summary_large_image", title, description, images: [ogImage] },
  };
}

export default async function PostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PostDetailView postId={id} />;
}
