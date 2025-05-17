from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Category, ProductRating, ProductComment, ProductImage
from django import forms


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1  # Number of empty forms to display
    fields = ("image", "alt_text", "is_primary", "image_preview")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="auto" />', obj.image.url
            )
        return "No image"


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = [
        "name",
        "model",
        "price",
        "stock_quantity",
        "is_visible",
        "thumbnail",
    ]
    list_filter = ["category", "is_visible"]
    search_fields = ["name", "model", "serial_number"]
    inlines = [ProductImageInline]

    @admin.display(description="Image")
    def thumbnail(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()

        if primary_image and primary_image.image:
            return format_html(
                '<img src="{}" width="50" height="50" />', primary_image.image.url
            )

        # Fall back to first image
        first_image = obj.images.first()
        if first_image and first_image.image:
            return format_html(
                '<img src="{}" width="50" height="50" />', first_image.image.url
            )

        return "No image"

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "model", "serial_number", "description", "category")},
        ),
        (
            "Pricing and Stock",
            {"fields": ("price", "cost_price", "stock_quantity", "warranty_months")},
        ),
        ("Additional Information", {"fields": ("distributor_info", "is_visible")}),
    )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ["id", "product", "is_primary", "image_thumbnail", "upload_date"]
    list_filter = ["is_primary", "upload_date"]
    search_fields = ["product__name", "alt_text"]

    @admin.display(description="Thumbnail")
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="auto" />', obj.image.url
            )
        return "No image"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name"]


@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "created_at"]
    list_filter = ["rating"]
    search_fields = ["product__name", "user__username"]


@admin.register(ProductComment)
class ProductCommentAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "comment_excerpt", "is_approved", "created_at"]
    list_filter = ["is_approved", "created_at"]
    search_fields = ["product__name", "user__username", "comment"]
    list_editable = ["is_approved"]
    actions = ["approve_comments"]
    
    def comment_excerpt(self, obj):
        if len(obj.comment) > 50:
            return f"{obj.comment[:50]}..."
        return obj.comment
    comment_excerpt.short_description = "Comment"
    
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} comment(s) have been approved.")
    approve_comments.short_description = "Approve selected comments"
