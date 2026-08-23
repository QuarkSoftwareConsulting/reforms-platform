from __future__ import annotations

from app.application.ports import PresignedUpload, StoragePort


class FakeStorage(StoragePort):
    def __init__(self, base_url: str = "https://cdn.test/reforma-hub") -> None:
        self.base_url = base_url
        self.deleted: list[str] = []
        self._counter = 0

    async def create_presigned_upload(
        self, *, key_prefix: str, filename: str, content_type: str
    ) -> PresignedUpload:
        self._counter += 1
        key = f"{key_prefix}/{self._counter:04d}/{filename}"
        return PresignedUpload(
            storage_key=key,
            upload_url=f"{self.base_url}/{key}?signature=fake",
            headers={"Content-Type": content_type},
        )

    def public_url(self, storage_key: str) -> str:
        return f"{self.base_url}/{storage_key}"

    async def delete(self, storage_key: str) -> None:
        self.deleted.append(storage_key)
