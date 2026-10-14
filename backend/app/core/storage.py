"""Lưu ảnh: thư mục local khi phát triển, Cloudflare R2 (giao diện S3) khi deploy.

Quy ước key:
  uploads/<uuid>.webp      ảnh người dùng tải lên (đã xoá EXIF), không trả URL cho client
  drafts/<job>/<cand>.webp ứng viên trong lúc agent chạy
  memes/<meme_id>.webp     meme cuối cùng, public
Trên R2 nên đặt lifecycle rule xoá uploads/ và drafts/ sau 24 giờ.
"""

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "image/webp") -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def url(self, key: str) -> str: ...


class LocalStorage:
    def __init__(self, root: str, public_base_url: str):
        self.root = Path(root)
        self.public_base_url = public_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"invalid key: {key}")
        return path

    def put(self, key: str, data: bytes, content_type: str = "image/webp") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/files/{key}"


class R2Storage:
    def __init__(self, account_id: str, access_key: str, secret_key: str, bucket: str, public_base_url: str):
        import boto3

        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")

    def put(self, key: str, data: bytes, content_type: str = "image/webp") -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "r2":
        return R2Storage(s.r2_account_id, s.r2_access_key_id, s.r2_secret_access_key, s.r2_bucket, s.r2_public_base_url)
    return LocalStorage(s.local_storage_dir, s.public_base_url)
