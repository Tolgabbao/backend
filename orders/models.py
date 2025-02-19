from django.db import models
from django.core.validators import MinValueValidator


class Order(models.Model):
    STATUS_CHOICES = (
        ("PROCESSING", "Processing"),
        ("IN_TRANSIT", "In Transit"),
        ("DELIVERED", "Delivered"),
    )

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PROCESSING"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipping_address = models.TextField()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)


class Cart(models.Model):
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, null=True, blank=True
    )
    session_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
