from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem
from accounts.models import Address


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
    shipping_address = serializers.CharField(required=False)
    address_id = serializers.IntegerField(write_only=True, required=False)
    total_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=True
    )
    status = serializers.ChoiceField(
        choices=Order.STATUS_CHOICES, default="PROCESSING", read_only=True
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    user = serializers.HiddenField(
        default=serializers.CurrentUserDefault(), write_only=True
    )
    payment_info = serializers.JSONField(write_only=True, required=True)
    card_last_four = serializers.CharField(max_length=4, write_only=True, required=False)
    card_holder = serializers.CharField(max_length=100, write_only=True, required=False)
    expiry_date = serializers.CharField(max_length=5, write_only=True, required=False)  # MM/YY format
    address_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "total_amount",
            "created_at",
            "shipping_address",
            "address_id",
            "address_details",
            "items",
            "items_to_create",
            "user",
            "card_last_four",
            "card_holder",
            "expiry_date",
            "updated_at",
            "payment_info",
        ]
        read_only_fields = ["user", "status", "created_at", "updated_at"]
        
    def get_address_details(self, obj):
        if obj.address:
            return {
                "id": obj.address.id,
                "name": obj.address.name,
                "street_address": obj.address.street_address,
                "city": obj.address.city,
                "state": obj.address.state,
                "postal_code": obj.address.postal_code,
                "country": obj.address.country
            }
        return None

    def validate(self, data):
        # Ensure total_amount is provided
        if 'total_amount' not in data:
            raise serializers.ValidationError({"total_amount": "This field is required."})

        # Extract payment info from the nested JSON
        if 'payment_info' in data:
            payment_info = data.pop('payment_info')
            data['card_last_four'] = payment_info.get('card_last_four')
            data['card_holder'] = payment_info.get('card_holder')
            data['expiry_date'] = payment_info.get('expiry_date')
        
        # Validate address_id if provided
        user = self.context['request'].user
        address_id = data.get('address_id')
        
        if address_id:
            try:
                # Ensure the address belongs to the user
                address = Address.objects.get(id=address_id, user=user)
                data['address'] = address
            except Address.DoesNotExist:
                raise serializers.ValidationError({
                    "address_id": "Address not found or does not belong to the user."
                })
        elif 'address_id' not in self.initial_data:
            # Only auto-assign if the user hasn't explicitly set address_id to null
            # If no address_id provided, try to use the user's main address
            main_address = user.get_main_address()
            if main_address:
                data['address'] = main_address
        
        # Ensure shipping_address is provided or can be derived from address
        if not data.get('shipping_address') and 'address' in data:
            address = data['address']
            data['shipping_address'] = f"{address.street_address}, {address.city}, {address.state}, {address.postal_code}, {address.country}"
        elif not data.get('shipping_address'):
            raise serializers.ValidationError({"shipping_address": "This field is required when no address is provided."})
        
        return data

    def create(self, validated_data):
        # Remove items field from validated_data as we'll handle it separately
        validated_data.pop('items', None)
        
        # Remove address_id as we've already set the address object in validate
        validated_data.pop('address_id', None)
        
        # shipping_address is now handled in validate method

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
