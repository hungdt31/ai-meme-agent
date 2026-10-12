import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Avatar } from "@/components/Avatar";
import { ReportButton } from "@/components/ReportButton";
import { ShareButtons } from "@/components/ShareButtons";
import { api, ApiError, type Meme } from "@/lib/api";

export const dynamic = "force-dynamic";

async function load(id: string): Promise<Meme | "hidden" | null> {
  try {
    return await api.meme(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 410) return "hidden";
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const meme = await load((await params).id);
  if (!meme || meme === "hidden") return { title: "Meme", robots: { index: false } };
  const title = Object.values(meme.captions).find(Boolean)?.split("\n")[0] ?? "Meme";
  return {
    title,
    description: meme.topic ? `Chế từ: ${meme.topic}` : "Meme chế bằng AI",
    // Messenger, Zalo, Facebook đọc các thẻ này để hiện ảnh xem trước khi dán link
    openGraph: { title, images: [{ url: meme.og_image_url }], type: "website", siteName: "ChếMeme" },
    twitter: { card: "summary_large_image", title, images: [meme.og_image_url] },
  };
}

export default async function MemePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const meme = await load(id);
  if (!meme) notFound();
  if (meme === "hidden") {
    return <p className="rounded-2xl border border-line bg-white p-6 text-muted">Meme này đang được xem xét sau khi có báo cáo.</p>;
  }
  return (
    <div className="flex flex-col gap-4 pt-2">
      <img
        src={meme.image_url}
        alt={Object.values(meme.captions).join(" / ")}
        className="block w-full rounded-3xl border border-line shadow-[0_6px_24px_rgba(20,20,19,0.06)]"
      />
      {meme.owner && (
        <Link href={`/u/${meme.owner.username}`} className="flex min-h-11 items-center gap-2 text-sm text-body">
          <Avatar name={meme.owner.display_name} url={meme.owner.avatar_url} size={28} />
          <span>
            Chế bởi <span className="font-medium">{meme.owner.display_name}</span>
          </span>
        </Link>
      )}
      {meme.topic && <p className="text-sm leading-relaxed text-muted">Chế từ tình huống: “{meme.topic}”</p>}
      <ShareButtons memeId={meme.id} imageUrl={meme.image_url} />
      <Link href="/" className="flex min-h-14 items-center justify-center rounded-2xl bg-clay-dark text-base font-semibold text-white">
        Chế meme của bạn
      </Link>
      <Link href="/arena" className="flex min-h-12 items-center justify-center rounded-2xl bg-sand text-[15px] text-body">
        Vào đấu trường bình chọn
      </Link>
      <ReportButton memeId={meme.id} />
    </div>
  );
}
