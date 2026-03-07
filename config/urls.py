from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("marketplace.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    # WARNING: DEBUG-only — never serve media via Django in production.
    # Use MEDIA_URL with a CDN or object store instead.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
