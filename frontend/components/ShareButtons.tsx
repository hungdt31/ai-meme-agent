"use client";

import { useState } from "react";
import { shareUrl } from "@/lib/api";

export function ShareButtons({ memeId, imageUrl, compact = false }: { memeId: string; imageUrl: string; compact?: boolean }) {
  const [copied, setCopied] = useState(false);
  const url = shareUrl(memeId);

  async function share() {
    if (navigator.share) {
      try {
        await navigator.share({ url, title: "Meme từ ChếMeme" });
        return;
      } catch {
        // người dùng đóng bảng chia sẻ: chuyển sang copy link
      }
    }
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (compact) {
    return (
      <button type="button" onClick={share} className="min-h-12 rounded-2xl bg-clay-dark text-[15px] font-semibold text-white">
        {copied ? "Đã copy link" : "Chia sẻ"}
      </button>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      <a
        href={imageUrl}
        target="_blank"
        rel="noopener"
        download
        className="flex min-h-12 items-center justify-center rounded-2xl border border-line-strong bg-white text-[15px]"
      >
        Tải ảnh
      </a>
      <button type="button" onClick={share} className="min-h-12 rounded-2xl border border-line-strong bg-white text-[15px]">
        {copied ? "Đã copy link" : "Copy link"}
      </button>
    </div>
  );
}
