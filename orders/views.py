from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import Order, Cart, CartItem
from products.models import Product
from .serializers import OrderSerializer, CartSerializer


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_customer():
            return Order.objects.filter(user=user)
        return Order.objects.all()

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

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Cart.objects.filter(user=self.request.user)
        return Cart.objects.filter(session_id=self.request.session.session_key)


@api_view(["POST"])
def add_item(request):
    product_id = request.data.get("product_id")
    quantity = request.data.get("quantity", 1)

    try:
        product = Product.objects.get(id=product_id)
        cart = Cart.objects.get_or_create(user=request.user)[0]

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        serializer = CartSerializer(cart)
        return Response(serializer.data)

    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )
