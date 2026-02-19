from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super-secret-key-change-this-in-production-2026')

# Supabase connection
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

supabase: Client = create_client(supabase_url, supabase_key)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, email, role='user'):
        self.id = user_id
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    try:
        role_data = supabase.table('users').select('role').eq('id', user_id).single().execute().data
        role = role_data.get('role', 'user') if role_data else 'user'
        return User(user_id, "loaded-from-supabase", role)
    except:
        return None

CATEGORIES = ["Fruits", "Vegetables", "Dairy", "Snacks", "Grains", "Beverages"]

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            auth_response = supabase.auth.sign_in_with_password({'email': email, 'password': password})
            if auth_response.user:
                user_id = auth_response.user.id
                role_response = supabase.table('users').select('role').eq('id', user_id).single().execute()
                role = role_response.data.get('role', 'user') if role_response.data else 'user'
                if role != 'admin':
                    flash('Access denied: Admin privileges required', 'danger')
                    return redirect(url_for('login'))
                user = User(user_id, email, role)
                login_user(user, remember=True)
                return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    supabase.auth.sign_out()
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    try:
        products = supabase.table('products').select('*').execute().data or []
        today = datetime.now().strftime('%Y-%m-%d')
        sales_today_data = supabase.table('sales').select('*').gte('created_at', today).execute().data or []

        total_products = len(products)
        total_stock_value = sum(float(p.get('price', 0)) * int(p.get('stock', 0)) for p in products)
        low_stock_items = [p for p in products if int(p.get('stock', 0)) <= 10]
        low_stock_count = len(low_stock_items)
        today_sales_revenue = sum(float(s.get('total_price', 0)) for s in sales_today_data)

        return render_template(
            'dashboard.html',
            total_products=total_products,
            total_stock_value=round(total_stock_value, 2),
            low_stock_count=low_stock_count,
            today_sales=round(today_sales_revenue, 2),
            low_stock_items=low_stock_items,
            products=products[:8]
        )
    except Exception as e:
        return render_template('dashboard.html', total_products=0, total_stock_value=0, low_stock_count=0, today_sales=0)

@app.route('/add-product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        data = request.form
        supabase.table('products').insert({
            'name': data['name'].strip(),
            'price': float(data['price']),
            'category': data['category'],
            'stock': int(data['stock'])
        }).execute()
        flash('Product added successfully', 'success')
        return redirect(url_for('inventory'))
    return render_template('add_product.html', categories=CATEGORIES)

@app.route('/inventory')
@login_required
def inventory():
    products = supabase.table('products').select('*').order('name').execute().data or []
    return render_template('inventory.html', products=products)

# --- UPDATED: DEDICATED JSON ROUTES FOR AJAX ---
# This fixes the "Unexpected token <" error by ensuring only JSON is returned

@app.route('/update-stock', methods=['POST'])
@login_required
def update_stock():
    try:
        data = request.get_json()
        p_id = data.get('id')
        p_stock = data.get('stock')
        
        supabase.table('products').update({'stock': int(p_stock)}).eq('id', p_id).execute()
        return jsonify({"success": True, "message": "Stock updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/delete-product', methods=['POST'])
@login_required
def delete_product():
    try:
        data = request.get_json()
        # Supporting both 'id' and 'delete_id' for maximum compatibility
        p_id = data.get('id') or data.get('delete_id')
        
        if not p_id:
            return jsonify({"success": False, "error": "No ID provided"}), 400

        supabase.table('products').delete().eq('id', p_id).execute()
        return jsonify({"success": True, "message": "Product removed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        try:
            product = supabase.table('products').select('*').eq('id', data['product_id']).single().execute().data
            quantity = int(data['quantity'])
            
            if product and product['stock'] >= quantity:
                total_price = product['price'] * quantity
                supabase.table('sales').insert({
                    'product_id': product['id'],
                    'quantity': quantity,
                    'total_price': total_price
                }).execute()
                
                supabase.table('products').update({'stock': product['stock'] - quantity}).eq('id', product['id']).execute()
                
                if request.is_json:
                    return jsonify({"success": True, "message": "Sale recorded"})
                flash('Sale recorded successfully', 'success')
            else:
                if request.is_json:
                    return jsonify({"success": False, "error": "Insufficient stock"}), 400
                flash('Insufficient stock', 'danger')
        except Exception as e:
            if request.is_json:
                return jsonify({"success": False, "error": str(e)}), 500
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('sales'))

    products = supabase.table('products').select('*').execute().data or []
    sales_list = supabase.table('sales').select('*').order('created_at', desc=True).execute().data or []
    return render_template('sales.html', products=products, sales=sales_list)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)