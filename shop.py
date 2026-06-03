import sys
import sqlite3
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtPrintSupport import *
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import textwrap

class DatabaseManager:
    def __init__(self, db_path="cosmetics_shop.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Categories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT
            )
        """)
        
        # Items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category_id INTEGER,
                brand TEXT,
                description TEXT,
                cost_price REAL,
                selling_price REAL,
                stock_quantity INTEGER DEFAULT 0,
                reorder_level INTEGER DEFAULT 10,
                supplier TEXT,
                expiry_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        """)
        
        # Sales table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                sale_type TEXT NOT NULL,
                customer_name TEXT,
                customer_phone TEXT,
                customer_address TEXT,
                subtotal REAL,
                vat_amount REAL,
                total_amount REAL,
                payment_status TEXT DEFAULT 'pending',
                payment_method TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Sale items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                item_id INTEGER,
                quantity INTEGER,
                unit_price REAL,
                total_price REAL,
                FOREIGN KEY (sale_id) REFERENCES sales (id),
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        """)
        
        # Purchase orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT UNIQUE NOT NULL,
                supplier_name TEXT NOT NULL,
                supplier_contact TEXT,
                order_type TEXT NOT NULL,
                total_amount REAL,
                paid_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expected_delivery DATE,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Purchase order items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id INTEGER,
                item_description TEXT,
                quantity INTEGER,
                unit_price REAL,
                total_price REAL,
                FOREIGN KEY (po_id) REFERENCES purchase_orders (id)
            )
        """)
        
        # Company settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                company_address TEXT,
                company_phone TEXT,
                company_email TEXT,
                company_website TEXT,
                kra_pin TEXT,
                vat_rate REAL DEFAULT 16.0,
                logo_path TEXT,
                invoice_prefix TEXT DEFAULT 'INV',
                receipt_prefix TEXT DEFAULT 'RCP',
                receipt_footer TEXT,
                printer_settings TEXT
            )
        """)
        
        # Create default admin user
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        if cursor.fetchone()[0] == 0:
            admin_password = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, email) 
                VALUES ('admin', ?, 'admin', 'admin@cosmetics.com')
            """, (admin_password,))
            
            # Create test salesperson
            salesperson_password = hashlib.sha256("sales123".encode()).hexdigest()
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, email) 
                VALUES ('sales', ?, 'salesperson', 'sales@cosmetics.com')
            """, (salesperson_password,))
        
        # Create default categories for cosmetics
        default_categories = [
            ("Skincare", "Facial cleansers, moisturizers, serums, and treatments"),
            ("Makeup", "Foundation, lipstick, eyeshadow, mascara, and other makeup products"),
            ("Hair Care", "Shampoos, conditioners, hair oils, and styling products"),
            ("Fragrances", "Perfumes, body sprays, and colognes"),
            ("Bath & Body", "Body washes, lotions, scrubs, and bath salts"),
            ("Nail Care", "Nail polishes, removers, and nail treatments"),
            ("Men's Grooming", "Beard oils, shaving creams, and men's skincare"),
            ("Tools & Accessories", "Brushes, sponges, applicators, and beauty tools")
        ]
        
        for category, description in default_categories:
            cursor.execute("""
                INSERT OR IGNORE INTO categories (name, description) 
                VALUES (?, ?)
            """, (category, description))
        
        # Create default company settings
        cursor.execute("SELECT COUNT(*) FROM company_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO company_settings 
                (company_name, company_address, company_phone, company_email, company_website, kra_pin, vat_rate, receipt_footer) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("Glamour Cosmetics", "123 Beauty Street, Nairobi, Kenya", "+254 700 000 000", 
                  "info@glamourcosmetics.com", "www.glamourcosmetics.com", "P051234567V", 16.0,
                  "Thank you for shopping with us!\nFollow us on Instagram: @glamourcosmetics\nQuality products for your beauty needs"))
        
        # Add sample products
        cursor.execute("SELECT COUNT(*) FROM items")
        if cursor.fetchone()[0] == 0:
            sample_products = [
                ("COS001", "Hydrating Facial Cleanser", "Skincare", "Glow Beauty", "Gentle foaming cleanser", 300, 580, 50, 10, "Beauty Supply Co.", "2025-12-31"),
                ("COS002", "Matte Lipstick - Red", "Makeup", "ColorPop", "Long-lasting matte finish", 250, 450, 100, 15, "Makeup Wholesalers", "2026-06-30"),
                ("COS003", "Argan Hair Oil", "Hair Care", "Nature's Essence", "Nourishing hair treatment", 400, 750, 30, 8, "Hair Products Ltd", "2025-09-30"),
                ("COS004", "Eau de Parfum - Rose", "Fragrances", "Luxury Scents", "Romantic floral fragrance", 800, 1500, 20, 5, "Fragrance Importers", "2027-01-15"),
                ("COS005", "Shea Body Butter", "Bath & Body", "Natural Glow", "Deep moisturizing", 200, 380, 60, 12, "Body Care Supplies", "2025-08-31"),
            ]
            
            for product in sample_products:
                # Get category id
                cursor.execute("SELECT id FROM categories WHERE name = ?", (product[2],))
                cat_id = cursor.fetchone()
                if cat_id:
                    cursor.execute("""
                        INSERT INTO items 
                        (item_code, name, category_id, brand, description, cost_price, selling_price, 
                         stock_quantity, reorder_level, supplier, expiry_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (product[0], product[1], cat_id[0], product[3], product[4], 
                          product[5], product[6], product[7], product[8], product[9], product[10]))
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)

class LoginDialog(QDialog):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Glamour Cosmetics - Login")
        self.setFixedSize(400, 350)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FF69B4, stop:1 #FF1493);
            }
            QLabel {
                font-size: 14px;
                color: white;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #FF69B4;
                border-radius: 5px;
                font-size: 14px;
                background-color: white;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Logo/Title
        title = QLabel("✨ Glamour Cosmetics ✨")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin: 20px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Management System")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 16px; color: #FFE0E0; margin-bottom: 30px;")
        layout.addWidget(subtitle)
        
        # Login form
        form_widget = QWidget()
        form_widget.setStyleSheet("background-color: rgba(255,255,255,0.9); border-radius: 10px; padding: 20px;")
        form_layout = QFormLayout(form_widget)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        form_layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_input)
        
        layout.addWidget(form_widget)
        
        # Login button
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)
        
        # Role info
        info_label = QLabel("Demo Accounts:\nAdmin: admin/admin123\nSales: sales/sales123")
        info_label.setStyleSheet("font-size: 11px; color: #FFE0E0; margin-top: 10px;")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        self.setLayout(layout)
        
        # Enter key to login
        self.password_input.returnPressed.connect(self.login)
    
    def login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password")
            return
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, role, email 
            FROM users 
            WHERE username = ? AND password_hash = ?
        """, (username, password_hash))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            self.user_data = {
                'id': user[0],
                'username': user[1],
                'role': user[2],
                'email': user[3]
            }
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid username or password")

class ReceiptPrinter:
    @staticmethod
    def generate_html_receipt(sale_data, company_data, cart_items, sale_type):
        """Generate beautiful HTML receipt"""
        
        # Calculate VAT exclusive prices if sale_type is invoice
        if sale_type == "invoice":
            vat_rate = company_data.get('vat_rate', 16)
            for item in cart_items:
                item['price_excl_vat'] = item['price'] / (1 + vat_rate/100)
                item['vat_amount'] = item['price'] - item['price_excl_vat']
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{'INVOICE' if sale_type == 'invoice' else 'PROFORMA' if sale_type == 'proforma' else 'CONSIGNMENT NOTE'}</title>
            <style>
                @page {{
                    size: 80mm 297mm;
                    margin: 5mm;
                }}
                body {{
                    font-family: 'Helvetica', Arial, sans-serif;
                    font-size: 10px;
                    margin: 0;
                    padding: 5px;
                    background: white;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 10px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #FF69B4;
                }}
                .company-name {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #FF1493;
                    margin-bottom: 5px;
                }}
                .company-details {{
                    font-size: 9px;
                    color: #666;
                    line-height: 1.3;
                }}
                .receipt-title {{
                    font-size: 14px;
                    font-weight: bold;
                    text-align: center;
                    margin: 10px 0;
                    padding: 5px;
                    background: #FF69B4;
                    color: white;
                }}
                .info-section {{
                    margin: 10px 0;
                    padding: 8px;
                    background: #F9F9F9;
                    border-left: 3px solid #FF69B4;
                }}
                .info-row {{
                    margin: 3px 0;
                }}
                .items-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                }}
                .items-table th {{
                    background: #FF69B4;
                    color: white;
                    padding: 5px;
                    font-size: 9px;
                    text-align: left;
                }}
                .items-table td {{
                    padding: 5px;
                    border-bottom: 1px solid #EEE;
                }}
                .totals {{
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 2px solid #FF69B4;
                    text-align: right;
                }}
                .total-row {{
                    margin: 5px 0;
                    font-weight: bold;
                }}
                .grand-total {{
                    font-size: 14px;
                    color: #FF1493;
                    margin-top: 10px;
                }}
                .footer {{
                    margin-top: 20px;
                    padding-top: 10px;
                    border-top: 1px dashed #CCC;
                    text-align: center;
                    font-size: 8px;
                    color: #999;
                }}
                .payment-details {{
                    margin: 10px 0;
                    padding: 8px;
                    background: #F0F8FF;
                }}
                .thankyou {{
                    text-align: center;
                    margin-top: 15px;
                    font-size: 11px;
                    font-weight: bold;
                    color: #FF1493;
                }}
                @media print {{
                    body {{
                        margin: 0;
                        padding: 0;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="company-name">{company_data.get('company_name', 'Glamour Cosmetics')}</div>
                <div class="company-details">
                    {company_data.get('company_address', '')}<br>
                    Tel: {company_data.get('company_phone', '')} | Email: {company_data.get('company_email', '')}<br>
                    PIN: {company_data.get('kra_pin', '')}
                </div>
            </div>
            
            <div class="receipt-title">
                {'TAX INVOICE' if sale_type == 'invoice' else 'PROFORMA INVOICE' if sale_type == 'proforma' else 'CONSIGNMENT NOTE'}
            </div>
            
            <div class="info-section">
                <div class="info-row"><strong>Invoice No:</strong> {sale_data['invoice_number']}</div>
                <div class="info-row"><strong>Date:</strong> {sale_data['date']}</div>
                <div class="info-row"><strong>Salesperson:</strong> {sale_data['salesperson']}</div>
                <div class="info-row"><strong>Customer:</strong> {sale_data.get('customer_name', 'Walk-in Customer')}</div>
                <div class="info-row"><strong>Phone:</strong> {sale_data.get('customer_phone', 'N/A')}</div>
            </div>
            
            <table class="items-table">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Qty</th>
                        <th>Price</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for item in cart_items:
            html += f"""
                    <tr>
                        <td>{item['name']}<br><small style="color:#999">{item.get('brand', '')}</small></td>
                        <td>{item['quantity']}</td>
                        <td>{item['price']:.2f}</td>
                        <td>{item['total']:.2f}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        """
        
        if sale_type == "invoice":
            html += f"""
            <div class="totals">
                <div class="total-row">Subtotal: KES {sale_data['subtotal']:.2f}</div>
                <div class="total-row">VAT ({company_data.get('vat_rate', 16)}%): KES {sale_data['vat_amount']:.2f}</div>
                <div class="grand-total"><strong>TOTAL: KES {sale_data['total']:.2f}</strong></div>
            </div>
            
            <div class="payment-details">
                <strong>Payment Details:</strong><br>
                Method: {sale_data.get('payment_method', 'Cash')}<br>
                Amount Paid: KES {sale_data.get('amount_paid', 0):.2f}<br>
                Change: KES {sale_data.get('change', 0):.2f}
            </div>
            """
        else:
            html += f"""
            <div class="totals">
                <div class="grand-total"><strong>TOTAL AMOUNT: KES {sale_data['total']:.2f}</strong></div>
                <div style="font-size: 9px; color: #FF0000; margin-top: 5px;">
                    * This is a {'proforma invoice' if sale_type == 'proforma' else 'consignment note'} - No tax applied
                </div>
            </div>
            """
        
        html += f"""
            <div class="footer">
                {company_data.get('receipt_footer', 'Thank you for shopping with us!')}<br>
                {company_data.get('company_website', '')}
            </div>
            
            <div class="thankyou">
                ✨ Thank you for choosing Glamour Cosmetics! ✨
            </div>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def print_receipt(html_content):
        """Print receipt using QTextDocument"""
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPaperSize(QPrinter.RollPaper)
        printer.setPageMargins(5, 5, 5, 5, QPrinter.Millimeter)
        
        dialog = QPrintDialog(printer)
        if dialog.exec_() == QPrintDialog.Accepted:
            doc = QTextDocument()
            doc.setHtml(html_content)
            doc.print_(printer)

class MainWindow(QMainWindow):
    def __init__(self, db_manager, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"Glamour Cosmetics Management - {self.user_data['username']} ({self.user_data['role']})")
        self.setGeometry(100, 100, 1200, 800)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 10px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #FF69B4;
                color: white;
            }
            QTableWidget {
                gridline-color: #e0e0e0;
                selection-background-color: #ffe0f0;
            }
            QHeaderView::section {
                background-color: #FF69B4;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #FF69B4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF1493;
            }
            QPushButton:pressed {
                background-color: #DB0D6B;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 8px;
                border: 2px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #FF69B4;
            }
        """)
        
        # Create central widget and tab widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Create tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Add tabs based on user role
        if self.user_data['role'] in ['admin', 'storekeeper']:
            self.tabs.addTab(self.create_inventory_tab(), "📦 Inventory")
            self.tabs.addTab(self.create_purchase_tab(), "📥 Purchase Orders")
        
        if self.user_data['role'] in ['admin', 'salesperson']:
            self.tabs.addTab(self.create_sales_tab(), "💰 Sales")
        
        if self.user_data['role'] == 'admin':
            self.tabs.addTab(self.create_reports_tab(), "📊 Reports")
            self.tabs.addTab(self.create_users_tab(), "👥 Users")
            self.tabs.addTab(self.create_settings_tab(), "⚙️ Settings")
        
        # Create menu bar
        self.create_menu_bar()
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage(f"Welcome, {self.user_data['username']} | Role: {self.user_data['role']}")
        
        # Check for low stock alerts
        self.check_low_stock_alerts()
    
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        backup_action = QAction('Backup Database', self)
        backup_action.triggered.connect(self.backup_database)
        file_menu.addAction(backup_action)
        
        file_menu.addSeparator()
        
        logout_action = QAction('Logout', self)
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_inventory_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Controls
        controls_layout = QHBoxLayout()
        
        add_item_btn = QPushButton("➕ Add Item")
        add_item_btn.clicked.connect(self.add_item)
        controls_layout.addWidget(add_item_btn)
        
        edit_item_btn = QPushButton("✏️ Edit Item")
        edit_item_btn.clicked.connect(self.edit_item)
        controls_layout.addWidget(edit_item_btn)
        
        delete_item_btn = QPushButton("🗑️ Delete Item")
        delete_item_btn.clicked.connect(self.delete_item)
        controls_layout.addWidget(delete_item_btn)
        
        controls_layout.addStretch()
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Search:"))
        self.inventory_search = QLineEdit()
        self.inventory_search.setPlaceholderText("Search by name, brand, or code...")
        self.inventory_search.textChanged.connect(self.filter_inventory)
        search_layout.addWidget(self.inventory_search)
        
        category_filter = QComboBox()
        category_filter.addItem("All Categories")
        self.load_categories_combo(category_filter)
        category_filter.currentTextChanged.connect(self.filter_inventory)
        search_layout.addWidget(category_filter)
        
        controls_layout.addLayout(search_layout)
        
        layout.addLayout(controls_layout)
        
        # Inventory table
        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(10)
        self.inventory_table.setHorizontalHeaderLabels([
            "Code", "Product", "Brand", "Category", "Stock", "Cost Price", "Selling Price", "Reorder", "Expiry", "Status"
        ])
        self.inventory_table.horizontalHeader().setStretchLastSection(True)
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inventory_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.inventory_table)
        
        widget.setLayout(layout)
        
        # Load inventory data
        self.load_inventory()
        
        return widget
    
    def create_sales_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Sales controls
        sales_controls = QHBoxLayout()
        
        new_sale_btn = QPushButton("💰 New Sale (Invoice)")
        new_sale_btn.clicked.connect(self.new_sale)
        sales_controls.addWidget(new_sale_btn)
        
        proforma_btn = QPushButton("📄 Proforma Invoice")
        proforma_btn.clicked.connect(self.new_proforma)
        sales_controls.addWidget(proforma_btn)
        
        consignment_btn = QPushButton("📦 Consignment Note")
        consignment_btn.clicked.connect(self.new_consignment)
        sales_controls.addWidget(consignment_btn)
        
        sales_controls.addStretch()
        
        # Search sales
        sales_search_layout = QHBoxLayout()
        sales_search_layout.addWidget(QLabel("🔍 Search:"))
        self.sales_search = QLineEdit()
        self.sales_search.setPlaceholderText("Search by invoice or customer...")
        self.sales_search.textChanged.connect(self.filter_sales)
        sales_search_layout.addWidget(self.sales_search)
        
        sales_controls.addLayout(sales_search_layout)
        
        layout.addLayout(sales_controls)
        
        # Sales table
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(9)
        self.sales_table.setHorizontalHeaderLabels([
            "Invoice #", "Type", "Customer", "Subtotal", "VAT", "Total", "Status", "Date", "Salesperson"
        ])
        self.sales_table.horizontalHeader().setStretchLastSection(True)
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sales_table.setAlternatingRowColors(True)
        self.sales_table.doubleClicked.connect(self.view_sale_details)
        
        layout.addWidget(self.sales_table)
        
        widget.setLayout(layout)
        
        # Load sales data
        self.load_sales()
        
        return widget
    
    def create_purchase_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Purchase controls
        purchase_controls = QHBoxLayout()
        
        new_po_btn = QPushButton("📋 New Purchase Order")
        new_po_btn.clicked.connect(self.new_purchase_order)
        purchase_controls.addWidget(new_po_btn)
        
        receive_goods_btn = QPushButton("📦 Receive Goods")
        receive_goods_btn.clicked.connect(self.receive_goods)
        purchase_controls.addWidget(receive_goods_btn)
        
        purchase_controls.addStretch()
        
        layout.addLayout(purchase_controls)
        
        # Purchase orders table
        self.purchase_table = QTableWidget()
        self.purchase_table.setColumnCount(7)
        self.purchase_table.setHorizontalHeaderLabels([
            "PO Number", "Supplier", "Type", "Total", "Paid", "Status", "Order Date"
        ])
        self.purchase_table.horizontalHeader().setStretchLastSection(True)
        self.purchase_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.purchase_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.purchase_table)
        
        widget.setLayout(layout)
        
        # Load purchase orders
        self.load_purchase_orders()
        
        return widget
    
    def create_reports_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Report controls
        report_controls = QHBoxLayout()
        
        sales_report_btn = QPushButton("📈 Sales Report")
        sales_report_btn.clicked.connect(self.generate_sales_report)
        report_controls.addWidget(sales_report_btn)
        
        inventory_report_btn = QPushButton("📊 Inventory Report")
        inventory_report_btn.clicked.connect(self.generate_inventory_report)
        report_controls.addWidget(inventory_report_btn)
        
        daily_summary_btn = QPushButton("📅 Daily Summary")
        daily_summary_btn.clicked.connect(self.generate_daily_summary)
        report_controls.addWidget(daily_summary_btn)
        
        profit_report_btn = QPushButton("💰 Profit Report")
        profit_report_btn.clicked.connect(self.generate_profit_report)
        report_controls.addWidget(profit_report_btn)
        
        export_excel_btn = QPushButton("📎 Export to Excel")
        export_excel_btn.clicked.connect(self.export_to_excel)
        report_controls.addWidget(export_excel_btn)
        
        report_controls.addStretch()
        
        layout.addLayout(report_controls)
        
        # Date range selection
        date_widget = QWidget()
        date_widget.setStyleSheet("background-color: #F0F0F0; padding: 10px; border-radius: 5px;")
        date_layout = QHBoxLayout(date_widget)
        date_layout.addWidget(QLabel("📅 From:"))
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        date_layout.addWidget(self.date_from)
        
        date_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_to)
        
        date_layout.addStretch()
        
        layout.addWidget(date_widget)
        
        # Report display area
        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        self.report_display.setStyleSheet("font-family: 'Courier New'; font-size: 11px;")
        layout.addWidget(self.report_display)
        
        widget.setLayout(layout)
        
        return widget
    
    def create_users_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # User controls
        user_controls = QHBoxLayout()
        
        add_user_btn = QPushButton("👤 Add User")
        add_user_btn.clicked.connect(self.add_user)
        user_controls.addWidget(add_user_btn)
        
        edit_user_btn = QPushButton("✏️ Edit User")
        edit_user_btn.clicked.connect(self.edit_user)
        user_controls.addWidget(edit_user_btn)
        
        delete_user_btn = QPushButton("🗑️ Delete User")
        delete_user_btn.clicked.connect(self.delete_user)
        user_controls.addWidget(delete_user_btn)
        
        user_controls.addStretch()
        
        layout.addLayout(user_controls)
        
        # Users table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(4)
        self.users_table.setHorizontalHeaderLabels([
            "Username", "Role", "Email", "Created"
        ])
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.users_table)
        
        widget.setLayout(layout)
        
        # Load users
        self.load_users()
        
        return widget
    
    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Company settings form
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        form_layout = QFormLayout(scroll_widget)
        
        self.company_name = QLineEdit()
        form_layout.addRow("🏢 Company Name:", self.company_name)
        
        self.company_address = QTextEdit()
        self.company_address.setMaximumHeight(80)
        form_layout.addRow("📍 Address:", self.company_address)
        
        self.company_phone = QLineEdit()
        form_layout.addRow("📞 Phone:", self.company_phone)
        
        self.company_email = QLineEdit()
        form_layout.addRow("📧 Email:", self.company_email)
        
        self.company_website = QLineEdit()
        form_layout.addRow("🌐 Website:", self.company_website)
        
        self.kra_pin = QLineEdit()
        form_layout.addRow("🔑 KRA PIN:", self.kra_pin)
        
        self.vat_rate = QDoubleSpinBox()
        self.vat_rate.setRange(0, 100)
        self.vat_rate.setSuffix("%")
        form_layout.addRow("💰 VAT Rate:", self.vat_rate)
        
        self.invoice_prefix = QLineEdit()
        form_layout.addRow("📄 Invoice Prefix:", self.invoice_prefix)
        
        self.receipt_prefix = QLineEdit()
        form_layout.addRow("🧾 Receipt Prefix:", self.receipt_prefix)
        
        self.receipt_footer = QTextEdit()
        self.receipt_footer.setMaximumHeight(100)
        form_layout.addRow("📝 Receipt Footer:", self.receipt_footer)
        
        layout.addWidget(scroll_area)
        scroll_area.setWidget(scroll_widget)
        
        # Logo selection
        logo_layout = QHBoxLayout()
        logo_layout.addWidget(QLabel("🖼️ Company Logo:"))
        self.logo_path = QLineEdit()
        logo_layout.addWidget(self.logo_path)
        
        browse_logo_btn = QPushButton("Browse")
        browse_logo_btn.clicked.connect(self.browse_logo)
        logo_layout.addWidget(browse_logo_btn)
        
        layout.addLayout(logo_layout)
        
        # Save settings button
        save_settings_btn = QPushButton("💾 Save Settings")
        save_settings_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_settings_btn)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        
        # Load current settings
        self.load_settings()
        
        return widget
    
    def load_inventory(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT i.item_code, i.name, i.brand, c.name, i.stock_quantity, 
                   i.cost_price, i.selling_price, i.reorder_level, i.expiry_date
            FROM items i
            LEFT JOIN categories c ON i.category_id = c.id
            ORDER BY i.name
        """)
        
        items = cursor.fetchall()
        conn.close()
        
        self.inventory_table.setRowCount(len(items))
        
        for row, item in enumerate(items):
            # Status calculation
            status = "✅ In Stock"
            status_color = QColor(200, 255, 200)
            
            if item[4] <= item[7]:
                status = "⚠️ Low Stock"
                status_color = QColor(255, 255, 200)
            
            if item[8]:
                expiry_date = datetime.strptime(item[8], "%Y-%m-%d")
                if expiry_date < datetime.now():
                    status = "❌ Expired"
                    status_color = QColor(255, 200, 200)
                elif expiry_date < datetime.now() + timedelta(days=90):
                    status = "⚠️ Expiring Soon"
                    status_color = QColor(255, 255, 200)
            
            for col, value in enumerate(item):
                cell_item = QTableWidgetItem(str(value) if value is not None else "")
                self.inventory_table.setItem(row, col, cell_item)
            
            # Add status column
            status_item = QTableWidgetItem(status)
            status_item.setBackground(status_color)
            self.inventory_table.setItem(row, 9, status_item)
    
    def load_sales(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.invoice_number, s.sale_type, s.customer_name, 
                   s.subtotal, s.vat_amount, s.total_amount, s.payment_status, 
                   s.created_at, u.username
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            ORDER BY s.created_at DESC
        """)
        
        sales = cursor.fetchall()
        conn.close()
        
        self.sales_table.setRowCount(len(sales))
        
        for row, sale in enumerate(sales):
            for col, value in enumerate(sale):
                if col == 7:  # Date column
                    date_obj = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                    value = date_obj.strftime("%Y-%m-%d %H:%M")
                
                cell_item = QTableWidgetItem(str(value) if value is not None else "")
                self.sales_table.setItem(row, col, cell_item)
    
    def load_purchase_orders(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT po_number, supplier_name, order_type, total_amount, 
                   paid_amount, status, order_date
            FROM purchase_orders
            ORDER BY order_date DESC
        """)
        
        orders = cursor.fetchall()
        conn.close()
        
        self.purchase_table.setRowCount(len(orders))
        
        for row, order in enumerate(orders):
            for col, value in enumerate(order):
                if col == 6:  # Date column
                    date_obj = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                    value = date_obj.strftime("%Y-%m-%d")
                
                cell_item = QTableWidgetItem(str(value) if value is not None else "")
                self.purchase_table.setItem(row, col, cell_item)
    
    def load_users(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT username, role, email, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        conn.close()
        
        self.users_table.setRowCount(len(users))
        
        for row, user in enumerate(users):
            for col, value in enumerate(user):
                if col == 3:  # Date column
                    date_obj = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                    value = date_obj.strftime("%Y-%m-%d")
                
                cell_item = QTableWidgetItem(str(value) if value is not None else "")
                self.users_table.setItem(row, col, cell_item)
    
    def load_settings(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM company_settings LIMIT 1")
        settings = cursor.fetchone()
        conn.close()
        
        if settings:
            self.company_name.setText(settings[1] or "")
            self.company_address.setText(settings[2] or "")
            self.company_phone.setText(settings[3] or "")
            self.company_email.setText(settings[4] or "")
            self.company_website.setText(settings[5] or "")
            self.kra_pin.setText(settings[6] or "")
            self.vat_rate.setValue(settings[7] or 16.0)
            self.logo_path.setText(settings[8] or "")
            self.invoice_prefix.setText(settings[9] or "INV")
            self.receipt_prefix.setText(settings[10] or "RCP")
            self.receipt_footer.setText(settings[11] or "")
    
    def load_categories_combo(self, combo_box):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM categories ORDER BY name")
        categories = cursor.fetchall()
        conn.close()
        
        for category in categories:
            combo_box.addItem(category[0])
    
    def get_company_settings(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM company_settings LIMIT 1")
        settings = cursor.fetchone()
        conn.close()
        
        if settings:
            return {
                'company_name': settings[1],
                'company_address': settings[2],
                'company_phone': settings[3],
                'company_email': settings[4],
                'company_website': settings[5],
                'kra_pin': settings[6],
                'vat_rate': settings[7],
                'logo_path': settings[8],
                'invoice_prefix': settings[9],
                'receipt_prefix': settings[10],
                'receipt_footer': settings[11]
            }
        return {}
    
    def check_low_stock_alerts(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, brand, stock_quantity, reorder_level 
            FROM items 
            WHERE stock_quantity <= reorder_level
        """)
        
        low_stock_items = cursor.fetchall()
        
        # Check for expired items
        cursor.execute("""
            SELECT name, brand, expiry_date 
            FROM items 
            WHERE expiry_date <= DATE('now')
        """)
        
        expired_items = cursor.fetchall()
        conn.close()
        
        alert_msg = ""
        
        if low_stock_items:
            alert_msg += "⚠️ LOW STOCK ALERT ⚠️\n\n"
            for item in low_stock_items:
                alert_msg += f"• {item[0]} ({item[1]}): {item[2]} units left (Reorder at {item[3]})\n"
        
        if expired_items:
            alert_msg += "\n❌ EXPIRED PRODUCTS ❌\n\n"
            for item in expired_items:
                alert_msg += f"• {item[0]} ({item[1]}) - Expired on {item[2]}\n"
        
        if alert_msg:
            QMessageBox.warning(self, "Inventory Alerts", alert_msg)
    
    def filter_inventory(self):
        search_text = self.inventory_search.text().lower()
        
        for row in range(self.inventory_table.rowCount()):
            show_row = False
            for col in range(9):  # Check all except status column
                item = self.inventory_table.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            
            self.inventory_table.setRowHidden(row, not show_row)
    
    def filter_sales(self):
        search_text = self.sales_search.text().lower()
        
        for row in range(self.sales_table.rowCount()):
            show_row = False
            for col in range(8):
                item = self.sales_table.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            
            self.sales_table.setRowHidden(row, not show_row)
    
    def add_item(self):
        dialog = ItemDialog(self.db_manager)
        if dialog.exec_() == QDialog.Accepted:
            self.load_inventory()
    
    def edit_item(self):
        current_row = self.inventory_table.currentRow()
        if current_row >= 0:
            item_code = self.inventory_table.item(current_row, 0).text()
            dialog = ItemDialog(self.db_manager, item_code)
            if dialog.exec_() == QDialog.Accepted:
                self.load_inventory()
        else:
            QMessageBox.warning(self, "Warning", "Please select an item to edit")
    
    def delete_item(self):
        current_row = self.inventory_table.currentRow()
        if current_row >= 0:
            item_code = self.inventory_table.item(current_row, 0).text()
            item_name = self.inventory_table.item(current_row, 1).text()
            
            reply = QMessageBox.question(self, "Confirm Delete", 
                                       f"Are you sure you want to delete '{item_name}'?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM items WHERE item_code = ?", (item_code,))
                conn.commit()
                conn.close()
                
                self.load_inventory()
                QMessageBox.information(self, "Success", "Item deleted successfully")
        else:
            QMessageBox.warning(self, "Warning", "Please select an item to delete")
    
    def new_sale(self):
        dialog = SalesDialog(self.db_manager, self.user_data, "invoice")
        if dialog.exec_() == QDialog.Accepted:
            self.load_sales()
    
    def new_proforma(self):
        dialog = SalesDialog(self.db_manager, self.user_data, "proforma")
        if dialog.exec_() == QDialog.Accepted:
            self.load_sales()
    
    def new_consignment(self):
        dialog = SalesDialog(self.db_manager, self.user_data, "consignment")
        if dialog.exec_() == QDialog.Accepted:
            self.load_sales()
    
    def view_sale_details(self):
        current_row = self.sales_table.currentRow()
        if current_row >= 0:
            invoice_number = self.sales_table.item(current_row, 0).text()
            dialog = SaleDetailsDialog(self.db_manager, invoice_number)
            dialog.exec_()
    
    def new_purchase_order(self):
        dialog = PurchaseOrderDialog(self.db_manager, self.user_data)
        if dialog.exec_() == QDialog.Accepted:
            self.load_purchase_orders()
    
    def receive_goods(self):
        current_row = self.purchase_table.currentRow()
        if current_row >= 0:
            po_number = self.purchase_table.item(current_row, 0).text()
            dialog = ReceiveGoodsDialog(self.db_manager, po_number)
            if dialog.exec_() == QDialog.Accepted:
                self.load_purchase_orders()
                self.load_inventory()
        else:
            QMessageBox.warning(self, "Warning", "Please select a purchase order")
    
    def add_user(self):
        dialog = UserDialog(self.db_manager)
        if dialog.exec_() == QDialog.Accepted:
            self.load_users()
    
    def edit_user(self):
        current_row = self.users_table.currentRow()
        if current_row >= 0:
            username = self.users_table.item(current_row, 0).text()
            dialog = UserDialog(self.db_manager, username)
            if dialog.exec_() == QDialog.Accepted:
                self.load_users()
        else:
            QMessageBox.warning(self, "Warning", "Please select a user to edit")
    
    def delete_user(self):
        current_row = self.users_table.currentRow()
        if current_row >= 0:
            username = self.users_table.item(current_row, 0).text()
            
            if username == self.user_data['username']:
                QMessageBox.warning(self, "Warning", "You cannot delete your own account")
                return
            
            reply = QMessageBox.question(self, "Confirm Delete", 
                                       f"Are you sure you want to delete user '{username}'?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE username = ?", (username,))
                conn.commit()
                conn.close()
                
                self.load_users()
                QMessageBox.information(self, "Success", "User deleted successfully")
        else:
            QMessageBox.warning(self, "Warning", "Please select a user to delete")
    
    def browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", 
                                                  "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.logo_path.setText(file_path)
    
    def save_settings(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE company_settings SET
                company_name = ?, company_address = ?, company_phone = ?,
                company_email = ?, company_website = ?, kra_pin = ?, vat_rate = ?,
                logo_path = ?, invoice_prefix = ?, receipt_prefix = ?, receipt_footer = ?
            WHERE id = 1
        """, (
            self.company_name.text(),
            self.company_address.toPlainText(),
            self.company_phone.text(),
            self.company_email.text(),
            self.company_website.text(),
            self.kra_pin.text(),
            self.vat_rate.value(),
            self.logo_path.text(),
            self.invoice_prefix.text(),
            self.receipt_prefix.text(),
            self.receipt_footer.toPlainText()
        ))
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(self, "Success", "Settings saved successfully")
    
    def generate_sales_report(self):
        from_date = self.date_from.date().toString("yyyy-MM-dd")
        to_date = self.date_to.date().toString("yyyy-MM-dd")
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        # Get sales data
        cursor.execute("""
            SELECT s.invoice_number, s.sale_type, s.customer_name, 
                   s.subtotal, s.vat_amount, s.total_amount, s.payment_status, 
                   s.payment_method, s.created_at, u.username
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
            ORDER BY s.created_at DESC
        """, (from_date, to_date))
        
        sales = cursor.fetchall()
        
        # Calculate totals
        total_sales = sum(sale[5] for sale in sales)
        total_vat = sum(sale[4] for sale in sales)
        total_subtotal = sum(sale[3] for sale in sales)
        
        # Get payment method breakdown
        cursor.execute("""
            SELECT payment_method, COUNT(*), SUM(total_amount)
            FROM sales
            WHERE DATE(created_at) BETWEEN ? AND ?
            GROUP BY payment_method
        """, (from_date, to_date))
        
        payment_breakdown = cursor.fetchall()
        
        # Get daily sales trend
        cursor.execute("""
            SELECT DATE(created_at), COUNT(*), SUM(total_amount)
            FROM sales
            WHERE DATE(created_at) BETWEEN ? AND ?
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
        """, (from_date, to_date))
        
        daily_trend = cursor.fetchall()
        
        conn.close()
        
        # Generate detailed report
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              SALES REPORT                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Period: {from_date} to {to_date}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

┌──────────────────────────────────────────────────────────────────────────────┐
│                                 SUMMARY                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Total Sales Amount:     KES {total_sales:>15,.2f}                              │
│ Total VAT Collected:    KES {total_vat:>15,.2f}                              │
│ Total Subtotal:         KES {total_subtotal:>15,.2f}                              │
│ Number of Transactions: {len(sales):>15}                                       │
│ Average Transaction:    KES {(total_sales/len(sales) if sales else 0):>15,.2f}│
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                          PAYMENT METHOD BREAKDOWN                             │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for method, count, amount in payment_breakdown:
            percentage = (amount / total_sales * 100) if total_sales > 0 else 0
            report += f"│ {method:<20} {count:>5} transactions   KES {amount:>12,.2f} ({percentage:>5.1f}%)│\n"
        
        report += f"""
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                            DAILY SALES TREND                                   │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for date, count, amount in daily_trend:
            report += f"│ {date}  {count:>3} sales   KES {amount:>12,.2f}│\n"
        
        report += f"""
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           DETAILED TRANSACTIONS                               │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for sale in sales:
            report += f"""
│ Invoice: {sale[0]}                                                              │
│ Type: {sale[1]} | Customer: {sale[2] or 'Walk-in'}                             │
│ Amount: KES {sale[5]:>10,.2f} | VAT: KES {sale[4]:>10,.2f}                      │
│ Status: {sale[6]} | Method: {sale[7] or 'N/A'}                                  │
│ Date: {sale[8]} | Salesperson: {sale[9]}                                        │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        self.report_display.setText(report)
    
    def generate_inventory_report(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT i.item_code, i.name, i.brand, c.name, i.stock_quantity, 
                   i.cost_price, i.selling_price, i.reorder_level, i.expiry_date,
                   (i.stock_quantity * i.cost_price) as stock_value,
                   (i.selling_price - i.cost_price) as profit_margin
            FROM items i
            LEFT JOIN categories c ON i.category_id = c.id
            ORDER BY i.name
        """)
        
        items = cursor.fetchall()
        conn.close()
        
        # Calculate totals
        total_items = len(items)
        total_stock_value = sum(item[9] for item in items)
        total_potential_profit = sum(item[10] * item[4] for item in items)
        low_stock_items = [item for item in items if item[4] <= item[7]]
        expired_items = [item for item in items if item[8] and datetime.strptime(item[8], "%Y-%m-%d") < datetime.now()]
        expiring_soon = [item for item in items if item[8] and datetime.strptime(item[8], "%Y-%m-%d") < datetime.now() + timedelta(days=90) and datetime.strptime(item[8], "%Y-%m-%d") >= datetime.now()]
        
        # Generate report
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            INVENTORY REPORT                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

┌──────────────────────────────────────────────────────────────────────────────┐
│                                 SUMMARY                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Total Products:          {total_items:>15}                                     │
│ Total Stock Value:       KES {total_stock_value:>15,.2f}                       │
│ Potential Profit:        KES {total_potential_profit:>15,.2f}                  │
│ Low Stock Items:         {len(low_stock_items):>15}                            │
│ Expired Items:           {len(expired_items):>15}                              │
│ Expiring Soon (90 days): {len(expiring_soon):>15}                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           LOW STOCK ALERTS                                     │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for item in low_stock_items:
            report += f"│ {item[1]} ({item[2]}): {item[4]} units left (Reorder at {item[7]})│\n"
        
        if not low_stock_items:
            report += "│ No low stock items                                                      │\n"
        
        report += f"""
├──────────────────────────────────────────────────────────────────────────────┤
│                           EXPIRY ALERTS                                        │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for item in expired_items:
            report += f"│ ❌ {item[1]} ({item[2]}): EXPIRED on {item[8]}                           │\n"
        
        for item in expiring_soon:
            days_left = (datetime.strptime(item[8], "%Y-%m-%d") - datetime.now()).days
            report += f"│ ⚠️  {item[1]} ({item[2]}): Expires in {days_left} days ({item[8]})        │\n"
        
        if not expired_items and not expiring_soon:
            report += "│ No expiry issues                                                         │\n"
        
        report += f"""
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         INVENTORY VALUE BY CATEGORY                           │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        # Group by category
        categories = {}
        for item in items:
            cat = item[3] if item[3] else "Uncategorized"
            categories[cat] = categories.get(cat, 0) + item[9]
        
        for cat, value in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            percentage = (value / total_stock_value * 100) if total_stock_value > 0 else 0
            report += f"│ {cat:<30} KES {value:>12,.2f} ({percentage:>5.1f}%)│\n"
        
        report += f"""
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           TOP 10 MOST VALUABLE PRODUCTS                       │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        sorted_items = sorted(items, key=lambda x: x[9], reverse=True)[:10]
        for item in sorted_items:
            report += f"│ {item[1]} ({item[2]}): KES {item[9]:>12,.2f} (Stock: {item[4]})│\n"
        
        report += """
└──────────────────────────────────────────────────────────────────────────────┘
"""
        
        self.report_display.setText(report)
    
    def generate_daily_summary(self):
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        # Today's sales
        cursor.execute("""
            SELECT COUNT(*), SUM(total_amount), SUM(vat_amount), SUM(subtotal)
            FROM sales
            WHERE DATE(created_at) = ?
        """, (today,))
        
        sales_data = cursor.fetchone()
        
        # Payment status breakdown
        cursor.execute("""
            SELECT payment_status, COUNT(*), SUM(total_amount)
            FROM sales
            WHERE DATE(created_at) = ?
            GROUP BY payment_status
        """, (today,))
        
        payment_breakdown = cursor.fetchall()
        
        # Sales by type
        cursor.execute("""
            SELECT sale_type, COUNT(*), SUM(total_amount)
            FROM sales
            WHERE DATE(created_at) = ?
            GROUP BY sale_type
        """, (today,))
        
        type_breakdown = cursor.fetchall()
        
        # Top selling items today
        cursor.execute("""
            SELECT i.name, i.brand, SUM(si.quantity) as total_qty, SUM(si.total_price) as total_value
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            JOIN sales s ON si.sale_id = s.id
            WHERE DATE(s.created_at) = ?
            GROUP BY i.name, i.brand
            ORDER BY total_value DESC
            LIMIT 10
        """, (today,))
        
        top_items = cursor.fetchall()
        
        # Best salesperson
        cursor.execute("""
            SELECT u.username, COUNT(*), SUM(s.total_amount)
            FROM sales s
            JOIN users u ON s.user_id = u.id
            WHERE DATE(s.created_at) = ?
            GROUP BY u.username
            ORDER BY SUM(s.total_amount) DESC
            LIMIT 1
        """, (today,))
        
        best_salesperson = cursor.fetchone()
        
        conn.close()
        
        # Generate report
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           DAILY BUSINESS SUMMARY                              ║
║                                    {today}                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│                              SALES SUMMARY                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Total Transactions:    {sales_data[0] or 0:>15}                                │
│ Total Sales:          KES {sales_data[1] or 0:>15,.2f}                        │
│ Total VAT:            KES {sales_data[2] or 0:>15,.2f}                        │
│ Total Subtotal:       KES {sales_data[3] or 0:>15,.2f}                        │
│ Average Sale:         KES {(sales_data[1] / sales_data[0] if sales_data[0] else 0):>15,.2f}│
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           SALES BY TYPE                                       │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for type_name, count, amount in type_breakdown:
            report += f"│ {type_name:<20} {count:>3} sales   KES {amount:>12,.2f}│\n"
        
        report += f"""
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                          PAYMENT STATUS                                       │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for status, count, amount in payment_breakdown:
            report += f"│ {status:<20} {count:>3} sales   KES {amount:>12,.2f}│\n"
        
        if best_salesperson:
            report += f"""
├──────────────────────────────────────────────────────────────────────────────┤
│                           TOP PERFORMER                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Best Salesperson:      {best_salesperson[0]}                                   │
│ Transactions:          {best_salesperson[1]}                                  │
│ Sales Amount:          KES {best_salesperson[2]:,.2f}                         │
└──────────────────────────────────────────────────────────────────────────────┘
"""
        
        report += f"""
┌──────────────────────────────────────────────────────────────────────────────┐
│                         TOP 10 SELLING PRODUCTS                               │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for idx, item in enumerate(top_items, 1):
            report += f"│ {idx:2}. {item[0]} ({item[1]})                                     │\n"
            report += f"│    Sold: {item[2]} units | Revenue: KES {item[3]:>12,.2f}                │\n"
        
        report += """
└──────────────────────────────────────────────────────────────────────────────┘

✨ TIPS FOR BETTER PERFORMANCE:
• Focus on promoting top-selling products
• Check low stock items and reorder
• Follow up on pending payments
• Maintain customer relationships
"""
        
        self.report_display.setText(report)
    
    def generate_profit_report(self):
        from_date = self.date_from.date().toString("yyyy-MM-dd")
        to_date = self.date_to.date().toString("yyyy-MM-dd")
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        # Get profit data
        cursor.execute("""
            SELECT i.name, i.brand, i.cost_price, i.selling_price, 
                   SUM(si.quantity) as total_sold,
                   (i.selling_price - i.cost_price) * SUM(si.quantity) as total_profit
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            JOIN sales s ON si.sale_id = s.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
            GROUP BY i.id
            ORDER BY total_profit DESC
        """, (from_date, to_date))
        
        profit_items = cursor.fetchall()
        
        # Overall totals
        total_revenue = sum(item[4] * item[3] for item in profit_items)
        total_cost = sum(item[4] * item[2] for item in profit_items)
        total_profit = total_revenue - total_cost
        profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        conn.close()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                             PROFIT & LOSS REPORT                              ║
║                     {from_date}  to  {to_date}                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│                              FINANCIAL SUMMARY                                │
├──────────────────────────────────────────────────────────────────────────────┤
│ Total Revenue:          KES {total_revenue:>15,.2f}                            │
│ Total Cost of Goods:    KES {total_cost:>15,.2f}                            │
│ Total Profit:           KES {total_profit:>15,.2f}                            │
│ Profit Margin:          {profit_margin:>14.2f}%                                │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         PROFIT BY PRODUCT CATEGORY                            │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        # Group by category
        category_profit = {}
        for item in profit_items:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM categories WHERE id = (SELECT category_id FROM items WHERE name = ?)", (item[0],))
            cat = cursor.fetchone()
            cat_name = cat[0] if cat else "Uncategorized"
            category_profit[cat_name] = category_profit.get(cat_name, 0) + item[5]
        
        for cat, profit in sorted(category_profit.items(), key=lambda x: x[1], reverse=True):
            report += f"│ {cat:<30} KES {profit:>12,.2f}│\n"
        
        report += f"""
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                      TOP 10 MOST PROFITABLE PRODUCTS                          │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for idx, item in enumerate(profit_items[:10], 1):
            unit_profit = item[3] - item[2]
            report += f"│ {idx:2}. {item[0]} ({item[1]})                                     │\n"
            report += f"│    Sold: {item[4]} units | Unit Profit: KES {unit_profit:.2f}               │\n"
            report += f"│    Total Profit: KES {item[5]:>12,.2f}                                │\n"
        
        report += """
└──────────────────────────────────────────────────────────────────────────────┘

📊 RECOMMENDATIONS:
• Focus on products with highest profit margins
• Consider discontinuing low-profit items
• Review pricing strategy for bestsellers
• Negotiate better cost prices from suppliers
"""
        
        self.report_display.setText(report)
    
    def export_to_excel(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", 
                                                  f"cosmetics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                                  "Excel Files (*.xlsx)")
        
        if file_path:
            try:
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    conn = self.db_manager.get_connection()
                    
                    # Export inventory
                    inventory_df = pd.read_sql_query("""
                        SELECT i.item_code, i.name, i.brand, c.name as category, 
                               i.stock_quantity, i.cost_price, i.selling_price, 
                               i.reorder_level, i.supplier, i.expiry_date
                        FROM items i
                        LEFT JOIN categories c ON i.category_id = c.id
                        ORDER BY i.name
                    """, conn)
                    inventory_df.to_excel(writer, sheet_name='Inventory', index=False)
                    
                    # Export sales
                    sales_df = pd.read_sql_query("""
                        SELECT s.invoice_number, s.sale_type, s.customer_name, 
                               s.subtotal, s.vat_amount, s.total_amount, 
                               s.payment_status, s.payment_method, s.created_at, u.username as salesperson
                        FROM sales s
                        LEFT JOIN users u ON s.user_id = u.id
                        ORDER BY s.created_at DESC
                    """, conn)
                    sales_df.to_excel(writer, sheet_name='Sales', index=False)
                    
                    # Export profit analysis
                    profit_df = pd.read_sql_query("""
                        SELECT i.name, i.brand, i.cost_price, i.selling_price, 
                               SUM(si.quantity) as units_sold,
                               (i.selling_price - i.cost_price) * SUM(si.quantity) as total_profit
                        FROM sale_items si
                        JOIN items i ON si.item_id = i.id
                        JOIN sales s ON si.sale_id = s.id
                        GROUP BY i.id
                        ORDER BY total_profit DESC
                    """, conn)
                    profit_df.to_excel(writer, sheet_name='Profit Analysis', index=False)
                    
                    conn.close()
                
                QMessageBox.information(self, "Success", f"Data exported successfully to {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export data: {str(e)}")
    
    def backup_database(self):
        backup_path, _ = QFileDialog.getSaveFileName(self, "Backup Database", 
                                                    f"cosmetics_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                                                    "Database Files (*.db)")
        
        if backup_path:
            try:
                import shutil
                shutil.copy2(self.db_manager.db_path, backup_path)
                QMessageBox.information(self, "Success", f"Database backed up to {backup_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to backup database: {str(e)}")
    
    def logout(self):
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to logout?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.close()
            login_dialog = LoginDialog(self.db_manager)
            if login_dialog.exec_() == QDialog.Accepted:
                main_window = MainWindow(self.db_manager, login_dialog.user_data)
                main_window.show()
    
    def show_about(self):
        QMessageBox.about(self, "About", 
                         "✨ Glamour Cosmetics Management System ✨\n\n"
                         "Version 2.0\n"
                         "Built with PyQt5\n\n"
                         "Features:\n"
                         "• User authentication with role-based access\n"
                         "• Inventory management with expiry tracking\n"
                         "• Beautiful HTML receipts with company branding\n"
                         "• VAT inclusive pricing with automatic calculation\n"
                         "• Invoice, Proforma, and Consignment support\n"
                         "• Comprehensive reports with profit analysis\n"
                         "• Excel export and database backup\n\n"
                         "© 2024 Glamour Cosmetics. All rights reserved.")

class ItemDialog(QDialog):
    def __init__(self, db_manager, item_code=None):
        super().__init__()
        self.db_manager = db_manager
        self.item_code = item_code
        self.is_edit = item_code is not None
        self.init_ui()
        
        if self.is_edit:
            self.load_item_data()
    
    def init_ui(self):
        self.setWindowTitle("Edit Item" if self.is_edit else "Add New Item")
        self.setFixedSize(600, 550)
        
        layout = QVBoxLayout()
        
        # Form layout
        form_layout = QFormLayout()
        
        self.item_code_input = QLineEdit()
        if not self.is_edit:
            self.item_code_input.setPlaceholderText("e.g., COS001")
        form_layout.addRow("Item Code:", self.item_code_input)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Product name")
        form_layout.addRow("Product Name:", self.name_input)
        
        self.brand_input = QLineEdit()
        self.brand_input.setPlaceholderText("Brand name")
        form_layout.addRow("Brand:", self.brand_input)
        
        self.category_combo = QComboBox()
        self.load_categories()
        form_layout.addRow("Category:", self.category_combo)
        
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_input)
        
        self.cost_price_input = QDoubleSpinBox()
        self.cost_price_input.setRange(0, 999999.99)
        self.cost_price_input.setPrefix("KES ")
        form_layout.addRow("Cost Price (excl. VAT):", self.cost_price_input)
        
        self.selling_price_input = QDoubleSpinBox()
        self.selling_price_input.setRange(0, 999999.99)
        self.selling_price_input.setPrefix("KES ")
        self.selling_price_input.setToolTip("This price includes VAT")
        form_layout.addRow("Selling Price (incl. VAT):", self.selling_price_input)
        
        self.stock_input = QSpinBox()
        self.stock_input.setRange(0, 999999)
        form_layout.addRow("Stock Quantity:", self.stock_input)
        
        self.reorder_input = QSpinBox()
        self.reorder_input.setRange(0, 999999)
        form_layout.addRow("Reorder Level:", self.reorder_input)
        
        self.supplier_input = QLineEdit()
        form_layout.addRow("Supplier:", self.supplier_input)
        
        self.expiry_date = QDateEdit()
        self.expiry_date.setCalendarPopup(True)
        self.expiry_date.setDate(QDate.currentDate().addDays(365))
        form_layout.addRow("Expiry Date:", self.expiry_date)
        
        layout.addLayout(form_layout)
        
        # Info label
        info_label = QLabel("💡 Note: Selling price includes VAT. VAT will be calculated automatically on invoices.")
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px; background: #FFF3CD; border-radius: 3px;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self.save_item)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_categories(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM categories ORDER BY name")
        categories = cursor.fetchall()
        conn.close()
        
        for category_id, name in categories:
            self.category_combo.addItem(name, category_id)
    
    def load_item_data(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT item_code, name, category_id, description, cost_price, 
                   selling_price, stock_quantity, reorder_level, supplier, brand, expiry_date
            FROM items WHERE item_code = ?
        """, (self.item_code,))
        
        item = cursor.fetchone()
        conn.close()
        
        if item:
            self.item_code_input.setText(item[0])
            self.name_input.setText(item[1])
            
            # Set category
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == item[2]:
                    self.category_combo.setCurrentIndex(i)
                    break
            
            self.description_input.setText(item[3] or "")
            self.cost_price_input.setValue(item[4] or 0)
            self.selling_price_input.setValue(item[5] or 0)
            self.stock_input.setValue(item[6] or 0)
            self.reorder_input.setValue(item[7] or 10)
            self.supplier_input.setText(item[8] or "")
            self.brand_input.setText(item[9] or "")
            
            if item[10]:
                expiry_date = datetime.strptime(item[10], "%Y-%m-%d")
                self.expiry_date.setDate(QDate(expiry_date.year, expiry_date.month, expiry_date.day))
    
    def save_item(self):
        # Validate inputs
        if not self.item_code_input.text().strip():
            QMessageBox.warning(self, "Error", "Please enter an item code")
            return
        
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "Please enter an item name")
            return
        
        if self.selling_price_input.value() <= 0:
            QMessageBox.warning(self, "Error", "Selling price must be greater than 0")
            return
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            if self.is_edit:
                cursor.execute("""
                    UPDATE items SET
                        name = ?, category_id = ?, description = ?, cost_price = ?,
                        selling_price = ?, stock_quantity = ?, reorder_level = ?, 
                        supplier = ?, brand = ?, expiry_date = ?
                    WHERE item_code = ?
                """, (
                    self.name_input.text().strip(),
                    self.category_combo.currentData(),
                    self.description_input.toPlainText().strip(),
                    self.cost_price_input.value(),
                    self.selling_price_input.value(),
                    self.stock_input.value(),
                    self.reorder_input.value(),
                    self.supplier_input.text().strip(),
                    self.brand_input.text().strip(),
                    self.expiry_date.date().toString("yyyy-MM-dd"),
                    self.item_code
                ))
            else:
                cursor.execute("""
                    INSERT INTO items 
                    (item_code, name, category_id, description, cost_price, 
                     selling_price, stock_quantity, reorder_level, supplier, brand, expiry_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.item_code_input.text().strip(),
                    self.name_input.text().strip(),
                    self.category_combo.currentData(),
                    self.description_input.toPlainText().strip(),
                    self.cost_price_input.value(),
                    self.selling_price_input.value(),
                    self.stock_input.value(),
                    self.reorder_input.value(),
                    self.supplier_input.text().strip(),
                    self.brand_input.text().strip(),
                    self.expiry_date.date().toString("yyyy-MM-dd")
                ))
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Success", "Item saved successfully")
            self.accept()
            
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Item code already exists")
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save item: {str(e)}")
            conn.close()

class SalesDialog(QDialog):
    def __init__(self, db_manager, user_data, sale_type):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.sale_type = sale_type
        self.cart_items = []
        self.vat_rate = 16.0
        self.init_ui()
        self.load_items()
        self.load_company_settings()
    
    def init_ui(self):
        self.setWindowTitle(f"New {self.sale_type.title()}")
        self.setGeometry(100, 100, 1000, 700)
        
        layout = QVBoxLayout()
        
        # Customer info
        customer_group = QGroupBox("Customer Information")
        customer_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        customer_layout = QFormLayout()
        
        self.customer_name = QLineEdit()
        self.customer_name.setPlaceholderText("Enter customer name")
        customer_layout.addRow("Customer Name:", self.customer_name)
        
        self.customer_phone = QLineEdit()
        self.customer_phone.setPlaceholderText("Phone number")
        customer_layout.addRow("Phone:", self.customer_phone)
        
        self.customer_address = QTextEdit()
        self.customer_address.setMaximumHeight(60)
        self.customer_address.setPlaceholderText("Customer address")
        customer_layout.addRow("Address:", self.customer_address)
        
        customer_group.setLayout(customer_layout)
        layout.addWidget(customer_group)
        
        # Item selection
        item_group = QGroupBox("Add Items")
        item_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        item_layout = QHBoxLayout()
        
        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(400)
        item_layout.addWidget(QLabel("Product:"))
        item_layout.addWidget(self.item_combo)
        
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 999)
        self.quantity_input.setValue(1)
        item_layout.addWidget(QLabel("Qty:"))
        item_layout.addWidget(self.quantity_input)
        
        add_item_btn = QPushButton("➕ Add to Cart")
        add_item_btn.clicked.connect(self.add_to_cart)
        add_item_btn.setStyleSheet("background-color: #4CAF50;")
        item_layout.addWidget(add_item_btn)
        
        item_group.setLayout(item_layout)
        layout.addWidget(item_group)
        
        # Cart
        cart_group = QGroupBox("Shopping Cart")
        cart_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cart_layout = QVBoxLayout()
        
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(6)
        self.cart_table.setHorizontalHeaderLabels([
            "Product", "Brand", "Quantity", "Unit Price", "Total", "Action"
        ])
        self.cart_table.horizontalHeader().setStretchLastSection(True)
        
        cart_layout.addWidget(self.cart_table)
        cart_group.setLayout(cart_layout)
        layout.addWidget(cart_group)
        
        # Totals
        totals_widget = QWidget()
        totals_widget.setStyleSheet("background-color: #F9F9F9; border-radius: 5px;")
        totals_layout = QHBoxLayout(totals_widget)
        totals_layout.addStretch()
        
        totals_form = QFormLayout()
        
        self.subtotal_label = QLabel("KES 0.00")
        self.subtotal_label.setStyleSheet("font-size: 12px;")
        totals_form.addRow("Subtotal:", self.subtotal_label)
        
        self.vat_label = QLabel("KES 0.00")
        self.vat_label.setStyleSheet("font-size: 12px;")
        totals_form.addRow(f"VAT ({self.vat_rate}%):", self.vat_label)
        
        self.total_label = QLabel("KES 0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #FF1493;")
        totals_form.addRow("TOTAL:", self.total_label)
        
        totals_layout.addLayout(totals_form)
        
        # Payment section (only for invoices)
        if self.sale_type == "invoice":
            payment_group = QGroupBox("Payment Details")
            payment_group.setStyleSheet("QGroupBox { font-weight: bold; }")
            payment_layout = QHBoxLayout()
            
            payment_layout.addWidget(QLabel("Payment Method:"))
            self.payment_method = QComboBox()
            self.payment_method.addItems(["Cash", "M-Pesa", "Credit Card", "Bank Transfer"])
            payment_layout.addWidget(self.payment_method)
            
            payment_layout.addWidget(QLabel("Amount Paid:"))
            self.amount_paid = QDoubleSpinBox()
            self.amount_paid.setRange(0, 999999.99)
            self.amount_paid.setPrefix("KES ")
            self.amount_paid.setValue(0)
            self.amount_paid.valueChanged.connect(self.calculate_change)
            payment_layout.addWidget(self.amount_paid)
            
            payment_layout.addWidget(QLabel("Change:"))
            self.change_label = QLabel("KES 0.00")
            self.change_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 14px;")
            payment_layout.addWidget(self.change_label)
            
            payment_group.setLayout(payment_layout)
            layout.addWidget(payment_group)
        
        layout.addWidget(totals_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        if self.sale_type == "invoice":
            process_btn = QPushButton("✅ Complete Sale & Print Receipt")
        elif self.sale_type == "proforma":
            process_btn = QPushButton("📄 Generate Proforma")
        else:
            process_btn = QPushButton("📦 Create Consignment Note")
        
        process_btn.clicked.connect(self.process_sale)
        process_btn.setStyleSheet("background-color: #FF1493; font-size: 14px; padding: 10px;")
        button_layout.addWidget(process_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_company_settings(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT vat_rate FROM company_settings LIMIT 1")
        settings = cursor.fetchone()
        conn.close()
        
        if settings:
            self.vat_rate = settings[0]
            self.vat_label.setText(f"VAT ({self.vat_rate}%):")
    
    def load_items(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, item_code, name, brand, selling_price, stock_quantity
            FROM items
            WHERE stock_quantity > 0
            ORDER BY name
        """)
        
        items = cursor.fetchall()
        conn.close()
        
        self.item_combo.clear()
        for item in items:
            display_text = f"{item[2]} | {item[3] or 'No Brand'} | KES {item[4]:.2f} | Stock: {item[5]}"
            self.item_combo.addItem(display_text, item)
    
    def add_to_cart(self):
        item_data = self.item_combo.currentData()
        if not item_data:
            return
        
        item_id, item_code, name, brand, price, stock = item_data
        quantity = self.quantity_input.value()
        
        if quantity > stock:
            QMessageBox.warning(self, "Error", f"Only {stock} units available in stock!")
            return
        
        # Check if item already in cart
        for i, cart_item in enumerate(self.cart_items):
            if cart_item['id'] == item_id:
                new_qty = cart_item['quantity'] + quantity
                if new_qty > stock:
                    QMessageBox.warning(self, "Error", f"Cannot add {quantity} more. Only {stock - cart_item['quantity']} left!")
                    return
                self.cart_items[i]['quantity'] = new_qty
                self.cart_items[i]['total'] = new_qty * price
                break
        else:
            self.cart_items.append({
                'id': item_id,
                'code': item_code,
                'name': name,
                'brand': brand or '',
                'price': price,
                'quantity': quantity,
                'total': quantity * price
            })
        
        self.update_cart_display()
        self.update_totals()
        self.quantity_input.setValue(1)
    
    def update_cart_display(self):
        self.cart_table.setRowCount(len(self.cart_items))
        
        for row, item in enumerate(self.cart_items):
            self.cart_table.setItem(row, 0, QTableWidgetItem(item['name']))
            self.cart_table.setItem(row, 1, QTableWidgetItem(item['brand']))
            self.cart_table.setItem(row, 2, QTableWidgetItem(str(item['quantity'])))
            self.cart_table.setItem(row, 3, QTableWidgetItem(f"KES {item['price']:.2f}"))
            self.cart_table.setItem(row, 4, QTableWidgetItem(f"KES {item['total']:.2f}"))
            
            remove_btn = QPushButton("❌")
            remove_btn.setMaximumWidth(40)
            remove_btn.clicked.connect(lambda checked, r=row: self.remove_from_cart(r))
            self.cart_table.setCellWidget(row, 5, remove_btn)
    
    def remove_from_cart(self, row):
        self.cart_items.pop(row)
        self.update_cart_display()
        self.update_totals()
    
    def update_totals(self):
        subtotal = sum(item['total'] for item in self.cart_items)
        
        if self.sale_type == "invoice":
            # Calculate VAT (selling price already includes VAT)
            vat = subtotal * (self.vat_rate / (100 + self.vat_rate))
            total = subtotal
        else:
            # For proforma and consignment, no tax
            vat = 0
            total = subtotal
        
        self.subtotal_label.setText(f"KES {subtotal:.2f}")
        self.vat_label.setText(f"KES {vat:.2f}")
        self.total_label.setText(f"KES {total:.2f}")
        
        if hasattr(self, 'amount_paid'):
            self.amount_paid.setMaximum(total)
            self.calculate_change()
    
    def calculate_change(self):
        total_text = self.total_label.text().replace("KES ", "").replace(",", "")
        total = float(total_text)
        paid = self.amount_paid.value()
        change = paid - total
        
        if change >= 0:
            self.change_label.setText(f"KES {change:.2f}")
            self.change_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 14px;")
        else:
            self.change_label.setText(f"Short by KES {abs(change):.2f}")
            self.change_label.setStyleSheet("font-weight: bold; color: #FF0000; font-size: 14px;")
    
    def process_sale(self):
        if not self.cart_items:
            QMessageBox.warning(self, "Error", "No items in cart!")
            return
        
        total_text = self.total_label.text().replace("KES ", "").replace(",", "")
        total = float(total_text)
        
        if self.sale_type == "invoice":
            paid = self.amount_paid.value()
            if paid < total:
                QMessageBox.warning(self, "Error", f"Insufficient payment! Amount short by KES {total - paid:.2f}")
                return
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # Generate invoice number
            prefix = {
                "invoice": "INV",
                "proforma": "PRO",
                "consignment": "CON"
            }[self.sale_type]
            
            cursor.execute("SELECT COUNT(*) FROM sales")
            count = cursor.fetchone()[0] + 1
            invoice_number = f"{prefix}{datetime.now().strftime('%Y%m%d')}{count:04d}"
            
            # Calculate amounts
            subtotal = sum(item['total'] for item in self.cart_items)
            
            if self.sale_type == "invoice":
                vat = subtotal * (self.vat_rate / (100 + self.vat_rate))
                total_amount = subtotal
            else:
                vat = 0
                total_amount = subtotal
            
            # Insert sale
            cursor.execute("""
                INSERT INTO sales 
                (invoice_number, sale_type, customer_name, customer_phone, customer_address,
                 subtotal, vat_amount, total_amount, payment_status, payment_method, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_number, self.sale_type,
                self.customer_name.text(), self.customer_phone.text(), self.customer_address.toPlainText(),
                subtotal, vat, total_amount,
                "completed" if self.sale_type == "invoice" else "pending",
                self.payment_method.currentText() if self.sale_type == "invoice" else None,
                self.user_data['id']
            ))
            
            sale_id = cursor.lastrowid
            
            # Insert sale items and update stock (only for invoices)
            for item in self.cart_items:
                cursor.execute("""
                    INSERT INTO sale_items (sale_id, item_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, (sale_id, item['id'], item['quantity'], item['price'], item['total']))
                
                # Update stock only for actual sales (invoices)
                if self.sale_type == "invoice":
                    cursor.execute("""
                        UPDATE items SET stock_quantity = stock_quantity - ?
                        WHERE id = ?
                    """, (item['quantity'], item['id']))
            
            conn.commit()
            
            # Get company settings for receipt
            cursor.execute("SELECT * FROM company_settings LIMIT 1")
            company = cursor.fetchone()
            company_data = {
                'company_name': company[1] if company else "Glamour Cosmetics",
                'company_address': company[2] if company else "",
                'company_phone': company[3] if company else "",
                'company_email': company[4] if company else "",
                'company_website': company[5] if company else "",
                'kra_pin': company[6] if company else "",
                'vat_rate': company[7] if company else 16,
                'receipt_footer': company[11] if company and len(company) > 11 else ""
            }
            
            conn.close()
            
            # Prepare sale data for receipt
            sale_data = {
                'invoice_number': invoice_number,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'salesperson': self.user_data['username'],
                'customer_name': self.customer_name.text(),
                'customer_phone': self.customer_phone.text(),
                'subtotal': subtotal,
                'vat_amount': vat,
                'total': total_amount,
                'payment_method': self.payment_method.currentText() if self.sale_type == "invoice" else None,
                'amount_paid': self.amount_paid.value() if self.sale_type == "invoice" else total_amount,
                'change': (self.amount_paid.value() - total_amount) if self.sale_type == "invoice" else 0
            }
            
            # Generate and print receipt
            html_receipt = ReceiptPrinter.generate_html_receipt(sale_data, company_data, self.cart_items, self.sale_type)
            ReceiptPrinter.print_receipt(html_receipt)
            
            QMessageBox.information(self, "Success", 
                f"{self.sale_type.title()} completed successfully!\n\n"
                f"Document Number: {invoice_number}\n"
                f"Total Amount: KES {total_amount:,.2f}\n\n"
                f"A receipt has been sent to the printer.")
            
            self.accept()
            
        except Exception as e:
            conn.rollback()
            conn.close()
            QMessageBox.critical(self, "Error", f"Failed to process sale: {str(e)}")

class PurchaseOrderDialog(QDialog):
    def __init__(self, db_manager, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.items = []
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("New Purchase Order")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        
        # Supplier info
        supplier_group = QGroupBox("Supplier Information")
        supplier_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        supplier_layout = QFormLayout()
        
        self.supplier_name = QLineEdit()
        self.supplier_name.setPlaceholderText("Supplier name")
        supplier_layout.addRow("Supplier Name:", self.supplier_name)
        
        self.supplier_contact = QLineEdit()
        self.supplier_contact.setPlaceholderText("Phone or email")
        supplier_layout.addRow("Contact:", self.supplier_contact)
        
        self.order_type = QComboBox()
        self.order_type.addItems(["Regular Order", "Urgent Order", "Backorder"])
        supplier_layout.addRow("Order Type:", self.order_type)
        
        self.expected_delivery = QDateEdit()
        self.expected_delivery.setDate(QDate.currentDate().addDays(7))
        self.expected_delivery.setCalendarPopup(True)
        supplier_layout.addRow("Expected Delivery:", self.expected_delivery)
        
        supplier_group.setLayout(supplier_layout)
        layout.addWidget(supplier_group)
        
        # Item entry
        item_group = QGroupBox("Add Items")
        item_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        item_layout = QHBoxLayout()
        
        self.item_desc = QLineEdit()
        self.item_desc.setPlaceholderText("Product description")
        self.item_desc.setMinimumWidth(300)
        item_layout.addWidget(self.item_desc)
        
        self.item_qty = QSpinBox()
        self.item_qty.setRange(1, 9999)
        self.item_qty.setValue(1)
        item_layout.addWidget(QLabel("Qty:"))
        item_layout.addWidget(self.item_qty)
        
        self.item_price = QDoubleSpinBox()
        self.item_price.setRange(0, 999999.99)
        self.item_price.setPrefix("KES ")
        item_layout.addWidget(QLabel("Unit Price:"))
        item_layout.addWidget(self.item_price)
        
        add_item_btn = QPushButton("➕ Add Item")
        add_item_btn.clicked.connect(self.add_item)
        add_item_btn.setStyleSheet("background-color: #4CAF50;")
        item_layout.addWidget(add_item_btn)
        
        item_group.setLayout(item_layout)
        layout.addWidget(item_group)
        
        # Items table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit Price", "Total", "Action"])
        layout.addWidget(self.items_table)
        
        # Totals
        totals_layout = QHBoxLayout()
        totals_layout.addStretch()
        
        self.po_total_label = QLabel("Total: KES 0.00")
        self.po_total_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FF1493;")
        totals_layout.addWidget(self.po_total_label)
        
        layout.addLayout(totals_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        create_po_btn = QPushButton("📋 Create Purchase Order")
        create_po_btn.clicked.connect(self.create_purchase_order)
        create_po_btn.setStyleSheet("background-color: #FF1493; font-size: 14px; padding: 10px;")
        button_layout.addWidget(create_po_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def add_item(self):
        if not self.item_desc.text().strip():
            QMessageBox.warning(self, "Error", "Please enter item description")
            return
        
        desc = self.item_desc.text()
        qty = self.item_qty.value()
        price = self.item_price.value()
        total = qty * price
        
        self.items.append({
            'description': desc,
            'quantity': qty,
            'unit_price': price,
            'total': total
        })
        
        self.update_items_display()
        
        # Clear inputs
        self.item_desc.clear()
        self.item_qty.setValue(1)
        self.item_price.setValue(0)
        self.item_desc.setFocus()
    
    def update_items_display(self):
        self.items_table.setRowCount(len(self.items))
        total_po = 0
        
        for row, item in enumerate(self.items):
            self.items_table.setItem(row, 0, QTableWidgetItem(item['description']))
            self.items_table.setItem(row, 1, QTableWidgetItem(str(item['quantity'])))
            self.items_table.setItem(row, 2, QTableWidgetItem(f"KES {item['unit_price']:.2f}"))
            self.items_table.setItem(row, 3, QTableWidgetItem(f"KES {item['total']:.2f}"))
            
            remove_btn = QPushButton("❌")
            remove_btn.setMaximumWidth(40)
            remove_btn.clicked.connect(lambda checked, r=row: self.remove_item(r))
            self.items_table.setCellWidget(row, 4, remove_btn)
            
            total_po += item['total']
        
        self.po_total_label.setText(f"Total: KES {total_po:.2f}")
    
    def remove_item(self, row):
        self.items.pop(row)
        self.update_items_display()
    
    def create_purchase_order(self):
        if not self.supplier_name.text().strip():
            QMessageBox.warning(self, "Error", "Please enter supplier name")
            return
        
        if not self.items:
            QMessageBox.warning(self, "Error", "Please add at least one item")
            return
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # Generate PO number
            cursor.execute("SELECT COUNT(*) FROM purchase_orders")
            count = cursor.fetchone()[0] + 1
            po_number = f"PO{datetime.now().strftime('%Y%m%d')}{count:04d}"
            
            total_amount = sum(item['total'] for item in self.items)
            
            # Insert purchase order
            cursor.execute("""
                INSERT INTO purchase_orders 
                (po_number, supplier_name, supplier_contact, order_type, total_amount, 
                 expected_delivery, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                po_number, self.supplier_name.text(), self.supplier_contact.text(),
                self.order_type.currentText(), total_amount,
                self.expected_delivery.date().toString("yyyy-MM-dd"),
                self.user_data['id']
            ))
            
            po_id = cursor.lastrowid
            
            # Insert items
            for item in self.items:
                cursor.execute("""
                    INSERT INTO purchase_order_items 
                    (po_id, item_description, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, (po_id, item['description'], item['quantity'], item['unit_price'], item['total']))
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Success", 
                f"Purchase Order {po_number} created successfully!\n\n"
                f"Total Amount: KES {total_amount:,.2f}\n"
                f"Expected Delivery: {self.expected_delivery.date().toString('yyyy-MM-dd')}")
            self.accept()
            
        except Exception as e:
            conn.rollback()
            conn.close()
            QMessageBox.critical(self, "Error", f"Failed to create purchase order: {str(e)}")

class ReceiveGoodsDialog(QDialog):
    def __init__(self, db_manager, po_number):
        super().__init__()
        self.db_manager = db_manager
        self.po_number = po_number
        self.init_ui()
        self.load_po_data()
    
    def init_ui(self):
        self.setWindowTitle(f"Receive Goods - {self.po_number}")
        self.setFixedSize(600, 500)
        
        layout = QVBoxLayout()
        
        # PO details
        self.po_details = QTextEdit()
        self.po_details.setReadOnly(True)
        self.po_details.setStyleSheet("font-family: 'Courier New'; font-size: 10px;")
        layout.addWidget(self.po_details)
        
        # Receiving form
        form_layout = QFormLayout()
        
        self.received_date = QDateEdit()
        self.received_date.setDate(QDate.currentDate())
        form_layout.addRow("Received Date:", self.received_date)
        
        self.quality_check = QCheckBox("All items received in good condition")
        form_layout.addRow("", self.quality_check)
        
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText("Any notes about this delivery...")
        form_layout.addRow("Notes:", self.notes)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        receive_btn = QPushButton("✅ Confirm Receipt & Update Inventory")
        receive_btn.clicked.connect(self.confirm_receipt)
        receive_btn.setStyleSheet("background-color: #4CAF50; font-size: 14px; padding: 10px;")
        button_layout.addWidget(receive_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_po_data(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT supplier_name, order_type, total_amount, order_date
            FROM purchase_orders
            WHERE po_number = ?
        """, (self.po_number,))
        
        po = cursor.fetchone()
        
        cursor.execute("""
            SELECT item_description, quantity, unit_price, total_price
            FROM purchase_order_items
            WHERE po_id = (SELECT id FROM purchase_orders WHERE po_number = ?)
        """, (self.po_number,))
        
        items = cursor.fetchall()
        conn.close()
        
        if po:
            details = f"""
╔════════════════════════════════════════════════════════════╗
║                   PURCHASE ORDER DETAILS                   ║
╚════════════════════════════════════════════════════════════╝

PO Number: {self.po_number}
Supplier: {po[0]}
Order Type: {po[1]}
Order Date: {po[3]}
Total Amount: KES {po[2]:,.2f}

ITEMS TO RECEIVE:
{'═'*60}
"""
            for item in items:
                details += f"\n• {item[0]}\n  Quantity: {item[1]} units @ KES {item[2]:.2f} = KES {item[3]:.2f}\n"
            
            details += f"\n{'═'*60}\nPlease verify all items before confirming receipt."
            self.po_details.setText(details)
    
    def confirm_receipt(self):
        if not self.quality_check.isChecked():
            reply = QMessageBox.question(self, "Quality Check", 
                                       "You indicated items may not be in good condition.\n"
                                       "Do you still want to receive these goods?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # Update purchase order status
            cursor.execute("""
                UPDATE purchase_orders 
                SET status = 'completed'
                WHERE po_number = ?
            """, (self.po_number,))
            
            # Get PO items
            cursor.execute("""
                SELECT item_description, quantity
                FROM purchase_order_items
                WHERE po_id = (SELECT id FROM purchase_orders WHERE po_number = ?)
            """, (self.po_number,))
            
            items = cursor.fetchall()
            
            # Update inventory for items (try to match by description)
            for item in items:
                # Try to find matching item in inventory
                cursor.execute("""
                    SELECT id, stock_quantity FROM items 
                    WHERE name LIKE ? OR item_code LIKE ?
                    LIMIT 1
                """, (f"%{item[0]}%", f"%{item[0]}%"))
                
                existing_item = cursor.fetchone()
                
                if existing_item:
                    # Update existing item stock
                    cursor.execute("""
                        UPDATE items 
                        SET stock_quantity = stock_quantity + ?
                        WHERE id = ?
                    """, (item[1], existing_item[0]))
                else:
                    # Could create new item, but for now just note it
                    QMessageBox.information(self, "Info", 
                        f"Item '{item[0]}' not found in inventory. Please add it manually.")
            
            # Add receiving notes
            if self.notes.toPlainText():
                cursor.execute("""
                    UPDATE purchase_orders 
                    SET notes = ?
                    WHERE po_number = ?
                """, (self.notes.toPlainText(), self.po_number))
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Success", 
                f"Goods received successfully!\n\n"
                f"PO Number: {self.po_number}\n"
                f"Date: {self.received_date.date().toString('yyyy-MM-dd')}\n\n"
                f"Inventory has been updated.")
            self.accept()
            
        except Exception as e:
            conn.rollback()
            conn.close()
            QMessageBox.critical(self, "Error", f"Failed to receive goods: {str(e)}")

class UserDialog(QDialog):
    def __init__(self, db_manager, username=None):
        super().__init__()
        self.db_manager = db_manager
        self.username = username
        self.is_edit = username is not None
        self.init_ui()
        
        if self.is_edit:
            self.load_user_data()
    
    def init_ui(self):
        self.setWindowTitle("Edit User" if self.is_edit else "Add New User")
        self.setFixedSize(450, 400)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        if self.is_edit:
            self.username_input.setReadOnly(True)
        form_layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Leave blank to keep current password" if self.is_edit else "Password")
        form_layout.addRow("Password:", self.password_input)
        
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setPlaceholderText("Confirm password")
        form_layout.addRow("Confirm Password:", self.confirm_password)
        
        self.role_combo = QComboBox()
        self.role_combo.addItems(["admin", "salesperson", "storekeeper"])
        self.role_combo.setToolTip("admin: Full access | salesperson: Sales only | storekeeper: Inventory only")
        form_layout.addRow("Role:", self.role_combo)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        form_layout.addRow("Email:", self.email_input)
        
        layout.addLayout(form_layout)
        
        # Info label
        info_label = QLabel("💡 Role Permissions:\n• Admin: Full system access\n• Salesperson: Sales and customer management\n• Storekeeper: Inventory and purchase orders")
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 10px; background: #FFF3CD; border-radius: 3px;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Save User")
        save_btn.clicked.connect(self.save_user)
        save_btn.setStyleSheet("background-color: #4CAF50;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_user_data(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT username, role, email FROM users WHERE username = ?", (self.username,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            self.username_input.setText(user[0])
            self.role_combo.setCurrentText(user[1])
            self.email_input.setText(user[2] or "")
    
    def save_user(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_password.text()
        role = self.role_combo.currentText()
        email = self.email_input.text().strip()
        
        if not username:
            QMessageBox.warning(self, "Error", "Please enter username")
            return
        
        if not self.is_edit and not password:
            QMessageBox.warning(self, "Error", "Please enter password for new user")
            return
        
        if password and password != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            if self.is_edit:
                if password:
                    password_hash = hashlib.sha256(password.encode()).hexdigest()
                    cursor.execute("""
                        UPDATE users 
                        SET password_hash = ?, role = ?, email = ?
                        WHERE username = ?
                    """, (password_hash, role, email, username))
                else:
                    cursor.execute("""
                        UPDATE users 
                        SET role = ?, email = ?
                        WHERE username = ?
                    """, (role, email, username))
            else:
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, email)
                    VALUES (?, ?, ?, ?)
                """, (username, password_hash, role, email))
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Success", f"User '{username}' saved successfully")
            self.accept()
            
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username already exists")
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save user: {str(e)}")
            conn.close()

class SaleDetailsDialog(QDialog):
    def __init__(self, db_manager, invoice_number):
        super().__init__()
        self.db_manager = db_manager
        self.invoice_number = invoice_number
        self.init_ui()
        self.load_sale_details()
    
    def init_ui(self):
        self.setWindowTitle(f"Sale Details - {self.invoice_number}")
        self.setGeometry(100, 100, 700, 600)
        
        layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("font-family: 'Courier New'; font-size: 11px;")
        layout.addWidget(self.details_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        print_btn = QPushButton("🖨️ Print")
        print_btn.clicked.connect(self.print_details)
        button_layout.addWidget(print_btn)
        
        close_btn = QPushButton("❌ Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_sale_details(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.*, u.username
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.invoice_number = ?
        """, (self.invoice_number,))
        
        sale = cursor.fetchone()
        
        cursor.execute("""
            SELECT i.name, i.brand, si.quantity, si.unit_price, si.total_price
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            WHERE si.sale_id = ?
        """, (sale[0],))
        
        items = cursor.fetchall()
        
        # Get company settings
        cursor.execute("SELECT vat_rate FROM company_settings LIMIT 1")
        company = cursor.fetchone()
        vat_rate = company[0] if company else 16
        
        conn.close()
        
        # Calculate VAT details
        subtotal = sale[6]
        vat = sale[7]
        
        details = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                         SALE DETAILS                                  ║
║                      {self.invoice_number}                              ║
╚══════════════════════════════════════════════════════════════════════╝

Document Type: {sale[2].upper()}
Date: {sale[12]}
Salesperson: {sale[13]}

┌──────────────────────────────────────────────────────────────────────┐
│ CUSTOMER INFORMATION                                                  │
├──────────────────────────────────────────────────────────────────────┤
│ Name: {sale[3] or 'Walk-in Customer'}
│ Phone: {sale[4] or 'N/A'}
│ Address: {sale[5] or 'N/A'}
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ ITEMS                                                                 │
├──────────────────────────────────────────────────────────────────────┤
"""
        
        for item in items:
            details += f"│ {item[0]} - {item[1] or 'No Brand'}\n"
            details += f"│   {item[2]} x KES {item[3]:.2f} = KES {item[4]:.2f}\n"
        
        details += f"""
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ FINANCIAL SUMMARY                                                    │
├──────────────────────────────────────────────────────────────────────┤
│ Subtotal:                           KES {subtotal:>12,.2f}
│ VAT ({vat_rate}%):                         KES {vat:>12,.2f}
│ TOTAL:                              KES {sale[8]:>12,.2f}
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ PAYMENT INFORMATION                                                  │
├──────────────────────────────────────────────────────────────────────┤
│ Status: {sale[9].upper()}
│ Method: {sale[10] or 'N/A'}
└──────────────────────────────────────────────────────────────────────┘

Thank you for choosing Glamour Cosmetics!
"""
        
        self.details_text.setText(details)
    
    def print_details(self):
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        
        if dialog.exec_() == QPrintDialog.Accepted:
            doc = QTextDocument()
            doc.setPlainText(self.details_text.toPlainText())
            doc.print_(printer)

# Main execution block
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application icon and style
    app.setStyle('Fusion')
    
    # Initialize database
    db_manager = DatabaseManager()
    
    # Show login dialog
    login_dialog = LoginDialog(db_manager)
    if login_dialog.exec_() == QDialog.Accepted:
        main_window = MainWindow(db_manager, login_dialog.user_data)
        main_window.show()
        sys.exit(app.exec_())
    else:
        sys.exit()