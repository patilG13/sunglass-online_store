// Main JavaScript functionality
document.addEventListener('DOMContentLoaded', function() {
    // Cart quantity handlers
    document.querySelectorAll('.quantity-btn').forEach(button => {
        button.addEventListener('click', function() {
            const input = this.parentElement.querySelector('.quantity-input');
            let quantity = parseInt(input.value);
            
            if (this.classList.contains('decrease')) {
                quantity = Math.max(1, quantity - 1);
            } else {
                quantity += 1;
            }
            
            input.value = quantity;
        });
    });

    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Search functionality
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const products = document.querySelectorAll('.product-card');
            
            products.forEach(product => {
                const productName = product.querySelector('.product-name').textContent.toLowerCase();
                if (productName.includes(searchTerm)) {
                    product.style.display = 'block';
                } else {
                    product.style.display = 'none';
                }
            });
        });
    }

    // Price range filter
    const priceFilter = document.getElementById('price-filter');
    if (priceFilter) {
        priceFilter.addEventListener('change', function() {
            const selectedPrice = this.value;
            const products = document.querySelectorAll('.product-card');
            
            products.forEach(product => {
                const price = parseFloat(product.querySelector('.product-price').textContent.replace('$', ''));
                let showProduct = true;
                
                switch(selectedPrice) {
                    case '0-50':
                        showProduct = price >= 0 && price <= 50;
                        break;
                    case '50-100':
                        showProduct = price > 50 && price <= 100;
                        break;
                    case '100-200':
                        showProduct = price > 100 && price <= 200;
                        break;
                    case '200+':
                        showProduct = price > 200;
                        break;
                }
                
                product.style.display = showProduct ? 'block' : 'none';
            });
        });
    }

    // Admin dashboard charts (placeholder)
    if (document.getElementById('salesChart')) {
        // This would be implemented with a charting library like Chart.js
        console.log('Sales chart placeholder');
    }
});

// AJAX functions
function addToCart(productId, quantity = 1) {
    fetch(`/add_to_cart/${productId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ quantity: quantity })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update cart count
            const cartCount = document.querySelector('.cart-count');
            if (cartCount) {
                cartCount.textContent = data.cart_count;
            }
            // Show success message
            showNotification('Product added to cart!', 'success');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error adding product to cart', 'error');
    });
}

function updateCartItem(cartItemId, quantity) {
    fetch(`/update_cart/${cartItemId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ quantity: quantity })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload(); // Reload to update totals
        }
    });
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 3000);
}

// Admin product management
function showAddProductModal() {
    const modal = new bootstrap.Modal(document.getElementById('addProductModal'));
    modal.show();
}

function editProduct(productId) {
    // Fetch product data and populate edit form
    fetch(`/admin/product/${productId}`)
        .then(response => response.json())
        .then(product => {
            document.getElementById('editProductId').value = product.id;
            document.getElementById('editName').value = product.name;
            document.getElementById('editDescription').value = product.description;
            document.getElementById('editPrice').value = product.price;
            document.getElementById('editBrand').value = product.brand;
            document.getElementById('editStyle').value = product.style;
            document.getElementById('editStock').value = product.stock_quantity;
            document.getElementById('editCategory').value = product.category_id;
            
            const modal = new bootstrap.Modal(document.getElementById('editProductModal'));
            modal.show();
        });
}