from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ("CUSTOMER", "Customer"),
        ("SALES_MANAGER", "Sales Manager"),
        ("PRODUCT_MANAGER", "Product Manager"),
    )
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    address = models.TextField()
    phone = models.CharField(max_length=15, blank=True)

    @property
    def is_admin(self):
        return (
            1
            if (
                self.user_type in ["SALES_MANAGER", "PRODUCT MANAGER", "ADMIN"]
                or super().is_staff
            )
            else 0
        )

    def is_customer(self):
        return self.user_type == "CUSTOMER"

    def is_sales_manager(self):
        return self.user_type == "SALES_MANAGER"

    def is_product_manager(self):
        return self.user_type == "PRODUCT_MANAGER"
