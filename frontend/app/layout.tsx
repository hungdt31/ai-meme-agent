import type { Metadata, Viewport } from "next";
import { Be_Vietnam_Pro, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import { AuthProvider } from "@/components/AuthProvider";
import { Logo } from "@/components/Logo";
import { UserMenu } from "@/components/UserMenu";
import { SITE_URL } from "@/lib/api";
import "./globals.css";

const sans = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-vn-sans",
});
const serif = Source_Serif_4({ subsets: ["latin", "vietnamese"], variable: "--font-vn-serif" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "ChếMeme · chế meme bằng AI", template: "%s · ChếMeme" },
  description: "Kể tình huống, nhận 3 meme tiếng Việt đã được AI tự chấm và lọc.",
};

export const viewport: Viewport = { themeColor: "#faf9f5", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className={`${sans.variable} ${serif.variable}`}>
      <body className="font-sans antialiased">
        <AuthProvider>
          <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4">
          <header className="flex items-center justify-between py-4">
            <Link href="/" className="flex min-h-11 items-center gap-2">
              <Logo />
              <span className="font-serif text-xl font-semibold tracking-tight">ChếMeme</span>
            </Link>
            <UserMenu />
          </header>
          <main className="flex-1 pb-10">{children}</main>
          <footer className="border-t border-line py-5 text-center text-xs leading-relaxed text-faint">
            Giải trí phi lợi nhuận · Không chế ảnh người khác khi chưa được đồng ý ·{" "}
            <Link href="/about" className="underline">
              Cách hoạt động
            </Link>
          </footer>
        </div>
        </AuthProvider>
      </body>
    </html>
  );
}
