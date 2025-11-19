from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
import string
import os
from werkzeug.utils import secure_filename
from database import db, User, Product, Category, CartItem, Order, OrderItem, Booking, BookingItem

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sunglass_store.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Image upload configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads/products'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create upload directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.context_processor
def inject_current_date():
    return {'current_date': datetime.now().strftime('%Y-%m-%d')}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_order_number():
    return 'ORD' + ''.join(random.choices(string.digits, k=8))

def generate_booking_number():
    return 'BKG' + ''.join(random.choices(string.digits, k=8))

@app.route('/')
def index():
    categories = Category.query.all()
    featured_products = Product.query.filter_by(is_active=True).limit(8).all()
    return render_template('index.html', 
                         categories=categories, 
                         featured_products=featured_products)

@app.route('/products')
def products():
    category_id = request.args.get('category_id', type=int)
    brand = request.args.get('brand')
    style = request.args.get('style')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    
    query = Product.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    if brand:
        query = query.filter(Product.brand.ilike(f'%{brand}%'))
    if style:
        query = query.filter(Product.style.ilike(f'%{style}%'))
    if min_price:
        query = query.filter(Product.price >= min_price)
    if max_price:
        query = query.filter(Product.price <= max_price)
    
    products = query.all()
    categories = Category.query.all()
    brands = db.session.query(Product.brand).distinct().all()
    styles = db.session.query(Product.style).distinct().all()
    
    return render_template('products.html', 
                         products=products, 
                         categories=categories,
                         brands=[b[0] for b in brands],
                         styles=[s[0] for s in styles])

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    related_products = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active == True
    ).limit(4).all()
    
    # Manually pass current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('product_detail.html', 
                         product=product, 
                         related_products=related_products,
                         current_date=current_date)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    
    if product.stock_quantity < quantity:
        flash('Not enough stock available', 'error')
        return redirect(url_for('product_detail', product_id=product_id))
    
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id, 
        product_id=product_id
    ).first()
    
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    flash('Product added to cart successfully!', 'success')
    return redirect(url_for('cart'))

@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/update_cart/<int:cart_item_id>', methods=['POST'])
@login_required
def update_cart(cart_item_id):
    cart_item = CartItem.query.get_or_404(cart_item_id)
    
    if cart_item.user_id != current_user.id:
        flash('Unauthorized action', 'error')
        return redirect(url_for('cart'))
    
    action = request.form.get('action')
    
    if action == 'update':
        quantity = int(request.form.get('quantity', 1))
        if quantity <= 0:
            db.session.delete(cart_item)
        else:
            cart_item.quantity = quantity
    elif action == 'remove':
        db.session.delete(cart_item)
    
    db.session.commit()
    flash('Cart updated successfully!', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty', 'error')
        return redirect(url_for('cart'))
    
    if request.method == 'POST':
        order_number = generate_order_number()
        total_amount = sum(item.product.price * item.quantity for item in cart_items)
        
        order = Order(
            order_number=order_number,
            total_amount=total_amount,
            payment_method=request.form.get('payment_method'),
            shipping_address=request.form.get('shipping_address'),
            user_id=current_user.id
        )
        db.session.add(order)
        
        for cart_item in cart_items:
            order_item = OrderItem(
                order=order,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                price=cart_item.product.price
            )
            db.session.add(order_item)
            
            cart_item.product.stock_quantity -= cart_item.quantity
        
        CartItem.query.filter_by(user_id=current_user.id).delete()
        
        db.session.commit()
        flash(f'Order #{order_number} placed successfully!', 'success')
        return redirect(url_for('orders'))
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/book_product/<int:product_id>', methods=['POST'])
@login_required
def book_product(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    pickup_date = request.form.get('pickup_date')
    
    if product.stock_quantity < quantity:
        flash('Not enough stock available', 'error')
        return redirect(url_for('product_detail', product_id=product_id))
    
    booking_number = generate_booking_number()
    total_amount = product.price * quantity
    
    booking = Booking(
        booking_number=booking_number,
        total_amount=total_amount,
        pickup_date=datetime.strptime(pickup_date, '%Y-%m-%d'),
        user_id=current_user.id
    )
    db.session.add(booking)
    
    booking_item = BookingItem(
        booking=booking,
        product_id=product_id,
        quantity=quantity,
        price=product.price
    )
    db.session.add(booking_item)
    
    product.stock_quantity -= quantity
    
    db.session.commit()
    flash(f'Product booked successfully! Booking #: {booking_number}', 'success')
    return redirect(url_for('bookings'))

@app.route('/orders')
@login_required
def orders():
    user_orders = Order.query.filter_by(user_id=current_user.id).order_by(
        Order.created_at.desc()
    ).all()
    return render_template('orders.html', orders=user_orders)

@app.route('/bookings')
@login_required
def bookings():
    user_bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
        Booking.created_at.desc()
    ).all()
    return render_template('bookings.html', bookings=user_bookings)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        current_user.email = request.form.get('email')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    stats = {
        'total_users': User.query.count(),
        'total_products': Product.query.count(),
        'total_orders': Order.query.count(),
        'total_bookings': Booking.query.count(),
        'recent_orders': Order.query.order_by(Order.created_at.desc()).limit(5).all(),
        'low_stock_products': Product.query.filter(Product.stock_quantity <= 5).all()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/products')
@login_required
def admin_products():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    products = Product.query.all()
    categories = Category.query.all()
    return render_template('admin/products.html', products=products, categories=categories)

@app.route('/admin/add_product', methods=['POST'])
@login_required
def admin_add_product():
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Handle image upload
        image_filename = None
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename != '':
                if allowed_file(image_file.filename):
                    # Generate secure filename
                    filename = secure_filename(image_file.filename)
                    # Add timestamp to make filename unique
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    image_filename = timestamp + filename
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                    image_file.save(image_path)
                else:
                    flash('Invalid file type. Please upload JPEG, PNG, GIF, or WebP images.', 'error')
                    return redirect(url_for('admin_products'))
        
        # Create product
        product = Product(
            name=request.form.get('name'),
            description=request.form.get('description'),
            price=float(request.form.get('price')),
            brand=request.form.get('brand'),
            style=request.form.get('style'),
            color=request.form.get('color'),
            frame_material=request.form.get('frame_material'),
            lens_type=request.form.get('lens_type'),
            stock_quantity=int(request.form.get('stock_quantity')),
            category_id=int(request.form.get('category_id')),
            uv_protection=bool(request.form.get('uv_protection')),
            polarization=bool(request.form.get('polarization')),
            image_url=image_filename  # Save only the filename
        )
        
        db.session.add(product)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding product: {str(e)}', 'error')
        return redirect(url_for('admin_products'))

@app.route('/admin/update_product/<int:product_id>', methods=['POST'])
@login_required
def admin_update_product(product_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    product = Product.query.get_or_404(product_id)
    
    # Handle image upload for update
    if 'image' in request.files:
        image_file = request.files['image']
        if image_file and image_file.filename != '':
            if allowed_file(image_file.filename):
                # Delete old image if exists
                if product.image_url and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], product.image_url)):
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], product.image_url))
                
                # Generate secure filename
                filename = secure_filename(image_file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                image_filename = timestamp + filename
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                image_file.save(image_path)
                product.image_url = image_filename
    
    product.name = request.form.get('name')
    product.description = request.form.get('description')
    product.price = float(request.form.get('price'))
    product.brand = request.form.get('brand')
    product.style = request.form.get('style')
    product.color = request.form.get('color')
    product.frame_material = request.form.get('frame_material')
    product.lens_type = request.form.get('lens_type')
    product.stock_quantity = int(request.form.get('stock_quantity'))
    product.category_id = int(request.form.get('category_id'))
    product.uv_protection = bool(request.form.get('uv_protection'))
    product.polarization = bool(request.form.get('polarization'))
    
    db.session.commit()
    flash('Product updated successfully!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/delete_product/<int:product_id>')
@login_required
def admin_delete_product(product_id):
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/update_order_status/<int:order_id>', methods=['POST'])
@login_required
def admin_update_order_status(order_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    order = Order.query.get_or_404(order_id)
    order.status = request.form.get('status')
    db.session.commit()
    
    flash('Order status updated successfully!', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login failed. Check your email and password.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Get form data
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            terms = request.form.get('terms')
            
            # Basic validation
            if not all([username, email, password, first_name, last_name]):
                flash('All fields are required.', 'error')
                return render_template('register.html')
            
            if len(username) < 3:
                flash('Username must be at least 3 characters long.', 'error')
                return render_template('register.html')
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long.', 'error')
                return render_template('register.html')
            
            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('register.html')
            
            if not terms:
                flash('You must agree to the terms and conditions.', 'error')
                return render_template('register.html')
            
            # Check if user already exists
            if User.query.filter_by(email=email).first():
                flash('Email already registered. Please use a different email.', 'error')
                return render_template('register.html')
            
            if User.query.filter_by(username=username).first():
                flash('Username already taken. Please choose a different username.', 'error')
                return render_template('register.html')
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
                first_name=first_name,
                last_name=last_name
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            # Log the user in after registration
            login_user(new_user)
            
            flash('🎉 Registration successful! Welcome to SunStyle!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            print(f"Registration error: {str(e)}")  # For debugging
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/test-date')
def test_date():
    return render_template('test_date.html')

@app.route('/test-register', methods=['GET', 'POST'])
def test_register():
    if request.method == 'POST':
        print("Form submitted!")
        print("Form data:", request.form)
        return "Form received successfully!"
    return '''
    <form method="POST">
        <input type="text" name="username" required>
        <input type="email" name="email" required>
        <input type="password" name="password" required>
        <button type="submit">Test Submit</button>
    </form>
    '''
@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if email:
        # Here you would typically save to database or send to email service
        flash('Thank you for subscribing to our newsletter!', 'success')
    else:
        flash('Please enter a valid email address.', 'error')
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

def init_db():
    with app.app_context():
        db.create_all()
        
        # Create admin user if not exists
        if not User.query.filter_by(email='admin@sunglassstore.com').first():
            admin_user = User(
                username='admin',
                email='admin@sunglassstore.com',
                password=generate_password_hash('admin123'),
                first_name='Admin',
                last_name='User',
                is_admin=True
            )
            db.session.add(admin_user)
        
        # Create sample categories if not exists
        if Category.query.count() == 0:
            categories = [
                Category(name='Men', description='Stylish sunglasses for men with premium designs'),
                Category(name='Women', description='Elegant sunglasses for women with fashionable frames'),
                Category(name='Kids', description='Fun and durable sunglasses for children'),
                Category(name='Sports', description='High-performance sunglasses for sports activities'),
                Category(name='Luxury', description='Premium designer sunglasses from top brands')
            ]
            db.session.add_all(categories)
        
        # Create sample products if not exists
        if Product.query.count() == 0:
            products = [
                Product(
                    name='Classic Aviator Gold',
                    description='Timeless aviator sunglasses with gold metal frame and green lenses. Perfect for any occasion with UV400 protection.',
                    price=149.99,
                    discount_price=179.99,
                    brand='Ray-Ban',
                    style='Aviator',
                    color='Gold/Green',
                    frame_material='Metal',
                    lens_type='Glass',
                    uv_protection=True,
                    polarization=True,
                    stock_quantity=25,
                    category_id=1,
                    image_url='classic_aviator.jpg'
                ),
                Product(
                    name='Wayfarer Classic Black',
                    description='Iconic wayfarer design with black acetate frame and gray lenses. A fashion staple with polarized protection.',
                    price=129.99,
                    brand='Ray-Ban',
                    style='Wayfarer',
                    color='Black/Gray',
                    frame_material='Acetate',
                    lens_type='Polycarbonate',
                    uv_protection=True,
                    polarization=True,
                    stock_quantity=30,
                    category_id=2,
                    image_url='wayfarer_black.jpg'
                )
            ]
            db.session.add_all(products)
        
        db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)