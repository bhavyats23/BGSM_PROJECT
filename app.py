from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super-secret-key-change-this-in-production-2026')

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

supabase: Client = create_client(supabase_url, supabase_key)

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
        return render_template('dashboard.html',
            total_products=total_products,
            total_stock_value=round(total_stock_value, 2),
            low_stock_count=low_stock_count,
            today_sales=round(today_sales_revenue, 2),
            low_stock_items=low_stock_items,
            products=products[:8])
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
    filter_type = request.args.get('filter', '')
    if filter_type == 'low-stock':
        products = supabase.table('products').select('*').lte('stock', 10).order('stock').execute().data or []
        return render_template('inventory.html', products=products, filter=filter_type, total_value=0)
    elif filter_type == 'stock-value':
        products = supabase.table('products').select('*').order('name').execute().data or []
        total_value = round(sum(float(p.get('price', 0)) * int(p.get('stock', 0)) for p in products), 2)
        return render_template('inventory.html', products=products, filter=filter_type, total_value=total_value)
    else:
        products = supabase.table('products').select('*').order('name').execute().data or []
        return render_template('inventory.html', products=products, filter=filter_type, total_value=0)


@app.route('/update-stock', methods=['POST'])
@login_required
def update_stock():
    try:
        data = request.get_json()
        supabase.table('products').update({'stock': int(data.get('stock'))}).eq('id', data.get('id')).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/delete-product', methods=['POST'])
@login_required
def delete_product():
    try:
        data = request.get_json()
        p_id = data.get('id') or data.get('delete_id')
        if not p_id:
            return jsonify({"success": False, "error": "No ID provided"}), 400
        supabase.table('products').delete().eq('id', p_id).execute()
        return jsonify({"success": True})
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
                    return jsonify({"success": True})
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
    products  = supabase.table('products').select('*').execute().data or []
    filter_type = request.args.get('filter')
    if filter_type == 'today':
        today_str = datetime.now().strftime('%Y-%m-%d')
        sales_list = supabase.table('sales').select('*').gte('created_at', today_str).order('created_at', desc=True).execute().data or []
    else:
        sales_list = supabase.table('sales').select('*').order('created_at', desc=True).execute().data or []
    return render_template('sales.html', products=products, sales=sales_list, filter=filter_type)


@app.route('/invoice/preview')
@login_required
def invoice_preview():
    subtotal    = 364.0
    tax         = round(subtotal * 0.05, 2)
    discount    = 20.0
    grand       = round(subtotal + tax - discount, 2)
    amount_paid = 400.0
    change      = round(max(amount_paid - grand, 0), 2)
    invoice_data = {
        'invoice_number': 'INV-PREVIEW',
        'datetime': datetime.now().strftime('%d %b %Y, %I:%M %p'),
        'payment_method': 'Cash',
        'subtotal': subtotal,
        'tax': tax,
        'discount': discount,
        'grand': grand,
        'amount_paid': amount_paid,
        'change': change,
        'sale_items': [
            {'name': 'Tomatoes',      'qty': 2, 'unit': 'kg',  'rate': 40,  'total': 80},
            {'name': 'Basmati Rice',  'qty': 1, 'unit': 'kg',  'rate': 120, 'total': 120},
            {'name': 'Milk (Amul)',   'qty': 3, 'unit': 'pcs', 'rate': 28,  'total': 84},
            {'name': 'Onions',        'qty': 1, 'unit': 'kg',  'rate': 35,  'total': 35},
            {'name': 'Bread (Brown)', 'qty': 1, 'unit': 'pcs', 'rate': 45,  'total': 45},
        ]
    }
    return render_template('invoice.html', invoice=invoice_data)


@app.route('/invoice/<sale_id>')
@login_required
def invoice(sale_id):
    try:
        sale = supabase.table('sales').select('*').eq('id', sale_id).single().execute().data
        if not sale:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('sales'))
        product = supabase.table('products').select('*').eq('id', sale['product_id']).single().execute().data
        qty     = int(sale['quantity'])
        rate    = float(product['price']) if product else 0
        total   = float(sale['total_price'])
        subtotal    = total
        tax         = round(subtotal * 0.05, 2)
        discount    = float(sale.get('discount', 0))
        grand       = round(subtotal + tax - discount, 2)
        amount_paid = float(sale.get('amount_paid', grand))
        change      = round(max(amount_paid - grand, 0), 2)
        invoice_data = {
            'invoice_number': f"INV-{str(sale_id)[:8].upper()}",
            'datetime': sale.get('created_at', datetime.now().isoformat()),
            'payment_method': sale.get('payment_method', 'Cash'),
            'subtotal': subtotal, 'tax': tax, 'discount': discount,
            'grand': grand, 'amount_paid': amount_paid, 'change': change,
            'sale_items': [{
                'name': product['name'] if product else 'Unknown',
                'qty': qty,
                'unit': product.get('unit', 'pcs') if product else 'pcs',
                'rate': rate, 'total': total
            }]
        }
        return render_template('invoice.html', invoice=invoice_data)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('sales'))


@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        data = request.form
        try:
            supabase.table('customers').insert({
                'name': data['name'].strip(),
                'phone': data.get('phone', '').strip() or None,
                'email': data.get('email', '').strip() or None,
                'address': data.get('address', '').strip() or None
            }).execute()
            flash('Customer added successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('customers'))
    customers_list = supabase.table('customers').select('*').order('created_at', desc=True).execute().data or []
    now = datetime.now().strftime('%d %b %Y')
    return render_template('customers.html', customers=customers_list, now=now)


@app.route('/customers/delete', methods=['POST'])
@login_required
def delete_customer():
    try:
        data = request.get_json()
        supabase.table('customers').delete().eq('id', data['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/discounts', methods=['GET', 'POST'])
@login_required
def discounts():
    if request.method == 'POST':
        data = request.form
        try:
            supabase.table('discounts').insert({
                'code': data['code'].strip().upper(),
                'description': data.get('description', '').strip() or None,
                'discount_type': data['discount_type'],
                'discount_value': float(data['discount_value']),
                'min_order_value': float(data.get('min_order_value') or 0),
                'expires_at': data.get('expires_at') or None,
                'is_active': True
            }).execute()
            flash('Discount created successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('discounts'))
    discounts_list = supabase.table('discounts').select('*').order('created_at', desc=True).execute().data or []
    return render_template('discounts.html', discounts=discounts_list)


@app.route('/discounts/delete', methods=['POST'])
@login_required
def delete_discount():
    try:
        data = request.get_json()
        supabase.table('discounts').delete().eq('id', data['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/discounts/toggle', methods=['POST'])
@login_required
def toggle_discount():
    try:
        data = request.get_json()
        supabase.table('discounts').update({'is_active': data['is_active']}).eq('id', data['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/purchase-orders', methods=['GET', 'POST'])
@login_required
def purchase_orders():
    if request.method == 'POST':
        data = request.form
        try:
            supabase.table('purchase_orders').insert({
                'product_id': int(data['product_id']),
                'supplier_id': int(data['supplier_id']),
                'quantity': int(data['quantity']),
                'unit_cost': float(data['unit_cost']),
                'status': 'Pending',
                'order_date': data.get('order_date') or datetime.now().strftime('%Y-%m-%d')
            }).execute()
            flash('Purchase order placed successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('purchase_orders'))
    raw_orders   = supabase.table('purchase_orders').select('*').order('created_at', desc=True).execute().data or []
    products     = supabase.table('products').select('id, name, stock').execute().data or []
    suppliers    = supabase.table('suppliers').select('id, name').execute().data or []
    product_map  = {p['id']: p['name'] for p in products}
    supplier_map = {s['id']: s['name'] for s in suppliers}
    orders = []
    for o in raw_orders:
        o['product_name']  = product_map.get(o.get('product_id'), '-')
        o['supplier_name'] = supplier_map.get(o.get('supplier_id'), '-')
        orders.append(o)
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('purchase_orders.html', orders=orders, products=products, suppliers=suppliers, today=today)


@app.route('/purchase-orders/status', methods=['POST'])
@login_required
def update_order_status():
    try:
        data   = request.get_json()
        status = data['status']
        supabase.table('purchase_orders').update({'status': status}).eq('id', data['id']).execute()
        if status == 'Received':
            order   = supabase.table('purchase_orders').select('*').eq('id', data['id']).single().execute().data
            product = supabase.table('products').select('stock').eq('id', order['product_id']).single().execute().data
            if product:
                new_stock = int(product['stock']) + int(order['quantity'])
                supabase.table('products').update({'stock': new_stock}).eq('id', order['product_id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/purchase-orders/delete', methods=['POST'])
@login_required
def delete_order():
    try:
        data = request.get_json()
        supabase.table('purchase_orders').delete().eq('id', data['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500





@app.route('/suppliers', methods=['GET', 'POST'])
@login_required
def suppliers():
    if request.method == 'POST':
        data = request.form
        try:
            supabase.table('suppliers').insert({
                'name': data['name'].strip(),
                'phone': data.get('phone', '').strip() or None,
                'email': data.get('email', '').strip() or None,
                'address': data.get('address', '').strip() or None,
                'product_type': data.get('product_type', '').strip() or None
            }).execute()
            flash('Supplier added successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('suppliers'))
    suppliers_list = supabase.table('suppliers').select('*').order('created_at', desc=True).execute().data or []
    return render_template('suppliers.html', suppliers=suppliers_list)


@app.route('/suppliers/delete', methods=['POST'])
@login_required
def delete_supplier():
    try:
        data = request.get_json()
        supabase.table('suppliers').delete().eq('id', data['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/returns', methods=['GET', 'POST'])
@login_required
def returns():
    if request.method == 'POST':
        data = request.form
        try:
            supabase.table('returns').insert({
                'sale_id': int(data['sale_id']),
                'product_id': int(data['product_id']),
                'quantity': int(data['quantity']),
                'refund_amount': float(data['refund_amount']),
                'reason': data.get('reason', '').strip() or None,
                'status': 'Pending'
            }).execute()
            flash('Return request submitted!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('returns'))

    raw_returns = supabase.table('returns').select('*').order('created_at', desc=True).execute().data or []
    products    = supabase.table('products').select('id, name').execute().data or []
    sales       = supabase.table('sales').select('id, total_price, created_at').order('created_at', desc=True).execute().data or []
    product_map = {p['id']: p['name'] for p in products}
    for r in raw_returns:
        r['product_name'] = product_map.get(r.get('product_id'), '-')
    return render_template('returns.html', returns=raw_returns, products=products, sales=sales)


@app.route('/returns/status', methods=['POST'])
@login_required
def update_return_status():
    try:
        data   = request.get_json()
        status = data['status']
        supabase.table('returns').update({'status': status}).eq('id', data['id']).execute()
        if status == 'Approved':
            ret     = supabase.table('returns').select('*').eq('id', data['id']).single().execute().data
            product = supabase.table('products').select('stock').eq('id', ret['product_id']).single().execute().data
            if product:
                new_stock = int(product['stock']) + int(ret['quantity'])
                supabase.table('products').update({'stock': new_stock}).eq('id', ret['product_id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/returns/delete', methods=['POST'])
@login_required
def delete_return():
    try:
        data = request.get_json()
        supabase.table('returns').delete().eq('id', data['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        data = request.form
        try:
            supabase.table('expenses').insert({
                'title': data['title'].strip(),
                'amount': float(data['amount']),
                'category': data.get('category', 'General'),
                'note': data.get('note', '').strip() or None,
                'expense_date': data.get('expense_date') or datetime.now().strftime('%Y-%m-%d')
            }).execute()
            flash('Expense added successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('expenses'))

    expenses_list = supabase.table('expenses').select('*').order('expense_date', desc=True).execute().data or []

    total_expenses = round(sum(float(e.get('amount', 0)) for e in expenses_list), 2)

    current_month = datetime.now().strftime('%Y-%m')
    monthly_expenses = round(sum(
        float(e.get('amount', 0)) for e in expenses_list
        if e.get('expense_date', '').startswith(current_month)
    ), 2)

    category_totals = {}
    for e in expenses_list:
        cat = e.get('category', 'General')
        category_totals[cat] = round(category_totals.get(cat, 0) + float(e.get('amount', 0)), 2)

    categories = list(category_totals.keys())
    today = datetime.now().strftime('%Y-%m-%d')

    return render_template('expenses.html',
        expenses=expenses_list,
        total_expenses=total_expenses,
        monthly_expenses=monthly_expenses,
        category_totals=category_totals,
        categories=categories,
        today=today)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)