import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Avatar } from "@/components/Avatar";
import { MemeGrid } from "@/components/MemeGrid";
import { api, ApiError, type Profile } from "@/lib/api";

export const dynamic = "force-dynamic";

async function load(username: string): Promise<Profile | null> {
  try {
    return await api.profile(username);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ username: string }> }): Promise<Metadata> {
  const profile = await load((await params).username);
  if (!profile) return { title: "Không tìm thấy", robots: { index: false } };
  const cover = profile.memes.items[0]?.og_image_url;
  return {
    title: `${profile.display_name} (@${profile.username})`,
    description: `${profile.meme_count} meme trên ChếMeme`,
    openGraph: { title: `Meme của ${profile.display_name}`, images: cover ? [{ url: cover }] : [] },
  };
}

export default async function ProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const profile = await load((await params).username);
  if (!profile) notFound();
  const joined = new Date(profile.joined_at).toLocaleDateString("vi-VN", { month: "long", year: "numeric" });
  return (
    <div className="flex flex-col gap-6 pt-2">
      <section className="flex items-center gap-4">
        <Avatar name={profile.display_name} url={profile.avatar_url} size={64} />
        <div className="min-w-0">
          <h1 className="truncate font-serif text-2xl font-normal">{profile.display_name}</h1>
          <p className="text-sm text-muted">
            @{profile.username} · {profile.meme_count} meme · tham gia {joined}
          </p>
        </div>
      </section>
      <MemeGrid items={profile.memes.items} />
    </div>
  );
}
