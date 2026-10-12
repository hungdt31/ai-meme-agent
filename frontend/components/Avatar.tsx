export function Avatar({ name, url, size = 32 }: { name: string; url: string | null; size?: number }) {
  if (url) {
    // Ảnh Google cần no-referrer, nếu không đôi khi bị chặn 403
    return <img src={url} alt="" width={size} height={size} referrerPolicy="no-referrer" className="shrink-0 rounded-full border border-line object-cover" style={{ width: size, height: size }} />;
  }
  return (
    <span
      aria-hidden="true"
      className="flex shrink-0 items-center justify-center rounded-full bg-clay-tint font-semibold text-clay-dark"
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}
