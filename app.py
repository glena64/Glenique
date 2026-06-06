from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from bson.objectid import ObjectId
from datetime import datetime
import os
import re
from werkzeug.utils import secure_filename

database_url = os.environ.get("DATABASE_URL", "mongodb://localhost:27017/")
client = pymongo.MongoClient(database_url)
db = client["glenbae"]

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'replace_this_with_a_highly_secure_random_string'
PLATFORM_NAME = os.environ.get("NAME", "ECOMMERCE")

# --- App Configuration ---
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
try:
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
except OSError:
    pass # Vercel uses a read-only filesystem; prevent crashing on startup

@app.context_processor
def inject_platform_name():
    """Makes PLATFORM_NAME available in all templates."""
    return dict(PLATFORM_NAME=PLATFORM_NAME)

def generate_slug(text):
    """Generates a URL-friendly slug from a product name."""
    return re.sub(r'[\W_]+', '-', text.lower()).strip('-')

# --- Decorators for Role-Based Access Control ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', role='user'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') != role:
                return "Unauthorized: You do not have permission to view this page.", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    # Redirect logged-in merchants and admins to their dashboards
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session.get('role') == 'merchant':
            return redirect(url_for('merchant_dashboard'))
            
    # Implement basic search functionality
    search_query = request.args.get('q', '')
    sort_by = request.args.get('sort', '')
    query = {}
    if search_query:
        query['name'] = {'$regex': search_query, '$options': 'i'}
        
    cursor = db.products.find(query)
    if sort_by == 'price_asc':
        cursor = cursor.sort('price', 1)
    elif sort_by == 'price_desc':
        cursor = cursor.sort('price', -1)
    elif sort_by == 'most_sold':
        cursor = cursor.sort('sales_count', -1)
        
    products = list(cursor)
    return render_template('index.html', products=products, search_query=search_query, sort_by=sort_by)

# --- Authentication Routes ---
@app.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if 'user_id' in session:
        return redirect(url_for('index'))
    if role not in ['user', 'merchant']:
        flash('Invalid role specified.')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        addresses = request.form.getlist('addresses')
        email = request.form.get('email')
        password = request.form.get('password')

        if db.users.find_one({'email': email}):
            flash('Email already registered!')
            return redirect(url_for('signup', role=role))

        hashed_password = generate_password_hash(password)
        db.users.insert_one({
            'name': name,
            'email': email,
            'phone': phone,
            'password_hash': hashed_password,
            'role': role,
            'addresses': [addr.strip() for addr in addresses if addr.strip()],
            'created_at': datetime.utcnow()
        })
        
        # Automatically log the user in after successful signup
        user = db.users.find_one({'email': email})
        session['user_id'] = str(user['_id'])
        session['role'] = user['role']
        flash(f'Signup successful! Welcome to {PLATFORM_NAME}.')
        
        if role == 'merchant':
            return redirect(url_for('merchant_dashboard'))
        return redirect(url_for('index'))
    return render_template('signup.html', role=role)

@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if 'user_id' in session:
        return redirect(url_for('index'))
    if role not in ['user', 'merchant']:
        flash('Invalid role specified.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = db.users.find_one({'email': email, 'role': role})
        if not user:
             user_fallback = db.users.find_one({'email': email})
             if user_fallback and user_fallback.get('role') != 'admin':
                 flash(f'Please login through the {user_fallback["role"]} portal.')
                 return redirect(url_for('login', role=user_fallback['role']))
                 
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            flash('Logged in successfully!')
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'merchant':
                return redirect(url_for('merchant_dashboard'))
            else:
                return redirect(url_for('list_products'))
        
        flash('Invalid email or password.')
    return render_template('login.html', role=role)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('index'))

# --- Legal/Policy Routes ---
@app.route('/policy/<policy_name>')
def policy(policy_name):
    policies = {
        'terms': (
            'Terms of Service',
            f"""
            <p>Welcome to {PLATFORM_NAME}. These Terms of Service ("Terms") govern your use of our website, services, and applications (collectively, the "Platform"). By accessing or using the Platform, you agree to be bound by these Terms. If you do not agree to these Terms, you may not use the Platform.</p>
            <h4>1. User Accounts</h4>
            <p>To access certain features, you must create an account. You agree to provide accurate, current, and complete information during the registration process and to update such information to keep it accurate. You are responsible for safeguarding your password and for all activities that occur under your account. You agree to notify us immediately of any unauthorized use of your account.</p>
            <h4>2. Prohibited Conduct</h4>
            <p>You agree not to engage in any of the following prohibited activities: (i) using the Platform for any illegal purpose or in violation of any local, state, national, or international law; (ii) violating or encouraging others to violate the rights of third parties, including intellectual property rights; (iii) posting, uploading, or distributing any content that is unlawful, defamatory, libelous, or that a reasonable person could deem to be objectionable, profane, or indecent; (iv) interfering with the security-related features of the Platform.</p>
            <h4>3. Limitation of Liability</h4>
            <p>In no event will {PLATFORM_NAME}, its affiliates, or their licensors, service providers, employees, agents, officers, or directors be liable for damages of any kind, under any legal theory, arising out of or in connection with your use, or inability to use, the Platform. The Platform is provided on an "as is" and "as available" basis without any warranties of any kind, either express or implied.</p>
            """
        ),
        'privacy': (
            'Privacy Policy',
            f"""
            <p>This Privacy Policy describes how {PLATFORM_NAME} ("we," "us," or "our") collects, uses, and discloses your personal information when you use our Platform. We are committed to protecting your privacy and ensuring that your personal information is handled in a safe and responsible manner.</p>
            <h4>1. Information We Collect</h4>
            <p>We collect information you provide directly to us, such as when you create an account, place an order, or contact customer support. This may include your name, email address, phone number, shipping address, and payment information. We also collect information automatically as you navigate the Platform, such as your IP address, browser type, and browsing behavior.</p>
            <h4>2. How We Use Your Information</h4>
            <p>We use the information we collect to: (i) process and fulfill your orders; (ii) communicate with you about your account and provide customer support; (iii) personalize and improve your experience on the Platform; (iv) send you marketing communications, with your consent; and (v) prevent fraudulent transactions and enhance the security of our Platform.</p>
            <h4>3. Information Sharing</h4>
            <p>We do not sell your personal information to third parties. We may share your information with third-party service providers who perform services on our behalf, such as payment processing, order fulfillment, and data analysis. We may also share information with merchants to facilitate your orders or if required by law to respond to a subpoena, court order, or other governmental request.</p>
            """
        ),
        'cancellation': (
            'Cancellation & Refund Policy',
            f"""
            <p>At {PLATFORM_NAME}, we are committed to providing an efficient and streamlined order processing system to ensure you receive your products as quickly as possible. To achieve this, our fulfillment process with our network of merchants begins immediately after an order is placed.</p>
            <h4>1. No Cancellation Policy</h4>
            <p>Once an order is successfully placed and confirmed on the Platform, it cannot be cancelled or modified. Users are urged to carefully review their cart and shipping details before completing the checkout process. This policy is in place to maintain operational integrity and to prevent disruptions to our merchants' fulfillment workflows.</p>
            <h4>2. No Refund Policy</h4>
            <p>All sales on the Platform are final. We do not offer refunds or returns for any products purchased, except where required by applicable consumer protection law. This includes, but is not limited to, cases of buyer's remorse, incorrect size selection, or other personal reasons. By completing a purchase, you acknowledge and agree to this no-refund policy.</p>
            <h4>3. Damaged or Incorrect Items</h4>
            <p>In the rare event that you receive a product that is damaged, defective, or incorrect, please contact the respective merchant through the order details page within 48 hours of delivery. The merchant will be responsible for assessing the situation and determining the appropriate resolution, which may include a replacement or store credit at their sole discretion.</p>
            """
        ),
        'user': (
            'User Policy',
            f"""
            <p>This User Policy outlines the standards of conduct expected from all users of the {PLATFORM_NAME} Platform. Your access to and use of the service is conditioned upon your acceptance of and compliance with this policy.</p>
            <h4>1. Account Integrity</h4>
            <p>You are responsible for all activity that occurs under your account. You must maintain the security of your account credentials and not share them with others. You must provide accurate and complete information and keep your account information updated. Misrepresentation of identity or affiliation is strictly prohibited.</p>
            <h4>2. Community Conduct and Reviews</h4>
            <p>Users are encouraged to leave honest and constructive reviews for products they have purchased and received. All user-generated content, including reviews and communications, must be respectful and free of harassment, hate speech, or obscenity. We reserve the right, but not the obligation, to monitor and remove content that violates these standards.</p>
            <h4>3. Prohibited Activities</h4>
            <p>You may not use the Platform to engage in fraudulent activities, including but not limited to, creating fake accounts, manipulating reviews, or interfering with other users' transactions. Any attempt to compromise the Platform's security, reverse-engineer its systems, or use automated scripts to scrape data is strictly forbidden and will result in immediate account termination and potential legal action.</p>
            """
        ),
        'merchant': (
            'Merchant Policy',
            f"""
            <p>This Merchant Policy outlines the responsibilities and standards for sellers on the {PLATFORM_NAME} Platform. Adherence to this policy is mandatory for maintaining a merchant account in good standing.</p>
            <h4>1. Product and Listing Integrity</h4>
            <p>Merchants must provide accurate, complete, and truthful information for all product listings. This includes high-quality images, detailed descriptions, correct pricing, and accurate stock levels. The sale of counterfeit, illegal, or prohibited items is strictly forbidden. Merchants are solely responsible for the authenticity and quality of their products.</p>
            <h4>2. Order Fulfillment and Customer Service</h4>
            <p>Merchants are obligated to fulfill orders in a timely and professional manner, as defined by the fulfillment status updates ('Packed', 'Delivered'). Communication with customers regarding their orders must be prompt and courteous. Failure to manage inventory or fulfill orders can lead to penalties, including account suspension.</p>
            <h4>3. Compliance and Payouts</h4>
            <p>Merchants must comply with all applicable laws and regulations, as well as all policies set forth by {PLATFORM_NAME}. Payouts for fulfilled orders will be processed according to the schedule and fee structure outlined in your merchant agreement. We reserve the right to withhold payouts in cases of policy violations or suspected fraudulent activity pending an investigation.</p>
            """
        )
    }
    policy_data = policies.get(policy_name, ('Policy Not Found', 'The requested policy does not exist.'))
    return render_template('policy.html', title=policy_data[0], content=policy_data[1])

# --- Customer/User Routes ---
@app.route('/products')
def list_products():
    products = list(db.products.find())
    return render_template('products.html', products=products)

@app.route('/product/<slug>/<product_id>')
def product_detail(slug, product_id):
    product = db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash('Product not found.')
        return redirect(url_for('index'))
    return render_template('product_detail.html', product=product)

@app.route('/cart')
@login_required
@role_required('user')
def view_cart():
    cart_items = list(db.carts.find({'user_id': session['user_id']}))
    
    total_cart_value = 0
    detailed_cart = []
    for item in cart_items:
        product = db.products.find_one({'_id': ObjectId(item['product_id'])})
        if product:
            item_total = product['price'] * item['quantity']
            total_cart_value += item_total
            detailed_cart.append({
                'cart_id': item['_id'],
                'product': product,
                'quantity': item['quantity'],
                'item_total': item_total
            })
            
    return render_template('cart.html', cart=detailed_cart, total=total_cart_value)

@app.route('/cart/add', methods=['POST'])
@login_required
@role_required('user')
def add_to_cart():
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    
    existing_item = db.carts.find_one({'user_id': session['user_id'], 'product_id': product_id})
    if existing_item:
        db.carts.update_one({'_id': existing_item['_id']}, {'$inc': {'quantity': quantity}})
    else:
        db.carts.insert_one({
            'user_id': session['user_id'],
            'product_id': product_id,
            'quantity': quantity,
            'added_at': datetime.utcnow()
        })
    flash('Product added to cart!')
    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<cart_id>', methods=['POST'])
@login_required
@role_required('user')
def remove_from_cart(cart_id):
    db.carts.delete_one({'_id': ObjectId(cart_id), 'user_id': session['user_id']})
    flash('Item removed from cart.')
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['POST'])
@login_required
@role_required('user')
def checkout():
    cart_items = list(db.carts.find({'user_id': session['user_id']}))
    if not cart_items:
        flash('Your cart is empty.')
        return redirect(url_for('view_cart'))
        
    orders_placed = 0
    for item in cart_items:
        product = db.products.find_one({'_id': ObjectId(item['product_id'])})
        if product and product['stock'] >= item['quantity']:
            total_amount = product['price'] * item['quantity']
            
            db.orders.insert_one({
                'user_id': session['user_id'],
                'merchant_id': product['merchant_id'],
                'product_id': str(product['_id']),
                'product_name': product['name'],
                'quantity': item['quantity'],
                'total_amount': total_amount,
                'status': 'received',
                'created_at': datetime.utcnow()
            })
            
            db.products.update_one(
                {'_id': product['_id']}, 
                {'$inc': {'stock': -item['quantity'], 'sales_count': item['quantity']}}
            )
            
            # Generate notifications for the merchant
            db.notifications.insert_one({
                'merchant_id': product['merchant_id'],
                'message': f"New order received for {item['quantity']}x {product['name']}",
                'type': 'order',
                'read': False,
                'created_at': datetime.utcnow()
            })
            if product['stock'] - item['quantity'] <= 5:
                db.notifications.insert_one({
                    'merchant_id': product['merchant_id'],
                    'message': f"Low stock alert: '{product['name']}' is down to {product['stock'] - item['quantity']} items left.",
                    'type': 'alert',
                    'read': False,
                    'created_at': datetime.utcnow()
                })
                
            orders_placed += 1
            
    if orders_placed > 0:
        db.carts.delete_many({'user_id': session['user_id']})
        flash('Order placed successfully for available items!')
    else:
        flash('Unable to place order. Items may be out of stock.')
        
    return redirect(url_for('list_products'))

# --- User Dashboard & Wishlist ---
@app.route('/wishlist/add', methods=['POST'])
@login_required
@role_required('user')
def add_to_wishlist():
    product_id = request.form.get('product_id')
    if not db.wishlists.find_one({'user_id': session['user_id'], 'product_id': product_id}):
        db.wishlists.insert_one({
            'user_id': session['user_id'],
            'product_id': product_id,
            'added_at': datetime.utcnow()
        })
        flash('Product added to your wishlist!')
    else:
        flash('Product is already in your wishlist.')
    return redirect(request.referrer or url_for('user_dashboard'))

@app.route('/wishlist/remove/<product_id>', methods=['POST'])
@login_required
@role_required('user')
def remove_from_wishlist(product_id):
    db.wishlists.delete_one({'user_id': session['user_id'], 'product_id': product_id})
    flash('Product removed from your wishlist.')
    return redirect(request.referrer or url_for('user_dashboard'))


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
@role_required('user')
def user_dashboard():
    user_id = session['user_id']
    
    if request.method == 'POST':
        if 'update_profile' in request.form:
            name = request.form.get('name')
            phone = request.form.get('phone')
            new_password = request.form.get('new_password')
            addresses_list = request.form.get('addresses', '').split('\n')
            addresses = [addr.strip() for addr in addresses_list if addr.strip()]
            
            update_data = {'name': name, 'phone': phone, 'addresses': addresses}
            if new_password:
                update_data['password_hash'] = generate_password_hash(new_password)
                
            db.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
            flash('Profile updated successfully!')
            return redirect(url_for('user_dashboard') + '#profile-section')

    user = db.users.find_one({'_id': ObjectId(user_id)})
    orders = list(db.orders.find({'user_id': user_id}).sort('created_at', -1))
    
    wishlist_items = list(db.wishlists.find({'user_id': user_id}))
    wishlist_product_ids = [ObjectId(item['product_id']) for item in wishlist_items]
    wishlist = list(db.products.find({'_id': {'$in': wishlist_product_ids}}))
    
    return render_template('user_dashboard.html', user=user, orders=orders, wishlist=wishlist, is_dashboard=True)

# --- Merchant Routes ---
@app.route('/merchant/dashboard', methods=['GET', 'POST'])
@login_required
@role_required('merchant')
def merchant_dashboard():
    if request.method == 'POST':
        # Handle posting a new product
        if 'add_product' in request.form:
            name = request.form.get('name')
            sizes_list = request.form.getlist('sizes')
            sizes = [s.strip() for s in sizes_list if s.strip()]
            
            # Handle File Uploads (Multiple Images)
            image_paths = []
            if 'images' in request.files:
                for file in request.files.getlist('images'):
                    if file.filename != '':
                        filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
                        try:
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                            image_paths.append(f"static/uploads/{filename}")
                        except OSError:
                            # Note: Vercel is read-only. For production, integrate Cloudinary, S3, etc.
                            flash("Warning: Image saves are disabled in this serverless environment.")

            db.products.insert_one({
                'merchant_id': session['user_id'],
                'name': name,
                'slug': generate_slug(name),
                'description': request.form.get('description'),
                'price': float(request.form.get('price')),
                'stock': int(request.form.get('stock')),
                'sizes': sizes,
                'images': image_paths,
                'sales_count': 0,
                'created_at': datetime.utcnow()
            })
            
            # Notification for adding product
            db.notifications.insert_one({
                'merchant_id': session['user_id'],
                'message': f"Product '{name}' was successfully added to your catalog.",
                'type': 'product',
                'read': False,
                'created_at': datetime.utcnow()
            })
            flash('Product added successfully!')
            
        # Handle deleting a product
        elif 'delete_product' in request.form:
            product_id = request.form.get('delete_product')
            product = db.products.find_one({'_id': ObjectId(product_id), 'merchant_id': session['user_id']})
            if product:
                # Erase associated image files to clean up storage
                for img_path in product.get('images', []):
                    full_path = os.path.join(app.root_path, img_path)
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                        except Exception:
                            pass
                db.products.delete_one({'_id': ObjectId(product_id)})
                flash('Product and its images deleted successfully!')
                
        # Handle updating order fulfillment status
        elif 'update_order' in request.form:
            order_id = request.form.get('order_id')
            new_status = request.form.get('status')
            db.orders.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': new_status}})
            flash('Order status updated!')
            return redirect(url_for('merchant_dashboard') + '#orders-section')
            
        elif 'update_profile' in request.form:
            name = request.form.get('name')
            phone = request.form.get('phone')
            new_password = request.form.get('new_password')
            addresses_list = request.form.get('addresses', '').split('\n')
            addresses = [addr.strip() for addr in addresses_list if addr.strip()]
            
            update_data = {'name': name, 'phone': phone, 'addresses': addresses}
            if new_password:
                update_data['password_hash'] = generate_password_hash(new_password)
                
            db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': update_data})
            flash('Profile updated successfully!')
            return redirect(url_for('merchant_dashboard') + '#profile-section')
        
        return redirect(url_for('merchant_dashboard'))

    merchant = db.users.find_one({'_id': ObjectId(session['user_id'])})
    products = list(db.products.find({'merchant_id': session['user_id']}))
    total_products = len(products)
    
    order_status_filter = request.args.get('status', '')
    order_query = {'merchant_id': session['user_id']}
    if order_status_filter:
        order_query['status'] = order_status_filter
    orders = list(db.orders.find(order_query).sort('created_at', -1))
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    stat_query = {'merchant_id': session['user_id']}
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        stat_query['created_at'] = {'$gte': start_dt, '$lte': end_dt}
        
    stats_orders = list(db.orders.find(stat_query))
    total_sales = sum(order['total_amount'] for order in stats_orders)
    total_orders_count = len(stats_orders)
    
    notifications = list(db.notifications.find({'merchant_id': session['user_id']}).sort('created_at', -1))
    unread_count = db.notifications.count_documents({'merchant_id': session['user_id'], 'read': False})
    
    return render_template('merchant_dashboard.html', merchant=merchant, products=products, total_products=total_products, orders=orders, total_sales=total_sales, total_orders_count=total_orders_count, start_date=start_date, end_date=end_date, notifications=notifications, unread_count=unread_count, is_dashboard=True)

@app.route('/merchant/notifications/read', methods=['POST'])
@login_required
@role_required('merchant')
def mark_notifications_read():
    db.notifications.update_many(
        {'merchant_id': session['user_id'], 'read': False},
        {'$set': {'read': True}}
    )
    return '', 204

# --- Admin Routes ---
@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = {}
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query['created_at'] = {'$gte': start_dt, '$lte': end_dt}
        
    orders = list(db.orders.find(query).sort('created_at', -1))
    total_sales = sum(order['total_amount'] for order in orders)
    
    return render_template('admin_dashboard.html', orders=orders, total_sales=total_sales, start_date=start_date, end_date=end_date, is_dashboard=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)