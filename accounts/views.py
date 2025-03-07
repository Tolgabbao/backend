from django.contrib.auth import authenticate, login, logout
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.cache import cache
from .models import User
from .tasks import send_welcome_email

# Cache key patterns
USER_CACHE_KEY_PREFIX = 'user_profile_'

@api_view(["POST"])
@permission_classes([AllowAny])
def log_in(request):
    email = request.data.get("email")
    password = request.data.get("password")
    user = authenticate(request, email=email, password=password)
    if user is not None:
        login(request, user)
        # When user logs in, set their profile in cache
        cache.set(f"{USER_CACHE_KEY_PREFIX}{user.id}", {
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined,
            "is_staff": user.is_admin,
        }, timeout=None)  # No timeout - cleared on logout
        return Response(
            {
                "message": "User authenticated",
                "username": user.username,
                "email": user.email,
                "id": user.id,
                "is_staff": user.is_admin,
            }
        )
    else:
        return Response(
            {"message": "Invalid credentials"}, status=400
        )


@api_view(["POST"])
def log_out(request):
    if request.user.is_authenticated:
        # Clear user cache on logout
        cache.delete(f"{USER_CACHE_KEY_PREFIX}{request.user.id}")

    logout(request)
    return Response({"message": "User logged out"})


@api_view(["GET"])
def get_user(request):
    if request.user.is_authenticated:
        # Try to get user data from cache
        cached_user = cache.get(f"{USER_CACHE_KEY_PREFIX}{request.user.id}")

        if (cached_user):
            return Response(cached_user)

        # If not in cache, get from DB and cache it
        user_data = {
            "username": request.user.username,
            "email": request.user.email,
            "date_joined": request.user.date_joined,
            "is_staff": request.user.is_admin(),
        }

        cache.set(f"{USER_CACHE_KEY_PREFIX}{request.user.id}", user_data, timeout=None)
        return Response(user_data)

    return Response({"message": "User not authenticated"}, status=400)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email")
    try:
        user = User.objects.create_user(
            username=username, password=password, email=email, user_type="CUSTOMER"
        )
        if user:
            #send_welcome_email.delay(user.id, username, email)
            return Response({"message": "User created"})
        return Response({"message": "Invalid data"}, status=400)
    except Exception:
        return Response({"message": f"User already exists, {Exception}"}, status=400)
