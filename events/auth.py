from datetime import datetime, timezone
from functools import wraps

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse


def issue_access_token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": str(user.pk), "email": user.email, "name": user.get_full_name() or user.username,
        "role": "admin" if user.is_staff else "user", "iat": now,
        "exp": now + settings.JWT_ACCESS_LIFETIME,
    }, settings.JWT_SECRET_KEY, algorithm="HS256")


def admin_jwt_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return JsonResponse({"error": "Authentication credentials were not provided."}, status=401)
        try:
            payload = jwt.decode(authorization[7:], settings.JWT_SECRET_KEY, algorithms=["HS256"])
            user = get_user_model().objects.get(pk=int(payload["sub"]), is_active=True)
        except (jwt.PyJWTError, ValueError, KeyError, get_user_model().DoesNotExist):
            return JsonResponse({"error": "Invalid or expired access token."}, status=401)
        if not user.is_staff:
            return JsonResponse({"error": "Administrator access required."}, status=403)
        request.jwt_user = user
        return view(request, *args, **kwargs)
    return wrapped

