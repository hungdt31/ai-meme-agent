"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Meme } from "@/lib/api";

const DEBOUNCE_MS = 500;

export function CaptionEditor({ meme, onChange, onDone }: { meme: Meme; onChange: (m: Meme) => void; onDone: () => void }) {
  const original = useRef(meme.captions);
  const [captions, setCaptions] = useState(meme.captions);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "overflow" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const memeId = useRef(meme.id);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setStatus("saving");
    const timer = setTimeout(async () => {
      try {
        const next = await api.rerender(memeId.current, captions);
        memeId.current = next.id;
        onChange(next);
        setStatus(next.overflow ? "overflow" : "saved");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Không vẽ lại được");
        setStatus("error");
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [captions, onChange]);

  return (
    <div className="flex flex-col gap-3">
      {meme.boxes.map((box, i) => {
        const value = captions[box.id] ?? "";
        const multiline = value.includes("\n") || box.max_chars > 50;
        const id = `cap-${meme.id}-${box.id}`;
        return (
          <div key={box.id} className="flex flex-col gap-1">
            <label htmlFor={id} className="flex justify-between text-sm font-medium text-body">
              <span>{box.hint ? `Khung ${i + 1}: ${box.hint}` : `Khung ${i + 1}`}</span>
              <span className={`font-normal ${value.length > box.max_chars ? "text-clay-dark" : "text-faint"}`}>
                {value.length} / {box.max_chars}
              </span>
            </label>
            {multiline ? (
              <textarea
                id={id}
                rows={2}
                value={value}
                onChange={(e) => setCaptions({ ...captions, [box.id]: e.target.value })}
                className={`resize-none rounded-xl border bg-white px-3.5 py-2.5 text-base ${status === "overflow" ? "border-clay" : "border-line-strong"}`}
              />
            ) : (
              <input
                id={id}
                value={value}
                onChange={(e) => setCaptions({ ...captions, [box.id]: e.target.value })}
                className={`min-h-12 rounded-xl border bg-white px-3.5 text-base ${status === "overflow" ? "border-clay" : "border-line-strong"}`}
              />
            )}
          </div>
        );
      })}

      <p className="text-sm text-muted" aria-live="polite">
        {status === "saving" && "Đang vẽ lại…"}
        {status === "saved" && "Đã cập nhật · không tốn lượt chế"}
        {status === "overflow" && "Chữ dài quá khung, rút gọn một chút nhé"}
        {status === "error" && error}
        {status === "idle" && "Ảnh vẽ lại ngay khi bạn gõ, không tốn lượt chế"}
      </p>

      <div className="grid grid-cols-2 gap-2">
        <button type="button" onClick={() => setCaptions(original.current)} className="min-h-12 rounded-2xl text-[15px] text-muted">
          Khôi phục chữ của agent
        </button>
        <button type="button" onClick={onDone} className="min-h-12 rounded-2xl bg-clay-dark text-[15px] font-semibold text-white">
          Xong
        </button>
      </div>
    </div>
  );
}
