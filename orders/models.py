from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from products.models import Product
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Order(models.Model):
    STATUS_CHOICES = (
        ("PROCESSING", "Processing"),
        ("IN_TRANSIT", "In Transit"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled")
    )

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PROCESSING"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipping_address = models.TextField()
    address = models.ForeignKey(
        "accounts.Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    # Add payment information fields
    card_last_four = models.CharField(max_length=4)
    card_holder = models.CharField(max_length=100)
    expiry_date = models.CharField(max_length=5)  # MM/YY format
    # Add delivery tracking fields
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)  # For product manager approval

    def __str__(self):
        return f"Order {self.id} - {self.user.username}"

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    session_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    def __str__(self):
        return f"Cart for {self.user.username if self.user else self.session_id}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, session_id__isnull=True)
                    | models.Q(user__isnull=True, session_id__isnull=False)
                ),
                name="user_xor_session_id",
            )
        ]


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


@receiver(post_save, sender="orders.Order")
def update_product_sales_count(sender, instance, **kwargs):
    """
    When an order is delivered, update the sales count for all products in the order
    """
    if instance.status == "DELIVERED":
        for item in instance.items.all():
            product = item.product
            product.sales_count += item.quantity
            product.save(update_fields=["sales_count"])

class RefundRequest(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected")
    )

    order_item = models.ForeignKey("OrderItem", on_delete=models.CASCADE, related_name="refund_requests")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="refund_requests")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_refunds"
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    def __str__(self):
        return f"Refund Request #{self.id} - Order Item #{self.order_item_id}"

    def approve(self, sales_manager):
        """Approve the refund request"""
        self.status = "APPROVED"
        self.approved_by = sales_manager
        self.approval_date = timezone.now()
        self.save()

    def reject(self, sales_manager, reason=""):
        """Reject the refund request"""
        self.status = "REJECTED"
        self.approved_by = sales_manager  # Recording who rejected it too
        self.approval_date = timezone.now()
        self.rejection_reason = reason
        self.save()

    class Meta:
        ordering = ['-created_at']
