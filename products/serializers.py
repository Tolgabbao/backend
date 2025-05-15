from rest_framework import serializers
from .models import Product, Category, ProductRating, ProductComment, ProductImage, Wishlist


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images"""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image", "image_url", "alt_text", "is_primary", "upload_date"]
        read_only_fields = ["upload_date"]
        extra_kwargs = {
            "image": {
                "write_only": True
            }  # Image file is write-only, URL is for reading
        }

    def get_image_url(self, obj):
        if obj.image:
            # Return the absolute URL, not just the relative path
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=True,
        required=False,
    )
    average_rating = serializers.FloatField(read_only=True)
    is_visible = serializers.BooleanField(default=True)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    price_approved = serializers.BooleanField(default=False, read_only=True)
    has_discount = serializers.BooleanField(read_only=True)
    in_wishlist = serializers.SerializerMethodField(read_only=True)

    # Multiple images handling
    images = ProductImageSerializer(many=True, read_only=True)
    main_image_url = serializers.SerializerMethodField()    # New image upload field for creating products with images
    image_upload = serializers.ImageField(required=False, write_only=True)
    
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
            "original_price",
            "discount_percent",
            "has_discount",
            "cost_price",
            "warranty_months",
            "category",
            "category_id",
            "distributor_info",
            "is_visible",
            "price_approved",
            "average_rating",
            "images",
            "main_image_url",
            "image_upload",
            "created_at",
            "updated_at",
            "in_wishlist",        ]
        extra_kwargs = {"is_visible": {"write_only": True}}
        
    def get_main_image_url(self, obj):
        # Return the absolute URL for the main image
        if obj.main_image:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.main_image)
        return obj.main_image
    
    def get_in_wishlist(self, obj):
        """Check if the product is in the user's wishlist"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Wishlist.objects.filter(user=request.user, product=obj).exists()
        return False

    def create(self, validated_data):
        # Handle image upload if provided
        image_file = validated_data.pop("image_upload", None)
        product = super().create(validated_data)

        # Create product image if an image was uploaded
        if image_file:
            ProductImage.objects.create(
                product=product,
                image=image_file,
                is_primary=True,
                alt_text=product.name,
            )

        return product

    def update(self, instance, validated_data):
        # Handle image upload if provided
        image_file = validated_data.pop("image_upload", None)
        product = super().update(instance, validated_data)

        # Update/create product image if an image was uploaded
        if image_file:
            # If there's already a primary image, update it
            primary_image = ProductImage.objects.filter(
                product=product, is_primary=True
            ).first()
            if primary_image:
                primary_image.image = image_file
                primary_image.save()
            else:
                # Otherwise create a new primary image
                ProductImage.objects.create(
                    product=product,
                    image=image_file,
                    is_primary=True,
                    alt_text=product.name,
                )

        return product

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Ensure is_visible is always present in the response
        if "is_visible" not in representation:
            representation["is_visible"] = (
                instance.is_visible if hasattr(instance, "is_visible") else False
            )

        return representation


class ProductRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRating
        fields = ["id", "product", "rating", "created_at"]
        read_only_fields = ["user", "product"]  # Make product read-only as we'll set it in the view


class ProductCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ProductComment
        fields = ["id", "product", "comment", "is_approved", "created_at", "user_name"]
        read_only_fields = ["user", "is_approved", "product"]  # Add product to read-only fields


class WishlistSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source="product", read_only=True)
    
    class Meta:
        model = Wishlist
        fields = ["id", "user", "product", "product_details", "created_at"]
        read_only_fields = ["user", "created_at"]
        extra_kwargs = {"product": {"write_only": True}}
