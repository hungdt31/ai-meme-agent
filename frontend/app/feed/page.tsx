import type { Metadata } from "next";
import { Feed } from "@/components/Feed";

export const metadata: Metadata = { title: "Cộng đồng", description: "Meme mọi người vừa tạo và chia sẻ trên Easy Meme." };

export default function FeedPage() {
  return <Feed />;
}
