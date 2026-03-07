"""
Image processing pipeline for profile (and future listing) uploads.

process_profile_image(file, user) -> (image_bytes: bytes, ext: str)

Steps:
  1. Size check (enforced by caller via MAX_UPLOAD_SIZE_BYTES before calling here)
  2. Content-type pre-screen (enforced by caller)
  3. Open with Pillow and call verify() — rejects corrupt / non-image data
  4. Reopen (verify() exhausts the file pointer)
  5. Dimension check (min 256×256)
  6. Transparency detection → choose output format
  7. Resize to 512×512 (LANCZOS)
  8. Re-encode (strips EXIF / metadata implicitly)
  9. Return bytes + extension
"""

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

CANONICAL_SIZE = (512, 512)
MIN_DIMENSION = 256
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageValidationError(Exception):
    """Raised for user-visible validation failures (form errors)."""


def process_profile_image(file, user):
    """
    Validate and process an uploaded image file.

    Args:
        file: Django UploadedFile (already size- and content-type-checked by caller).
        user: The authenticated User instance (used for logging only).

    Returns:
        (image_bytes: bytes, ext: str)  — ext is 'jpg' or 'png'.

    Raises:
        ImageValidationError: for any user-visible rejection (bad image, too small).
    """
    # Step 3: Pillow verify — detects corrupt or non-image data
    try:
        img = Image.open(file)
        img.verify()
    except Exception:
        logger.warning(
            "Profile image rejected: Pillow could not verify file. "
            "user_id=%s email=%s content_type=%s size=%s",
            user.pk,
            user.email,
            getattr(file, "content_type", "unknown"),
            getattr(file, "size", "unknown"),
        )
        raise ImageValidationError(
            "The uploaded file is not a valid image or could not be read."
        )

    # Step 4: Reopen after verify() (verify exhausts the file pointer)
    file.seek(0)
    img = Image.open(file)

    # Step 5: Minimum dimension check
    width, height = img.size
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise ImageValidationError(
            f"Image must be at least {MIN_DIMENSION}×{MIN_DIMENSION} pixels "
            f"(uploaded image is {width}×{height})."
        )

    # Step 6: Transparency detection → choose output format
    mode = img.mode
    if mode in ("RGBA", "LA"):
        output_format = "PNG"
        ext = "png"
    elif mode == "PA":
        output_format = "PNG"
        ext = "png"
    elif mode == "P":
        # Palette mode: check for transparency info
        if "transparency" in img.info:
            output_format = "PNG"
            ext = "png"
        else:
            img = img.convert("RGB")
            output_format = "JPEG"
            ext = "jpg"
    else:
        img = img.convert("RGB")
        output_format = "JPEG"
        ext = "jpg"

    # Step 7: Resize to canonical 512×512
    img = img.resize(CANONICAL_SIZE, Image.LANCZOS)

    # Step 8: Re-encode into bytes (strips EXIF / metadata)
    buf = io.BytesIO()
    if output_format == "JPEG":
        img.save(buf, format="JPEG", quality=85)
    else:
        img.save(buf, format="PNG")
    buf.seek(0)

    return buf.read(), ext
