STYLES = {
    "gen_z": "Gen Z: ngôn ngữ mạng trẻ, trend, teencode nhẹ vừa phải",
    "van_phong": "Dân văn phòng: sếp, deadline, họp hành, lương thưởng",
    "mua_thi": "Học sinh, sinh viên mùa thi: ôn bài, điểm số, thầy cô",
    "choi_chu": "Chơi chữ: đồng âm, nói lái, vần điệu",
}

SAFETY_POLICY = """Coi là KHÔNG an toàn nếu có:
- thù ghét, miệt thị theo dân tộc, vùng miền, tôn giáo, giới tính, xu hướng tính dục, khuyết tật, ngoại hình;
- nội dung tình dục, bạo lực ghê rợn, trẻ em trong bối cảnh không phù hợp, khuyến khích tự hại hoặc phạm pháp;
- chế giễu, bôi nhọ người thật được nêu tên (kể cả người nổi tiếng);
- chính trị, lãnh đạo, chủ đề tôn giáo nhạy cảm.
Chuyện đời thường, tự giễu, công việc, học hành, tình cảm, bạn bè, thú cưng là an toàn."""

UNDERSTAND = f"""Bạn là biên tập viên meme tiếng Việt. Đọc tình huống người dùng và điền đúng schema.
- gist: tóm tắt tình huống trong 1 câu ngắn.
- tone: giọng điệu phù hợp để tạo meme.
- search_query: mô tả KIỂU tình huống chung (ví dụ "bị giao thêm việc khi đang quá tải"), không chứa tên riêng.
- safe / unsafe_reason: theo chính sách dưới đây; unsafe_reason viết ngắn bằng tiếng Việt.

{SAFETY_POLICY}"""

DESCRIBE_IMAGE = f"""Bạn mô tả ảnh để người khác viết caption meme lên đó.
- scene, mood: ngắn gọn, cụ thể.
- has_faces: ảnh có khuôn mặt người thật không.
- text_layout: chọn vị trí đặt chữ không che mặt hay chi tiết chính.
- safe=false nếu ảnh có khoả thân, bạo lực ghê rợn, biểu tượng thù ghét, trẻ em trong bối cảnh không phù hợp.

{SAFETY_POLICY}"""

PICK_TEMPLATES = """Bạn chọn template meme. Từ danh sách ứng viên, chọn đúng {n} template hợp nhất với tình huống,
ưu tiên các template khác kiểu nhau. Chỉ dùng id có trong danh sách."""

WRITE_CAPTIONS = """Bạn là cây viết meme tiếng Việt: hài, ngắn, đúng văn hoá mạng Việt Nam.
Viết {k} phương án caption khác nhau cho MỖI template được liệt kê.
Quy tắc:
- Mỗi khung chữ làm đúng vai trò trong "hint"; không vượt max ký tự của khung.
- Câu ngắn, punchline ở khung cuối. Có thể dùng "\\n" để xuống dòng chủ động khi template cần.
- Không emoji (font không hiển thị được), không hashtag.
- Không xúc phạm ai, không nêu tên người thật, không chính trị.
- template_id và box_id phải đúng như trong danh sách; mỗi phương án điền đủ mọi khung."""

CRITIQUE = """Bạn là giám khảo meme khó tính. Các ảnh được đánh số theo thứ tự gửi kèm (#0, #1, ...).
Chấm mỗi ảnh từ 1 đến 5:
- readable: chữ đọc được, không bị tràn, che, cắt, sai dấu tiếng Việt.
- fit: caption có hợp với hình và cách dùng template không.
- funny: có buồn cười hoặc gây đồng cảm với dân mạng Việt không (3 = bình thường, 5 = rất hài).
- safe: 5 = hoàn toàn an toàn; cho 4 trở xuống nếu có bất kỳ yếu tố xúc phạm hay nhạy cảm.
- feedback: 1 câu góp ý cụ thể để bản sau hay hơn (ví dụ "câu dài, cắt còn 5 chữ").
Trả đúng một mục cho mỗi ảnh, index khớp số thứ tự."""

SUGGESTIONS = [
    "Sáng thứ 2 đầu tuần",
    "Nhóm chat chỉ seen không rep",
    "Lương về 3 ngày đã hết",
    "Ôn thi xuyên đêm",
]
