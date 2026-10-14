"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Avatar } from "@/components/Avatar";
import { DeleteAccountDialog } from "@/components/DeleteAccountDialog";
import { MemeGrid } from "@/components/MemeGrid";
import { Pagination } from "@/components/Pagination";
import { api, ApiError, type Meme } from "@/lib/api";

export function MyAccount() {
  const router = useRouter();
  const { user, loading, logout, setUser, refresh } = useAuth();
  const [memes, setMemes] = useState<Meme[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loadingMemes, setLoadingMemes] = useState(true);
  const memesRef = useRef<HTMLElement>(null);

  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login?next=/me");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name);
    setUsername(user.username);
    setIsPublic(user.profile_public);
  }, [user]);

  const userId = user?.id;
  const loadPage = useCallback(async (n: number) => {
    setLoadingMemes(true);
    try {
      const res = await api.myMemes(n);
      setMemes(res.items);
      setPage(res.page);
      setPages(res.pages);
      setTotal(res.total);
    } finally {
      setLoadingMemes(false);
    }
  }, []);

  useEffect(() => {
    if (userId) loadPage(1);
  }, [userId, loadPage]);

  if (!user) return <p className="pt-6 text-muted">Đang tải…</p>;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      setUser(await api.updateMe({ display_name: displayName, username, profile_public: isPublic }));
      setMessage({ ok: true, text: "Đã lưu" });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : "Không lưu được" });
    } finally {
      setSaving(false);
    }
  }

  function goTo(n: number) {
    loadPage(n);
    memesRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function removeMeme(id: string) {
    if (!confirm("Xoá meme này? Link chia sẻ cũng sẽ không mở được nữa.")) return;
    await api.deleteMeme(id);
    await loadPage(memes.length === 1 && page > 1 ? page - 1 : page); // tải lại để trang không bị hụt
    refresh();
  }

  async function removeAccount() {
    await api.deleteMe();
    await logout();
    router.replace("/");
  }

  return (
    <div className="flex flex-col gap-6 pt-2">
      <section className="flex items-center gap-4 rounded-2xl border border-line bg-white p-5">
        <Avatar name={user.display_name} url={user.avatar_url} size={56} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-serif text-xl">{user.display_name}</p>
          <p className="text-sm text-muted">@{user.username}</p>
          {user.profile_public && (
            <Link href={`/u/${user.username}`} className="text-sm underline">
              Xem hồ sơ công khai
            </Link>
          )}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
        <Stat value={`${user.quota.left}/${user.quota.limit}`} label="lượt còn lại" />
        <Stat value={String(user.stats.memes)} label="meme" />
        <Stat value={String(user.stats.posts)} label="bài đăng" />
        <Stat value={String(user.stats.likes)} label="lượt tim" />
      </section>

      <form onSubmit={save} className="flex flex-col gap-4 rounded-2xl border border-line bg-white p-5">
        <h2 className="font-serif text-xl">Cài đặt</h2>
        <label className="flex flex-col gap-1 text-sm font-medium text-body">
          Tên hiển thị
          <input value={displayName} maxLength={60} onChange={(e) => setDisplayName(e.target.value)} className="min-h-12 rounded-xl border border-line-strong px-3.5 text-base font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-body">
          Tên người dùng (dùng trong link hồ sơ)
          <input
            value={username}
            maxLength={20}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            className="min-h-12 rounded-xl border border-line-strong px-3.5 text-base font-normal"
          />
          <span className="font-normal text-faint">3–20 ký tự: chữ thường, số, dấu gạch dưới</span>
        </label>
        <label className="flex items-start gap-2 text-sm text-body">
          <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} className="mt-1 size-4 accent-clay-dark" />
          Hồ sơ công khai: hiện tên tôi dưới meme và cho mọi người xem trang hồ sơ
        </label>
        {message && <p className={`text-sm ${message.ok ? "text-good" : "text-clay-dark"}`}>{message.text}</p>}
        <button type="submit" disabled={saving} className="min-h-12 rounded-2xl bg-clay-dark font-semibold text-white disabled:opacity-50">
          {saving ? "Đang lưu…" : "Lưu"}
        </button>
      </form>

      <section ref={memesRef} className="flex scroll-mt-4 flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <h2 className="font-serif text-xl">Meme của tôi</h2>
          {total > 0 && (
            <span className="text-sm text-muted">
              {total} meme · trang {page}/{pages}
            </span>
          )}
        </div>
        <div className={loadingMemes && memes.length ? "opacity-50 transition-opacity" : ""}>
          {loadingMemes && !memes.length ? <p className="text-sm text-muted">Đang tải…</p> : <MemeGrid items={memes} onDelete={removeMeme} />}
        </div>
        <Pagination page={page} pages={pages} onChange={goTo} />
      </section>

      <section className="flex flex-col gap-2">
        <button
          type="button"
          onClick={async () => {
            await logout();
            router.replace("/");
          }}
          className="min-h-12 rounded-2xl border border-line-strong bg-white text-[15px]"
        >
          Đăng xuất
        </button>
        <button type="button" onClick={() => setConfirmDelete(true)} className="min-h-11 text-sm text-clay-dark underline">
          Xoá tài khoản
        </button>
        <DeleteAccountDialog open={confirmDelete} onClose={() => setConfirmDelete(false)} onConfirm={removeAccount} />
      </section>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-3">
      <div className="font-serif text-2xl">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}
