import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

# ---------- Output có cấu trúc của Gemini ----------


class MemeIntent(BaseModel):
    gist: str = Field(description="Ý chính của tình huống, 1 câu ngắn tiếng Việt")
    tone: str = Field(description="Giọng điệu: mỉa mai, tự giễu, dễ thương, cà khịa nhẹ...")
    language: Literal["vi", "en", "mix"] = "vi"
    search_query: str = Field(description="Mô tả KIỂU tình huống chung chung để tìm template, không chứa tên riêng")
    safe: bool
    unsafe_reason: str | None = None


class ImageDescription(BaseModel):
    scene: str = Field(description="Ảnh có gì: người/vật, hành động, bối cảnh")
    mood: str = Field(description="Biểu cảm, cảm xúc toát ra")
    has_faces: bool
    text_layout: Literal["top_bottom", "top_only", "bottom_only"] = Field(
        description="Chỗ trống để đặt chữ mà không che mặt hay chi tiết chính"
    )
    safe: bool
    unsafe_reason: str | None = None


class TemplateChoice(BaseModel):
    template_ids: list[str] = Field(description="Id template theo thứ tự phù hợp giảm dần")


class BoxText(BaseModel):
    box_id: str
    text: str


class CaptionOption(BaseModel):
    template_id: str
    texts: list[BoxText]


class CaptionBatch(BaseModel):
    options: list[CaptionOption]


class ImageScore(BaseModel):
    index: int
    readable: int = Field(ge=1, le=5, description="Chữ đọc được, không tràn/che/cắt, đúng dấu")
    fit: int = Field(ge=1, le=5, description="Caption hợp với hình và cách dùng template")
    funny: int = Field(ge=1, le=5, description="Mức buồn cười hoặc đồng cảm với dân mạng Việt")
    safe: int = Field(ge=1, le=5, description="5 = hoàn toàn an toàn")
    feedback: str = Field(description="Một câu góp ý cụ thể để viết lại")


class CritiqueBatch(BaseModel):
    scores: list[ImageScore]


class BaselineMeme(BaseModel):
    template_id: str
    texts: list[BoxText]


# ---------- State của graph ----------


class Candidate(BaseModel):
    id: str
    round: int
    template_id: str | None  # None = ảnh người dùng tải lên
    captions: dict[str, str]
    image_key: str | None = None
    overflow: bool = False
    scores: dict[str, int] | None = None
    feedback: str | None = None
    kept: bool = False

    def total(self) -> int:
        s = self.scores or {}
        return s.get("readable", 0) + s.get("fit", 0) + 2 * s.get("funny", 0)


class MemeState(TypedDict, total=False):
    job_id: str
    topic: str
    style: str | None
    upload_key: str | None
    forced_template: str | None
    intent: MemeIntent | None
    image_desc: ImageDescription | None
    template_ids: list[str]
    candidates: list[Candidate]
    round: int
    winners: list[Candidate]
    refusal: str | None
    suggestions: list[str]
    decision: str  # done | rewrite, do node select quyết định
    llm_calls: Annotated[int, operator.add]
