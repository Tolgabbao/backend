# E-Commerce Backend API

This is a Django-based e-commerce backend API that provides functionality for user accounts, products management, and order processing.

## Tech Stack

- Python 3.11
- Django
- Celery -> not yet implemented
- PostgreSQL
- Redis -> not yet implemented
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
git clone <repository-url>
cd <project-directory>
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
- `/api/categories/` - List and create categories

#### Image Storage
Images are stored directly in PostgreSQL using BinaryField, which allows for:
- Direct database backup including all images
- No need for separate file storage system
- Consistent data handling across different environments

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
