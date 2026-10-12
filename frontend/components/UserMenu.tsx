"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { Avatar } from "@/components/Avatar";

export function UserMenu() {
  const { user, loading } = useAuth();
  return (
    <nav className="flex items-center gap-2 text-sm">
      <Link href="/arena" className="flex min-h-11 items-center rounded-full border border-line-strong bg-white px-4 text-body">
        Đấu trường
      </Link>
      {loading ? (
        <span className="size-11" aria-hidden="true" />
      ) : user ? (
        <Link href="/me" aria-label="Tài khoản của tôi" className="flex min-h-11 items-center">
          <Avatar name={user.display_name} url={user.avatar_url} size={40} />
        </Link>
      ) : (
        <Link href="/login" className="flex min-h-11 items-center rounded-full bg-ink px-4 font-medium text-white">
          Đăng nhập
        </Link>
      )}
    </nav>
  );
}
