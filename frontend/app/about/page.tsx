import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Cách hoạt động" };

const STEPS = [
  ["Hiểu ý", "Gemini tóm tắt tình huống, chọn giọng điệu và kiểm tra an toàn."],
  ["Chọn template", "Tìm template theo ý nghĩa tình huống: kết hợp tìm vector (embedding) và từ khoá, rồi Gemini chọn 3."],
  ["Viết caption", "4 phương án cho mỗi template, đúng số khung và giới hạn ký tự."],
  ["Vẽ chữ", "Code Pillow đặt chữ, tự co cỡ chữ và phát hiện chữ tràn khung. Gemini không tự vẽ chữ."],
  ["Tự chấm", "Gemini xem từng ảnh đã vẽ, chấm dễ đọc, hợp template, hài, an toàn."],
  ["Lọc và viết lại", "Code giữ ảnh đạt chuẩn; thiếu thì viết lại theo nhận xét, tối đa 2 vòng."],
];

export default function About() {
  return (
    <div className="flex flex-col gap-6 pt-2">
      <h1 className="font-serif text-3xl font-normal">Cách Easy Meme hoạt động</h1>
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
        <h2 className="font-serif text-xl">Chia sẻ với cộng đồng</h2>
        <p className="text-sm leading-relaxed text-muted">
          Đăng nhập rồi tạo meme, bấm “Chia sẻ lên cộng đồng” và viết thêm vài dòng nếu muốn. Mọi người có thể thả tim và bình luận.
        </p>
        <Link href="/feed" className="text-[15px] font-semibold text-clay-dark underline">
          Xem bảng tin cộng đồng
        </Link>
      </section>
    </div>
  );
}
