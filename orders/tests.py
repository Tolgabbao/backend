from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Order, OrderItem, RefundRequest
from products.models import Product, Category
from accounts.models import Address
from django.utils import timezone
from datetime import timedelta
from .serializers import RefundRequestSerializer

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


class RefundRequestModelTest(TestCase):
    def setUp(self):
        # Create users
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="password123",
            user_type="CUSTOMER"
        )
        self.sales_manager = User.objects.create_user(
            username="salesmanager",
            email="sales@example.com",
            password="password123",
            user_type="SALES_MANAGER"
        )

        # Create product
        self.product = Product.objects.create(
            name="Test Product",
            model="ModelX",
            serial_number="SN12345",
            description="Test Description",
            price=100.00,
            cost_price=50.00,
            category=Category.objects.create(name="Test Category"),
            distributor_info="Test Distributor"
        )

        # Create order and order item
        self.order = Order.objects.create(
            user=self.customer,
            status="DELIVERED",
            total_amount=100.00,
            shipping_address="123 Test Street, Test City",
            card_last_four="1234",
            card_holder="Test User",
            expiry_date="12/25",
            delivered_at=timezone.now() - timedelta(days=5)
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )

        # Create refund request
        self.refund_request = RefundRequest.objects.create(
            order_item=self.order_item,
            user=self.customer,
            reason="Product doesn't work as expected"
        )

    def test_refund_request_creation(self):
        """Test that a refund request can be created with proper defaults"""
        self.assertEqual(self.refund_request.status, "PENDING")
        self.assertIsNone(self.refund_request.approved_by)
        self.assertIsNone(self.refund_request.approval_date)
        self.assertEqual(self.refund_request.rejection_reason, "")

    def test_refund_request_approval(self):
        """Test the approve method"""
        self.refund_request.approve(self.sales_manager)

        # Refresh from database
        self.refund_request.refresh_from_db()

        self.assertEqual(self.refund_request.status, "APPROVED")
        self.assertEqual(self.refund_request.approved_by, self.sales_manager)
        self.assertIsNotNone(self.refund_request.approval_date)

    def test_refund_request_rejection(self):
        """Test the reject method"""
        rejection_reason = "Product was damaged by customer"
        self.refund_request.reject(self.sales_manager, rejection_reason)

        # Refresh from database
        self.refund_request.refresh_from_db()

        self.assertEqual(self.refund_request.status, "REJECTED")
        self.assertEqual(self.refund_request.approved_by, self.sales_manager)
        self.assertIsNotNone(self.refund_request.approval_date)
        self.assertEqual(self.refund_request.rejection_reason, rejection_reason)

    def test_string_representation(self):
        """Test the string representation of a refund request"""
        expected_string = f"Refund Request #{self.refund_request.id} - Order Item #{self.order_item.id}"
        self.assertEqual(str(self.refund_request), expected_string)


class RefundRequestSerializerTest(TestCase):
    def setUp(self):
        # Create users
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="password123",
            user_type="CUSTOMER"
        )

        # Create product
        self.product = Product.objects.create(
            name="Test Product",
            model="ModelX",
            serial_number="SN12346",
            description="Test Description",
            price=100.00,
            cost_price=50.00,
            category=Category.objects.create(name="Test Category 2"),
            distributor_info="Test Distributor"
        )

        # Create orders in different states
        self.delivered_order = Order.objects.create(
            user=self.customer,
            status="DELIVERED",
            total_amount=100.00,
            delivered_at=timezone.now() - timedelta(days=5)
        )
        self.pending_order = Order.objects.create(
            user=self.customer,
            status="PENDING",
            total_amount=100.00
        )
        self.old_order = Order.objects.create(
            user=self.customer,
            status="DELIVERED",
            total_amount=100.00,
            delivered_at=timezone.now() - timedelta(days=35)
        )

        # Create order items
        self.delivered_item = OrderItem.objects.create(
            order=self.delivered_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )
        self.pending_item = OrderItem.objects.create(
            order=self.pending_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )
        self.old_item = OrderItem.objects.create(
            order=self.old_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )

        # Create a refund request for testing duplicate validations
        self.existing_refund = RefundRequest.objects.create(
            order_item=self.delivered_item,
            user=self.customer,
            reason="Already requested refund"
        )

    def test_serializer_with_valid_data(self):
        """Test serializer validation with valid data"""
        # Create a new order item that doesn't have a refund request yet
        valid_order = Order.objects.create(
            user=self.customer,
            status="DELIVERED",
            total_amount=100.00,
            delivered_at=timezone.now() - timedelta(days=5)
        )
        valid_item = OrderItem.objects.create(
            order=valid_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )

        data = {
            'order_item': valid_item.id,
            'reason': 'Valid reason for refund'
        }

        serializer = RefundRequestSerializer(
            data=data,
            context={'request': type('obj', (object,), {'user': self.customer})}
        )

        self.assertTrue(serializer.is_valid())

    def test_serializer_with_non_delivered_order(self):
        """Test serializer validation with an order that's not delivered"""
        data = {
            'order_item': self.pending_item.id,
            'reason': 'Should not be valid'
        }

        serializer = RefundRequestSerializer(
            data=data,
            context={'request': type('obj', (object,), {'user': self.customer})}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('order_item', serializer.errors)
        self.assertIn('Refund can only be requested for delivered orders', str(serializer.errors))

    def test_serializer_with_old_order(self):
        """Test serializer validation with an order delivered more than 30 days ago"""
        data = {
            'order_item': self.old_item.id,
            'reason': 'Too old for refund'
        }

        serializer = RefundRequestSerializer(
            data=data,
            context={'request': type('obj', (object,), {'user': self.customer})}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('order_item', serializer.errors)
        self.assertIn('Refund can only be requested within 30 days after delivery', str(serializer.errors))

    def test_serializer_with_existing_refund(self):
        """Test serializer validation with an item that already has a refund request"""
        data = {
            'order_item': self.delivered_item.id,
            'reason': 'Duplicate refund request'
        }

        serializer = RefundRequestSerializer(
            data=data,
            context={'request': type('obj', (object,), {'user': self.customer})}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('order_item', serializer.errors)
        self.assertIn('A refund request already exists for this item', str(serializer.errors))


class RefundRequestViewSetTest(APITestCase):
    def setUp(self):
        # Create users
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="password123",
            user_type="CUSTOMER"
        )
        self.another_customer = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="password123",
            user_type="CUSTOMER"
        )
        self.sales_manager = User.objects.create_user(
            username="salesmanager",
            email="sales@example.com",
            password="password123",
            user_type="SALES_MANAGER"
        )

        # Create product
        self.product = Product.objects.create(
            name="Test Product",
            model="ModelX",
            serial_number="SN12347",
            description="Test Description",
            price=100.00,
            cost_price=50.00,
            category=Category.objects.create(name="Test Category 3"),
            distributor_info="Test Distributor"
        )

        # Create orders
        self.customer_order = Order.objects.create(
            user=self.customer,
            status="DELIVERED",
            total_amount=100.00,
            delivered_at=timezone.now() - timedelta(days=5)
        )
        self.another_customer_order = Order.objects.create(
            user=self.another_customer,
            status="DELIVERED",
            total_amount=100.00,
            delivered_at=timezone.now() - timedelta(days=5)
        )

        # Create order items
        self.customer_item = OrderItem.objects.create(
            order=self.customer_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )
        self.another_customer_item = OrderItem.objects.create(
            order=self.another_customer_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )

        # Create refund requests
        self.pending_refund = RefundRequest.objects.create(
            order_item=self.customer_item,
            user=self.customer,
            reason="Product doesn't work"
        )
        self.another_pending_refund = RefundRequest.objects.create(
            order_item=self.another_customer_item,
            user=self.another_customer,
            reason="Product arrived damaged"
        )

        # Create URLs
        self.list_url = reverse('refund-list')
        self.detail_url = reverse('refund-detail', args=[self.pending_refund.id])
        self.another_detail_url = reverse('refund-detail', args=[self.another_pending_refund.id])
        self.approve_url = reverse('refund-approve', args=[self.pending_refund.id])
        self.reject_url = reverse('refund-reject', args=[self.pending_refund.id])
        self.pending_refunds_url = reverse('refund-pending-refunds')
        self.my_refunds_url = reverse('refund-my-refunds')

    def test_get_queryset_for_customer(self):
        """Test that customers can only see their own refund requests"""
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.pending_refund.id)

    def test_get_queryset_for_sales_manager(self):
        """Test that sales managers can see all refund requests"""
        self.client.force_authenticate(user=self.sales_manager)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Both customers' refunds

    def test_create_refund_as_customer(self):
        """Test creating a new refund request as a customer"""
        # Create a new order/item for the test
        new_order = Order.objects.create(
            user=self.customer,
            status="DELIVERED",
            total_amount=100.00,
            delivered_at=timezone.now() - timedelta(days=1)
        )
        new_item = OrderItem.objects.create(
            order=new_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )

        self.client.force_authenticate(user=self.customer)
        data = {
            'order_item': new_item.id,
            'reason': 'Product is defective'
        }

        response = self.client.post(self.list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['reason'], 'Product is defective')
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertEqual(response.data['user'], self.customer.id)

    def test_create_refund_as_sales_manager(self):
        """Test that sales managers cannot create refund requests"""
        new_order = Order.objects.create(
            user=self.customer,
            status="DELIVERED",
            total_amount=100.00,
            delivered_at=timezone.now() - timedelta(days=1)
        )
        new_item = OrderItem.objects.create(
            order=new_order,
            product=self.product,
            quantity=1,
            price_at_time=100.00
        )

        self.client.force_authenticate(user=self.sales_manager)
        data = {
            'order_item': new_item.id,
            'reason': 'Product is defective'
        }

        response = self.client.post(self.list_url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only customers can request refunds', str(response.data))

    def test_update_own_pending_refund(self):
        """Test that customers can update their own pending refund requests"""
        self.client.force_authenticate(user=self.customer)
        data = {
            'order_item': self.customer_item.id,
            'reason': 'Updated reason: Product is damaged'
        }

        response = self.client.put(self.detail_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['reason'], 'Updated reason: Product is damaged')

    def test_update_another_customer_refund(self):
        """Test that customers cannot update another customer's refund requests"""
        self.client.force_authenticate(user=self.customer)
        data = {
            'order_item': self.another_customer_item.id,
            'reason': 'Trying to update another customer\'s refund'
        }

        response = self.client.put(self.another_detail_url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('You can only update your own refund requests', str(response.data))

    def test_destroy_pending_refund(self):
        """Test that customers can cancel their own pending refund requests"""
        self.client.force_authenticate(user=self.customer)
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Verify the request was deleted
        self.assertFalse(RefundRequest.objects.filter(id=self.pending_refund.id).exists())

    def test_destroy_another_customer_refund(self):
        """Test that customers cannot cancel another customer's refund requests"""
        self.client.force_authenticate(user=self.customer)
        response = self.client.delete(self.another_detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('You can only cancel your own refund requests', str(response.data))

    def test_approve_refund_as_sales_manager(self):
        """Test approving refund requests as a sales manager"""
        self.client.force_authenticate(user=self.sales_manager)
        response = self.client.post(self.approve_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the refund was approved
        approved_refund = RefundRequest.objects.get(id=self.pending_refund.id)
        self.assertEqual(approved_refund.status, 'APPROVED')
        self.assertEqual(approved_refund.approved_by, self.sales_manager)
        self.assertIsNotNone(approved_refund.approval_date)

    def test_approve_refund_as_customer(self):
        """Test that customers cannot approve refund requests"""
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(self.approve_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only sales managers can approve refund requests', str(response.data))

    def test_reject_refund_as_sales_manager(self):
        """Test rejecting refund requests as a sales manager"""
        self.client.force_authenticate(user=self.sales_manager)
        data = {
            'rejection_reason': 'Product was damaged by customer, not eligible for refund'
        }

        response = self.client.post(self.reject_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the refund was rejected
        rejected_refund = RefundRequest.objects.get(id=self.pending_refund.id)
        self.assertEqual(rejected_refund.status, 'REJECTED')
        self.assertEqual(rejected_refund.approved_by, self.sales_manager)
        self.assertEqual(rejected_refund.rejection_reason, data['rejection_reason'])
        self.assertIsNotNone(rejected_refund.approval_date)

    def test_reject_refund_as_customer(self):
        """Test that customers cannot reject refund requests"""
        self.client.force_authenticate(user=self.customer)
        data = {
            'rejection_reason': 'Trying to reject my own refund'
        }

        response = self.client.post(self.reject_url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only sales managers can reject refund requests', str(response.data))

    def test_pending_refunds_endpoint_as_sales_manager(self):
        """Test that sales managers can access the pending_refunds endpoint"""
        self.client.force_authenticate(user=self.sales_manager)
        response = self.client.get(self.pending_refunds_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Both are pending

    def test_pending_refunds_endpoint_as_customer(self):
        """Test that customers cannot access the pending_refunds endpoint"""
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(self.pending_refunds_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only sales managers can view pending refunds list', str(response.data))

    def test_my_refunds_endpoint_as_customer(self):
        """Test that customers can access the my_refunds endpoint"""
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(self.my_refunds_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.pending_refund.id)

    def test_my_refunds_endpoint_as_sales_manager(self):
        """Test that sales managers cannot access the my_refunds endpoint"""
        self.client.force_authenticate(user=self.sales_manager)
        response = self.client.get(self.my_refunds_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only customers can view their refunds', str(response.data))

    def test_update_approved_refund(self):
        """Test that customers cannot update approved refund requests"""
        # First approve the refund
        self.client.force_authenticate(user=self.sales_manager)
        self.client.post(self.approve_url)

        # Now try to update it as the customer
        self.client.force_authenticate(user=self.customer)
        data = {
            'order_item': self.customer_item.id,
            'reason': 'Trying to update approved refund'
        }

        response = self.client.put(self.detail_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only pending refund requests can be updated', str(response.data))

    def test_destroy_approved_refund(self):
        """Test that customers cannot cancel approved refund requests"""
        # First approve the refund
        self.client.force_authenticate(user=self.sales_manager)
        self.client.post(self.approve_url)

        # Now try to delete it as the customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only pending refund requests can be canceled', str(response.data))

    def test_approve_already_approved_refund(self):
        """Test that sales managers cannot approve already approved refund requests"""
        # First approve the refund
        self.client.force_authenticate(user=self.sales_manager)
        self.client.post(self.approve_url)

        # Try to approve it again
        response = self.client.post(self.approve_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only pending refund requests can be approved', str(response.data))

    def test_reject_already_approved_refund(self):
        """Test that sales managers cannot reject already approved refund requests"""
        # First approve the refund
        self.client.force_authenticate(user=self.sales_manager)
        self.client.post(self.approve_url)

        # Try to reject it
        data = {
            'rejection_reason': 'Trying to reject approved refund'
        }
        response = self.client.post(self.reject_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only pending refund requests can be rejected', str(response.data))
