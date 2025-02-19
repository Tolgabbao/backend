from rest_framework import serializers
from .models import Product, Category, ProductRating, ProductComment


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]


class ProductSerializer(serializers.ModelSerializer):
    average_rating = serializers.FloatField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

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
            "warranty_months",
            "category",
            "category_name",
            "distributor_info",
            "average_rating",
        ]


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
