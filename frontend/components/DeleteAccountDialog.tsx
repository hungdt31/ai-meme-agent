"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

const CONFIRM_WORD = "delete";

/** Hộp thoại xác nhận xoá tài khoản: phải gõ đúng "delete" mới bấm được nút xoá. */
export function DeleteAccountDialog({ open, onClose, onConfirm }: { open: boolean; onClose: () => void; onConfirm: () => Promise<void> }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setText("");
      setError(null);
      dialog.showModal(); // modal thật: khoá nền, Esc để đóng, focus nằm trong hộp thoại
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const matches = text.trim() === CONFIRM_WORD;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!matches || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không xoá được tài khoản, thử lại nhé");
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && !busy && onClose()} // bấm ra ngoài hộp để đóng
      aria-labelledby="delete-account-title"
      className="m-auto w-[min(92vw,420px)] rounded-3xl border border-line bg-white p-0 text-ink shadow-2xl backdrop:bg-ink/50"
    >
      <form onSubmit={submit} className="flex flex-col gap-4 p-6">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-clay-tint text-clay-dark" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3l9.5 17h-19z" />
              <path d="M12 10v4" />
              <path d="M12 17.5v.5" />
            </svg>
          </span>
          <div className="flex flex-col gap-1">
            <h2 id="delete-account-title" className="font-serif text-xl">
              Xoá tài khoản?
            </h2>
            <p className="text-sm leading-relaxed text-muted">
              Toàn bộ meme, bài đăng, lượt tim và bình luận của bạn sẽ bị xoá vĩnh viễn và không khôi phục được.
            </p>
          </div>
        </div>

        <label htmlFor="delete-confirm" className="flex flex-col gap-1.5 text-sm text-body">
          <span>
            Gõ <strong className="font-mono text-clay-dark">{CONFIRM_WORD}</strong> để xác nhận
          </span>
          <input
            id="delete-confirm"
            value={text}
            onChange={(e) => setText(e.target.value)}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            placeholder={CONFIRM_WORD}
            className="min-h-12 rounded-xl border border-line-strong bg-white px-3.5 font-mono text-base"
          />
        </label>

        {error && <p className="text-sm text-clay-dark">{error}</p>}

        <div className="grid grid-cols-2 gap-2">
          <button type="button" onClick={onClose} disabled={busy} className="min-h-12 rounded-2xl border border-line-strong bg-white text-[15px]">
            Huỷ
          </button>
          <button
            type="submit"
            disabled={!matches || busy}
            className="min-h-12 rounded-2xl bg-[#C2392B] text-[15px] font-semibold text-white disabled:opacity-40"
          >
            {busy ? "Đang xoá…" : "Xoá vĩnh viễn"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
