from django.contrib import admin
from .models import Cart, RefundRequest
# Register your models here.

from .models import Order

admin.site.register(Order)


admin.site.register(Cart)

@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'get_order_id',
        'get_product_name',
        'status',
        'created_at',
        'approved_by'
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'user__username',
        'order_item__order__id',
        'order_item__product__name'
    )

    def get_order_id(self, obj):
        return obj.order_item.order.id
    get_order_id.short_description = 'Order ID'

    def get_product_name(self, obj):
        return obj.order_item.product.name if obj.order_item.product else "Product Removed"
    get_product_name.short_description = 'Product'
