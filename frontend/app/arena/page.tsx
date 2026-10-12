import type { Metadata } from "next";
import { Arena } from "@/components/Arena";

export const metadata: Metadata = { title: "Đấu trường" };

export default function ArenaPage() {
  return <Arena />;
}
