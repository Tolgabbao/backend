from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ("CUSTOMER", "Customer"),
        ("SALES_MANAGER", "Sales Manager"),
        ("PRODUCT_MANAGER", "Product Manager"),
    )
    email = models.EmailField(unique=True, blank=False)
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

    def get_main_address(self):
        try:
            return self.addresses.get(is_main=True)
        except Address.DoesNotExist:
            # Return the first address or None if no addresses exist
            return self.addresses.first()

    def get_addresses(self):
        """Return a list of address dictionaries"""
        addresses = []
        for address in self.addresses.all():
            addresses.append({
                "id": address.id,
                "name": address.name,
                "street_address": address.street_address,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "country": address.country,
                "is_main": address.is_main
            })
        return addresses

    def get_main_address_dict(self):
        """Return the main address as a dictionary"""
        main_address = self.get_main_address()
        if main_address:
            return {
                "id": main_address.id,
                "name": main_address.name,
                "street_address": main_address.street_address,
                "city": main_address.city,
                "state": main_address.state,
                "postal_code": main_address.postal_code,
                "country": main_address.country,
                "is_main": main_address.is_main
            }
        return None


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    name = models.CharField(max_length=100)  # E.g., "Home", "Work", etc.
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        ordering = ['-is_main', '-updated_at']  # Main address first, then most recently updated

    def __str__(self):
        return f"{self.name} - {self.street_address}, {self.city}"

    def save(self, *args, **kwargs):
        # If this address is being set as main, unset is_main for all other addresses of this user
        if self.is_main:
            Address.objects.filter(user=self.user, is_main=True).update(is_main=False)

        # Save the address first
        super().save(*args, **kwargs)

        # If there are no main addresses after this save, set this or another address as main
        if not Address.objects.filter(user=self.user, is_main=True).exists() and Address.objects.filter(
            user=self.user).exists():
            # If this is the only address, make it the main address
            if Address.objects.filter(user=self.user).count() == 1:
                self.is_main = True
                super().save(update_fields=['is_main'])
            else:
                # Otherwise, set the first address (other than this one) as main
                other_address = Address.objects.filter(user=self.user).exclude(pk=self.pk).first()
                if other_address:
                    other_address.is_main = True
                    other_address.save(update_fields=['is_main'])
