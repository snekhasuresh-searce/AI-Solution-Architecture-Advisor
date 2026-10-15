"""Uploading, serving and removing a profile photo."""

import io
import uuid

from fastapi.testclient import TestClient
from PIL import Image

from advisor import auth
from advisor.api import app

HEADERS = {"X-Advisor-Client": "test"}


def _signed_in() -> TestClient:
    client = TestClient(app, headers=HEADERS)
    email = f"photo-{uuid.uuid4().hex[:6]}@searce.com"
    assert client.post("/api/auth/dev-login", json={"email": email}).status_code == 200
    return client


def _image(fmt: str = "PNG", size=(800, 400), **save) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (99, 23, 238)).save(out, fmt, **save)
    return out.getvalue()


def _upload(client: TestClient, data: bytes, name="me.png", kind="image/png"):
    return client.put("/api/auth/me/picture", files={"file": (name, data, kind)})


def test_upload_serve_and_remove():
    client = _signed_in()
    me = client.get("/api/auth/me").json()
    assert me["has_custom_picture"] is False

    res = _upload(client, _image())
    assert res.status_code == 200, res.text
    me = res.json()
    assert me["has_custom_picture"] and me["picture"].startswith(f"/api/users/{me['id']}/picture?v=")
    assert client.get("/api/auth/me").json()["picture"] == me["picture"]

    photo = client.get(me["picture"])
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/webp"
    assert "immutable" in photo.headers["cache-control"]
    img = Image.open(io.BytesIO(photo.content))
    assert img.format == "WEBP" and img.size == (auth.PICTURE_SIZE, auth.PICTURE_SIZE)  # cropped square

    second = _upload(client, _image("JPEG")).json()
    assert second["picture"] != me["picture"]  # new version, so browsers do not show the cached one

    removed = client.delete("/api/auth/me/picture").json()
    assert removed["has_custom_picture"] is False and removed["picture"] is None
    assert client.get(me["picture"]).status_code == 404


def test_other_signed_in_users_can_see_it_but_not_anonymous():
    owner = _signed_in()
    url = _upload(owner, _image()).json()["picture"]
    assert _signed_in().get(url).status_code == 200
    assert TestClient(app).get(url).status_code == 401


def test_metadata_and_orientation():
    exif = Image.Exif()
    exif[0x0112] = 6        # orientation: rotate 90°, as phones store portrait photos
    exif[0x010F] = "Phone"  # camera make: must not survive re-encoding
    portrait = Image.new("RGB", (400, 800), (0, 0, 255))
    portrait.paste((255, 0, 0), (0, 0, 400, 400))  # top half red, bottom half blue
    raw = io.BytesIO()
    portrait.save(raw, "JPEG", exif=exif.tobytes())
    client = _signed_in()
    url = _upload(client, raw.getvalue(), "p.jpg", "image/jpeg").json()["picture"]
    img = Image.open(io.BytesIO(client.get(url).content)).convert("RGB")
    assert not img.getexif() and "exif" not in img.info
    right, left = img.getpixel((240, 128)), img.getpixel((16, 128))
    assert right[0] > 200 > right[2] and left[2] > 200 > left[0]  # turned 90° clockwise: red is now on the right


def test_rejects_non_images_and_oversized_files():
    client = _signed_in()
    assert _upload(client, b"<svg xmlns='http://www.w3.org/2000/svg'/>", "x.svg", "image/svg+xml").status_code == 400
    assert _upload(client, b"%PDF-1.4 not an image", "x.png", "image/png").status_code == 400  # lies about its type
    bmp = io.BytesIO()
    Image.new("RGB", (10, 10)).save(bmp, "BMP")
    assert _upload(client, bmp.getvalue(), "x.bmp", "image/bmp").status_code == 400  # real image, unsupported format
    assert _upload(client, b"0" * (auth.PICTURE_MAX_BYTES + 1)).status_code == 413
    assert client.get("/api/auth/me").json()["has_custom_picture"] is False


def test_needs_sign_in_and_the_client_header():
    assert TestClient(app, headers=HEADERS).put("/api/auth/me/picture",
                                                files={"file": ("a.png", _image(), "image/png")}).status_code == 401
    client = _signed_in()
    bare = TestClient(app)
    bare.cookies = client.cookies
    assert bare.put("/api/auth/me/picture", files={"file": ("a.png", _image(), "image/png")}).status_code == 403


def test_google_sign_in_keeps_the_uploaded_photo():
    client = _signed_in()
    me = _upload(client, _image()).json()
    user = auth.upsert_user(email=me["email"], name="G", picture="https://lh3/google-photo", google_sub=uuid.uuid4().hex)
    assert user.display_picture == me["picture"]          # the upload still wins
    assert user.picture == "https://lh3/google-photo"      # the Google photo is kept underneath
    assert client.delete("/api/auth/me/picture").json()["picture"] == "https://lh3/google-photo"
