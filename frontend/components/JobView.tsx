"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { MemeCard } from "@/components/MemeCard";
import { api, ApiError, streamJob, type JobEvent, type Meme } from "@/lib/api";

const STEP_LABELS: Record<string, string> = {
  understand: "Hiểu ý",
  describe_image: "Xem ảnh",
  pick_templates: "Chọn template",
  write_captions: "Viết caption",
  render: "Vẽ chữ lên ảnh",
  critique: "Tự chấm",
  select: "Lọc kết quả",
};

type Step = { node: string; summary?: string; done: boolean };
type Draft = { id: string; image_url: string; overflow: boolean; scored: boolean; kept: boolean | null; feedback?: string };

export function JobView({ jobId }: { jobId: string }) {
  const [topic, setTopic] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [memes, setMemes] = useState<Meme[] | null>(null);
  const [refusal, setRefusal] = useState<{ message: string; suggestions: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    // Chỉ chạy job một lần cho mỗi trang. Không huỷ request khi effect dọn dẹp: StrictMode (lúc dev)
    // gắn component 2 lần, nếu abort ở lần gỡ đầu thì lệnh chạy job sẽ không bao giờ được gửi.
    if (started.current) return;
    started.current = true;

    const onEvent = (e: JobEvent) => {
      switch (e.type) {
        case "node_start":
          setSteps((s) => [...s, { node: e.node, done: false }]);
          break;
        case "node_end":
          setSteps((s) => {
            const i = s.findLastIndex((x) => x.node === e.node && !x.done);
            return i < 0 ? s : s.map((x, j) => (j === i ? { ...x, summary: e.summary, done: true } : x));
          });
          break;
        case "candidate":
          setDrafts((d) => [...d, { id: e.candidate_id, image_url: e.image_url, overflow: e.overflow, scored: false, kept: null }]);
          break;
        case "scored": {
          const s = e.scores;
          const ok = s.safe >= 5 && s.readable >= 3 && s.fit >= 2;
          setDrafts((d) => d.map((x) => (x.id === e.candidate_id ? { ...x, scored: true, feedback: e.feedback, kept: ok && !x.overflow ? null : false } : x)));
          break;
        }
        case "result":
          setMemes(e.memes);
          break;
        case "refused":
          setRefusal({ message: e.message, suggestions: e.suggestions });
          break;
        case "error":
          setError(e.message);
          break;
      }
    };

    const poll = async () => {
      // Job đã chạy ở tab khác hoặc người dùng tải lại trang: đợi kết quả
      for (let i = 0; i < 40; i++) {
        const job = await api.job(jobId);
        if (job.status === "done") return setMemes(job.memes);
        if (job.status === "refused") return setRefusal({ message: "Chủ đề này không chế được. Thử chủ đề khác nhé.", suggestions: [] });
        if (job.status === "failed") return setError("Lần chế này bị lỗi. Thử lại nhé.");
        await new Promise((r) => setTimeout(r, 1500));
      }
      setError("Chạy quá lâu, thử tải lại trang.");
    };

    (async () => {
      try {
        const job = await api.job(jobId);
        setTopic(job.topic);
        if (job.status === "created") await streamJob(jobId, onEvent);
        else await poll();
      } catch (err) {
        if (err instanceof ApiError && err.code === "already_running") await poll().catch(() => setError("Mất kết nối"));
        else setError(err instanceof ApiError ? err.message : "Mất kết nối với máy chủ");
      }
    })();
  }, [jobId]);

  const running = !memes && !refusal && !error;

  return (
    <div className="flex flex-col gap-5 pt-2">
      {topic && (
        <div className="flex justify-end">
          <p className="max-w-[85%] rounded-2xl bg-sand px-4 py-2.5 text-[15px] leading-normal">{topic}</p>
        </div>
      )}

      {(running || steps.length > 0) && !memes && (
        <ol className="flex flex-col gap-2 rounded-2xl border border-line bg-white p-4" aria-live="polite">
          {steps.length === 0 && <li className="text-sm text-muted">Đang khởi động…</li>}
          {steps.map((s, i) => (
            <li key={i} className="flex items-start gap-3 text-sm">
              <StepIcon done={s.done} />
              <span>
                <span className="font-medium">{STEP_LABELS[s.node] ?? s.node}</span>
                {s.summary && <span className="block text-muted">{s.summary}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}

      {!memes && drafts.length > 0 && (
        <div className="grid grid-cols-4 gap-2">
          {drafts.map((d) => (
            <img
              key={d.id}
              src={d.image_url}
              alt=""
              title={d.feedback}
              className={`aspect-square w-full rounded-lg object-cover transition ${d.kept === false ? "opacity-25 grayscale" : d.scored ? "" : "blur-[2px]"}`}
            />
          ))}
        </div>
      )}

      {memes && (
        <section className="flex flex-col gap-5">
          {memes.length === 0 && <p className="text-muted">Không có meme nào đạt chuẩn. Thử diễn đạt khác nhé.</p>}
          {memes.map((m) => (
            <MemeCard key={m.id} meme={m} />
          ))}
          <Link href="/" className="flex min-h-12 items-center justify-center rounded-2xl border border-line-strong bg-white text-[15px]">
            Chế cái khác
          </Link>
        </section>
      )}

      {refusal && (
        <div className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-5">
          <p className="font-medium">{refusal.message}</p>
          {refusal.suggestions.length > 0 && (
            <>
              <p className="text-sm text-muted">Thử một chủ đề vui hơn:</p>
              <div className="flex flex-wrap gap-2">
                {refusal.suggestions.map((s) => (
                  <Link key={s} href={`/?topic=${encodeURIComponent(s)}`} className="min-h-10 rounded-xl bg-sand px-4 py-2 text-sm">
                    {s}
                  </Link>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {error && (
        <div className="flex flex-col gap-3 rounded-2xl bg-clay-tint p-5 text-clay-dark">
          <p>{error}</p>
          <Link href="/" className="font-medium underline">
            Về trang chủ
          </Link>
        </div>
      )}
    </div>
  );
}

function StepIcon({ done }: { done: boolean }) {
  return done ? (
    <svg width="20" height="20" viewBox="0 0 22 22" className="mt-0.5 shrink-0" aria-hidden="true">
      <circle cx="11" cy="11" r="10" fill="#D97757" />
      <path d="M6.5 11.5l3 3 6-6.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg width="20" height="20" viewBox="0 0 22 22" className="mt-0.5 shrink-0 animate-spin" aria-hidden="true">
      <circle cx="11" cy="11" r="9" fill="none" stroke="#E8C3B2" strokeWidth="2.5" />
      <path d="M11 2a9 9 0 0 1 9 9" fill="none" stroke="#D97757" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
