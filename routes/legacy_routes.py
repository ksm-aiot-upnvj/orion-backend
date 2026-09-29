"""
Permanent redirects from pre-refactor API URLs to their clean RESTful replacements,
so existing bookmarks and integrations keep working.

GET/HEAD answer 301; every other method answers 308 so the method and body are preserved.
Must be included before the resource routers so e.g. /members/count is not captured by /members/{identifier}.
"""

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from config.config import settings

# (old path, new path, methods) — path parameters use the same names on both sides
LEGACY_REDIRECTS: list[tuple[str, str, list[str]]] = [
    ("/members/", "/members", ["GET", "POST"]),
    ("/members/count", "/members/stats", ["GET"]),
    ("/members/public/organization", "/members/public", ["GET"]),
    ("/members/import-excel", "/members/imports", ["POST"]),
    ("/members/{identifier}/reset-password", "/members/{identifier}/password", ["POST"]),
    ("/registrations/", "/registrations", ["GET", "POST"]),
    ("/audit-logs/", "/audit-logs", ["GET"]),
    ("/auth/change-password", "/auth/me/password", ["POST"]),
    ("/uploads/avatar", "/uploads/avatars", ["POST"]),
    ("/uploads/cv", "/uploads/cvs", ["POST"]),
    ("/avatars/{filename}", "/uploads/avatars/{filename}", ["GET"]),
    ("/cvs/{filename}", "/uploads/cvs/{filename}", ["GET"]),
    ("/db-test", "/health/db", ["GET"]),
]

router = APIRouter(include_in_schema=False)


def _make_redirect(new_path: str):
    async def redirect(request: Request) -> RedirectResponse:
        params = {key: quote(str(value), safe="") for key, value in request.path_params.items()}
        target = settings.API_V1_STR.rstrip("/") + new_path.format(**params)
        # Read the raw query string: request.url is rebuilt from the decoded path and would misparse %3F
        query = request.scope.get("query_string", b"").decode("latin-1")
        if query:
            target = f"{target}?{query}"
        status_code = 301 if request.method in ("GET", "HEAD") else 308
        return RedirectResponse(url=target, status_code=status_code)

    return redirect


for old_path, new_path, methods in LEGACY_REDIRECTS:
    router.add_api_route(old_path, _make_redirect(new_path), methods=methods)
