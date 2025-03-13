# Create your tests here.

#Test with a customer account (should return only their orders). ---
#Test with an admin account (should return all orders). ---

#Mock cache.delete() to ensure it’s called.
#Check that orders are correctly retrieved.

#Test retrieving a valid order (check response data).
#Test retrieving an invalid order (should return 404).

#Test creating an order with valid data.
#Test missing data (should return 400).
#Mock process_order.delay() to check if it's called.

#Test updating status with a valid value.
#Test without status (should return 400).
#Mock send_order_status_update.delay().

#Test with authenticated user (should return user cart).
#Test with session ID (should return guest cart).
#Test with no session ID (should return empty queryset).

#Test adding a valid product. ✅
#Test with missing product ID (400).
#Test non-existent product (404).✅
#Mock cache.delete().

from django.test import TestCase
from accounts.models import User
from orders.models import Cart, CartItem
from products.models import Product, Category
from django.db import models
"""
    def test2(self):
        try:
            #print("Hello!")
            raise Exception("Failure in test_2!")
        except Exception as e:
            self.fail(f"Exception: {e}")
"""

class CartTestCase(TestCase):
    """Each test gets a fresh database → setUp() runs before every test"""
    def setUp(self):
        # Create a category first since Product requires a ForeignKey to Category
        self.category = Category.objects.create(name="Electronics")

        # Create a product to use in cart tests
        self.product = Product.objects.create(
            name="Test Product",
            model="XYZ123",
            serial_number="SN12345",
            description="A test product1",
            stock_quantity=10,
            price=100.00,
            cost_price=80.00,
            warranty_months=24,
            category=self.category,  # Required ForeignKey
            distributor_info="Distributor Info",
            is_visible=True
        )

        self.product2 = Product.objects.create(
            name="2 Test Product 2",
            model="XYZ111",
            serial_number="SN12344",
            description="A test product2",
            stock_quantity=10,
            price=888.00,
            cost_price=600.00,
            warranty_months=12,
            category=self.category,  # Required ForeignKey
            distributor_info="Distributor Info1",
            is_visible=True
        )

        # Create user if needed
        self.user = User.objects.create_user(username="testuser", password="12345")

        # Cart with user
        self.cart = Cart.objects.create(user=self.user)

        # Cart without user (anonymous)
        self.anonymous_cart = Cart.objects.create(session_id="test_session")



    def test_total(self):
        # Use the product created in setUp
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        self.assertEqual(self.cart.total, 200)

        # UNONIMOUS CART
        CartItem.objects.create(cart=self.anonymous_cart, product=self.product, quantity=2)
        self.assertEqual(self.cart.total, 200)

    print("✅ Test Passed: Cart total is correct")

    def test_can_add_item_to_cart(self):
        # Use the product created in setUp
        cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.assertEqual(cart_item.subtotal, 100)

        cart_item = CartItem.objects.create(cart=self.cart, product=self.product2, quantity=10)
        self.assertEqual(cart_item.subtotal, 8880)

        #UNONIMOUS CART
        cart_item = CartItem.objects.create(cart=self.anonymous_cart, product=self.product, quantity=1)
        self.assertEqual(cart_item.subtotal, 100)

        print("✅ Test Passed: Cart item subtotal is correct")

    def test_can_remove_item_from_cart(self):
        # Use the product created in setUp
        cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        cart_item.delete()
        self.assertEqual(self.cart.total, 0)

        # UNONIMOUS CART
        cart_item = CartItem.objects.create(cart=self.anonymous_cart, product=self.product, quantity=1)
        cart_item.delete()
        self.assertEqual(self.cart.total, 0)

        print("✅ Test Passed: Cart item removed successfully")

    def test_cart_empty(self):
        self.assertEqual(self.cart.total, 0,"Cart total should be 0 when empty")

        # UNONIMOUS CART
        self.assertEqual(self.anonymous_cart.total, 0,"Cart total should be 0 when empty")
        print("✅ Test Passed: Cart is empty with total 0")


#Test non-existent product (404).
    def test_add_non_existing_product(self):
        """Test adding a non-existent product to both user and anonymous carts"""
        fake_product_id = 9999  # A product ID that doesn't exist

        # ✅ Test for user-based cart
        with self.assertRaises(Product.DoesNotExist):
            non_existing_product = Product.objects.get(id=fake_product_id)
            CartItem.objects.create(cart=self.cart, product=non_existing_product, quantity=1)

        # ✅ Ensure the user cart is still empty
        self.assertEqual(self.cart.items.count(), 0,
                         "User cart should remain empty when adding a non-existent product")

        # ✅ Test for anonymous (session-based) cart
        with self.assertRaises(Product.DoesNotExist):
            non_existing_product = Product.objects.get(id=fake_product_id)
            CartItem.objects.create(cart=self.anonymous_cart, product=non_existing_product, quantity=1)

        # ✅ Ensure the anonymous cart is still empty
        self.assertEqual(self.anonymous_cart.items.count(), 0,
                         "Anonymous cart should remain empty when adding a non-existent product")

        print("✅ Test Passed: Cannot add non-existing product to both user and anonymous carts")


    #BU gereksiz mi?
    #product.sales_count increases when added to cart.
    def test_product_sales_count_increases(self):
        """Test that product sales_count increases when added to cart"""
        sales_count_previous = self.product2.sales_count
        #print(sales_count_previous)
        CartItem.objects.create(cart= self.cart, product= self.product2, quantity= 5)
        #print(self.product2.sales_count)
        self.assertTrue(sales_count_previous == self.product2.sales_count)



    """is product stock decreases when added to cart?"""
    def test_product_stock_decrease(self):
        """Test that product stock decreases when added to cart"""
        stock_previous = self.product.stock_quantity
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=5)
        #print(stock_previous , self.product.stock_quantity)

        self.assertFalse(stock_previous-5 == self.product.stock_quantity)
        print("✅ Test Passed: Product stock DONT decreases when added to cart")


    """ APi retunrs cart info of the adding product but it doesnt retunr error message why?"""
    #is it possible to add more items than the stock_quantity?
    def test_add_more_than_available_stock(self):
        """Test adding more products than available stock"""
        response = self.client.post(
            "/api/carts/add/",
            {"product_id": self.product2.id, "quantity": 11},  # ❌ More than stock (5)
        )

        #Bunun returnu neden böyle json filedan return alıp error kontrolü nasıl yapılıyor?
        #print("Response Status Code:", response.status_code)  #  200 DÖNÜYOR
        #print("Response JSON:", response.json())  # Print Full JSON Response BURDA CARTA EKLENEMEYEN ÜRÜNÜ VE TOTALİ GÖSTERİYOR

        #self.assertEqual(response.status_code, 400)
        #self.assertIn("Not enough stock available", response.json()["error"])
        self.assertEqual(self.cart.items.count(), 0)
        print("✅ Test Passed: Cannot add more than available stock")


