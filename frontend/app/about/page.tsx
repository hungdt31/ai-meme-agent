import type { Metadata } from "next";
import { api } from "@/lib/api";

export const metadata: Metadata = { title: "Cách hoạt động" };
export const dynamic = "force-dynamic";

const STEPS = [
  ["Hiểu ý", "Gemini tóm tắt tình huống, chọn giọng điệu và kiểm tra an toàn."],
  ["Chọn template", "Tìm template theo ý nghĩa tình huống: kết hợp tìm vector (embedding) và từ khoá, rồi Gemini chọn 3."],
  ["Viết caption", "4 phương án cho mỗi template, đúng số khung và giới hạn ký tự."],
  ["Vẽ chữ", "Code Pillow đặt chữ, tự co cỡ chữ và phát hiện chữ tràn khung. Gemini không tự vẽ chữ."],
  ["Tự chấm", "Gemini xem từng ảnh đã vẽ, chấm dễ đọc, hợp template, hài, an toàn."],
  ["Lọc và viết lại", "Code giữ ảnh đạt chuẩn; thiếu thì viết lại theo nhận xét, tối đa 2 vòng."],
];

export default async function About() {
  const stats = await api.stats().catch(() => null);
  return (
    <div className="flex flex-col gap-6 pt-2">
      <h1 className="font-serif text-3xl font-normal">Cách ChếMeme hoạt động</h1>
      <ol className="flex flex-col gap-3">
        {STEPS.map(([title, body], i) => (
          <li key={title} className="flex gap-3 rounded-2xl border border-line bg-white p-4">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-clay-tint text-sm font-semibold text-clay-dark">
              {i + 1}
            </span>
            <span>
              <span className="block font-medium">{title}</span>
              <span className="text-sm leading-relaxed text-muted">{body}</span>
            </span>
          </li>
        ))}
      </ol>

      <section className="flex flex-col gap-2 rounded-2xl border border-line bg-white p-5">
        <h2 className="font-serif text-xl">Kết quả đấu trường</h2>
        <p className="text-sm leading-relaxed text-muted">
          Mỗi chủ đề có một meme của agent và một meme do Gemini làm trong một lần gọi (không tự chấm). Người bầu không biết bên nào là agent.
        </p>
        {stats && stats.votes > 0 && stats.agent_win_rate !== null && stats.ci95 ? (
          <p className="text-[15px]">
            Agent thắng <strong>{Math.round(stats.agent_win_rate * 100)}%</strong> trên {stats.votes} phiếu (khoảng tin cậy 95%:{" "}
            {Math.round(stats.ci95[0] * 100)}–{Math.round(stats.ci95[1] * 100)}%).
            {stats.votes < 300 && " Chưa đủ 300 phiếu nên con số còn dao động nhiều."}
          </p>
        ) : (
          <p className="text-[15px]">Chưa có phiếu nào.</p>
        )}
      </section>
    </div>
  );
}
