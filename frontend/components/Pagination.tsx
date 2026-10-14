/** Thanh phân trang: ‹ 1 … 4 5 6 … 12 ›. Rút gọn bằng "…" khi nhiều trang. */
export function Pagination({ page, pages, onChange }: { page: number; pages: number; onChange: (page: number) => void }) {
  if (pages <= 1) return null;

  const nums: (number | "gap")[] = [];
  for (let n = 1; n <= pages; n++) {
    if (n === 1 || n === pages || Math.abs(n - page) <= 1) nums.push(n);
    else if (nums.at(-1) !== "gap") nums.push("gap");
  }

  const base = "flex min-h-11 min-w-11 items-center justify-center rounded-xl text-sm";
  return (
    <nav aria-label="Phân trang" className="flex flex-wrap items-center justify-center gap-1">
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page === 1}
        aria-label="Trang trước"
        className={`${base} text-body hover:bg-sand disabled:opacity-30 disabled:hover:bg-transparent`}
      >
        <Arrow dir="left" />
      </button>
      {nums.map((n, i) =>
        n === "gap" ? (
          <span key={`gap-${i}`} className={`${base} text-faint`} aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            aria-current={n === page ? "page" : undefined}
            aria-label={`Trang ${n}`}
            className={`${base} ${n === page ? "bg-ink font-semibold text-white" : "border border-line-strong bg-white text-body"}`}
          >
            {n}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page === pages}
        aria-label="Trang sau"
        className={`${base} text-body hover:bg-sand disabled:opacity-30 disabled:hover:bg-transparent`}
      >
        <Arrow dir="right" />
      </button>
    </nav>
  );
}

function Arrow({ dir }: { dir: "left" | "right" }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={dir === "left" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"} />
    </svg>
  );
}
