from io import BytesIO
from uuid import uuid4

import httpx
import pytest
from app.integrations.storage import LocalPrivateStorage, SupabasePrivateStorage


def test_local_storage_roundtrip_is_private_and_delete_is_exact(tmp_path):
    storage = LocalPrivateStorage(tmp_path)
    key = f"{uuid4()}/{uuid4()}/{uuid4()}.pdf"
    storage.put(key, BytesIO(b"%PDF-private"))
    storage.put(key + ".other", BytesIO(b"keep"))
    with storage.open(key) as stream:
        assert stream.read() == b"%PDF-private"
    with pytest.raises(NotImplementedError):
        storage.signed_url(key, 60)
    storage.delete(key)
    storage.delete(key)
    assert not (tmp_path / key).exists()
    assert (tmp_path / (key + ".other")).read_bytes() == b"keep"


@pytest.mark.parametrize("key", ["../escape", "/absolute", "a/../../escape", "a\\escape"])
def test_local_rejects_unsafe_keys(tmp_path, key):
    storage = LocalPrivateStorage(tmp_path)
    for operation in [
        lambda: storage.put(key, BytesIO(b"x")),
        lambda: storage.open(key),
        lambda: storage.delete(key),
    ]:
        with pytest.raises(ValueError):
            operation()
    assert list(tmp_path.iterdir()) == []


def test_supabase_rest_uses_private_bucket_and_server_auth():
    objects = {}
    key = f"{uuid4()}/{uuid4()}/{uuid4()}.txt"

    def respond(request):
        assert request.headers["authorization"] == "Bearer server-secret"
        assert request.headers["apikey"] == "server-secret"
        assert "/public/" not in request.url.path
        if request.url.path == "/storage/v1/bucket/private-documents":
            return httpx.Response(200, json={"public": False})
        if "/sign/" in request.url.path:
            assert request.read() == b'{"expiresIn":60}'
            return httpx.Response(
                200, json={"signedURL": f"/object/sign/private-documents/{key}?token=private"}
            )
        if request.method == "POST":
            objects[key] = request.read()
            return httpx.Response(200, json={"Key": key})
        if request.method == "GET":
            return httpx.Response(200, content=objects[key])
        if request.method == "DELETE":
            objects.pop(key)
            return httpx.Response(200, json={})
        raise AssertionError(request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    storage = SupabasePrivateStorage(
        "https://storage.example.test", "private-documents", "server-secret", client=client
    )
    storage.put(key, BytesIO(b"private bytes"))
    with storage.open(key) as stream:
        assert stream.read() == b"private bytes"
    url = storage.signed_url(key, 60)
    assert url.startswith("https://storage.example.test/storage/v1/object/sign/")
    assert "server-secret" not in url
    storage.delete(key)
    assert objects == {}


def test_supabase_refuses_public_bucket():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"public": True}))
    )
    with pytest.raises(ValueError):
        SupabasePrivateStorage("https://storage.example.test", "public", "secret", client=client)
