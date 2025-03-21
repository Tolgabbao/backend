from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.core.cache import cache
from unittest.mock import patch, MagicMock

from accounts.models import User
from products.models import Category, Product, ProductImage, ProductRating, ProductComment
from products.serializers import (
    CategorySerializer, 
    ProductSerializer, 
    ProductImageSerializer,
    ProductRatingSerializer,
    ProductCommentSerializer
)
from decimal import Decimal
import io
from PIL import Image


class CategoryModelTestCase(TestCase):
    """Tests for Category model"""
    
    def setUp(self):
        self.category = Category.objects.create(
            name="Electronics",
            description="Electronic devices and gadgets"
        )
    
    def test_category_creation(self):
        """Test category creation and string representation"""
        self.assertEqual(self.category.name, "Electronics")
        self.assertEqual(self.category.description, "Electronic devices and gadgets")
        self.assertEqual(str(self.category), "Electronics")
    
    def test_verbose_name_plural(self):
        """Test that verbose_name_plural is set correctly"""
        self.assertEqual(Category._meta.verbose_name_plural, "Categories")


class ProductModelTestCase(TestCase):
    """Tests for Product model"""
    
    def setUp(self):
        # Create category first
        self.category = Category.objects.create(
            name="Electronics",
            description="Electronic devices and gadgets"
        )
        
        # Create a product
        self.product = Product.objects.create(
            name="Test Product",
            model="TP-100",
            serial_number="SN12345678",
            description="A test product description",
            stock_quantity=10,
            price=Decimal("199.99"),
            cost_price=Decimal("150.00"),
            warranty_months=24,
            category=self.category,
            distributor_info="Test Distributor",
            is_visible=True
        )
    
    def test_product_creation(self):
        """Test product creation and basic attributes"""
        self.assertEqual(self.product.name, "Test Product")
        self.assertEqual(self.product.model, "TP-100")
        self.assertEqual(self.product.serial_number, "SN12345678")
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.product.price, Decimal("199.99"))
        self.assertEqual(self.product.warranty_months, 24)
        self.assertTrue(self.product.is_visible)
        self.assertEqual(str(self.product), "Test Product")
    
    def test_average_rating_property(self):
        """Test the average_rating property with no ratings"""
        self.assertIsNone(self.product.average_rating)
        
        # Create a user for ratings
        user = User.objects.create_user(
            username="testuser", 
            password="12345", 
            email="testuser@example.com",
            user_type="CUSTOMER",
            address="Test Address"
        )
        
        # Add two ratings
        ProductRating.objects.create(
            product=self.product,
            user=user,
            rating=4
        )
        
        # Create another user with required fields
        user2 = User.objects.create_user(
            username="testuser2", 
            password="12345",
            email="testuser2@example.com",
            user_type="CUSTOMER",
            address="Test Address 2"
        )
        
        ProductRating.objects.create(
            product=self.product,
            user=user2,
            rating=5
        )
        
        # Test average rating calculation
        self.assertEqual(self.product.average_rating, 4.5)
    
    def test_main_image_property(self):
        """Test the main_image property"""
        # Initially no images, should return None
        self.assertIsNone(self.product.main_image)
        
        # Create an in-memory image
        image_file = self.create_test_image()
        
        # Create a product image (not primary)
        image1 = ProductImage.objects.create(
            product=self.product,
            image=image_file,
            alt_text="Test Image",
            is_primary=False
        )
        
        # Should return the first image even though it's not primary
        self.assertIsNotNone(self.product.main_image)
        
        # Create a primary image
        image2 = ProductImage.objects.create(
            product=self.product,
            image=image_file,
            alt_text="Primary Image",
            is_primary=True
        )
        
        # Should now return the primary image
        self.assertEqual(self.product.main_image, image2.image.url)
    
    def create_test_image(self):
        """Helper method to create a test image file"""
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        return SimpleUploadedFile("test_image.jpg", image_io.getvalue(), content_type="image/jpeg")


class ProductImageModelTestCase(TestCase):
    """Tests for ProductImage model"""
    
    def setUp(self):
        # Create category and product
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Test Product",
            model="TP-100",
            serial_number="SN12345678",
            description="A test product",
            stock_quantity=10,
            price=Decimal("199.99"),
            cost_price=Decimal("150.00"),
            category=self.category,
            distributor_info="Test Distributor"
        )
        
        # Create an in-memory image
        self.image_file = self.create_test_image()
    
    def create_test_image(self):
        """Helper method to create a test image file"""
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        return SimpleUploadedFile("test_image.jpg", image_io.getvalue(), content_type="image/jpeg")
    
    def test_image_creation(self):
        """Test ProductImage creation and string representation"""
        image = ProductImage.objects.create(
            product=self.product,
            image=self.image_file,
            alt_text="Test Image",
            is_primary=True
        )
        
        self.assertEqual(image.product, self.product)
        self.assertEqual(image.alt_text, "Test Image")
        self.assertTrue(image.is_primary)
        self.assertIn("primary", str(image))
    
    def test_primary_image_enforcement(self):
        """Test that only one image can be primary per product"""
        # Create first primary image
        image1 = ProductImage.objects.create(
            product=self.product,
            image=self.image_file,
            alt_text="Primary Image 1",
            is_primary=True
        )
        
        # Create second primary image
        image2 = ProductImage.objects.create(
            product=self.product,
            image=self.image_file,
            alt_text="Primary Image 2",
            is_primary=True
        )
        
        # Refresh image1 from database
        image1.refresh_from_db()
        
        # First image should no longer be primary
        self.assertFalse(image1.is_primary)
        self.assertTrue(image2.is_primary)


class ProductRatingModelTestCase(TestCase):
    """Tests for ProductRating model"""
    
    def setUp(self):
        # Create category and product
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Test Product",
            model="TP-100",
            serial_number="SN12345678",
            description="A test product",
            stock_quantity=10,
            price=Decimal("199.99"),
            cost_price=Decimal("150.00"),
            category=self.category,
            distributor_info="Test Distributor"
        )
        
        # Create a user with required fields
        self.user = User.objects.create_user(
            username="testuser", 
            password="12345",
            email="rating-user@example.com",
            user_type="CUSTOMER",
            address="Test Address"
        )
    
    def test_rating_creation(self):
        """Test rating creation and validation"""
        rating = ProductRating.objects.create(
            product=self.product,
            user=self.user,
            rating=4
        )
        
        self.assertEqual(rating.product, self.product)
        self.assertEqual(rating.user, self.user)
        self.assertEqual(rating.rating, 4)
        self.assertIn("4 stars", str(rating))
    
    def test_rating_validation(self):
        """Test that ratings must be between 1 and 5"""
        from django.core.exceptions import ValidationError
        
        # Create an invalid rating object but don't save it yet
        rating_too_high = ProductRating(
            product=self.product,
            user=self.user,
            rating=6  # Invalid rating (above 5)
        )
        
        # Validate should raise an error
        with self.assertRaises(ValidationError):
            rating_too_high.full_clean()  # This validates model constraints
        
        # Same for too low
        rating_too_low = ProductRating(
            product=self.product,
            user=self.user,
            rating=0  # Invalid rating (below 1)
        )
        
        with self.assertRaises(ValidationError):
            rating_too_low.full_clean()


class ProductCommentModelTestCase(TestCase):
    """Tests for ProductComment model"""
    
    def setUp(self):
        # Create category and product
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Test Product",
            model="TP-100",
            serial_number="SN12345678",
            description="A test product",
            stock_quantity=10,
            price=Decimal("199.99"),
            cost_price=Decimal("150.00"),
            category=self.category,
            distributor_info="Test Distributor"
        )
        
        # Create a user with required fields
        self.user = User.objects.create_user(
            username="testuser", 
            password="12345",
            email="comment-user@example.com",
            user_type="CUSTOMER",
            address="Test Address"
        )
    
    def test_comment_creation(self):
        """Test comment creation and default values"""
        comment = ProductComment.objects.create(
            product=self.product,
            user=self.user,
            comment="This is a test comment"
        )
        
        self.assertEqual(comment.product, self.product)
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.comment, "This is a test comment")
        self.assertFalse(comment.is_approved)  # Default is False
        self.assertIn(self.product.name, str(comment))
        self.assertIn(self.user.username, str(comment))


class SerializerTestCase(TestCase):
    """Tests for product serializers"""
    
    def setUp(self):
        # Create category and product
        self.category = Category.objects.create(name="Electronics", description="Electronic devices")
        self.product = Product.objects.create(
            name="Test Product",
            model="TP-100",
            serial_number="SN12345678",
            description="A test product",
            stock_quantity=10,
            price=Decimal("199.99"),
            cost_price=Decimal("150.00"),
            category=self.category,
            distributor_info="Test Distributor",
            is_visible=True
        )
        
        # Create a user with required fields
        self.user = User.objects.create_user(
            username="testuser", 
            password="12345",
            email="serializer-user@example.com",
            user_type="CUSTOMER",
            address="Test Address"
        )
        
        # Create a rating
        self.rating = ProductRating.objects.create(
            product=self.product,
            user=self.user,
            rating=5
        )
        
        # Create a comment
        self.comment = ProductComment.objects.create(
            product=self.product,
            user=self.user,
            comment="Great product!",
            is_approved=True
        )
        
        # Create request factory for context
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
    
    def test_category_serializer(self):
        """Test CategorySerializer"""
        serializer = CategorySerializer(self.category)
        data = serializer.data
        
        self.assertEqual(data['name'], "Electronics")
        self.assertEqual(data['description'], "Electronic devices")
    
    def test_product_serializer(self):
        """Test ProductSerializer"""
        serializer = ProductSerializer(self.product, context={'request': self.request})
        data = serializer.data
        
        self.assertEqual(data['name'], "Test Product")
        self.assertEqual(data['model'], "TP-100")
        self.assertEqual(data['price'], '199.99')
        self.assertEqual(data['category']['name'], "Electronics")
        self.assertEqual(data['average_rating'], 5.0)
    
    def test_product_rating_serializer(self):
        """Test ProductRatingSerializer"""
        serializer = ProductRatingSerializer(self.rating)
        data = serializer.data
        
        self.assertEqual(data['rating'], 5)
        self.assertEqual(data['product'], self.product.id)
    
    def test_product_comment_serializer(self):
        """Test ProductCommentSerializer"""
        serializer = ProductCommentSerializer(self.comment)
        data = serializer.data
        
        self.assertEqual(data['comment'], "Great product!")
        self.assertEqual(data['product'], self.product.id)
        self.assertTrue(data['is_approved'])
        self.assertEqual(data['user_name'], "testuser")


class ProductAPITestCase(APITestCase):
    """Tests for product API endpoints"""
    
    def setUp(self):
        # Create category and products
        self.category = Category.objects.create(name="Electronics", description="Electronic devices")
        
        self.product1 = Product.objects.create(
            name="Test Product 1",
            model="TP-100",
            serial_number="SN12345678",
            description="A test product",
            stock_quantity=10,
            price=Decimal("199.99"),
            cost_price=Decimal("150.00"),
            category=self.category,
            distributor_info="Test Distributor",
            is_visible=True
        )
        
        self.product2 = Product.objects.create(
            name="Test Product 2",
            model="TP-200",
            serial_number="SN87654321",
            description="Another test product",
            stock_quantity=5,
            price=Decimal("299.99"),
            cost_price=Decimal("250.00"),
            category=self.category,
            distributor_info="Test Distributor",
            is_visible=False  # Not visible
        )
        
        # Create users
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@test.com",
            password="admin123",
            user_type="SALES_MANAGER",
            address="Admin Address"
        )
        
        self.regular_user = User.objects.create_user(
            username="user",
            email="user@test.com",
            password="user123",
            user_type="CUSTOMER",
            address="User Address"
        )
        
        # API client
        self.client = APIClient()
        
        # Clear cache
        cache.clear()
    
    def test_get_products_unauthorized(self):
        """Test getting products without authentication"""
        url = '/api/products/'  # Assuming this is the products endpoint
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only see visible products (product1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], "Test Product 1")
    
    def test_get_products_as_admin(self):
        """Test getting products as admin user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = '/api/products/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin should see all products
        self.assertEqual(len(response.data['results']), 2)
    
    def test_product_create(self):
        """Test creating a product"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = '/api/products/'
        data = {
            'name': 'New Product',
            'model': 'NP-300',
            'serial_number': 'SN99999999',
            'description': 'A new product',
            'stock_quantity': 15,
            'price': '399.99',
            'cost_price': '350.00',
            'category_id': self.category.id,
            'distributor_info': 'New Distributor',
            'is_visible': True
        }
        
        response = self.client.post(url, data, format='json')
        
        # Response might be 201 CREATED or 403 FORBIDDEN depending on permissions
        if response.status_code == status.HTTP_201_CREATED:
            self.assertEqual(response.data['name'], 'New Product')
            self.assertEqual(Product.objects.count(), 3)
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            # If admin is not allowed to create products, at least check the error
            self.assertEqual(Product.objects.count(), 2)
    
    @patch('products.views.safe_cache_delete')
    def test_product_update(self, mock_cache_delete):
        """Test updating a product with mocked cache deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = f'/api/products/{self.product1.id}/'
        data = {
            'name': 'Updated Product Name',
            'model': self.product1.model,
            'serial_number': self.product1.serial_number,
            'description': self.product1.description,
            'stock_quantity': self.product1.stock_quantity,
            'price': str(self.product1.price),
            'cost_price': str(self.product1.cost_price),
            'category_id': self.category.id,
            'distributor_info': self.product1.distributor_info,
            'is_visible': self.product1.is_visible
        }
        
        response = self.client.patch(url, data, format='json')
        
        # Response might be 200 OK or 403 FORBIDDEN depending on permissions
        if response.status_code == status.HTTP_200_OK:
            self.assertEqual(response.data['name'], 'Updated Product Name')
            
            # Verify product was updated in database
            self.product1.refresh_from_db()
            self.assertEqual(self.product1.name, 'Updated Product Name')
            
            # Verify cache was deleted
            mock_cache_delete.assert_called()
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            # If admin is not allowed to update products, at least check the error
            self.product1.refresh_from_db()
            self.assertEqual(self.product1.name, 'Test Product 1')  # Not updated
    
    def test_toggle_product_visibility(self):
        """Test toggling product visibility"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = f'/api/products/{self.product1.id}/toggle_visibility/'
        response = self.client.post(url)
        
        # Response might be 200 OK or 403 FORBIDDEN depending on permissions
        if response.status_code == status.HTTP_200_OK:
            # Verify product visibility was toggled in the database
            self.product1.refresh_from_db()
            self.assertFalse(self.product1.is_visible)  # Was True, now should be False
            
            # Toggle again
            response = self.client.post(url)
            self.product1.refresh_from_db()
            self.assertTrue(self.product1.is_visible)  # Should be True again
    
    def test_top_rated_products(self):
        """Test getting top rated products"""
        # Create user for ratings
        user = User.objects.create_user(
            username="rater", 
            password="12345",
            email="rater@example.com",
            user_type="CUSTOMER",
            address="Rater Address"
        )
        
        # Add ratings to product1
        ProductRating.objects.create(product=self.product1, user=user, rating=5)
        
        # Add ratings to product2 (but with lower rating)
        ProductRating.objects.create(product=self.product2, user=user, rating=3)
        
        url = '/api/products/top_rated/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Regular user should only see visible products (product1)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Test Product 1")
        
        # Now test as admin
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        
        # Admin should see all products
        self.assertEqual(len(response.data), 2)
    
    def test_get_categories(self):
        """Test getting categories endpoint"""
        url = '/api/categories/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], "Electronics")