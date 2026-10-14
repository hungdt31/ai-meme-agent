"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { CaptionEditor } from "@/components/CaptionEditor";
import { ShareButtons } from "@/components/ShareButtons";
import { ShareToCommunity } from "@/components/ShareToCommunity";
import type { Meme } from "@/lib/api";

const SCORE_LABELS: Record<string, string> = { readable: "Dễ đọc", fit: "Hợp template", funny: "Hài" };

export function MemeCard({ meme: initial }: { meme: Meme }) {
  const [meme, setMeme] = useState(initial);
  const [editing, setEditing] = useState(false);
  const { user } = useAuth();
  // Meme có chủ thì chỉ chủ được sửa (backend cũng kiểm tra); so theo owner_id để đúng cả khi hồ sơ riêng tư
  const canEdit = !meme.owner_id || meme.owner_id === user?.id;

  return (
    <article className="overflow-hidden rounded-3xl border border-line bg-white shadow-[0_6px_24px_rgba(20,20,19,0.06)]">
      <img src={meme.image_url} alt={Object.values(meme.captions).join(" / ")} className="block w-full" />
      <div className="flex flex-col gap-3 p-4">
        {meme.scores && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-body">
            {meme.rank && <span className="rounded-full bg-clay-tint px-2 py-0.5 font-semibold text-clay-dark">Top {meme.rank}</span>}
            {Object.entries(SCORE_LABELS).map(([k, label]) => (
              <span key={k}>
                {label} {meme.scores?.[k]}
              </span>
            ))}
          </div>
        )}
        {editing ? (
          <CaptionEditor meme={meme} onChange={setMeme} onDone={() => setEditing(false)} />
        ) : (
          <div className={`grid gap-2 ${canEdit ? "grid-cols-2" : "grid-cols-1"}`}>
            {canEdit && (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="min-h-12 rounded-2xl border border-line-strong bg-white text-[15px] font-medium"
            >
              Sửa chữ
            </button>
            )}
            <ShareButtons memeId={meme.id} imageUrl={meme.image_url} compact />
          </div>
        )}
        {!editing && <ShareToCommunity memeId={meme.id} ownerId={meme.owner_id} initialPostId={meme.post_id} />}
      </div>
    </article>
  );
}
