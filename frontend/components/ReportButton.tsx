"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function ReportButton({ memeId }: { memeId: string }) {
  const [sent, setSent] = useState(false);

  async function report() {
    if (!confirm("Báo cáo meme này có nội dung không phù hợp?")) return;
    await api.report(memeId, "user_report").catch(() => undefined);
    setSent(true);
  }

  return (
    <button type="button" onClick={report} disabled={sent} className="mx-auto min-h-11 text-sm text-faint underline disabled:no-underline">
      {sent ? "Đã gửi báo cáo, cảm ơn bạn" : "Báo cáo nội dung này"}
    </button>
  );
}
