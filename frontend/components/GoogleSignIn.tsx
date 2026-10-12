"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { ApiError, GOOGLE_CLIENT_ID } from "@/lib/api";

type GoogleId = {
  initialize: (config: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: "popup" }) => void;
  renderButton: (el: HTMLElement, options: Record<string, string | number>) => void;
};

declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";

function loadGsi(): Promise<GoogleId> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve(window.google.accounts.id);
    let script = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    if (!script) {
      script = document.createElement("script");
      script.src = GSI_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
    script.addEventListener("load", () => (window.google ? resolve(window.google.accounts.id) : reject()));
    script.addEventListener("error", () => reject());
  });
}

/** Nút "Đăng nhập với Google" chính thức (Google Identity Services). */
export function GoogleSignIn({ onSignedIn }: { onSignedIn?: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const { loginWithGoogle } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const onDone = useRef(onSignedIn);
  onDone.current = onSignedIn;

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    loadGsi()
      .then((gsi) => {
        if (cancelled || !ref.current) return;
        gsi.initialize({
          client_id: GOOGLE_CLIENT_ID,
          ux_mode: "popup",
          callback: async ({ credential }) => {
            setError(null);
            try {
              await loginWithGoogle(credential);
              onDone.current?.();
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Không đăng nhập được, thử lại nhé");
            }
          },
        });
        gsi.renderButton(ref.current, { theme: "outline", size: "large", shape: "pill", text: "signin_with", locale: "vi", width: 280 });
      })
      .catch(() => setError("Không tải được nút đăng nhập Google (bị chặn hoặc mất mạng)"));
    return () => {
      cancelled = true;
    };
  }, [loginWithGoogle]);

  if (!GOOGLE_CLIENT_ID) {
    return <p className="text-sm text-muted">Đăng nhập chưa được cấu hình (thiếu NEXT_PUBLIC_GOOGLE_CLIENT_ID).</p>;
  }
  return (
    <div className="flex flex-col items-center gap-2">
      <div ref={ref} className="min-h-11" />
      {error && <p className="text-sm text-clay-dark">{error}</p>}
    </div>
  );
}
