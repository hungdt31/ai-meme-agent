from pydantic import BaseModel, Field


class GoogleLogin(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)


class UpdateMe(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    username: str | None = None
    profile_public: bool | None = None
