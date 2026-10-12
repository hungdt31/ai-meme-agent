"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError } from "@/lib/api";

type Pair = Awaited<ReturnType<typeof api.arenaPair>>;
const COUNT_KEY = "chememe.votes";

function readCount(): number {
  try {
    return Number(localStorage.getItem(COUNT_KEY) ?? 0) || 0;
  } catch {
    return 0;
  }
}

export function Arena() {
  const [pair, setPair] = useState<Pair | null>(null);
  const [voted, setVoted] = useState<"a" | "b" | "tie" | null>(null);
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();

  const next = useCallback(async () => {
    setVoted(null);
    setError(null);
    try {
      setPair(await api.arenaPair());
    } catch (err) {
      setPair(null);
      if (err instanceof ApiError && err.code === "no_pairs") setError("Đấu trường chưa có cặp meme nào, quay lại sau nhé.");
      else setError(err instanceof ApiError ? err.message : "Không tải được cặp meme");
    }
  }, []);

  useEffect(() => {
    setCount(readCount());
    next();
  }, [next, user?.id]);

  // Đã đăng nhập: lấy số phiếu từ máy chủ thay vì bộ đếm trên trình duyệt
  useEffect(() => {
    if (user) setCount(user.stats.votes);
  }, [user]);

  async function vote(winner: "a" | "b" | "tie") {
    if (!pair || voted) return;
    setVoted(winner);
    await api.vote(pair.pair_token, winner).catch(() => undefined);
    const n = count + 1;
    setCount(n);
    try {
      localStorage.setItem(COUNT_KEY, String(n));
    } catch {
      // trình duyệt chặn lưu trữ: chỉ mất bộ đếm
    }
  }

  return (
    <div className="flex flex-col gap-4 pt-2">
      <div className="flex items-baseline justify-between">
        <h1 className="font-serif text-3xl font-normal">Cái nào hài hơn?</h1>
        <span className="rounded-full bg-sand px-3 py-1 text-sm text-body">Đã bầu: {count}</span>
      </div>
      {pair && (
        <p className="text-sm leading-relaxed text-muted">
          Chủ đề: “{pair.topic}”. Bạn sẽ không biết cái nào do agent tạo, đó là chủ ý.
        </p>
      )}
      {error && <p className="rounded-2xl border border-line bg-white p-5 text-muted">{error}</p>}
      {!user && (
        <p className="text-xs text-faint">
          <Link href="/login?next=/arena" className="underline">
            Đăng nhập
          </Link>{" "}
          để không gặp lại cặp đã bầu và xem thống kê phiếu của bạn.
        </p>
      )}

      {pair &&
        (["a", "b"] as const).map((side) => (
          <article
            key={pair[side].id}
            className={`overflow-hidden rounded-3xl border-2 bg-white ${voted === side ? "border-clay" : "border-line"}`}
          >
            <div className="relative">
              <img src={pair[side].image_url} alt={`Meme ${side.toUpperCase()}`} className="block w-full" />
              <span className="absolute top-3 left-3 flex size-8 items-center justify-center rounded-full bg-ink text-sm font-bold text-white">
                {side.toUpperCase()}
              </span>
            </div>
            <div className="p-3">
              <button
                type="button"
                onClick={() => vote(side)}
                disabled={!!voted}
                className="min-h-12 w-full rounded-2xl bg-clay-dark text-[15px] font-semibold text-white disabled:opacity-50"
              >
                {side.toUpperCase()} hài hơn
              </button>
            </div>
          </article>
        ))}

      {pair && (
        <button
          type="button"
          onClick={() => vote("tie")}
          disabled={!!voted}
          className="min-h-12 rounded-2xl border border-line-strong bg-white text-[15px] text-body disabled:opacity-50"
        >
          Ngang nhau
        </button>
      )}

      {voted && (
        <div className="flex items-center justify-between gap-3 rounded-2xl bg-ink p-3 pl-4 text-white" aria-live="polite">
          <span className="text-sm">Đã ghi phiếu. Cảm ơn bạn!</span>
          <button type="button" onClick={next} className="min-h-11 rounded-xl bg-clay px-4 text-sm font-semibold text-ink">
            Cặp tiếp theo
          </button>
        </div>
      )}
    </div>
  );
}
