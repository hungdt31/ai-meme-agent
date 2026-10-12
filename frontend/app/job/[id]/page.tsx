import type { Metadata } from "next";
import { JobView } from "@/components/JobView";

export const metadata: Metadata = { title: "Đang chế", robots: { index: false } };

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobView jobId={id} />;
}
