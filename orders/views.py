from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.http import HttpResponse # Import HttpResponse
from .models import Order, OrderItem, Cart, CartItem, RefundRequest
from products.models import Product
from .serializers import OrderSerializer, CartSerializer
from .tasks import process_order, send_order_status_update, generate_order_pdf # Import generate_order_pdf
from django.utils import timezone
from datetime import datetime
from .serializers import RefundRequestSerializer

# Cache key patterns
# Remove ORDER_LIST_CACHE_KEY_PREFIX and ORDER_DETAIL_CACHE_KEY_PREFIX
CART_CACHE_KEY_PREFIX = "cart_"


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'PRODUCT_MANAGER':
            return Order.objects.all()
        elif user.user_type == 'SALES_MANAGER':
            return Order.objects.all()
        elif user.is_customer():
            return Order.objects.filter(user=user)
        return Order.objects.none()

    # Remove cache decorator
    def list(self, request, *args, **kwargs):
        # Remove cache clearing code
        return super().list(request, *args, **kwargs)

    # Remove cache decorator
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create the order first
        order = serializer.save(user=request.user)

        # Get the items from the request data
        items_data = request.data.get('items', [])

        # Manually create order items
        for item_data in items_data:
            product_id = item_data.get('product')
            quantity = item_data.get('quantity', 1)

            try:
                product = Product.objects.get(id=product_id)
                # Get the current price of the product
                price_at_time = product.price

                # Create the order item
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price_at_time=price_at_time
                )

            except Product.DoesNotExist:
                # Log error but continue processing other items
                print(f"Product with ID {product_id} not found")

        # Remove order list cache clearing

        # Clear cart cache since it will be emptied
        if request.user.is_authenticated:
            cache.delete(f"{CART_CACHE_KEY_PREFIX}user_{request.user.id}")

        # Refresh the order to include created items in the response
        order.refresh_from_db()
        serializer = self.get_serializer(order)

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

        # Remove order cache clearing

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
    @action(detail=True, methods=['get'], url_path='download-invoice')
    def download_invoice(self, request, pk=None):
        """
        Generates and returns the PDF invoice for the order.
        """
        order = self.get_object()

        # Check if the user requesting is the owner of the order, admin/staff, or a manager
        if not (request.user == order.user or
                request.user.is_staff or
                request.user.is_superuser or
                request.user.user_type == 'PRODUCT_MANAGER' or
                request.user.user_type == 'SALES_MANAGER'):
             return Response({"detail": "Not authorized to view this invoice."}, status=status.HTTP_403_FORBIDDEN)

        try:
            pdf_buffer = generate_order_pdf(order)
            response = HttpResponse(pdf_buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="order_{order.id}_invoice.pdf"'
            return response
        except Exception as e:
            # Log the error e
            print(f"Error generating PDF for order {order.id}: {e}")
            return Response({"error": "Failed to generate PDF invoice."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def approve_order(self, request, pk=None):
        """Product manager approves an order for delivery"""
        if request.user.user_type != 'PRODUCT_MANAGER':
            return Response(
                {"error": "Only product managers can approve orders"},
                status=status.HTTP_403_FORBIDDEN
            )

        order = self.get_object()
        order.is_approved = True
        order.status = 'IN_TRANSIT'
        order.save()

        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'])
    def update_delivery_status(self, request, pk=None):
        """Product manager updates delivery status"""
        if request.user.user_type != 'PRODUCT_MANAGER':
            return Response(
                {"error": "Only product managers can update delivery status"},
                status=status.HTTP_403_FORBIDDEN
            )

        order = self.get_object()
        new_status = request.data.get('status')
        delivery_notes = request.data.get('delivery_notes', '')

        if new_status not in dict(Order.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = new_status
        order.delivery_notes = delivery_notes

        if new_status == 'DELIVERED':
            order.delivered_at = timezone.now()

        order.save()

        # Send status update notification
        send_order_status_update.delay(order.id, new_status)

        return Response(self.get_serializer(order).data)

    @action(detail=False, methods=['get'])
    def pending_deliveries(self, request):
        """Get all pending deliveries for product managers"""
        if request.user.user_type != 'PRODUCT_MANAGER':
            return Response(
                {"error": "Only product managers can view pending deliveries"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get all orders with status 'IN_TRANSIT' or 'PROCESSING'
        orders = self.get_queryset().filter(
            status__in=['IN_TRANSIT', 'PROCESSING']
            )
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def sales_report(self, request):
        """Generate sales report for sales managers"""
        if request.user.user_type != 'SALES_MANAGER':
            return Response(
                {"error": "Only sales managers can view sales reports"},
                status=status.HTTP_403_FORBIDDEN
            )

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not start_date or not end_date:
            return Response(
                {"error": "Both start_date and end_date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        orders = self.get_queryset().filter(
            created_at__range=[start_date, end_date],
            status__in=['DELIVERED', 'IN_TRANSIT']
        )

        total_revenue = sum(order.total_amount for order in orders)
        total_cost = sum(
            sum(item.price_at_time * 0.5 * item.quantity for item in order.items.all())
            for order in orders
        )

        report = {
            'total_orders': orders.count(),
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_profit': total_revenue - total_cost,
            'orders': self.get_serializer(orders, many=True).data
        }

        return Response(report)


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
            session_id = getattr(self.request, "cart_session_id", None)
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
                session_id = getattr(request, "cart_session_id", None)
                if not session_id:
                    return Response({"error": "No session ID available"}, status=400)
                cart, _ = Cart.objects.get_or_create(session_id=session_id)
                cache_key = f"{CART_CACHE_KEY_PREFIX}session_{session_id}"

            # Check current quantity in cart for this product
            cart_item = CartItem.objects.filter(cart=cart, product=product).first()
            current_quantity = cart_item.quantity if cart_item else 0
            total_requested = current_quantity + quantity

            if total_requested > product.stock_quantity:
                return Response(
                    {"error": f"Cannot add more than {product.stock_quantity} items to cart. Only {product.stock_quantity - current_quantity} left."},
                    status=400
                )

            # Add or update item in cart
            if cart_item:
                cart_item.quantity = total_requested
                cart_item.save()
            else:
                CartItem.objects.create(cart=cart, product=product, quantity=quantity)

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
                session_id = getattr(request, "cart_session_id", None)
                if not session_id:
                    return Response({"error": "No session ID available"}, status=400)
                cart, _ = Cart.objects.get_or_create(session_id=session_id)
                cache_key = f"{CART_CACHE_KEY_PREFIX}session_{session_id}"

            cart_item = CartItem.objects.filter(cart=cart, product=product).first()
            if cart_item:
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
            session_id = getattr(request, "cart_session_id", None)
            if not session_id:
                return Response({"items": [], "total": 0})
            cart, _ = Cart.objects.get_or_create(session_id=session_id)

        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(
        detail=False, methods=["post"], url_path="update", permission_classes=[AllowAny]
    )
    def update_item(self, request):
        """Update quantity of an item in the cart"""
        product_id = request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1))

        try:
            product = Product.objects.get(id=product_id)

            # Get cart for user or session
            if request.user.is_authenticated:
                cart = Cart.objects.get(user=request.user)
                cache_key = f"{CART_CACHE_KEY_PREFIX}user_{request.user.id}"
            else:
                session_id = getattr(request, "cart_session_id", None)
                if not session_id:
                    return Response({"error": "No session ID available"}, status=400)
                cart = Cart.objects.get(session_id=session_id)
                cache_key = f"{CART_CACHE_KEY_PREFIX}session_{session_id}"

            # Find the cart item
            cart_item = CartItem.objects.filter(cart=cart, product=product).first()

            if not cart_item:
                return Response({"error": "Item not in cart"}, status=404)

            # Check if the requested quantity exceeds available stock
            if quantity > product.stock_quantity:
                return Response(
                    {"error": f"Cannot add more than {product.stock_quantity} items. Only {product.stock_quantity} in stock."},
                    status=400
                )

            # Update quantity
            cart_item.quantity = max(1, quantity)  # Ensure quantity is at least 1
            cart_item.save()

            # Clear cache
            cache.delete(cache_key)

            serializer = CartSerializer(cart)
            return Response(serializer.data)

        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=404)

    @action(detail=False, methods=["post"], url_path="clear")
    def clear_cart(self, request):
        """Clear all items from the cart"""
        try:
            # Get cart based on user or session
            if request.user.is_authenticated:
                cart, _ = Cart.objects.get_or_create(user=request.user)
                cache_key = f"{CART_CACHE_KEY_PREFIX}user_{request.user.id}"
            else:
                session_id = getattr(request, "cart_session_id", None)
                if not session_id:
                    return Response({"error": "No session ID available"}, status=400)
                cart, _ = Cart.objects.get_or_create(session_id=session_id)
                cache_key = f"{CART_CACHE_KEY_PREFIX}session_{session_id}"

            # Delete all items in the cart
            cart.items.all().delete()

            # Clear cache for this cart
            cache.delete(cache_key)

            # Return empty cart
            serializer = CartSerializer(cart)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=400)

class RefundRequestViewSet(viewsets.ModelViewSet):
    serializer_class = RefundRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'SALES_MANAGER':
            # Sales managers can see all refund requests
            return RefundRequest.objects.all()
        elif user.is_customer():
            # Customers can only see their own refund requests
            return RefundRequest.objects.filter(user=user)
        return RefundRequest.objects.none()

    def create(self, request, *args, **kwargs):
        """Create a new refund request"""
        if not request.user.is_customer():
            return Response({
                "error": "Only customers can request refunds"
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Send notification asynchronously (if you have a notification system)
        # notify_sales_managers_of_refund_request.delay(serializer.instance.id)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Customers can only update pending refund requests"""
        refund_request = self.get_object()

        if not request.user.is_customer():
            return Response({
                "error": "Only customers can update refund requests"
            }, status=status.HTTP_403_FORBIDDEN)

        if refund_request.user != request.user:
            return Response({
                "error": "You can only update your own refund requests"
            }, status=status.HTTP_403_FORBIDDEN)

        if refund_request.status != 'PENDING':
            return Response({
                "error": "Only pending refund requests can be updated"
            }, status=status.HTTP_400_BAD_REQUEST)

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Customers can only cancel their own pending refund requests"""
        refund_request = self.get_object()

        if not request.user.is_customer():
            return Response({
                "error": "Only customers can cancel refund requests"
            }, status=status.HTTP_403_FORBIDDEN)

        if refund_request.user != request.user:
            return Response({
                "error": "You can only cancel your own refund requests"
            }, status=status.HTTP_403_FORBIDDEN)

        if refund_request.status != 'PENDING':
            return Response({
                "error": "Only pending refund requests can be canceled"
            }, status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Sales manager approves a refund request"""
        if request.user.user_type != 'SALES_MANAGER':
            return Response({
                "error": "Only sales managers can approve refund requests"
            }, status=status.HTTP_403_FORBIDDEN)

        refund_request = self.get_object()

        if refund_request.status != 'PENDING':
            return Response({
                "error": "Only pending refund requests can be approved"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Approve the refund request
        refund_request.approve(request.user)

        # Send notification asynchronously (if you have a notification system)
        # notify_customer_refund_approved.delay(refund_request.id)

        return Response(self.get_serializer(refund_request).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Sales manager rejects a refund request"""
        if request.user.user_type != 'SALES_MANAGER':
            return Response({
                "error": "Only sales managers can reject refund requests"
            }, status=status.HTTP_403_FORBIDDEN)

        refund_request = self.get_object()
        rejection_reason = request.data.get('rejection_reason', '')

        if refund_request.status != 'PENDING':
            return Response({
                "error": "Only pending refund requests can be rejected"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Reject the refund request
        refund_request.reject(request.user, rejection_reason)

        # Send notification asynchronously (if you have a notification system)
        # notify_customer_refund_rejected.delay(refund_request.id)

        return Response(self.get_serializer(refund_request).data)

    @action(detail=False, methods=['get'])
    def pending_refunds(self, request):
        """Get all pending refund requests (for sales managers)"""
        if request.user.user_type != 'SALES_MANAGER':
            return Response({
                "error": "Only sales managers can view pending refunds list"
            }, status=status.HTTP_403_FORBIDDEN)

        # Get all pending refund requests
        refunds = RefundRequest.objects.filter(status='PENDING')
        serializer = self.get_serializer(refunds, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_refunds(self, request):
        """Get all refund requests for the current customer"""
        if not request.user.is_customer():
            return Response({
                "error": "Only customers can view their refunds"
            }, status=status.HTTP_403_FORBIDDEN)

        # Get all refund requests for this customer
        refunds = RefundRequest.objects.filter(user=request.user)
        serializer = self.get_serializer(refunds, many=True)
        return Response(serializer.data)
