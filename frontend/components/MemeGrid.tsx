import Link from "next/link";
import type { Meme } from "@/lib/api";

export function MemeGrid({ items, onDelete }: { items: Meme[]; onDelete?: (id: string) => void }) {
  if (items.length === 0) return <p className="rounded-2xl border border-line bg-white p-5 text-sm text-muted">Chưa có meme nào.</p>;
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {items.map((m) => (
        <li key={m.id} className="flex flex-col gap-1.5">
          <Link href={`/m/${m.id}`} className="block overflow-hidden rounded-2xl border border-line bg-white">
            <img src={m.image_url} alt={Object.values(m.captions).join(" / ")} loading="lazy" className="aspect-square w-full object-cover" />
          </Link>
          <div className="flex items-start justify-between gap-2 px-1">
            <span className="line-clamp-2 text-xs leading-snug text-muted">{m.topic ?? ""}</span>
            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(m.id)}
                className="-mt-2 -mr-2 min-h-11 shrink-0 px-2 text-xs text-faint underline"
              >
                Xoá
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
