# Profile Image Upload — Design Document

## Overview

This spec is additive. No existing tables are dropped or altered; no migration checkpoint advances. The work divides into two phases:

- **Phase 1 (Convergence):** Install Pillow, configure media storage, add model fields, build the upload pipeline, wire the crop UX, add the default avatar, surface avatars in three template locations.
- **Phase 2 (Verification):** Full test suite, sign-off.

## Pre-Execution Gate

Before any Phase 1 task begins, confirm both gates pass:

```python
# Gate 1 — CP5 confirmed
manage.py shell -c "
from marketplace.migration_control.state import get_or_create_state
s = get_or_create_state()
assert s.checkpoint_order == 5, f'CP5 required, got CP{s.checkpoint_order}'
print('Gate 1 OK — CP5 confirmed')
"

# Gate 2 — Pillow available
manage.py shell -c "
try:
    import PIL
    print('Gate 2 OK — Pillow available:', PIL.__version__)
except ImportError:
    raise AssertionError('Pillow not installed — run: .venv/bin/pip install Pillow')
"
```

If either gate fails, STOP. Install Pillow before proceeding.

---

## Architecture

```
Phase 1: Convergence (reversible)
  ┌─────────────────────────────────────────────────────────────────────┐
  │  Dependencies                                                       │
  │  └── Pillow added to requirements.txt                               │
  │                                                                     │
  │  config/settings.py                                                 │
  │  ├── MEDIA_ROOT (env-overridable, default BASE_DIR / "media")       │
  │  ├── MEDIA_URL  (env-overridable, default "/media/")                │
  │  └── MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024                        │
  │                                                                     │
  │  config/urls.py                                                     │
  │  └── + static(MEDIA_URL, document_root=MEDIA_ROOT) in DEBUG         │
  │                                                                     │
  │  marketplace/models.py                                              │
  │  └── User                                                           │
  │       ├── profile_image      (ImageField, nullable)                 │
  │       ├── profile_image_updated_at (DateTimeField, nullable)        │
  │       └── profile_image_url  (property)                             │
  │                                                                     │
  │  marketplace/migrations/                                            │
  │  └── 0016_user_profile_image.py (new, additive)                     │
  │                                                                     │
  │  marketplace/image_pipeline.py  (new module)                        │
  │  └── process_profile_image(file, user) → (content, ext)             │
  │       validates → detects transparency → resizes → re-encodes       │
  │                                                                     │
  │  marketplace/views.py                                               │
  │  └── upload_profile_image (new view, POST /profile/upload-avatar/)  │
  │                                                                     │
  │  marketplace/urls.py                                                │
  │  └── path("profile/upload-avatar/", ..., name="upload_avatar")      │
  │                                                                     │
  │  static/img/default_avatar.png  (new static asset)                 │
  │  static/js/avatar-upload.js     (new — Cropper.js wiring)          │
  │  static/vendor/cropper.min.js   (vendored Cropper.js)              │
  │  static/vendor/cropper.min.css  (vendored Cropper.js CSS)          │
  │                                                                     │
  │  templates/marketplace/profile.html     (updated — avatar display) │
  │  templates/marketplace/supply_lot_detail.html  (updated — avatar)  │
  │  templates/marketplace/demand_post_detail.html (updated — avatar)  │
  │  templates/marketplace/thread_detail.html      (updated — avatars) │
  │  templates/includes/_avatar_lightbox.html      (new — modal)       │
  └─────────────────────────────────────────────────────────────────────┘

Phase 2: Verification
  ┌─────────────────────────────────────────────────────────────────────┐
  │  marketplace/tests/test_profile_image.py (new)                      │
  │  Full test suite passing, 0 regressions                             │
  └─────────────────────────────────────────────────────────────────────┘

Request/response flow:

  Browser                              Django
    │                                    │
    ├─ user selects file                 │
    ├─ Cropper.js modal opens            │
    ├─ user drags/resizes crop box       │
    ├─ user clicks Save                  │
    ├─ Canvas API → square blob          │
    ├─ AJAX POST /profile/upload-avatar/ │
    │   FormData { avatar: <blob> }  ───>│
    │                                    ├─ check auth (302 if anon)
    │                                    ├─ check file size ≤ 5 MB
    │                                    ├─ check MIME type whitelist
    │                                    ├─ Pillow verify (log + reject if fail)
    │                                    ├─ check dimensions ≥ 256×256
    │                                    ├─ detect transparency
    │                                    ├─ resize to 512×512
    │                                    ├─ re-encode (JPEG q85 / PNG)
    │                                    ├─ save to storage
    │                                    ├─ update User record
    │                                    ├─ delete old file
    │<── JSON { avatar_url: "..." }  ────┤
    ├─ update <img> src in page          │
    ├─ close modal                       │
```

---

## Data Model

### User model additions

```python
def _profile_image_upload_to(instance, filename):
    # filename is ignored — UUID is assigned by the pipeline
    return f"profile_images/{instance.pk}/"

class User(AbstractUser):
    ...
    profile_image = models.ImageField(
        upload_to=_profile_image_upload_to,
        null=True,
        blank=True,
    )
    profile_image_updated_at = models.DateTimeField(null=True, blank=True)

    @property
    def profile_image_url(self):
        if self.profile_image:
            return self.profile_image.url
        from django.templatetags.static import static
        return static("img/default_avatar.png")
```

The `upload_to` callable returns the directory only. The pipeline supplies the full UUID filename when calling `field.save(name, content)`, so the stored path is always `profile_images/{user_id}/{uuid}.{ext}`.

### Migration

Migration `0016_user_profile_image` adds `profile_image` (ImageField, nullable) and `profile_image_updated_at` (DateTimeField, nullable) to `User`. Additive only — no existing columns altered.

---

## Settings

```python
# config/settings.py

import os
from pathlib import Path

MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media"))
MEDIA_URL  = os.environ.get("MEDIA_URL", "/media/")
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
```

### Development media serving

In `config/urls.py`, append media serving in DEBUG mode:

```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    ...
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

This is Django's standard pattern. It is not suitable for production — a real web server (nginx) or object storage handles media in production.

---

## Image Pipeline Module

A new module `marketplace/image_pipeline.py` contains the `process_profile_image` function. Isolating the pipeline in its own module makes it independently testable and reusable for future image features (e.g., listing images) without importing from `views.py`.

### Function signature

```python
def process_profile_image(file, user) -> tuple[BytesIO, str]:
    """
    Validate, process, and re-encode a profile image upload.

    Args:
        file: The uploaded file object (the crop blob from the client).
        user: The authenticated User instance (used for logging).

    Returns:
        (buffer, ext) where buffer is a BytesIO of the processed image
        and ext is 'jpg' or 'png'.

    Raises:
        ValidationError on any rejection condition.
    """
```

### Processing steps (in order)

1. **Size check** — reject if `file.size > MAX_UPLOAD_SIZE_BYTES`
2. **MIME type check** — reject if content type not in `{'image/jpeg', 'image/png', 'image/webp'}`
3. **Pillow open + verify** — call `Image.open(file)` then `img.verify()`. On failure: log `WARNING` with `user.pk`, `user.email`, reported content type, file size; raise `ValidationError`
4. **Reopen** — `img.verify()` exhausts the file object; reopen with `Image.open(file)` before further processing
5. **Dimension check** — reject if `img.width < 256 or img.height < 256`
6. **Transparency detection** — if `img.mode` in `{'RGBA', 'LA', 'PA'}`: output format is PNG; else: convert to RGB, output format is JPEG
7. **Resize to 512×512** — `img.resize((512, 512), Image.LANCZOS)`. The incoming blob is already square (produced by Canvas API); this step normalizes to the canonical dimension
8. **Color space** — convert to sRGB if needed (Pillow handles this on re-encode)
9. **Re-encode** — write to `BytesIO`. JPEG: `img.save(buf, format='JPEG', quality=85)`; PNG: `img.save(buf, format='PNG')`
10. Return `(buf, ext)` where `ext` is `'jpg'` or `'png'`

EXIF metadata is stripped implicitly in step 9 — Pillow does not copy EXIF when re-encoding to a new buffer.

---

## Upload View

```
POST /profile/upload-avatar/
name: upload_avatar
auth: @login_required
```

### Request

`multipart/form-data` with a single field `avatar` containing the crop blob.

### Response

- **Success:** `HTTP 200` JSON `{ "avatar_url": "<url>" }`
- **Validation error:** `HTTP 400` JSON `{ "error": "<message>" }`
- **Unauthenticated:** `HTTP 302` redirect to login

### View logic

```python
@login_required
@require_POST
def upload_profile_image(request):
    file = request.FILES.get("avatar")
    if not file:
        return JsonResponse({"error": "No file provided."}, status=400)

    try:
        buf, ext = process_profile_image(file, request.user)
    except ValidationError as e:
        return JsonResponse({"error": e.message}, status=400)

    # Save new file
    filename = f"{uuid4()}.{ext}"
    old_name = request.user.profile_image.name if request.user.profile_image else None

    request.user.profile_image.save(filename, ContentFile(buf.getvalue()), save=False)
    request.user.profile_image_updated_at = timezone_now()
    request.user.save(update_fields=["profile_image", "profile_image_updated_at"])

    # Delete old file after successful save
    if old_name:
        try:
            default_storage.delete(old_name)
        except Exception:
            logger.warning("Failed to delete old profile image: %s", old_name)

    return JsonResponse({"avatar_url": request.user.profile_image_url})
```

---

## Default Avatar

A neutral silhouette PNG lives at `static/img/default_avatar.png`. It is:

- A simple greyscale circular-safe silhouette (head + shoulders outline)
- Sized at 512×512 to match canonical profile images
- Served by the static file pipeline — no MEDIA_ROOT required
- Displayed identically to real avatars (same CSS classes, same `border-radius: 50%`)

The `User.profile_image_url` property returns `static("img/default_avatar.png")` when `profile_image` is falsy. No template ever checks `user.profile_image` directly.

---

## Cropping UX

### Dependencies

Cropper.js is vendored (not CDN-linked) for offline dev and version stability:

```
static/vendor/cropper.min.js
static/vendor/cropper.min.css
```

Version: Cropper.js 1.x (stable, no npm required, plain JS).

### Client-side module

`static/js/avatar-upload.js` wires the crop flow:

1. Listens for `change` on the file `<input>`
2. Reads the file with `FileReader` → sets as `<img>` src in the crop modal
3. Initialises `Cropper` on the `<img>` with `aspectRatio: 1` (square lock)
4. Renders a circular preview using Cropper's `preview` option pointed at a circular `<div>` (CSS `border-radius: 50%; overflow: hidden`)
5. On "Save" click: calls `cropper.getCroppedCanvas({ width: 512, height: 512 })` → `canvas.toBlob()` → builds `FormData` → `fetch` POST to `/profile/upload-avatar/`
6. On success: updates the `<img src>` on the profile page with the returned `avatar_url`; closes the modal
7. On error: shows the error message inline; keeps the modal open

### Crop modal HTML structure

```html
<dialog id="avatar-crop-modal">
  <div class="avatar-crop-container">
    <img id="avatar-crop-image" src="" alt="">
  </div>
  <div class="avatar-crop-preview-wrap">
    <div id="avatar-crop-preview"></div>  <!-- circular preview -->
  </div>
  <div class="avatar-crop-actions">
    <button type="button" id="avatar-crop-save">Save</button>
    <button type="button" id="avatar-crop-cancel">Cancel</button>
  </div>
</dialog>
```

The `<dialog>` element is used rather than a custom overlay div. It provides native focus trapping, blocks interaction with the page behind it when opened with `showModal()`, and is dismissable with `close()`. No custom focus management code is needed.

### Crop modal trigger

The profile page contains:

```html
<img src="{{ user.profile_image_url }}" id="current-avatar" class="avatar avatar-lg">
<label for="avatar-file-input" class="btn btn-secondary">Change photo</label>
<input type="file" id="avatar-file-input" accept="image/jpeg,image/png,image/webp" class="visually-hidden">
```

`avatar-upload.js` handles the rest. No form submit; the upload is entirely AJAX.

---

## Image Surfaces

### Profile page (`/profile/`)

The existing profile template gains:

- Circular avatar at the top (`avatar-lg` CSS class, ~96px display)
- "Change photo" label/button that triggers the file input
- The crop modal HTML (hidden until triggered)
- `avatar-upload.js` and Cropper.js loaded in the page

### Listing detail pages

Both `supply_lot_detail.html` and `demand_post_detail.html` gain an owner avatar section above the `<dl>`:

```html
<div class="listing-owner">
  <img src="{{ lot.created_by_user.profile_image_url }}"
       class="avatar avatar-sm avatar-clickable"
       data-fullsrc="{{ lot.created_by_user.profile_image_url }}"
       alt="{{ lot.created_by_user.display_name }}">
  <span>{{ lot.created_by_user.display_name }}</span>
</div>
```

Clicking the avatar opens the lightbox modal (see below).

### Message thread (`/threads/<pk>/`)

Each message row in `thread_detail.html` gains the sender's avatar inline:

```html
<div class="message sent/received">
  <img src="{{ message.sender.profile_image_url }}"
       class="avatar avatar-xs"
       alt="{{ message.sender.display_name }}">
  <div class="message-body">{{ message.body }}</div>
</div>
```

No lightbox on thread avatars — small context, no click action needed.

---

## Avatar Lightbox Modal

A reusable `templates/includes/_avatar_lightbox.html` include provides the lightbox structure:

```html
<dialog id="avatar-lightbox">
  <button id="avatar-lightbox-close" aria-label="Close">&times;</button>
  <img id="avatar-lightbox-img" src="" alt="">
</dialog>
```

Inline `<script>` (or `avatar-upload.js`) handles:

- Delegated click listener on `.avatar-clickable` → reads `data-fullsrc` → sets lightbox `<img src>` → calls `lightbox.showModal()`
- Click on close button or outside the image → `lightbox.close()`

The `<dialog>` element's native `showModal()` provides focus trapping and the backdrop. No external library needed.

The `_avatar_lightbox.html` include is added once to `base.html` so it is available on all pages that may eventually use it.

---

## CSS

New classes required in both skin files (`skin-simple-blue.css` and `skin-warm-editorial.css`):

| Class | Purpose |
|-------|---------|
| `.avatar` | Base: `border-radius: 50%; object-fit: cover; display: inline-block` |
| `.avatar-xs` | 32×32px — message thread |
| `.avatar-sm` | 48×48px — listing detail owner |
| `.avatar-lg` | 96×96px — profile page |
| `.avatar-clickable` | `cursor: pointer` |
| `.listing-owner` | Flex row, aligns avatar + name |
| `.avatar-crop-container` | Crop modal image area |
| `.avatar-crop-preview-wrap` | Preview area |
| `#avatar-crop-preview` | `border-radius: 50%; overflow: hidden; width: 96px; height: 96px` |
| `dialog::backdrop` | Semi-transparent overlay |
| `.visually-hidden` | Screen-reader-only file input |

---

## Test Strategy

All tests in `marketplace/tests/test_profile_image.py`, tagged `@tag('profile_image')`.

Test settings override:

```python
import tempfile

_TEMP_MEDIA = tempfile.mkdtemp()

@override_settings(
    MEDIA_ROOT=_TEMP_MEDIA,
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}},
)
```

Helper: `_make_image_upload(width, height, mode='RGB', fmt='JPEG')` — creates an in-memory image with Pillow and returns a `SimpleUploadedFile`.

### Test cases

| Test | Covers |
|------|--------|
| `test_upload_valid_jpeg` | Valid JPEG → 200, profile_image set, stored as `.jpg` |
| `test_upload_valid_png_opaque` | Opaque PNG → stored as `.jpg` (no alpha) |
| `test_upload_transparent_png` | RGBA PNG → stored as `.png` |
| `test_upload_webp` | WebP → accepted, processed |
| `test_upload_too_large` | File > 5 MB → 400 error |
| `test_upload_invalid_mime` | GIF → 400 error |
| `test_upload_corrupt_file` | Unparseable bytes → 400 error + WARNING logged |
| `test_upload_too_small` | 128×128 image → 400 error |
| `test_upload_exactly_min_size` | 256×256 image → accepted |
| `test_upload_unauthenticated` | No session → 302 to login |
| `test_old_file_deleted_after_new_upload` | Second upload → old file removed from storage |
| `test_old_file_missing_does_not_raise` | Old path gone from storage → deletion swallowed, new image saved |
| `test_output_is_512x512` | Processed image dimensions are exactly 512×512 |
| `test_profile_image_url_with_image` | Returns media URL when image set |
| `test_profile_image_url_without_image` | Returns static default avatar URL when no image |
| `test_stored_path_contains_user_id` | Stored path matches `profile_images/{user_id}/` pattern |
