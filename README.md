# Easy Meme

Web app tạo meme tiếng Việt bằng AI agent. Kể tạomột tình huống (hoặc tải ảnh lên), agent chọn template, viết caption, dùng code vẽ chữ lên ảnh, rồi tự chấm bằng Gemini để lọc ra 3 meme đọc được và đủ hài. Mỗi meme có link riêng hiện ảnh xem trước khi dán vào Messenger, Zalo.

- **Agent:** LangGraph, 8 node, vòng tự chấm và viết lại tối đa 2 vòng
- **LLM:** Gemini (viết, xem ảnh, embedding) qua `langchain-google-genai`
- **RAG:** chọn template bằng hybrid search (vector + BM25, gộp bằng Reciprocal Rank Fusion)
- **Backend:** FastAPI + SSE, Pillow, SQLAlchemy (SQLite local / Postgres khi deploy)
- **Frontend:** Next.js 16, Tailwind CSS 4

```
upload/chủ đề → understand ─┬─ không an toàn → refuse
                            ├─ có ảnh → describe_image ─┐
                            └─ pick_templates (RAG) ────┴→ write_captions → render (Pillow) → critique → select
                                                              ↑                                            │
                                                              └────────── chưa đủ 3 ảnh, vòng < 2 ─────────┘
```

## Cấu trúc

```
chememe/
├── backend/
│   ├── agent/      graph.py, nodes.py, state.py, prompts.py, llm.py (Gemini + FakeLLM)
│   ├── rag/        search.py: hybrid search chọn template
│   ├── render/     renderer.py (đặt chữ, đo tràn), templates.py, fonts/ (Anton, Be Vietnam Pro, giấy phép OFL)
│   ├── app/        main.py, api.py, service.py, db.py, storage.py (local / Cloudflare R2), security.py
│   ├── data/templates/   JSON + ảnh template
│   ├── scripts/    make_templates.py, index_templates.py
│   ├── evals/      run_eval.py + bộ dữ liệu
│   └── tests/
├── frontend/       app/ (/, /job/[id], /m/[id], /feed, /p/[id], /me, /u/[username], /about), components/, lib/api.ts
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Chạy local

Không có Gemini key vẫn chạy được: backend tự dùng **FakeLLM** (kết quả cố định, chỉ để thử giao diện và luồng).

```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # điền GOOGLE_API_KEY nếu có
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (terminal khác)
cd frontend
npm install
cp .env.example .env.local
npm run dev                      # http://localhost:3000
```

Khi đã có key, tạo embedding cho template một lần để bật tìm kiếm vector:

```bash
cd backend && .venv/bin/python -m scripts.index_templates
```

Muốn chạy với Postgres giống môi trường thật: `docker compose up` (backend ở cổng 8000).

## Đăng nhập Google

Khách chưa đăng nhập vẫn tạo được meme (5 lượt mỗi 24 giờ, đếm theo IP). Đăng nhập được 20 lượt, trang **Meme của tôi**, hồ sơ công khai `/u/<username>`, và chia sẻ meme lên cộng đồng.

1. Vào Google Cloud Console → **APIs & Services → Credentials → Create credentials → OAuth client ID**, loại **Web application**. Lần đầu sẽ phải cấu hình OAuth consent screen (chọn External, điền tên app và email).
2. Ở **Authorized JavaScript origins**, thêm `http://localhost`, `http://localhost:3000` và domain Vercel khi deploy. Không cần redirect URI.
3. Copy Client ID vào `GOOGLE_CLIENT_ID` (backend `.env`) và `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (frontend `.env.local`). Hai biến phải giống nhau.

Cách hoạt động: frontend lấy ID token bằng Google Identity Services, backend xác thực token với Google rồi cấp token phiên riêng (lưu dạng hash trong bảng `sessions`, hạn 30 ngày). Token gửi qua header `Authorization: Bearer`, không dùng cookie vì frontend và backend khác domain.

**Bảng dữ liệu:** `users` (google_sub, email riêng tư, tên hiển thị, username, profile_public), `sessions`, cùng cột `user_id` trong `jobs`, `memes`.

**Database tạo từ phiên bản trước** (chưa có bảng người dùng): backend báo lỗi `Database thiếu cột …` khi khởi động, vì `create_all` không thêm cột vào bảng đã có. Xoá các bảng `jobs`, `memes`, `votes` cũ (hoặc tạo database hay branch mới trên Neon), backend sẽ tự tạo lại đủ bảng.

## Test và lint

```bash
cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd frontend && npm run typecheck && npm run build
```

Test luôn chạy FakeLLM nên không tốn quota. CI chạy đúng các lệnh trên.

## Thêm template

1. Đặt ảnh vào `backend/data/templates/images/`.
2. Viết `backend/data/templates/<id>.json` theo mẫu có sẵn. Toạ độ khung chữ `x, y, w, h` tính theo tỉ lệ 0–1 của ảnh. `when_to_use` và `examples` quyết định template được tìm thấy khi nào, nên viết cụ thể.
3. Chạy `python -m scripts.index_templates` (cần key) để cập nhật embedding.

6 template khởi đầu do `scripts/make_templates.py` tự vẽ, nên không dính bản quyền. Nếu dùng template meme phổ biến, hãy ghi nguồn vào trường `source` và giữ app phi lợi nhuận.

## Cộng đồng

Người dùng đã đăng nhập chia sẻ meme của mình lên bảng tin `/feed` kèm caption tuỳ chọn. Mọi người thả tim và bình luận ở trang bài viết `/p/[id]` (link này có ảnh xem trước khi dán vào chat). Bảng tin có hai tab: Mới nhất và Nổi bật (tương tác chia theo tuổi bài, trong 7 ngày). Người đăng sửa caption hoặc xoá bài; chủ bài xoá được mọi bình luận trong bài; bài bị báo cáo 3 lần tự ẩn.

Dữ liệu: bảng `posts`, `post_likes`, `comments` (tự tạo khi backend khởi động).

## Eval

```bash
python -m evals.run_eval templates           # recall@3: keyword vs vector vs hybrid
python -m evals.run_eval safety              # tỷ lệ chặn 20 prompt tấn công, tỷ lệ chặn nhầm 20 chủ đề vô hại
python -m evals.run_eval quality --limit 10  # tỷ lệ tràn chữ, số lần gọi Gemini, độ trễ
```

## Deploy

**Backend → Google Cloud Run**

```bash
cd backend
gcloud run deploy chememe-api --source . --region asia-southeast1 --allow-unauthenticated \
  --memory 1Gi --timeout 300 --min-instances 0 --max-instances 3 \
  --set-secrets GOOGLE_API_KEY=gemini-key:latest,DATABASE_URL=database-url:latest,R2_SECRET_ACCESS_KEY=r2-secret:latest,IP_HASH_SALT=ip-salt:latest \
  --set-env-vars STORAGE_BACKEND=r2,R2_ACCOUNT_ID=...,R2_ACCESS_KEY_ID=...,R2_BUCKET=chememe,R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev,ALLOWED_ORIGINS=https://<frontend>.vercel.app,PUBLIC_BASE_URL=https://<url-cloud-run>
```

- **Database:** Postgres trên Neon (region Singapore). Bảng tự tạo khi backend khởi động.
- **Ảnh:** Cloudflare R2, bật public access cho bucket. Đặt lifecycle rule xoá `uploads/` và `drafts/` sau 1 ngày.
- **Frontend → Vercel:** import repo, chọn Root Directory = `frontend`, đặt `NEXT_PUBLIC_API_URL` (URL Cloud Run) và `NEXT_PUBLIC_SITE_URL` (domain Vercel).
- Nên đặt budget alert trên Google Cloud. `--max-instances 3` cùng giới hạn 20 job/IP/ngày giúp chặn chi phí khi bị spam.

## Khác với spec v0.1

| Spec | Bản này | Lý do |
| --- | --- | --- |
| pgvector trên Neon | Vector lưu trong `data/template_index.json`, tính cosine trong bộ nhớ | Vài chục đến vài trăm template thì tính trong bộ nhớ mất dưới 1 ms và đỡ một phụ thuộc. Vượt vài nghìn template mới cần pgvector. |
| Tài khoản người dùng: ngoài phạm vi v0.1 | Có đăng nhập Google, lịch sử, hồ sơ, quota theo tài khoản | Bổ sung theo yêu cầu sau spec. |
| Checkpointer Postgres | Không dùng | Graph chạy một mạch trong một request, không có `interrupt`, nên không cần lưu trạng thái giữa chừng. |
| 60 template | 6 template tự vẽ | Đủ để chạy thử; thêm template theo hướng dẫn ở trên. |
| Safety settings của Gemini | Kiểm tra an toàn bằng prompt ở bước `understand` và điểm `safe` ở bước `critique` | Tránh phụ thuộc vào API safety settings hay thay đổi giữa các phiên bản thư viện. |
| ESLint | Chỉ `tsc` + `next build` | Next 16 bỏ `next lint`; thêm ESLint sau nếu cần. |

**Giới hạn đã biết:**
- Lượt tạo đếm trong database nên đúng với mọi instance. Các giới hạn phụ (upload, sửa chữ, bầu chọn) vẫn dùng `slowapi` lưu trong bộ nhớ từng instance.
- Token phiên lưu trong `localStorage` của trình duyệt: tiện nhưng nếu trang dính lỗi XSS thì token có thể bị đọc.
- Không có migration tự động: thêm cột mới vào bảng đã có thì phải tự `ALTER TABLE` hoặc tạo lại bảng.
- Ảnh tải lên chỉ được bảo vệ bằng key ngẫu nhiên khó đoán, không phải bucket riêng tư.
