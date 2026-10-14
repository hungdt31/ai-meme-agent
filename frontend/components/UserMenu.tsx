"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Avatar } from "@/components/Avatar";

export function UserMenu() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => setOpen(false), [pathname]); // chuyển trang thì đóng menu

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (loading) return <span className="size-11" aria-hidden="true" />;

  if (!user) {
    return (
      <Link href="/login" className="flex min-h-11 items-center rounded-full bg-ink px-4 text-sm font-medium text-white">
        Đăng nhập
      </Link>
    );
  }

  async function signOut() {
    setOpen(false);
    await logout();
    router.push("/");
  }

  const item = "flex min-h-11 w-full items-center gap-3 px-4 text-left text-[15px] text-body hover:bg-sand";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Mở menu tài khoản"
        className="flex min-h-11 items-center rounded-full"
      >
        <Avatar name={user.display_name} url={user.avatar_url} size={40} />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-2xl border border-line bg-white py-1 shadow-lg">
          <div className="border-b border-line px-4 py-2.5">
            <p className="truncate text-sm font-semibold text-ink">{user.display_name}</p>
            <p className="truncate text-xs text-muted">@{user.username}</p>
          </div>
          <Link href="/me" role="menuitem" className={item}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21a8 8 0 0 1 16 0" />
            </svg>
            Hồ sơ
          </Link>
          <Link href="/feed" role="menuitem" className={item}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            Cộng đồng
          </Link>
          <button type="button" role="menuitem" onClick={signOut} className={`${item} border-t border-line text-clay-dark`}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <path d="M16 17l5-5-5-5" />
              <path d="M21 12H9" />
            </svg>
            Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}
