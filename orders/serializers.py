from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "quantity", "price_at_time"]
        read_only_fields = ["price_at_time"]


class OrderItemCreateSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    items_to_create = OrderItemCreateSerializer(many=True, write_only=True, required=False, source='items')

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "total_amount",
            "created_at",
            "shipping_address",
            "items",
            "items_to_create",
        ]
        read_only_fields = ["user"]

    def validate(self, data):
        # Ensure total_amount is provided
        if 'total_amount' not in data:
            raise serializers.ValidationError({"total_amount": "This field is required."})
        return data

    def create(self, validated_data):
        # Remove items field from validated_data as we'll handle it separately
        validated_data.pop('items', None)
        
        # Create order instance
        order = Order.objects.create(**validated_data)
        return order


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", read_only=True, max_digits=10, decimal_places=2
    )

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_name", "product_price", "quantity"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "items", "total"]

    def get_total(self, obj):
        return sum(item.product.price * item.quantity for item in obj.items.all())
