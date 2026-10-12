import { CreateForm } from "@/components/CreateForm";

export default async function Home({ searchParams }: { searchParams: Promise<{ topic?: string }> }) {
  const { topic } = await searchParams;
  return (
    <div className="flex flex-col gap-6 pt-4">
      <section className="flex flex-col gap-2">
        <h1 className="font-serif text-4xl leading-tight font-normal tracking-tight">
          Kể tình huống,
          <br />
          nhận 3 meme.
        </h1>
        <p className="text-[15px] leading-relaxed text-muted">
          Agent tự chọn ảnh, viết chữ và tự chấm, chỉ đưa bạn những cái đọc được và đủ hài.
        </p>
      </section>
      <CreateForm initialTopic={topic ?? ""} />
    </div>
  );
}
