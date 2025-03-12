# E-Commerce Backend API

This is a Django-based e-commerce backend API that provides functionality for user accounts, products management, and order processing.

## Tech Stack

- Python 3.11
- Django
- Celery -> not yet implemented
- PostgreSQL
- Redis
- Docker

## Project Structure

The project consists of three main apps:
- `accounts`: User management and authentication
- `products`: Product catalog and management
- `orders`: Shopping cart and order processing

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Setup and Installation

1. Clone the repository:
```bash
git clone https://github.com/Tolgabbao/backend.git
cd backend
```

2. Build and start the Docker containers, recommended to download the frontend as well before this:
```bash
docker-compose up -d --build
```

### Initial Setup

1. Create database migrations:
```bash
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

2. Create a superuser:
```bash
docker-compose exec backend python manage.py createsuperuser
```

## API Endpoints

### Authentication
- `/api/auth/register/` - User registration
- `/api/auth/login/` - User login

### Products
- `/api/products/` - List and create products
- `/api/products/<id>/` - Retrieve, update, and delete products
- `/api/products/<id>/images/` - List all images for a product
- `/api/products/<id>/add_image/` - Add a new image to a product (staff only)
- `/api/products/<id>/remove_image/?image_id=<image_id>` - Remove an image (staff only)
- `/api/products/<id>/set_primary_image/` - Set an image as primary (staff only)
- `/api/categories/` - List and create categories

#### Image Storage
Images are stored in the filesystem under media/product_images/ with the following benefits:
- Better performance for image serving
- Support for multiple images per product
- Primary image designation for main product display
- Separation of image data from product metadata

### Orders
- `/api/cart/` - Shopping cart operations
- `/api/orders/` - List and create orders
- `/api/orders/<id>/` - Retrieve order details

## Development Commands

### Running Tests
```bash
docker-compose exec backend python manage.py test
```

### Creating New Apps
```bash
docker-compose exec backend python manage.py startapp app_name
```

### Making Migrations
```bash
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

### Accessing Django Shell
```bash
docker-compose exec backend python manage.py shell
```

## Maintenance

### Checking Logs
```bash
docker-compose logs -f backend
```

### Restarting Services
```bash
docker-compose restart backend
```

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Submit a pull request
