from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import Order, Cart, CartItem
from products.models import Product
from .serializers import OrderSerializer, CartSerializer
from .tasks import process_order, send_order_status_update

# Cache key patterns
ORDER_LIST_CACHE_KEY_PREFIX = 'user_orders_'
ORDER_DETAIL_CACHE_KEY_PREFIX = 'order_detail_'
CART_CACHE_KEY_PREFIX = 'cart_'

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_customer():
            return Order.objects.filter(user=user)
        return Order.objects.all()

    @method_decorator(cache_page(settings.CACHE_TTL))
    def list(self, request, *args, **kwargs):
        # Clear any existing cache for this user's orders
        cache.delete(f"{ORDER_LIST_CACHE_KEY_PREFIX}{request.user.id}")
        return super().list(request, *args, **kwargs)
    
    @method_decorator(cache_page(settings.CACHE_TTL))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(user=request.user)
        
        # Clear order list cache for this user
        cache.delete(f"{ORDER_LIST_CACHE_KEY_PREFIX}{request.user.id}")
        
        # Clear cart cache since it will be emptied
        cache.delete(f"{CART_CACHE_KEY_PREFIX}user_{request.user.id}")
        
        # Process order asynchronously with Celery
        process_order.delay(order.id)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get("status")
        
        if not new_status:
            return Response({"error": "Status is required"}, status=400)
        
        order.status = new_status
        order.save()
        
        # Clear order cache
        cache.delete(f"{ORDER_DETAIL_CACHE_KEY_PREFIX}{order.id}")
        cache.delete(f"{ORDER_LIST_CACHE_KEY_PREFIX}{request.user.id}")
        
        # Send status update asynchronously with Celery
        send_order_status_update.delay(order.id, new_status)
        
        return Response({"status": f"Order status updated to {new_status}"})

    @action(detail=True, methods=["post"])
    def cancel_order(self, request, pk=None):
        order = self.get_object()
        if order.status != "PROCESSING":
            return Response(
                {"error": "Can only cancel orders in processing status"}, status=400
            )
        order.status = "CANCELLED"
        order.save()
        return Response({"status": "order cancelled"})


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [AllowAny]  # Allow anonymous users
    
    def get_queryset(self):
        if self.request.user.is_authenticated:
            # Get cart for authenticated user
            cart, _ = Cart.objects.get_or_create(user=self.request.user)
            return Cart.objects.filter(id=cart.id)
        else:
            # Get cart for anonymous user with session ID
            session_id = getattr(self.request, 'cart_session_id', None)
            if session_id:
                cart, _ = Cart.objects.get_or_create(session_id=session_id)
                return Cart.objects.filter(id=cart.id)
        return Cart.objects.none()
    
    @action(detail=False, methods=["post"], url_path="add")
    def add_item(self, request):
        product_id = request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1))
        
        if not product_id:
            return Response({"error": "Product ID is required"}, status=400)
            
        try:
            product = Product.objects.get(id=product_id)
            
            # Get or create cart based on user or session
            if request.user.is_authenticated:
                cart, _ = Cart.objects.get_or_create(user=request.user)
                cache_key = f"{CART_CACHE_KEY_PREFIX}user_{request.user.id}"
            else:
                session_id = getattr(request, 'cart_session_id', None)
                if not session_id:
                    return Response({"error": "No session ID available"}, status=400)
                cart, _ = Cart.objects.get_or_create(session_id=session_id)
                cache_key = f"{CART_CACHE_KEY_PREFIX}session_{session_id}"
            
            # Add or update item in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart, product=product, defaults={"quantity": quantity}
            )
            
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
                
            # Clear cache
            cache.delete(cache_key)
            
            serializer = CartSerializer(cart)
            return Response(serializer.data)
            
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)
    
    @action(detail=False, methods=["post"], url_path="remove")
    def remove_item(self, request):
        product_id = request.data.get("product_id")
        try:
            product = Product.objects.get(id=product_id)
            
            # Get or create cart based on user or session
            if request.user.is_authenticated:
                cart, _ = Cart.objects.get_or_create(user=request.user)
                cache_key = f"{CART_CACHE_KEY_PREFIX}user_{request.user.id}"
            else:
                session_id = getattr(request, 'cart_session_id', None)
                if not session_id:
                    return Response({"error": "No session ID available"}, status=400)
                cart, _ = Cart.objects.get_or_create(session_id=session_id)
                cache_key = f"{CART_CACHE_KEY_PREFIX}session_{session_id}"
            
            cart_item = CartItem.objects.filter(cart=cart, product=product).first()
            if (cart_item):
                cart_item.delete()

            # Clear cart cache for this user
            cache.delete(cache_key)

            serializer = CartSerializer(cart)
            return Response(serializer.data)

        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"], url_path="items")
    def get_items(self, request):
        # Get cart based on user or session
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)
        else:
            session_id = getattr(request, 'cart_session_id', None)
            if not session_id:
                return Response({"items": [], "total": 0})
            cart, _ = Cart.objects.get_or_create(session_id=session_id)
        
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="update", permission_classes=[AllowAny])
    def update_item(self, request):
        """Update quantity of an item in the cart"""
        product_id = request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1))
        
        try:
            product = Product.objects.get(id=product_id)
            
            # Get cart for user or session
            if request.user.is_authenticated:
                cart = Cart.objects.get(user=request.user)
            else:
                session_id = getattr(request, 'cart_session_id', None)
                if not session_id:
                    return Response({"error": "No session ID available"}, status=400)
                cart = Cart.objects.get(session_id=session_id)
            
            # Find the cart item
            cart_item = CartItem.objects.filter(cart=cart, product=product).first()
            
            if not cart_item:
                return Response({"error": "Item not in cart"}, status=404)
            
            # Update quantity
            cart_item.quantity = max(1, quantity)  # Ensure quantity is at least 1
            cart_item.save()
            
            # Clear cache
            if request.user.is_authenticated:
                cache.delete(f"cart_user_{request.user.id}")
            else:
                cache.delete(f"cart_session_{getattr(request, 'cart_session_id', '')}")
            
            serializer = CartSerializer(cart)
            return Response(serializer.data)
            
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=404)
