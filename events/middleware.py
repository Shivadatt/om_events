class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://*.supabase.co https://*.googleapis.com https://firebasestorage.googleapis.com; "
            "script-src 'self'; "
            "connect-src 'self' https://*.supabase.co https://*.googleapis.com; "
            "media-src 'self' https://*.supabase.co;",
        )
        if request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store, max-age=0"
        return response
