# Implementation Plan

## Pre-Execution Gate Checklist

Before any task begins, confirm both gates pass:

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

## Phase 1: Convergence (Reversible)

### Group 1 — Dependencies and Settings

- [ ] 1.1 Install Pillow and add to `requirements.txt`
  - Run `.venv/bin/pip install Pillow`
  - Add `Pillow` to `requirements.txt` (or equivalent deps file)
  - Confirm `import PIL` succeeds in the venv
  - _Requirements: 8.4_

- [ ] 1.2 Add media settings to `config/settings.py`
  - Add `MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media"))`
  - Add `MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")`
  - Add `MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024`
  - _Requirements: 8.1, 8.2, 8.3_

- [ ] 1.3 Wire DEBUG-only media serving in `config/urls.py`
  - Append `+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` to `urlpatterns`, guarded by `settings.DEBUG`
  - This is for development only — confirm the guard is in place so it cannot activate in production
  - _Requirements: 3.5_

---

### Group 2 — Static Assets

- [ ] 2.1 Create default avatar at `static/img/default_avatar.png`
  - A simple neutral greyscale head-and-shoulders silhouette, 512×512px
  - Must display correctly as a circle via `border-radius: 50%`
  - Served by the static file pipeline — no MEDIA_ROOT required
  - _Requirements: 2.1, 2.3_

- [ ] 2.2 Vendor Cropper.js under `static/vendor/`
  - Download `cropper.min.js` and `cropper.min.css` from Cropper.js 1.x release
  - Place at `static/vendor/cropper.min.js` and `static/vendor/cropper.min.css`
  - No npm or build step — plain JS files loaded via `{% static %}`
  - _Requirements: 6.5_

---

### Group 3 — Data Model and Migration

- [ ] 3.1 Add profile image fields and property to `User` in `marketplace/models.py`
  - Add `_profile_image_upload_to(instance, filename)` callable above the `User` class returning `f"profile_images/{instance.pk}/"`
  - Add `profile_image = models.ImageField(upload_to=_profile_image_upload_to, null=True, blank=True)`
  - Add `profile_image_updated_at = models.DateTimeField(null=True, blank=True)` with comment noting it is audit metadata, not the cache-busting mechanism (UUID filename handles cache busting)
  - Add `profile_image_url` property: returns `self.profile_image.url` if set, else `static("img/default_avatar.png")`
  - _Requirements: 1.1, 1.2, 1.3, 2.2_

- [ ] 3.2 Generate and apply additive migration
  - Run `manage.py makemigrations` — confirm migration is additive only (no drops, no alters)
  - Run `manage.py migrate`
  - Confirm `manage.py migration_validate --scope all --fail-on-error` still passes
  - _Requirements: 1.5_

---

### Group 4 — Image Pipeline Module

- [ ] 4.1 Create `marketplace/image_pipeline.py` with `process_profile_image(file, user)`
  - Implement validation and processing steps in this exact order:
    1. Reject if `file.size > MAX_UPLOAD_SIZE_BYTES` → `ValidationError`
    2. Reject if content type not in `{'image/jpeg', 'image/png', 'image/webp'}` → `ValidationError`
    3. `Image.open(file)` + `img.verify()` — on any exception: log `WARNING` with `user.pk`, `user.email`, reported content type, `file.size`; raise `ValidationError`
    4. `file.seek(0)` then `Image.open(file)` to reopen for processing (verify exhausts the file pointer)
    5. Reject if `img.width < 256 or img.height < 256` → `ValidationError`
    6. Transparency detection:
       - Mode `RGBA` or `LA` → output PNG
       - Mode `P` → inspect `img.info.get('transparency')`; if present, convert to RGBA → output PNG; else convert to RGB → output JPEG
       - All other modes → convert to RGB → output JPEG
    7. `img.resize((512, 512), Image.LANCZOS)`
    8. Write to `BytesIO`: JPEG → `img.save(buf, format='JPEG', quality=85)`; PNG → `img.save(buf, format='PNG')`
    9. Return `(buf, ext)` where `ext` is `'jpg'` or `'png'`
  - Module-level `logger = logging.getLogger(__name__)`
  - No Django view imports in this module — keeps it independently testable
  - _Requirements: 4.1–4.6, 5.1–5.5_

---

### Group 5 — Upload View and URL

- [ ] 5.1 Add `upload_profile_image` view to `marketplace/views.py`
  - Decorated with `@login_required` and `@require_POST`
  - Reads `file = request.FILES.get("avatar")`; returns `JsonResponse({"error": "No file provided."}, status=400)` if missing
  - Calls `process_profile_image(file, request.user)`; on `ValidationError` returns `JsonResponse({"error": e.message}, status=400)`
  - On success: generate `filename = f"{uuid4()}.{ext}"`; read old path from `request.user.profile_image.name` if set; call `request.user.profile_image.save(filename, ContentFile(buf.getvalue()), save=False)`; set `profile_image_updated_at = timezone_now()`; call `request.user.save(update_fields=["profile_image", "profile_image_updated_at"])`
  - After user record saved: if old path exists, call `default_storage.delete(old_path)` inside `try/except` — log warning on failure, do not raise
  - Return `JsonResponse({"avatar_url": request.user.profile_image_url})`
  - _Requirements: 4.6, 5.6, 5.7_

- [ ] 5.2 Add URL pattern to `marketplace/urls.py`
  - `path("profile/upload-avatar/", views.upload_profile_image, name="upload_avatar")`
  - _Requirements: 4.6_

---

### Group 6 — Crop Modal and Client JavaScript

- [ ] 6.1 Create `static/js/avatar-upload.js`
  - On `change` of `#avatar-file-input`: read file with `FileReader`; set as `src` on `#avatar-crop-image`; initialise `Cropper` with `aspectRatio: 1` and `preview: '#avatar-crop-preview'`; call `document.getElementById('avatar-crop-modal').showModal()`
  - On `#avatar-crop-save` click: call `cropper.getCroppedCanvas({width: 512, height: 512})`; `canvas.toBlob(blob => { ... })`; build `FormData` with `avatar` field; `fetch` POST to `upload_avatar` URL with CSRF header; on success update `#current-avatar` `src` with returned `avatar_url` and call `modal.close()`; on error display message inline in the modal
  - On `#avatar-crop-cancel` click: call `modal.close()`; destroy cropper instance; reset file input
  - _Requirements: 6.1–6.6_

- [ ] 6.2 Update `templates/marketplace/profile.html` with crop modal and upload trigger
  - Add current avatar display: `<img src="{{ user.profile_image_url }}" id="current-avatar" class="avatar avatar-lg" alt="{{ user.display_name }}">`
  - Add file input: `<input type="file" id="avatar-file-input" accept="image/jpeg,image/png,image/webp" class="visually-hidden">` with a `<label>` styled as a button
  - Add crop modal: `<dialog id="avatar-crop-modal">` containing `#avatar-crop-image`, `#avatar-crop-preview`, Save and Cancel buttons
  - Load `{% static 'vendor/cropper.min.css' %}` in `{% block head %}` and `{% static 'vendor/cropper.min.js' %}` + `{% static 'js/avatar-upload.js' %}` before `</body>`
  - _Requirements: 6.1–6.7, 7.1_

---

### Group 7 — Lightbox Modal

- [ ] 7.1 Create `templates/includes/_avatar_lightbox.html`
  - `<dialog id="avatar-lightbox">` containing a close button (`#avatar-lightbox-close`) and `<img id="avatar-lightbox-img" src="" alt="">`
  - Include click handler (inline script or in a shared JS block): `.avatar-clickable` click → read `data-fullsrc` → set lightbox img src → `lightbox.showModal()`; close button click and click outside img → `lightbox.close()`
  - _Requirements: 7.2_

- [ ] 7.2 Include `_avatar_lightbox.html` in `templates/base.html`
  - Add `{% include "includes/_avatar_lightbox.html" %}` once, just before `</body>`, so it is available on all pages
  - _Requirements: 7.2_

---

### Group 8 — Image Surfaces

- [ ] 8.1 Update `templates/marketplace/supply_lot_detail.html` with owner avatar
  - Add owner block above `<dl>`: `<div class="listing-owner"><img src="{{ lot.created_by_user.profile_image_url }}" class="avatar avatar-sm avatar-clickable" data-fullsrc="{{ lot.created_by_user.profile_image_url }}" alt="{{ lot.created_by_user.display_name }}"><span>{{ lot.created_by_user.display_name }}</span></div>`
  - _Requirements: 7.2, 7.4, 7.5_

- [ ] 8.2 Update `templates/marketplace/demand_post_detail.html` with owner avatar
  - Same pattern as 8.1 using `post.created_by_user`
  - _Requirements: 7.2, 7.4, 7.5_

- [ ] 8.3 Update `templates/marketplace/thread_detail.html` with per-message sender avatars
  - For each message in the thread, add `<img src="{{ message.sender.profile_image_url }}" class="avatar avatar-xs" alt="{{ message.sender.display_name }}">` alongside the message body
  - No lightbox on thread avatars
  - _Requirements: 7.3, 7.4, 7.5_

---

### Group 9 — CSS

- [ ] 9.1 Add avatar and related classes to both skin files (`static/css/skin-simple-blue.css` and `static/css/skin-warm-editorial.css`)
  - `.avatar` — `border-radius: 50%; object-fit: cover; display: inline-block; flex-shrink: 0`
  - `.avatar-xs` — `width: 32px; height: 32px`
  - `.avatar-sm` — `width: 48px; height: 48px`
  - `.avatar-lg` — `width: 96px; height: 96px`
  - `.avatar-clickable` — `cursor: pointer`
  - `.listing-owner` — `display: flex; align-items: center; gap: var(--space-sm)`
  - `.avatar-crop-container` — contains the Cropper.js image; set `max-height: 400px; overflow: hidden`
  - `#avatar-crop-preview` — `border-radius: 50%; overflow: hidden; width: 96px; height: 96px`
  - `dialog::backdrop` — `background: rgba(0,0,0,0.6)`
  - `.visually-hidden` — `position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0)`
  - _Requirements: 7.4_

---

## Phase 1 Gate — Before Proceeding to Phase 2

```
manage.py test marketplace --verbosity=1
```

Expected: all existing tests still pass, 0 failures, 0 errors. If any regression is introduced, fix it before proceeding to Phase 2.

---

## Phase 2: Tests and Final Verification

### Group 10 — Tests

- [ ] 10.1 Create `marketplace/tests/test_profile_image.py`
  - All tests tagged `@tag('profile_image')`
  - Module-level temp dir: `_TEMP_MEDIA = tempfile.mkdtemp()`
  - Class-level `@override_settings(MEDIA_ROOT=_TEMP_MEDIA, STORAGES=_STATIC_TEST_SETTINGS)`
  - Helper `_make_image_upload(width, height, mode='RGB', fmt='JPEG')` — creates in-memory image with Pillow, returns `SimpleUploadedFile`
  - _Requirements: 8.5_

- [ ] 10.2 Write `test_upload_valid_jpeg`
  - POST a valid 512×512 RGB JPEG to `upload_avatar`
  - Assert HTTP 200, `profile_image` set on user, stored path ends in `.jpg`
  - _Requirements: 4.1, 4.2, 5.1, 5.3_

- [ ] 10.3 Write `test_upload_opaque_png_stored_as_jpeg`
  - POST a valid opaque 512×512 PNG (no alpha)
  - Assert stored path ends in `.jpg` (transparency detection correctly chooses JPEG)
  - _Requirements: 5.3_

- [ ] 10.4 Write `test_upload_transparent_png_stored_as_png`
  - POST a valid 512×512 RGBA PNG
  - Assert stored path ends in `.png`
  - _Requirements: 5.3_

- [ ] 10.5 Write `test_upload_webp_accepted`
  - POST a valid 512×512 WebP image
  - Assert HTTP 200 and `profile_image` set
  - _Requirements: 4.2_

- [ ] 10.6 Write `test_upload_too_large_rejected`
  - POST a file whose `size` exceeds `MAX_UPLOAD_SIZE_BYTES`
  - Assert HTTP 400 with error in response
  - _Requirements: 4.1_

- [ ] 10.7 Write `test_upload_invalid_mime_rejected`
  - POST a file with content type `image/gif`
  - Assert HTTP 400 with error in response
  - _Requirements: 4.2_

- [ ] 10.8 Write `test_upload_corrupt_file_rejected_and_logged`
  - POST a `SimpleUploadedFile` containing random bytes with `content_type='image/jpeg'`
  - Assert HTTP 400
  - Assert a WARNING was logged containing the user's email
  - _Requirements: 4.3_

- [ ] 10.9 Write `test_upload_too_small_rejected`
  - POST a valid 128×128 JPEG
  - Assert HTTP 400 with error in response
  - _Requirements: 4.6_

- [ ] 10.10 Write `test_upload_exactly_min_size_accepted`
  - POST a valid 256×256 JPEG
  - Assert HTTP 200 and `profile_image` set
  - _Requirements: 4.6_

- [ ] 10.11 Write `test_upload_unauthenticated_redirects`
  - POST to `upload_avatar` without a session
  - Assert HTTP 302 redirect to login
  - _Requirements: 4.7_

- [ ] 10.12 Write `test_old_file_deleted_after_new_upload`
  - Upload a first image; record stored path
  - Upload a second image
  - Assert the first file no longer exists in `MEDIA_ROOT`
  - Assert the second file exists
  - _Requirements: 5.7_

- [ ] 10.13 Write `test_old_file_missing_does_not_raise`
  - Set `user.profile_image` to a path that does not exist on disk
  - Upload a new image
  - Assert HTTP 200 and new image saved — deletion failure is swallowed
  - _Requirements: 5.7_

- [ ] 10.14 Write `test_output_is_512x512`
  - Upload a 1024×768 JPEG
  - Open the stored file with Pillow
  - Assert dimensions are exactly 512×512
  - _Requirements: 5.2_

- [ ] 10.15 Write `test_profile_image_url_returns_media_url_when_set`
  - Assign a mock `profile_image` to a user
  - Assert `user.profile_image_url` returns a URL containing `"/media/"`
  - _Requirements: 1.3_

- [ ] 10.16 Write `test_profile_image_url_returns_default_when_unset`
  - User with no `profile_image`
  - Assert `user.profile_image_url` contains `"default_avatar.png"`
  - _Requirements: 1.3, 2.2_

- [ ] 10.17 Write `test_stored_path_contains_user_id`
  - Upload a valid image
  - Assert stored path matches pattern `profile_images/{user.pk}/`
  - _Requirements: 3.4_

---

### Group 11 — Final Verification Checkpoint

- [ ] 11.1 Run full test suite
  ```
  manage.py test marketplace --verbosity=1
  ```
  Expected: all tests pass. Zero failures. Zero errors.
  _Requirements: all_

- [ ] 11.2 Run migration validate
  ```
  manage.py migration_validate --scope all --fail-on-error
  ```
  Expected: all scopes pass.
  _Requirements: 3.2_

- [ ] 11.3 Confirm scope boundaries — no unrelated features included
  - No per-listing image upload added
  - No initials-based avatar generation added
  - No multiple image sizes or thumbnail generation
  - No `django-storages` or S3 integration
  - No image deletion without replacement
  - _Requirements: 9.1–9.7_

- [ ] 11.4 Update `specs/SPEC_ORDER.md` status to `REQ, DES, TASK, EXEC`
  - Update `ai-docs/SESSION_STATUS.md` with implementation summary
