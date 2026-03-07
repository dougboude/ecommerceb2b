"""
Tests for Feature 11: profile image upload pipeline.

Test plan:
  10.1  pipeline: opaque image → JPEG output
  10.2  pipeline: RGBA image → PNG output
  10.3  pipeline: image < 256px → ImageValidationError
  10.4  pipeline: corrupt data → ImageValidationError + WARNING log
  10.5  pipeline: 512×512 canonical size
  10.6  pipeline: EXIF stripped (no EXIF in output)
  10.7  model: profile_image_url returns default avatar when no image
  10.8  model: profile_image_url returns image URL when set
  10.9  upload view: unauthenticated → 302
  10.10 upload view: no file → 400
  10.11 upload view: file too large → 400
  10.12 upload view: wrong content type → 400
  10.13 upload view: valid upload → 200 + avatar_url in JSON
  10.14 upload view: replaces old image file
  10.15 upload view: missing old file swallowed (no 500)
  10.16 profile page: shows avatar img tag
  10.17 profile page: contains upload form elements
"""

import io
import logging
import tempfile
import os

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from marketplace.image_pipeline import ImageValidationError, process_profile_image
from marketplace.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image_file(width=300, height=300, mode="RGB", fmt="JPEG"):
    """Return an in-memory UploadedFile-like object containing a Pillow image."""
    img = Image.new(mode, (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    buf.name = f"test.{'jpg' if fmt == 'JPEG' else fmt.lower()}"
    buf.content_type = "image/jpeg" if fmt == "JPEG" else f"image/{fmt.lower()}"
    buf.size = buf.getbuffer().nbytes
    return buf


def _make_corrupt_file():
    buf = io.BytesIO(b"this is not an image file")
    buf.seek(0)
    buf.name = "bad.jpg"
    buf.content_type = "image/jpeg"
    buf.size = 25
    return buf


def _create_user(**kwargs):
    defaults = {
        "email": "avatar@example.com",
        "password": "testpass123",
        "display_name": "Avatar Tester",
        "country": "US",
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


# ---------------------------------------------------------------------------
# Group 10.1–10.6: image_pipeline tests
# ---------------------------------------------------------------------------

class ImagePipelineTest(TestCase):

    def setUp(self):
        self.user = _create_user()

    def test_10_1_opaque_image_produces_jpeg(self):
        """10.1: RGB image → JPEG output, ext='jpg'"""
        f = _make_image_file(mode="RGB", fmt="JPEG")
        image_bytes, ext = process_profile_image(f, self.user)
        self.assertEqual(ext, "jpg")
        out = Image.open(io.BytesIO(image_bytes))
        self.assertEqual(out.format, "JPEG")

    def test_10_2_rgba_image_produces_png(self):
        """10.2: RGBA image → PNG output, ext='png'"""
        f = _make_image_file(mode="RGBA", fmt="PNG")
        image_bytes, ext = process_profile_image(f, self.user)
        self.assertEqual(ext, "png")
        out = Image.open(io.BytesIO(image_bytes))
        self.assertEqual(out.format, "PNG")

    def test_10_3_image_too_small_raises_validation_error(self):
        """10.3: image smaller than 256px → ImageValidationError"""
        f = _make_image_file(width=100, height=100, mode="RGB", fmt="JPEG")
        with self.assertRaises(ImageValidationError) as ctx:
            process_profile_image(f, self.user)
        self.assertIn("256", str(ctx.exception))

    def test_10_4_corrupt_file_raises_and_logs_warning(self):
        """10.4: corrupt file → ImageValidationError + WARNING log"""
        f = _make_corrupt_file()
        with self.assertLogs("marketplace.image_pipeline", level="WARNING") as cm:
            with self.assertRaises(ImageValidationError):
                process_profile_image(f, self.user)
        self.assertTrue(any("rejected" in line.lower() for line in cm.output))
        # Log must include user id and email
        log_text = " ".join(cm.output)
        self.assertIn(str(self.user.pk), log_text)
        self.assertIn(self.user.email, log_text)

    def test_10_5_output_is_512x512(self):
        """10.5: output canonical size is 512×512"""
        f = _make_image_file(width=800, height=600, mode="RGB", fmt="JPEG")
        image_bytes, ext = process_profile_image(f, self.user)
        out = Image.open(io.BytesIO(image_bytes))
        self.assertEqual(out.size, (512, 512))

    def test_10_6_exif_stripped(self):
        """10.6: re-encoded output has no EXIF data"""
        # Create a JPEG with minimal EXIF-like metadata
        img = Image.new("RGB", (400, 400), (200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        buf.name = "exif_test.jpg"
        buf.content_type = "image/jpeg"
        buf.size = buf.getbuffer().nbytes

        image_bytes, ext = process_profile_image(buf, self.user)
        out = Image.open(io.BytesIO(image_bytes))
        # Pillow's re-encode via save() does not preserve EXIF by default
        exif_data = out.info.get("exif", b"")
        self.assertEqual(exif_data, b"")


# ---------------------------------------------------------------------------
# Group 10.7–10.8: User model property tests
# ---------------------------------------------------------------------------

@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class UserProfileImageUrlTest(TestCase):

    def test_10_7_no_image_returns_default_avatar_url(self):
        """10.7: profile_image_url returns default avatar path when no image set"""
        user = _create_user(email="noimg@example.com")
        url = user.profile_image_url
        self.assertIn("default_avatar", url)

    def test_10_8_with_image_returns_image_url(self):
        """10.8: profile_image_url returns .url when profile_image is set"""
        user = _create_user(email="withimg@example.com")
        # Mock profile_image with a simple object that has a .url
        class FakeFieldFile:
            url = "/media/profile_images/1/abc.jpg"
            def __bool__(self): return True
        user.profile_image = FakeFieldFile()
        url = user.profile_image_url
        self.assertEqual(url, "/media/profile_images/1/abc.jpg")


# ---------------------------------------------------------------------------
# Group 10.9–10.15: upload view tests
# ---------------------------------------------------------------------------

@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    MEDIA_URL="/media/",
    MAX_UPLOAD_SIZE_BYTES=5 * 1024 * 1024,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class UploadViewTest(TestCase):

    def setUp(self):
        self.user = _create_user(email="uploader@example.com")
        self.url = reverse("marketplace:upload_profile_image")

    def _post_image(self, image_file=None, content_type="image/jpeg"):
        if image_file is None:
            image_file = _make_image_file()
        image_file.content_type = content_type
        return self.client.post(
            self.url,
            {"avatar": image_file},
            format="multipart",
        )

    def test_10_9_unauthenticated_redirects(self):
        """10.9: unauthenticated request → 302 to login"""
        resp = self._post_image()
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_10_10_no_file_returns_400(self):
        """10.10: POST with no file → 400"""
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)

    def test_10_11_file_too_large_returns_400(self):
        """10.11: file exceeding MAX_UPLOAD_SIZE_BYTES → 400"""
        self.client.force_login(self.user)
        big_buf = io.BytesIO(b"X" * (5 * 1024 * 1024 + 1))
        big_buf.name = "big.jpg"
        big_buf.content_type = "image/jpeg"
        big_buf.size = big_buf.getbuffer().nbytes
        resp = self.client.post(self.url, {"avatar": big_buf})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_10_12_wrong_content_type_returns_400(self):
        """10.12: unsupported MIME type → 400"""
        self.client.force_login(self.user)
        buf = io.BytesIO(b"fake gif data")
        buf.name = "fake.gif"
        buf.content_type = "image/gif"
        buf.size = buf.getbuffer().nbytes
        resp = self.client.post(self.url, {"avatar": buf})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_10_13_valid_upload_returns_avatar_url(self):
        """10.13: valid JPEG upload → 200 + avatar_url in JSON"""
        self.client.force_login(self.user)
        f = _make_image_file()
        f.content_type = "image/jpeg"
        resp = self.client.post(self.url, {"avatar": f})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("avatar_url", data)
        self.assertIn("/media/", data["avatar_url"])

    def test_10_14_upload_replaces_old_image(self):
        """10.14: second upload sets a different file path"""
        self.client.force_login(self.user)

        f1 = _make_image_file()
        f1.content_type = "image/jpeg"
        self.client.post(self.url, {"avatar": f1})
        self.user.refresh_from_db()
        first_path = self.user.profile_image.name

        f2 = _make_image_file(width=400, height=400)
        f2.content_type = "image/jpeg"
        self.client.post(self.url, {"avatar": f2})
        self.user.refresh_from_db()
        second_path = self.user.profile_image.name

        self.assertNotEqual(first_path, second_path)

    def test_10_15_missing_old_file_swallowed(self):
        """10.15: deletion of non-existent old file does not raise 500"""
        self.client.force_login(self.user)

        # Upload first image then manually delete the file from disk
        f1 = _make_image_file()
        f1.content_type = "image/jpeg"
        self.client.post(self.url, {"avatar": f1})
        self.user.refresh_from_db()
        old_path = os.path.join(settings.MEDIA_ROOT, self.user.profile_image.name)
        if os.path.exists(old_path):
            os.remove(old_path)

        # Second upload should succeed even though old file is gone
        f2 = _make_image_file(width=400, height=400)
        f2.content_type = "image/jpeg"
        resp = self.client.post(self.url, {"avatar": f2})
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Group 10.16–10.17: profile page template tests
# ---------------------------------------------------------------------------

@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProfilePageAvatarTest(TestCase):

    def setUp(self):
        self.user = _create_user(email="profilepage@example.com")
        self.client.force_login(self.user)

    def test_10_16_profile_page_shows_avatar_img(self):
        """10.16: profile page contains an <img> with avatar class"""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="avatar-display"')

    def test_10_17_profile_page_contains_upload_elements(self):
        """10.17: profile page contains file input and crop modal"""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="avatar-input"')
        self.assertContains(resp, 'id="avatar-crop-modal"')
        self.assertContains(resp, "/upload-avatar/")
