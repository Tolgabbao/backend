from django.shortcuts import render
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from orders.models import Order
from .models import Product, Category, ProductRating, ProductComment
from .serializers import (
    ProductSerializer, CategorySerializer,
    ProductRatingSerializer, ProductCommentSerializer
)



class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['category']
    ordering_fields = ['price', 'average_rating']

    @action(detail=True, methods=['post'])
    def rate_product(self, request, pk=None):
        product = self.get_object()
        user = request.user

        # Check if product is delivered to user
        if not Order.objects.filter(
            user=user,
            items__product=product,
            status='DELIVERED'
        ).exists():
            return Response(
                {'error': 'You can only rate products you have purchased'},
                status=400
            )

        serializer = ProductRatingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user, product=product)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['post'])
    def comment_product(self, request, pk=None):
        product = self.get_object()
        user = request.user

        # Similar delivery check as rate_product
        if not Order.objects.filter(
            user=user,
            items__product=product,
            status='DELIVERED'
        ).exists():
            return Response(
                {'error': 'You can only comment on products you have purchased'},
                status=400
            )

        serializer = ProductCommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user, product=product)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)



@api_view(['GET'])
def get_product_ratings(request, product_id):
    ratings = ProductRating.objects.filter(product_id=product_id)
    serializer = ProductRatingSerializer(ratings, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_product_comments(request, product_id):
    comments = ProductComment.objects.filter(product_id=product_id)
    serializer = ProductCommentSerializer(comments, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_products_by_category(request, category_id):
    products = Product.objects.filter(category_id=category_id)
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_categories(request):
    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)
