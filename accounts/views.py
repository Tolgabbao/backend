from django.contrib.auth import authenticate, login, logout
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import User

from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes

# Create your views here.

# login shouldnt need authentication


@api_view(["POST"])
@permission_classes([AllowAny])
def log_in(request):
    email = request.data.get("email")
    password = request.data.get("password")
    user = authenticate(request, email=email, password=password)
    if user is not None:
        login(request, user)
        return Response(
            {
                "message": "User authenticated",
                "username": user.username,
                "email": user.email,
                "id": user.id,
            }
        )
    else:
        return Response(
            {"message": f"Invalid credentials 2 + {email + password}"}, status=400
        )


@api_view(["POST"])
def log_out(request):
    logout(request)
    return Response({"message": "User logged out"})


@api_view(["GET"])
def get_user(request):
    if request.user.is_authenticated:
        return Response({"username": request.user.username,
                         "email": request.user.email,
                         "date_joined": request.user.date_joined,})
    return Response({"message": "User not authenticated"}, status=400)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email")
    try:
        user = User.objects.create_user(
            username=username, password=password, email=email
        )
        if user:
            return Response({"message": "User created"})
        return Response({"message": "Invalid data"}, status=400)
    except Exception:
        return Response({"message": "User already exists"}, status=400)
