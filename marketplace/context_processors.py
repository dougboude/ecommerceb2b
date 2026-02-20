def skin(request):
    if hasattr(request, "user") and request.user.is_authenticated:
        skin_name = request.user.skin or "warm-editorial"
    else:
        skin_name = "warm-editorial"
    return {"skin_css": f"css/skin-{skin_name}.css"}


def nav_section(request):
    """Provide the current nav section name based on the URL path."""
    path = request.path
    if path == "/":
        return {"nav_section": "dashboard"}
    prefix_map = [
        ("/discover", "discover"),
        ("/watchlist", "watchlist"),
        ("/profile", "profile"),
        ("/demands", "listings"),
        ("/supply", "listings"),
        ("/threads", "watchlist"),
    ]
    for prefix, section in prefix_map:
        if path.startswith(prefix):
            return {"nav_section": section}
    return {"nav_section": ""}
