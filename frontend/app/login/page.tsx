import type { Metadata } from "next";
import { LoginPanel } from "@/components/LoginPanel";

export const metadata: Metadata = { title: "Đăng nhập", robots: { index: false } };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  // Chỉ cho chuyển hướng nội bộ, tránh open redirect
  const target = next?.startsWith("/") && !next.startsWith("//") ? next : "/me";
  return <LoginPanel next={target} />;
}
