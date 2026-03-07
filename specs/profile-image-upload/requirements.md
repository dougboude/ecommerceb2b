# Requirements Document

## Introduction

This spec implements a reusable image upload pipeline, starting with user profile images. Users may upload a profile photo that appears on their profile page, on listing detail pages, and in message threads. The design uses Django's storage abstraction so the backend can later be swapped to S3 or another object store without code changes.

This is the first image feature in the product. The pipeline established here (upload, validate, process, store) is designed to be reused for listing images in a future spec without architectural changes.

## State Assumptions

| Assumption | Required State | Fail Condition |
|---|---|---|
| Foundation complete | CP5 achieved | Block execution if `MigrationState.checkpoint_order < 5` |
| Pillow available | Installable in `.venv` | Block if `import PIL` fails |
| Feature 9 complete | `email-verification-and-account-activation` is `EXEC` | Block if Feature 9 is not marked `EXEC` in `specs/SPEC_ORDER.md` |

**Pre-execution gate (run before any task begins):**
```python
manage.py shell -c "
from marketplace.migration_control.state import get_or_create_state
s = get_or_create_state()
assert s.checkpoint_order == 5, f'CP5 required, got CP{s.checkpoint_order}'
print('Gate 1 OK — CP5 confirmed')

try:
    import PIL
    print('Gate 2 OK — Pillow available')
except ImportError:
    raise AssertionError('Pillow not installed — run: .venv/bin/pip install Pillow')
"
```

## Dependencies

- **Required predecessor specs:** all foundation specs 1–7 (`EXEC`), Features 8–9 (`EXEC`)
- **New dependency:** Pillow must be added to project requirements
- **New settings:** `MEDIA_ROOT`, `MEDIA_URL` must be configured
- Changes are additive only — no destructive schema changes

## Glossary

- **Profile image:** A single image uploaded by a user, stored as a normalized 512×512 derivative. Surfaces on profile page, listing detail, and message threads.
- **Canonical derivative:** The processed output image (512×512, JPEG or PNG) stored by the server. The original upload is discarded.
- **Opaque image:** An image with no alpha channel — stored as JPEG.
- **Transparent image:** An image with an alpha channel (RGBA, LA, or PA mode) — stored as PNG to preserve transparency.
- **Default avatar:** A static placeholder image shown when a user has no uploaded profile image.
- **Crop blob:** The pre-cropped square image produced client-side via the Canvas API before POSTing to the server.

---

## Requirements

### Requirement 1: User Model — Profile Image Fields

**User Story:** As a platform architect, I want the User model to carry a profile image field so that the image is associated with the user record and accessible anywhere the user object is available.

#### Acceptance Criteria

1. THE `User` model SHALL add a nullable `ImageField` named `profile_image` with `upload_to="profile_images/{user_id}/"`, `null=True`, `blank=True`.
2. THE `User` model SHALL add a nullable `DateTimeField` named `profile_image_updated_at` (`null=True`, `blank=True`) updated by the upload view each time a new image is stored.
3. THE `User` model SHALL expose a `profile_image_url` property that returns `self.profile_image.url` when an image is set, and the URL of the static default avatar (`static/img/default_avatar.png`) when no image is set.
4. All templates that display a user avatar SHALL use `user.profile_image_url` (or the equivalent context variable) rather than accessing `user.profile_image.url` directly, so the null case is never handled in templates.
5. THE migration for these fields SHALL be additive only — no existing fields altered or dropped.

---

### Requirement 2: Default Avatar Fallback

**User Story:** As a user viewing profiles, listings, or messages, I want to see a neutral placeholder when another user has not uploaded a photo, so the UI never shows a broken image.

#### Acceptance Criteria

1. A static placeholder image SHALL exist at `static/img/default_avatar.png` — a simple neutral silhouette suitable for circular display.
2. `User.profile_image_url` SHALL return the static URL for this placeholder when `profile_image` is falsy.
3. The placeholder SHALL be served by the static file pipeline (not the media pipeline) and SHALL NOT require storage configuration to function.
4. The placeholder SHALL display correctly when rendered as a circle via CSS `border-radius: 50%`.

---

### Requirement 3: Storage Configuration

**User Story:** As a developer, I want storage configured through Django's abstraction layer so that switching to S3 later requires only a settings change.

#### Acceptance Criteria

1. `settings.py` SHALL define `MEDIA_ROOT` (defaulting to a `media/` directory under the project root) and `MEDIA_URL` (defaulting to `/media/`), both overridable via environment variables.
2. The default storage backend SHALL be `django.core.files.storage.FileSystemStorage`. No `django-storages` dependency is required for V1.
3. All file writes SHALL go through Django's storage API (`storage.save()`, `storage.delete()`, `FieldFile.url`) — no direct `open()` or `os.path` file operations in the upload pipeline.
4. The upload path pattern SHALL be `profile_images/{user_id}/{uuid}.{ext}` where `user_id` is the integer PK of the uploading user, `uuid` is a server-generated UUID4, and `ext` is `jpg` or `png` determined by transparency detection (see Req 5).
5. In development, Django's `runserver` SHALL serve media files via the `MEDIA_URL` prefix using `django.views.static.serve`.

---

### Requirement 4: Upload Validation and Security

**User Story:** As a security-conscious developer, I want all uploaded images validated and sanitized before storage so that malicious files cannot be stored or served.

#### Acceptance Criteria

1. THE upload view SHALL reject any file exceeding **5 MB** before passing it to Pillow. The response SHALL be a form error, not a 500.
2. THE upload view SHALL reject files whose reported content type is not one of: `image/jpeg`, `image/png`, `image/webp`. The response SHALL be a form error.
3. After content-type pre-screening, the file SHALL be opened with Pillow and verified with `image.verify()`. Any file Pillow cannot parse as a valid image SHALL be rejected with a form error.
4. THE original filename provided by the client SHALL be discarded entirely. The stored filename SHALL always be a server-generated UUID4 with the extension determined by the pipeline, never derived from client input.
5. All uploads SHALL be re-encoded through Pillow unconditionally before storage. This re-encoding serves as the primary security control: it strips EXIF metadata and defuses parser-level exploits regardless of the source format.
6. THE upload endpoint SHALL require an authenticated session. Unauthenticated requests SHALL receive a 302 redirect to login.

---

### Requirement 5: Image Processing Pipeline

**User Story:** As a platform architect, I want all stored profile images normalized to a canonical format so that display is consistent and predictable across the product.

#### Acceptance Criteria

1. THE pipeline SHALL produce exactly one stored derivative per upload. The original upload file SHALL NOT be retained.
2. THE canonical output size SHALL be **512 × 512 pixels**, square.
3. THE pipeline SHALL detect transparency before re-encoding:
   - If the image mode is `RGBA`, `LA`, or `PA`, output SHALL be **PNG**.
   - Otherwise, the image SHALL be converted to `RGB` and output SHALL be **JPEG at quality 85**.
4. THE pipeline SHALL strip all EXIF and metadata. This is achieved implicitly by re-encoding through Pillow — no explicit EXIF removal step is required beyond the re-encode.
5. THE output image SHALL use the sRGB color space. Images in other color spaces SHALL be converted during re-encoding.
6. THE pipeline SHALL accept the crop region as a parameter (pixel coordinates of the square crop within the pre-cropped blob received from the client). If no crop coordinates are provided, the pipeline SHALL center-crop to square before resizing.
7. When a user uploads a new profile image, the pipeline SHALL delete the previously stored file from the storage backend before saving the new file. If the old file does not exist on the storage backend, the deletion failure SHALL be logged and silently swallowed — it SHALL NOT prevent the new image from being saved.

---

### Requirement 6: Cropping UX

**User Story:** As a user uploading a profile photo, I want an in-browser crop tool so I can choose exactly which part of my photo to use as my avatar before it is saved.

#### Acceptance Criteria

1. THE profile edit page SHALL include an image upload control that, on file selection, opens a crop modal without a page navigation.
2. THE crop modal SHALL display the selected image with a **square crop box** that the user can drag and resize.
3. THE crop modal SHALL display a **circular preview** of the current crop selection so the user can see how the avatar will appear. The circle is a CSS effect — the stored image is always square.
4. On confirmation, the client SHALL use the **Canvas API** to produce a square image blob from the selected crop region and POST that blob to the upload endpoint. The original file SHALL NOT be uploaded to the server.
5. THE crop tool SHALL be implemented using **Cropper.js**, loaded as a static file. No npm build pipeline or bundler is required.
6. THE crop modal SHALL be dismissable (cancel) without saving any changes.
7. After a successful upload, the page SHALL display the new avatar without a full page reload if technically straightforward; a full page reload is acceptable as a fallback.

---

### Requirement 7: Image Surfaces

**User Story:** As a user of the platform, I want to see profile avatars on profiles, listing detail pages, and in message threads so I can identify who I am interacting with.

#### Acceptance Criteria

1. **Profile page** (`/profile/`): THE user's own profile page SHALL display their avatar (or the default placeholder) prominently, with an affordance to upload or change the image.
2. **Listing detail pages** (`/supply/<pk>/` and `/demand/<pk>/`): THE listing owner's avatar SHALL be displayed alongside their name in the listing detail view.
3. **Message thread** (`/threads/<pk>/`): Each message SHALL display the sender's avatar (or placeholder) alongside the message body.
4. In all surfaces, avatars SHALL be rendered as circles via CSS `border-radius: 50%` and SHALL use `User.profile_image_url` so the default fallback is applied automatically.
5. Avatar images in message threads and listing detail SHALL be rendered at a display size appropriate to the context (e.g., 40×40px for message avatars, 64×64px for listing owner). The same 512×512 source file is used in all cases; CSS constrains the display size.

---

### Requirement 8: Settings and Dependencies

**User Story:** As a developer, I want all image-related settings overridable via environment variables so the app behaves correctly in dev, test, and production without code changes.

#### Acceptance Criteria

1. `MEDIA_ROOT` SHALL default to `BASE_DIR / "media"` and be overridable via `os.environ.get("MEDIA_ROOT")`.
2. `MEDIA_URL` SHALL default to `"/media/"` and be overridable via `os.environ.get("MEDIA_URL")`.
3. `MAX_UPLOAD_SIZE_BYTES` SHALL be defined in settings as `5 * 1024 * 1024` (5 MB) and referenced by the upload view — not hardcoded in the view itself.
4. **Pillow** SHALL be added to the project's Python dependencies (`.venv/bin/pip install Pillow`; add to `requirements.txt` or equivalent).
5. In the test environment, `MEDIA_ROOT` SHALL be overridden to a temporary directory so uploaded files during tests do not pollute the development media directory.

---

### Requirement 9: Scope Boundaries

The following are explicitly **out of scope** for this spec:

1. Per-listing images (photos of the item being listed) — future spec.
2. Initials-based or dynamically generated avatars — future enhancement to §6.4 in the roadmap.
3. Multiple image sizes or thumbnail generation — single 512×512 derivative only.
4. Image deletion without replacement (a user cannot remove their avatar without uploading a new one — they revert to the default via the placeholder).
5. CDN configuration — `MEDIA_URL` is the only URL surface; CDN prefix is applied at the settings level when needed.
6. Admin UI for reviewing or moderating uploaded images — deferred to operator tools roadmap.
7. `django-storages` or any S3 integration — filesystem only for V1.
