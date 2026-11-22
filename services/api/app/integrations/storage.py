"""Server-only private document storage adapters."""

import shutil
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryFile
from typing import BinaryIO, Protocol
from urllib.parse import quote

import httpx
from app.core.config import settings


def checked_key(key: str) -> str:
    path = PurePosixPath(key)
    if (
        not key
        or path.is_absolute()
        or "\\" in key
        or any(part in {"", ".", ".."} for part in key.split("/"))
        or ":" in key
    ):
        raise ValueError("Invalid private object key")
    return key


class DocumentStorage(Protocol):
    def put(self, key: str, stream: BinaryIO) -> None: ...
    def open(self, key: str): ...
    def delete(self, key: str) -> None: ...
    def signed_url(self, key: str, expires_seconds: int) -> str: ...


class LocalPrivateStorage:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        target = (self.root / checked_key(key)).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Invalid private object key")
        return target

    def put(self, key: str, stream: BinaryIO) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as destination:
            target.chmod(0o600)
            shutil.copyfileobj(stream, destination, length=64 * 1024)

    def open(self, key: str):
        return self._path(key).open("rb")

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def signed_url(self, key: str, expires_seconds: int) -> str:
        checked_key(key)
        # Local files are delivered by authenticated application routes, never file URLs.
        raise NotImplementedError("Local private storage does not issue signed URLs")


class SupabasePrivateStorage:
    def __init__(self, url: str, bucket: str, service_key: str, *, client=None):
        self.base_url = url.rstrip("/") + "/storage/v1"
        self.bucket = quote(checked_key(bucket), safe="")
        self.client = client or httpx.Client(timeout=30)
        self.headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
        response = self.client.get(f"{self.base_url}/bucket/{self.bucket}", headers=self.headers)
        response.raise_for_status()
        if response.json().get("public") is not False:
            raise ValueError("Document storage requires a private bucket")

    def _object_url(self, key: str, operation: str = "") -> str:
        return (
            f"{self.base_url}/object/{operation}{self.bucket}/{quote(checked_key(key), safe='/')}"
        )

    def put(self, key: str, stream: BinaryIO) -> None:
        def chunks():
            while data := stream.read(64 * 1024):
                yield data

        response = self.client.post(
            self._object_url(key),
            headers={
                **self.headers,
                "Content-Type": "application/octet-stream",
                "x-upsert": "false",
            },
            content=chunks(),
        )
        response.raise_for_status()

    @contextmanager
    def open(self, key: str):
        with TemporaryFile("w+b") as output:
            with self.client.stream("GET", self._object_url(key), headers=self.headers) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(64 * 1024):
                    output.write(chunk)
            output.seek(0)
            yield output

    def delete(self, key: str) -> None:
        response = self.client.delete(self._object_url(key), headers=self.headers)
        if response.status_code != 404:
            response.raise_for_status()

    def signed_url(self, key: str, expires_seconds: int) -> str:
        if not 1 <= expires_seconds <= 3600:
            raise ValueError("Invalid signed URL lifetime")
        response = self.client.post(
            self._object_url(key, "sign/"),
            headers=self.headers,
            json={"expiresIn": expires_seconds},
        )
        response.raise_for_status()
        path = response.json()["signedURL"]
        expected = f"/object/sign/{self.bucket}/"
        if not path.startswith(expected):
            raise ValueError("Invalid signed object URL")
        return self.base_url + path


def get_storage() -> DocumentStorage:
    if settings.storage_backend == "local":
        return LocalPrivateStorage(settings.private_storage_root)
    return SupabasePrivateStorage(
        settings.supabase_url,
        settings.supabase_storage_bucket,
        settings.supabase_service_role_key.get_secret_value(),
    )
