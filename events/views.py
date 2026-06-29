from html import escape

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import DecorationItem
from .firebase_supabase import get_firestore_client


def home(request):
    return render(request, "index.html", {"business_phone": settings.BUSINESS_PHONE})


def studio(request):
    return render(request, "admin.html")


def docs(request):
    return render(request, "docs.html")


def item_visual(request, slug):
    item = None
    db = get_firestore_client()
    if db is not None:
        try:
            doc = db.collection("items").document(slug).get()
            if doc.exists:
                d = doc.to_dict()
                
                class CategoryObject:
                    def __init__(self, name, slug):
                        self.name = name
                        self.slug = slug

                class ItemObject:
                    def __init__(self, data):
                        self.name = data["name"]
                        self.category = CategoryObject(
                            data.get("category_id", "").title(), 
                            data.get("category_id", "")
                        )
                item = ItemObject(d)
        except Exception:
            pass

    if item is None:
        item = get_object_or_404(DecorationItem.objects.select_related("category"), slug=slug, is_active=True)

    palettes = {
        "birthday": ("#f0b3be", "#8bc1c5", "#f9dd9a"), "wedding": ("#c39463", "#f1e3cf", "#7c493d"),
        "baby": ("#a7c8c5", "#eee1cf", "#d8a7ac"), "corporate": ("#7782ad", "#c5a96e", "#232d35"),
        "proposal": ("#b96362", "#e9b8a5", "#48343f"), "entries": ("#9b81af", "#d4ad63", "#303344"),
    }
    a, b, c = palettes.get(item.category.slug, ("#bd976c", "#8ba4a0", "#303b38"))
    title, category = escape(item.name.upper()), escape(item.category.name)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 850" role="img" aria-label="{title}">
    <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{a}"/><stop offset="1" stop-color="{c}"/></linearGradient>
    <radialGradient id="glow"><stop stop-color="{b}" stop-opacity=".95"/><stop offset="1" stop-color="{b}" stop-opacity="0"/></radialGradient>
    <filter id="blur"><feGaussianBlur stdDeviation="18"/></filter><pattern id="grain" width="80" height="80" patternUnits="userSpaceOnUse"><circle cx="10" cy="12" r="1" fill="white" opacity=".2"/><circle cx="62" cy="48" r="1.2" fill="white" opacity=".14"/></pattern></defs>
    <rect width="1200" height="850" fill="url(#bg)"/><rect width="1200" height="850" fill="url(#grain)"/><circle cx="950" cy="170" r="330" fill="url(#glow)" filter="url(#blur)"/>
    <path d="M0 650 Q230 510 450 645 T890 620 T1200 590 V850 H0Z" fill="#17221f" opacity=".58"/>
    <path d="M360 650 V330 Q600 145 840 330 V650" fill="none" stroke="{b}" stroke-width="22" opacity=".85"/><path d="M435 650 V365 Q600 240 765 365 V650" fill="#f8f0e6" opacity=".18"/>
    <g fill="{b}" opacity=".9"><circle cx="350" cy="345" r="56"/><circle cx="414" cy="285" r="42"/><circle cx="480" cy="246" r="52"/><circle cx="720" cy="246" r="52"/><circle cx="786" cy="285" r="42"/><circle cx="850" cy="345" r="56"/></g>
    <g fill="{a}" opacity=".8"><circle cx="323" cy="410" r="38"/><circle cx="877" cy="410" r="38"/><circle cx="540" cy="220" r="35"/><circle cx="660" cy="220" r="35"/></g>
    <g stroke="{b}" stroke-width="4" opacity=".8"><path d="M174 560 V300"/><path d="M1026 560 V300"/></g><g fill="{b}"><circle cx="174" cy="290" r="18"/><circle cx="1026" cy="290" r="18"/></g>
    <text x="600" y="445" text-anchor="middle" fill="#fffaf2" font-family="Georgia,serif" font-size="42" letter-spacing="7">{title}</text>
    <text x="600" y="500" text-anchor="middle" fill="#fffaf2" opacity=".72" font-family="Arial,sans-serif" font-size="18" letter-spacing="5">{category}</text></svg>"""
    response = HttpResponse(svg, content_type="image/svg+xml")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def robots(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    return HttpResponse(f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nSitemap: {sitemap_url}", content_type="text/plain")


def sitemap(request):
    pages = [request.build_absolute_uri(reverse("home")), request.build_absolute_uri(reverse("docs"))]
    body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(
        f"<url><loc>{escape(page)}</loc></url>" for page in pages
    ) + "</urlset>"
    return HttpResponse(body, content_type="application/xml")


def error_404(request, exception):
    return render(request, "error.html", {"code": 404, "message": "This celebration has moved."}, status=404)


def error_500(request):
    return render(request, "error.html", {"code": 500, "message": "Something went off-script. We’re fixing it."}, status=500)
