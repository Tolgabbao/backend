from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Category, ProductRating, ProductComment
import base64
from django import forms


class ProductAdminForm(forms.ModelForm):
    image_upload = forms.ImageField(required=False)

    class Meta:
        model = Product
        exclude = (
            "image_data",
            "image_type",
            "image_name",
        )  # Exclude binary fields from direct editing


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
    readonly_fields = ["image_preview"]

    @admin.display(description="Image")
    def thumbnail(self, obj):
        if obj.image_data:
            image_base64 = base64.b64encode(obj.image_data).decode("utf-8")
            return format_html(
                '<img src="data:{};base64,{}" width="50" height="50" />',
                obj.image_type or "image/jpeg",
                image_base64,
            )
        return "No image"

    @admin.display(description="Image Preview")
    def image_preview(self, obj):
        if obj.image_data:
            image_base64 = base64.b64encode(obj.image_data).decode("utf-8")
            return format_html(
                '<img src="data:{};base64,{}" width="300" />',
                obj.image_type or "image/jpeg",
                image_base64,
            )
        return "No image uploaded"

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get("image_upload"):
            image_file = form.cleaned_data["image_upload"]
            obj.image_data = image_file.read()
            obj.image_type = image_file.content_type
            obj.image_name = image_file.name
        super().save_model(request, obj, form, change)

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "model", "serial_number", "description", "category")},
        ),
        (
            "Pricing and Stock",
            {"fields": ("price", "cost_price", "stock_quantity", "warranty_months")},
        ),
        (
            "Image",
            {
                "fields": (
                    "image_upload",
                    "image_preview",
                )  # Changed from image_data to image_upload
            },
        ),
        ("Additional Information", {"fields": ("distributor_info", "is_visible")}),
    )


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
    list_display = ["product", "user", "is_approved", "created_at"]
    list_filter = ["is_approved"]
    search_fields = ["product__name", "user__username", "comment"]
