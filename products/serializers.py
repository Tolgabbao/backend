import base64
from rest_framework import serializers
from .models import Product, Category, ProductRating, ProductComment


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]


class ProductSerializer(serializers.ModelSerializer):
    image = serializers.CharField(required=False, write_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "model",
            "serial_number",
            "description",
            "stock_quantity",
            "price",
            "cost_price",
            "warranty_months",
            "category",
            "distributor_info",
            "is_visible",
            "image",
            "image_url",
            "created_at",
            "updated_at",
        ]

    def get_image_url(self, obj):
        if obj.image_data:
            return f"/api/products/{obj.id}/image/"
        return None

    def create(self, validated_data):
        image_data = validated_data.pop("image", None)
        if image_data:
            # Handle base64 encoded image
            format, imgstr = image_data.split(";base64,")
            ext = format.split("/")[-1]
            validated_data["image_data"] = base64.b64decode(imgstr)
            validated_data["image_type"] = f"image/{ext}"
            validated_data["image_name"] = f"product_image.{ext}"
        return super().create(validated_data)

    def update(self, instance, validated_data):
        image_data = validated_data.pop("image", None)
        if image_data:
            # Handle base64 encoded image
            format, imgstr = image_data.split(";base64,")
            ext = format.split("/")[-1]
            instance.image_data = base64.b64decode(imgstr)
            instance.image_type = f"image/{ext}"
            instance.image_name = f"product_image.{ext}"
        return super().update(instance, validated_data)


class ProductRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRating
        fields = ["id", "product", "rating", "created_at"]
        read_only_fields = ["user"]


class ProductCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ProductComment
        fields = ["id", "product", "comment", "is_approved", "created_at", "user_name"]
        read_only_fields = ["user", "is_approved"]
