# Agent Notes — Hard-Won Knowledge

This file captures gotchas, non-obvious patterns, and conventions that are
not evident from reading the code alone. Any AI agent working in this repo
should read this before touching existing code.

**Audience:** All agents (Claude, Codex, and others).
**Maintained by:** Update this file whenever a new gotcha is discovered or
a convention is established. Do not let lessons stay trapped in a session transcript.

---

## Codebase Conventions

### Template blocks in base.html
- `{% block extra_css %}` — inside `<head>` (line ~9)
- `{% block extra_js %}` — just before `</body>` (line ~34)
- There is **no** `{% block head %}` block. Using it silently does nothing.

### Listing URLs (post-Feature 7 cleanup)
- Supply detail: `/available/<pk>/`
- Demand detail: `/wanted/<pk>/`
- The old `/supply/<pk>/` and `/demand/<pk>/` routes were removed in Feature 7
  and no longer exist. Do not reference them anywhere.

### Listing type/status field separation
`Listing.clean()` enforces strict type boundaries:
- Supply listings: `radius_km` and `frequency` must be null/blank; status cannot be `FULFILLED`
- Demand listings: `shipping_scope` and `price_unit` must be blank; status cannot be `WITHDRAWN`
Violating these raises `ValidationError`. Always respect them when creating seed data or test fixtures.

### No role field on User
`User.role` was removed in Feature 7 (migration 0013). There is no buyer/supplier
distinction anywhere in the codebase. Do not reference it, re-add it, or design
features around it.

### Profile image upload path
The `ImageField` has `upload_to="profile_images/"` but the upload view constructs
the full path manually as `profile_images/{user_id}/{uuid}.{ext}` before calling
`profile_image.save()`. The field-level `upload_to` is effectively overridden.

---

## Known Gotchas

### FieldFile.delete(save=False) clears the field on the instance
Calling `some_field_file.delete(save=False)` sets the field back to empty on the
model instance as a side effect — even though `save=False` means "don't write to DB".
**Fix:** Capture the old filename as a plain string first, then delete via
`default_storage.delete(old_name)` directly. See `upload_profile_image` in `views.py`.

### Pillow verify() exhausts the file pointer
After calling `img.verify()`, the file pointer is at EOF.
**Always** call `file.seek(0)` before reopening with `Image.open()` for processing.

### STORAGES must include a "default" key for ImageField
Django's `ImageField` / `FieldFile` uses `STORAGES["default"]`. If `STORAGES` only
defines `"staticfiles"` (e.g. whitenoise only), file uploads crash with
`InvalidStorageError: Could not find config for 'default'`.
Both keys must always be present in `STORAGES`.

### CompressedManifestStaticFilesStorage raises errors in tests
Whitenoise's manifest storage raises `ValueError: Missing staticfiles manifest entry`
in any test that renders a template or calls `static()` if `collectstatic` has never
been run. Fix with `@override_settings` on the test class:
```python
@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
```

### Vector index is not automatically updated by the seeder
`manage.py seed_test_data` writes to the Django database only. The ChromaDB vector
index used by Discover semantic search is **not** updated automatically. After seeding,
the embedding sidecar must be running and you must call:
```bash
.venv/bin/python manage.py rebuild_vector_index
```
`bash qa/full_reset.sh` handles this automatically — it starts the ecosystem, seeds,
and rebuilds the index in the correct order.

### Embedding sidecar cold start takes 60–90 seconds
The SentenceTransformer model loads once at startup. Any script that seeds data and
then immediately tries to rebuild the vector index will fail if it doesn't wait for
the `/health` endpoint to respond first. `full_reset.sh` polls for health before proceeding.

---

## Testing Patterns

### The five-test-class override pattern
Tests that exercise any view rendering a template, or any code that calls `static()`,
need to override `STORAGES` to avoid the CompressedManifestStaticFilesStorage error
described above. See `marketplace/tests/test_profile_image.py` for the established pattern.

### Controlling timestamps in tests
`Message.created_at` and `Listing.created_at` use `auto_now_add=True`. To set
controlled timestamps in tests or seed data, save the object first then update
via `Model.objects.filter(pk=obj.pk).update(created_at=desired_time)`.

---

## Database — PostgreSQL

### DATABASE_URL is required — no SQLite fallback
`config/settings.py` raises `django.core.exceptions.ImproperlyConfigured` at startup
if `DATABASE_URL` is not set. There is no SQLite fallback. Configure it via `.env`
(copy `.env.example` to `.env`). `python-dotenv` loads `.env` automatically — no
manual shell exports needed.

### data/pgdata/ is the Postgres data directory
The Docker container stores its data in `data/pgdata/` (a bind mount). Do not delete
this directory unless you intend to wipe all data. To do a clean wipe:
```bash
bash stop.sh && rm -rf data/pgdata/ && bash qa/full_reset.sh
```

### start.sh manages the full Postgres lifecycle
`start.sh` creates the container on first run, starts it if stopped, and waits for
it to be ready before starting Django. `stop.sh` stops the container. You never need
to run `docker run` or `docker stop` manually.

---

## QA Infrastructure — Quick Reference

| Command | Purpose |
|---------|---------|
| `bash start.sh` | Start full ecosystem (Postgres + all 3 services) |
| `bash stop.sh` | Stop full ecosystem (including Postgres) |
| `bash qa/full_reset.sh` | Complete reset: start + seed + vector index rebuild |
| `bash qa/reset_and_seed.sh` | DB-only reset when ecosystem is already running |
| `.venv/bin/python manage.py seed_test_data` | Seed the database |
| `.venv/bin/python manage.py rebuild_vector_index` | Rebuild ChromaDB index |

Seed account password: **`Seedpass1!`**
See `qa/README.md` for the full personas table and pre-wired relationships.

---

## Feature Status Summary

Features 1–11 complete; Feature 13 (Postgres migration) in progress.
See `specs/SPEC_ORDER.md` for the full list and `ai-docs/SESSION_STATUS.md`
for detailed implementation notes.
