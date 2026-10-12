import type { Metadata } from "next";
import { MyAccount } from "@/components/MyAccount";

export const metadata: Metadata = { title: "Tài khoản của tôi", robots: { index: false } };

export default function MePage() {
  return <MyAccount />;
}
