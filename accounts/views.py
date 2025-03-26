from django.contrib.auth import authenticate, login, logout
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.cache import cache
from .models import User
from .models import Address

# Cache key patterns
USER_CACHE_KEY_PREFIX = "user_profile_"


@api_view(["POST"])
@permission_classes([AllowAny])
def log_in(request):
    email = request.data.get("email")
    password = request.data.get("password")
    user = authenticate(request, email=email, password=password)
    if user is not None:
        login(request, user)
        # When user logs in, set their profile in cache
        cache.set(
            f"{USER_CACHE_KEY_PREFIX}{user.id}",
            {
                "username": user.username,
                "email": user.email,
                "date_joined": user.date_joined,
                "is_staff": user.is_admin,
                "addresses": user.get_addresses(),
                "main_address": user.get_main_address_dict()
            },
            timeout=None,
        )  # No timeout - cleared on logout
        return Response(
            {
                "message": "User authenticated",
                "username": user.username,
                "email": user.email,
                "id": user.id,
                "is_staff": user.is_admin,
                "addresses": user.get_addresses(),
                "main_address": user.get_main_address_dict()
            }
        )
    else:
        return Response({"message": "Invalid credentials"}, status=400)


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

        if cached_user:
            return Response(cached_user)

        # If not in cache, get from DB and cache it
        user_data = {
            "username": request.user.username,
            "email": request.user.email,
            "date_joined": request.user.date_joined,
            "is_staff": request.user.is_admin(),
            "addresses": request.user.get_addresses(),
            "main_address": request.user.get_main_address_dict()
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
        if not username or not password or not email:
            raise ValueError("Invalid data")
        user = User.objects.create_user(
            username=username, password=password, email=email, user_type="CUSTOMER"
        )
        if user:
            # send_welcome_email.delay(user.id, username, email)
            return Response({"message": "User created"})
        return Response({"message": "Invalid data"}, status=400)
    except Exception:
        return Response({"message": f"User already exists, {Exception}"}, status=400)


@api_view(['GET', 'POST'])
def address_list(request):
    """List all addresses or create a new address for the authenticated user"""
    if not request.user.is_authenticated:
        return Response({"message": "User not authenticated"}, status=400)

    if request.method == 'GET':
        addresses = request.user.get_addresses()
        return Response(addresses)

    elif request.method == 'POST':
        try:
            if request.data.get('is_main', False):
                # Unset previous main address
                Address.objects.filter(user=request.user, is_main=True).update(is_main=False)


            # Create a new address
            address = Address(
                user=request.user,
                name=request.data.get('name', ''),
                street_address=request.data.get('street_address', ''),
                city=request.data.get('city', ''),
                state=request.data.get('state', ''),
                postal_code=request.data.get('postal_code', ''),
                country=request.data.get('country', ''),
                is_main=request.data.get('is_main', False)
            )
            address.save()

            # Clear user cache to reflect the address changes
            cache.delete(f"{USER_CACHE_KEY_PREFIX}{request.user.id}")

            return Response({
                "id": address.id,
                "name": address.name,
                "street_address": address.street_address,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "country": address.country,
                "is_main": address.is_main
            }, status=201)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


@api_view(['GET', 'PUT', 'DELETE'])
def address_detail(request, pk):
    """Retrieve, update or delete an address"""
    if not request.user.is_authenticated:
        return Response({"message": "User not authenticated"}, status=400)

    try:
        address = Address.objects.get(pk=pk, user=request.user)
    except Address.DoesNotExist:
        return Response(status=404)

    if request.method == 'GET':
        return Response({
            "id": address.id,
            "name": address.name,
            "street_address": address.street_address,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postal_code,
            "country": address.country,
            "is_main": address.is_main
        })

    elif request.method == 'PUT':
        try:
            # Update address fields
            address.name = request.data.get('name', address.name)
            address.street_address = request.data.get('street_address', address.street_address)
            address.city = request.data.get('city', address.city)
            address.state = request.data.get('state', address.state)
            address.postal_code = request.data.get('postal_code', address.postal_code)
            address.country = request.data.get('country', address.country)
            address.is_main = request.data.get('is_main', address.is_main)
            address.save()

            # Clear user cache to reflect the address changes
            cache.delete(f"{USER_CACHE_KEY_PREFIX}{request.user.id}")

            return Response({
                "id": address.id,
                "name": address.name,
                "street_address": address.street_address,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "country": address.country,
                "is_main": address.is_main
            })
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    elif request.method == 'DELETE':
        # If this is the main address, try to set another address as main
        if address.is_main:
            next_address = Address.objects.filter(user=request.user).exclude(pk=pk).order_by("id").first()
            if next_address:
                next_address.is_main = True
                next_address.save()

        address.delete()

        # Clear user cache to reflect the address changes
        cache.delete(f"{USER_CACHE_KEY_PREFIX}{request.user.id}")

        return Response(status=204)


@api_view(['PUT'])
def set_main_address(request, pk):
    """Set an address as the main address"""
    if not request.user.is_authenticated:
        return Response({"message": "User not authenticated"}, status=400)

    try:
        address = Address.objects.get(pk=pk, user=request.user)

        # Unset all other main addresses
        Address.objects.filter(user=request.user, is_main=True).update(is_main=False)

        # Set new main address
        address.is_main = True
        address.save()

        cache.delete(f"{USER_CACHE_KEY_PREFIX}{request.user.id}")

        return Response({"message": "Address set as main"})
    except Address.DoesNotExist:
        return Response(status=404)
