from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Order, OrderItem
from products.models import Product, Category
from accounts.models import Address

User = get_user_model()

class OrderAddressTestCase(APITestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
            user_type="CUSTOMER",
            address="Default Address"
        )
        
        # Create an address for the user
        self.address = Address.objects.create(
            user=self.user,
            name="Home",
            street_address="123 Test Street",
            city="Test City",
            state="Test State",
            postal_code="12345",
            country="Test Country",
            is_main=True
        )
        
        # Create a category for the product
        self.category = Category.objects.create(
            name="Test Category",
            description="Test Category Description"
        )
        
        # Create a product
        self.product = Product.objects.create(
            name="Test Product",
            model="Test Model",
            serial_number="TEST123456",
            description="Test Description",
            price=10.00,
            cost_price=5.00,
            stock_quantity=10,
            category=self.category,
            distributor_info="Test Distributor"
        )
        
        # Authenticate the client
        self.client.force_authenticate(user=self.user)
    
    def test_create_order_with_address(self):
        """Test that an order can be created with an address"""
        order_data = {
            "total_amount": "10.00",
            "shipping_address": "Custom Address",
            "address_id": self.address.id,
            "items": [
                {
                    "product": self.product.id,
                    "quantity": 1
                }
            ],
            "payment_info": {
                "card_last_four": "1234",
                "card_holder": "Test User",
                "expiry_date": "12/25"
            }
        }
        
        url = reverse("order-list")
        response = self.client.post(url, order_data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 1)
        
        # Verify order has address linked
        order = Order.objects.first()
        self.assertEqual(order.address.id, self.address.id)
        self.assertEqual(order.address.street_address, "123 Test Street")
    
    def test_create_order_with_invalid_address(self):
        """Test that an order cannot be created with an invalid address ID"""
        invalid_address_id = 999  # Non-existent address ID
        
        order_data = {
            "total_amount": "10.00",
            "shipping_address": "Custom Address",
            "address_id": invalid_address_id,
            "items": [
                {
                    "product": self.product.id,
                    "quantity": 1
                }
            ],
            "payment_info": {
                "card_last_four": "1234",
                "card_holder": "Test User",
                "expiry_date": "12/25"
            }
        }
        
        url = reverse("order-list")
        response = self.client.post(url, order_data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("address_id", response.data)
    
    def test_create_order_with_explicit_shipping_only(self):
        """Test that an order can be created with explicit shipping address and no saved address"""
        # Delete all addresses so it doesn't auto-assign
        Address.objects.all().delete()
        
        order_data = {
            "total_amount": "10.00",
            "shipping_address": "Custom Address",
            "items": [
                {
                    "product": self.product.id,
                    "quantity": 1
                }
            ],
            "payment_info": {
                "card_last_four": "1234",
                "card_holder": "Test User",
                "expiry_date": "12/25"
            }
        }
        
        url = reverse("order-list")
        response = self.client.post(url, order_data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 1)
        
        # Verify order has no address linked (only shipping_address text)
        order = Order.objects.first()
        self.assertIsNone(order.address)
        self.assertEqual(order.shipping_address, "Custom Address")
        
    def test_create_order_with_address_auto_shipping_address(self):
        """Test that an order uses address for shipping_address when not provided"""
        order_data = {
            "total_amount": "10.00",
            "address_id": self.address.id,
            "items": [
                {
                    "product": self.product.id,
                    "quantity": 1
                }
            ],
            "payment_info": {
                "card_last_four": "1234",
                "card_holder": "Test User",
                "expiry_date": "12/25"
            }
        }
        
        url = reverse("order-list")
        response = self.client.post(url, order_data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify shipping_address was created from address
        order = Order.objects.first()
        expected_address = "123 Test Street, Test City, Test State, 12345, Test Country"
        self.assertEqual(order.shipping_address, expected_address)
        
    def test_create_order_with_main_address_auto_assigned(self):
        """Test that an order automatically uses the user's main address when no address is specified"""
        # Clear any existing orders
        Order.objects.all().delete()
        
        order_data = {
            "total_amount": "10.00",
            "shipping_address": "Custom Address",
            "items": [
                {
                    "product": self.product.id,
                    "quantity": 1
                }
            ],
            "payment_info": {
                "card_last_four": "1234",
                "card_holder": "Test User",
                "expiry_date": "12/25"
            }
        }
        
        url = reverse("order-list")
        response = self.client.post(url, order_data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify the order was assigned the user's main address
        order = Order.objects.first()
        self.assertIsNotNone(order.address)
        self.assertEqual(order.address.id, self.address.id)
        self.assertEqual(order.address.street_address, "123 Test Street")