"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { GoogleSignIn } from "@/components/GoogleSignIn";

const PERKS = [
  "20 lượt tạo mỗi ngày thay vì 5",
  "Lưu lại mọi meme đã tạo, xoá được meme của mình",
  "Trang hồ sơ riêng để khoe meme với bạn bè",
  "Chia sẻ meme lên cộng đồng, thả tim và bình luận",
];

export function LoginPanel({ next }: { next: string }) {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [user, loading, next, router]);

  return (
    <div className="flex flex-col gap-6 pt-6">
      <h1 className="font-serif text-3xl font-normal">Đăng nhập Easy Meme</h1>
      <ul className="flex flex-col gap-2 rounded-2xl border border-line bg-white p-5 text-[15px]">
        {PERKS.map((p) => (
          <li key={p} className="flex items-start gap-2">
            <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-clay" />
            {p}
          </li>
        ))}
      </ul>
      <GoogleSignIn onSignedIn={() => router.replace(next)} />
      <p className="text-center text-xs leading-relaxed text-faint">
        Chúng tôi chỉ lưu tên, email và ảnh đại diện Google. Email không bao giờ hiện cho người khác. Bạn có thể xoá tài khoản bất cứ lúc nào.
      </p>
    </div>
  );
}
