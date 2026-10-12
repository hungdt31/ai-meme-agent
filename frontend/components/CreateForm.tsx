"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError, STYLES, type Quota, type Style, type TemplateItem } from "@/lib/api";

type Tab = "topic" | "upload" | "template";

const TABS: { id: Tab; label: string }[] = [
  { id: "topic", label: "Chủ đề" },
  { id: "upload", label: "Ảnh của bạn" },
  { id: "template", label: "Template" },
];

const QUICK = ["Sáng thứ 2 đầu tuần", "Nhóm chat chỉ seen", "Crush rep đúng một chữ “ok”", "Lương về 3 ngày đã hết"];
const MAX_TOPIC = 300;

export function CreateForm({ initialTopic = "" }: { initialTopic?: string }) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("topic");
  const [topic, setTopic] = useState(initialTopic.slice(0, MAX_TOPIC));
  const [style, setStyle] = useState<Style | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [quota, setQuota] = useState<(Quota & { signed_in: boolean }) | null>(null);
  const { user, loading: authLoading } = useAuth();

  useEffect(() => {
    if (authLoading) return;
    api.quota().then(setQuota).catch(() => setQuota(null));
  }, [authLoading, user?.id]);

  useEffect(() => {
    if (tab === "template" && templates.length === 0) {
      api.templates().then(setTemplates).catch(() => setError({ code: "error", message: "Không tải được danh sách template" }));
    }
  }, [tab, templates.length]);

  const canSubmit =
    !busy &&
    ((tab === "topic" && topic.trim()) || (tab === "upload" && file && consent) || (tab === "template" && templateId && topic.trim()));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      let upload_id: string | undefined;
      if (tab === "upload" && file) upload_id = (await api.upload(file)).upload_id;
      const { job_id } = await api.createJob({
        topic: topic.trim() || undefined,
        style: style ?? undefined,
        upload_id,
        consent: tab === "upload" ? consent : undefined,
        template_id: tab === "template" ? (templateId ?? undefined) : undefined,
      });
      router.push(`/job/${job_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? { code: err.code, message: err.message } : { code: "error", message: "Không kết nối được máy chủ" });
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div role="tablist" className="grid grid-cols-3 gap-1 rounded-2xl bg-sand p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`min-h-11 rounded-xl text-sm ${tab === t.id ? "bg-white font-semibold text-ink shadow-sm" : "text-muted"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "upload" && (
        <div className="flex flex-col gap-3 rounded-2xl border border-line-strong bg-white p-4">
          <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-line-strong bg-ivory text-sm text-muted">
            <span className="font-medium text-ink">{file ? file.name : "Chọn ảnh (JPG, PNG, WebP, tối đa 5 MB)"}</span>
            <span>Ảnh được xoá thông tin vị trí và tự xoá sau 24 giờ</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label className="flex items-start gap-2 text-sm text-body">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 size-4 accent-clay-dark" />
            Tôi có quyền dùng ảnh này và người trong ảnh đồng ý.
          </label>
        </div>
      )}

      {tab === "template" && (
        <div className="grid grid-cols-3 gap-2">
          {templates.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTemplateId(t.id)}
              aria-pressed={templateId === t.id}
              className={`flex flex-col gap-1 rounded-xl border-2 bg-white p-1 text-left text-xs ${templateId === t.id ? "border-clay" : "border-transparent"}`}
            >
              <img src={t.thumb_url} alt="" className="aspect-square w-full rounded-lg object-cover" />
              <span className="px-1 pb-1 font-medium">{t.name}</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-1.5 rounded-2xl border border-line-strong bg-white p-4 shadow-[0_4px_18px_rgba(20,20,19,0.05)]">
        <label htmlFor="topic" className="text-sm text-muted">
          {tab === "upload" ? "Ý bạn muốn nói (tuỳ chọn)" : "Tình huống của bạn"}
        </label>
        <textarea
          id="topic"
          rows={3}
          maxLength={MAX_TOPIC}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Ví dụ: deadline thứ 6 mà sếp giao thêm việc chiều thứ 5"
          className="resize-none bg-transparent text-[17px] leading-normal outline-none placeholder:text-faint"
        />
        <div className="text-right text-xs text-faint">
          {topic.length} / {MAX_TOPIC}
        </div>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm text-muted">Phong cách</legend>
        <div className="flex flex-wrap gap-2">
          {STYLES.map((s) => (
            <button
              key={s.id}
              type="button"
              aria-pressed={style === s.id}
              onClick={() => setStyle(style === s.id ? null : s.id)}
              className={`min-h-10 rounded-full border px-4 text-sm ${style === s.id ? "border-ink bg-ink text-white" : "border-line-strong bg-white text-body"}`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </fieldset>

      {error && (
        <p className="rounded-xl bg-clay-tint px-4 py-3 text-sm text-clay-dark">
          {error.message}
          {error.code === "quota_exceeded" && !user && (
            <>
              {" "}
              <Link href="/login?next=/" className="font-semibold underline">
                Đăng nhập
              </Link>
            </>
          )}
        </p>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="flex min-h-14 items-center justify-center rounded-2xl bg-clay-dark text-[17px] font-semibold text-white disabled:opacity-50"
      >
        {busy ? "Đang gửi…" : "Chế meme"}
      </button>
      {quota && (
        <p className="-mt-2 text-center text-sm text-muted">
          Còn {quota.left}/{quota.limit} lượt trong 24 giờ
          {!quota.signed_in && (
            <>
              {" · "}
              <Link href="/login?next=/" className="underline">
                Đăng nhập để có thêm lượt
              </Link>
            </>
          )}
        </p>
      )}

      {tab === "topic" && (
        <div className="flex flex-col gap-2">
          <span className="text-sm text-muted">Thử nhanh</span>
          <div className="flex flex-wrap gap-2">
            {QUICK.map((q) => (
              <button key={q} type="button" onClick={() => setTopic(q)} className="min-h-10 rounded-xl bg-sand px-4 text-sm text-body">
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </form>
  );
}
