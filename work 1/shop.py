# shop_enhanced.py
# -*- coding: utf-8 -*-
import sys
import sqlite3
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from decimal import Decimal
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtPrintSupport import *
from PyQt5.QtCore import QSizeF
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import textwrap
import base64
import qrcode
from io import BytesIO

class DatabaseManager:
    def __init__(self, db_path="cosmetics_shop.db"):
        self.db_path = db_path
        self.init_database()
        self.migrate_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table with permissions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                permissions TEXT,
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
        
        # Items table with batch tracking
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
                barcode TEXT,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        """)
        
        # Batch tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                batch_number TEXT NOT NULL,
                quantity INTEGER,
                cost_price REAL,
                expiry_date DATE,
                manufacture_date DATE,
                supplier_invoice TEXT,
                received_date DATE,
                remaining_quantity INTEGER,
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        """)
        
        # Sales table (enhanced with KRA PIN)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                sale_type TEXT NOT NULL,
                customer_name TEXT,
                customer_phone TEXT,
                customer_address TEXT,
                customer_kra_pin TEXT,
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
        
        # Sale items table with batch reference
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                item_id INTEGER,
                batch_id INTEGER,
                quantity INTEGER,
                unit_price REAL,
                total_price REAL,
                FOREIGN KEY (sale_id) REFERENCES sales (id),
                FOREIGN KEY (item_id) REFERENCES items (id),
                FOREIGN KEY (batch_id) REFERENCES batches (id)
            )
        """)
        
        # Purchase orders table (enhanced)
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
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Purchase order items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id INTEGER,
                item_id INTEGER,
                item_description TEXT,
                quantity INTEGER,
                unit_price REAL,
                total_price REAL,
                batch_number TEXT,
                FOREIGN KEY (po_id) REFERENCES purchase_orders (id),
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        """)
        
        # Supplier contracts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supplier_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                contract_number TEXT UNIQUE,
                start_date DATE,
                end_date DATE,
                terms TEXT,
                document_path TEXT,
                amount REAL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Product certificates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                certificate_number TEXT,
                certificate_type TEXT,
                issue_date DATE,
                expiry_date DATE,
                document_path TEXT,
                issuing_body TEXT,
                status TEXT DEFAULT 'valid',
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        """)
        
        # KRA Documents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kra_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_number TEXT UNIQUE,
                document_type TEXT,
                tax_period TEXT,
                amount REAL,
                issue_date DATE,
                due_date DATE,
                status TEXT DEFAULT 'pending',
                document_path TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Chart of Accounts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chart_of_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_code TEXT UNIQUE NOT NULL,
                account_name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                parent_account INTEGER,
                normal_balance TEXT,
                is_active BOOLEAN DEFAULT 1,
                description TEXT,
                FOREIGN KEY (parent_account) REFERENCES chart_of_accounts (id)
            )
        """)
        
        # Journal Entries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_number TEXT UNIQUE NOT NULL,
                entry_date DATE NOT NULL,
                description TEXT,
                reference TEXT,
                is_posted BOOLEAN DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        """)
        
        # Journal Entry Lines
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journal_entry_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_id INTEGER,
                account_id INTEGER,
                debit_amount REAL DEFAULT 0,
                credit_amount REAL DEFAULT 0,
                description TEXT,
                FOREIGN KEY (journal_id) REFERENCES journal_entries (id),
                FOREIGN KEY (account_id) REFERENCES chart_of_accounts (id)
            )
        """)
        
        # Bank Accounts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                account_number TEXT UNIQUE NOT NULL,
                bank_name TEXT,
                account_type TEXT,
                opening_balance REAL DEFAULT 0,
                current_balance REAL DEFAULT 0,
                currency TEXT DEFAULT 'KES',
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Bank Transactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_account_id INTEGER,
                transaction_date DATE,
                transaction_type TEXT,
                amount REAL,
                reference TEXT,
                description TEXT,
                reconciled BOOLEAN DEFAULT 0,
                reconciliation_date DATE,
                FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id)
            )
        """)
        
        # Cashbook
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cashbook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date DATE,
                transaction_type TEXT,
                receipt_no TEXT,
                payment_no TEXT,
                description TEXT,
                account_id INTEGER,
                amount REAL,
                reference TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES chart_of_accounts (id)
            )
        """)
        
        # Company settings (enhanced with ETR)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                company_address TEXT,
                company_phone TEXT,
                company_email TEXT,
                company_website TEXT,
                kra_pin TEXT,
                vat_registration TEXT,
                vat_rate REAL DEFAULT 16.0,
                logo_path TEXT,
                invoice_prefix TEXT DEFAULT 'INV',
                receipt_prefix TEXT DEFAULT 'RCP',
                receipt_footer TEXT,
                printer_settings TEXT,
                etr_device_id TEXT,
                etr_serial_number TEXT,
                business_certificate TEXT,
                tin_number TEXT
            )
        """)
        
        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id TEXT,
                details TEXT,
                user_id INTEGER,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                kra_pin TEXT,
                credit_limit REAL DEFAULT 0,
                outstanding_balance REAL DEFAULT 0,
                loyalty_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Expenses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                payment_method TEXT,
                reference TEXT,
                expense_date DATE DEFAULT CURRENT_DATE,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Suppliers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                kra_pin TEXT,
                payment_terms TEXT,
                outstanding_balance REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Dashboard widgets/settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                widget_name TEXT,
                widget_position INTEGER,
                is_visible BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Insert default chart of accounts
        default_accounts = [
            ('1000', 'Cash', 'Asset', None, 'Debit'),
            ('1010', 'Bank', 'Asset', None, 'Debit'),
            ('1100', 'Accounts Receivable', 'Asset', None, 'Debit'),
            ('1200', 'Inventory', 'Asset', None, 'Debit'),
            ('1300', 'Prepaid Expenses', 'Asset', None, 'Debit'),
            ('1400', 'Fixed Assets', 'Asset', None, 'Debit'),
            ('2000', 'Accounts Payable', 'Liability', None, 'Credit'),
            ('2100', 'VAT Payable', 'Liability', None, 'Credit'),
            ('2200', 'Accrued Expenses', 'Liability', None, 'Credit'),
            ('3000', 'Owner\'s Equity', 'Equity', None, 'Credit'),
            ('3100', 'Retained Earnings', 'Equity', None, 'Credit'),
            ('4000', 'Sales Revenue', 'Revenue', None, 'Credit'),
            ('4100', 'Service Revenue', 'Revenue', None, 'Credit'),
            ('5000', 'Cost of Goods Sold', 'Expense', None, 'Debit'),
            ('6000', 'Rent Expense', 'Expense', None, 'Debit'),
            ('6100', 'Utilities Expense', 'Expense', None, 'Debit'),
            ('6200', 'Salaries Expense', 'Expense', None, 'Debit'),
            ('6300', 'Marketing Expense', 'Expense', None, 'Debit'),
            ('6400', 'Supplies Expense', 'Expense', None, 'Debit'),
            ('6500', 'Depreciation Expense', 'Expense', None, 'Debit'),
        ]
        
        cursor.execute("SELECT COUNT(*) FROM chart_of_accounts")
        if cursor.fetchone()[0] == 0:
            for code, name, acct_type, parent, balance in default_accounts:
                cursor.execute("""
                    INSERT INTO chart_of_accounts (account_code, account_name, account_type, parent_account, normal_balance)
                    VALUES (?, ?, ?, ?, ?)
                """, (code, name, acct_type, parent, balance))
        
        # Create default admin user with full permissions
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        if cursor.fetchone()[0] == 0:
            admin_password = hashlib.pbkdf2_hmac("sha256", b"admin123", b"glamour_static_salt", 260000).hex()
            admin_permissions = json.dumps({
                'inventory': ['view', 'add', 'edit', 'delete'],
                'sales': ['view', 'add', 'edit', 'void'],
                'purchases': ['view', 'add', 'edit'],
                'customers': ['view', 'add', 'edit', 'delete'],
                'suppliers': ['view', 'add', 'edit', 'delete'],
                'reports': ['view', 'export'],
                'users': ['view', 'add', 'edit', 'delete'],
                'settings': ['view', 'edit'],
                'accounting': ['view', 'add', 'edit', 'post'],
                'dashboard': ['view']
            })
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, permissions, email) 
                VALUES ('admin', ?, 'admin', ?, 'admin@cosmetics.com')
            """, (admin_password, admin_permissions))
            
            # Create test salesperson with limited permissions
            salesperson_password = hashlib.pbkdf2_hmac("sha256", b"sales123", b"glamour_static_salt", 260000).hex()
            sales_permissions = json.dumps({
                'inventory': ['view'],
                'sales': ['view', 'add'],
                'customers': ['view', 'add'],
                'reports': ['view'],
                'dashboard': ['view']
            })
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, permissions, email) 
                VALUES ('sales', ?, 'salesperson', ?, 'sales@cosmetics.com')
            """, (salesperson_password, sales_permissions))
        
        # Create default categories
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
                (company_name, company_address, company_phone, company_email, company_website, 
                 kra_pin, vat_rate, receipt_footer) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("Glamour Cosmetics", "123 Beauty Street, Nairobi, Kenya", "+254 700 000 000", 
                  "info@glamourcosmetics.com", "www.glamourcosmetics.com", "P051234567V", 16.0,
                  "Thank you for shopping with us!\nFollow us on Instagram: @glamourcosmetics\nQuality products for your beauty needs"))
        
        # Add sample products with barcodes
        cursor.execute("SELECT COUNT(*) FROM items")
        if cursor.fetchone()[0] == 0:
            sample_products = [
                ("COS001", "Hydrating Facial Cleanser", "Skincare", "Glow Beauty", "Gentle foaming cleanser", 
                 300, 580, 50, 10, "Beauty Supply Co.", "8901234567890"),
                ("COS002", "Matte Lipstick - Red", "Makeup", "ColorPop", "Long-lasting matte finish", 
                 250, 450, 100, 15, "Makeup Wholesalers", "8901234567891"),
                ("COS003", "Argan Hair Oil", "Hair Care", "Nature's Essence", "Nourishing hair treatment", 
                 400, 750, 30, 8, "Hair Products Ltd", "8901234567892"),
                ("COS004", "Eau de Parfum - Rose", "Fragrances", "Luxury Scents", "Romantic floral fragrance", 
                 800, 1500, 20, 5, "Fragrance Importers", "8901234567893"),
                ("COS005", "Shea Body Butter", "Bath & Body", "Natural Glow", "Deep moisturizing", 
                 200, 380, 60, 12, "Body Care Supplies", "8901234567894"),
            ]
            
            for product in sample_products:
                cursor.execute("SELECT id FROM categories WHERE name = ?", (product[2],))
                cat_id = cursor.fetchone()
                if cat_id:
                    cursor.execute("""
                        INSERT INTO items 
                        (item_code, name, category_id, brand, description, cost_price, selling_price, 
                         stock_quantity, reorder_level, supplier, barcode)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (product[0], product[1], cat_id[0], product[3], product[4], 
                          product[5], product[6], product[7], product[8], product[9], product[10]))
                    
                    # Add initial batch
                    item_id = cursor.lastrowid
                    cursor.execute("""
                        INSERT INTO batches (item_id, batch_number, quantity, cost_price, expiry_date, 
                                           manufacture_date, remaining_quantity)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (item_id, f"BATCH{product[0]}", product[7], product[5], 
                          (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
                          datetime.now().strftime("%Y-%m-%d"), product[7]))
        
        # Performance: WAL mode and indexes
        conn.execute("PRAGMA journal_mode=WAL")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_stock ON items(stock_quantity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_item ON batches(item_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_expiry ON batches(expiry_date)")
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, query, params=()):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.fetchall()
        
        
    def migrate_database(self):
        """Migrate existing database to new schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
    
        # Check if new columns exist in company_settings
        cursor.execute("PRAGMA table_info(company_settings)")
        columns = [col[1] for col in cursor.fetchall()]
    
        # Add missing columns to company_settings
        if 'etr_device_id' not in columns:
            cursor.execute("ALTER TABLE company_settings ADD COLUMN etr_device_id TEXT")
        if 'etr_serial_number' not in columns:
            cursor.execute("ALTER TABLE company_settings ADD COLUMN etr_serial_number TEXT")
        if 'tin_number' not in columns:
            cursor.execute("ALTER TABLE company_settings ADD COLUMN tin_number TEXT")
        if 'business_certificate' not in columns:
            cursor.execute("ALTER TABLE company_settings ADD COLUMN business_certificate TEXT")
    
        # Check if barcode column exists in items
        cursor.execute("PRAGMA table_info(items)")
        item_columns = [col[1] for col in cursor.fetchall()]
    
        if 'barcode' not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN barcode TEXT")
        if 'image_path' not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN image_path TEXT")
    
        # Check if customer_kra_pin exists in sales
        cursor.execute("PRAGMA table_info(sales)")
        sale_columns = [col[1] for col in cursor.fetchall()]
    
        if 'customer_kra_pin' not in sale_columns:
            cursor.execute("ALTER TABLE sales ADD COLUMN customer_kra_pin TEXT")
    
        # Check if batches table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='batches'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    batch_number TEXT NOT NULL,
                    quantity INTEGER,
                    cost_price REAL,
                    expiry_date DATE,
                    manufacture_date DATE,
                    supplier_invoice TEXT,
                    received_date DATE,
                    remaining_quantity INTEGER,
                    FOREIGN KEY (item_id) REFERENCES items (id)
                )
            """)
    
        # Check if supplier_contracts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='supplier_contracts'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS supplier_contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_name TEXT NOT NULL,
                    contract_number TEXT UNIQUE,
                    start_date DATE,
                    end_date DATE,
                    terms TEXT,
                    document_path TEXT,
                    amount REAL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
        # Check if product_certificates table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='product_certificates'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_certificates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    certificate_number TEXT,
                    certificate_type TEXT,
                    issue_date DATE,
                    expiry_date DATE,
                    document_path TEXT,
                    issuing_body TEXT,
                    status TEXT DEFAULT 'valid',
                    FOREIGN KEY (item_id) REFERENCES items (id)
                )
            """)
    
        # Check if kra_documents table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kra_documents'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kra_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_number TEXT UNIQUE,
                    document_type TEXT,
                    tax_period TEXT,
                    amount REAL,
                    issue_date DATE,
                    due_date DATE,
                    status TEXT DEFAULT 'pending',
                    document_path TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
        # Check if chart_of_accounts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chart_of_accounts'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chart_of_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_code TEXT UNIQUE NOT NULL,
                    account_name TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    parent_account INTEGER,
                    normal_balance TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    description TEXT,
                    FOREIGN KEY (parent_account) REFERENCES chart_of_accounts (id)
                )
            """)
        
            # Insert default accounts
            default_accounts = [
                ('1000', 'Cash', 'Asset', None, 'Debit'),
                ('1010', 'Bank', 'Asset', None, 'Debit'),
                ('1100', 'Accounts Receivable', 'Asset', None, 'Debit'),
                ('1200', 'Inventory', 'Asset', None, 'Debit'),
                ('1300', 'Prepaid Expenses', 'Asset', None, 'Debit'),
                ('1400', 'Fixed Assets', 'Asset', None, 'Debit'),
                ('2000', 'Accounts Payable', 'Liability', None, 'Credit'),
                ('2100', 'VAT Payable', 'Liability', None, 'Credit'),
                ('2200', 'Accrued Expenses', 'Liability', None, 'Credit'),
                ('3000', "Owner's Equity", 'Equity', None, 'Credit'),
                ('3100', 'Retained Earnings', 'Equity', None, 'Credit'),
                ('4000', 'Sales Revenue', 'Revenue', None, 'Credit'),
                ('4100', 'Service Revenue', 'Revenue', None, 'Credit'),
                ('5000', 'Cost of Goods Sold', 'Expense', None, 'Debit'),
                ('6000', 'Rent Expense', 'Expense', None, 'Debit'),
                ('6100', 'Utilities Expense', 'Expense', None, 'Debit'),
                ('6200', 'Salaries Expense', 'Expense', None, 'Debit'),
                ('6300', 'Marketing Expense', 'Expense', None, 'Debit'),
                ('6400', 'Supplies Expense', 'Expense', None, 'Debit'),
                ('6500', 'Depreciation Expense', 'Expense', None, 'Debit'),
            ]
        
            for code, name, acct_type, parent, balance in default_accounts:
                cursor.execute("""
                    INSERT OR IGNORE INTO chart_of_accounts (account_code, account_name, account_type, parent_account, normal_balance)
                    VALUES (?, ?, ?, ?, ?)
                """, (code, name, acct_type, parent, balance))
    
        # Check if journal_entries table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='journal_entries'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    journal_number TEXT UNIQUE NOT NULL,
                    entry_date DATE NOT NULL,
                    description TEXT,
                    reference TEXT,
                    is_posted BOOLEAN DEFAULT 0,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            """)
    
        # Check if journal_entry_lines table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='journal_entry_lines'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entry_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    journal_id INTEGER,
                    account_id INTEGER,
                    debit_amount REAL DEFAULT 0,
                    credit_amount REAL DEFAULT 0,
                    description TEXT,
                    FOREIGN KEY (journal_id) REFERENCES journal_entries (id),
                    FOREIGN KEY (account_id) REFERENCES chart_of_accounts (id)
                )
            """)
    
        # Check if bank_accounts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bank_accounts'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bank_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL,
                    account_number TEXT UNIQUE NOT NULL,
                    bank_name TEXT,
                    account_type TEXT,
                    opening_balance REAL DEFAULT 0,
                    current_balance REAL DEFAULT 0,
                    currency TEXT DEFAULT 'KES',
                    is_active BOOLEAN DEFAULT 1
                )
            """)
    
        # Check if bank_transactions table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bank_transactions'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bank_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_account_id INTEGER,
                    transaction_date DATE,
                    transaction_type TEXT,
                    amount REAL,
                    reference TEXT,
                    description TEXT,
                    reconciled BOOLEAN DEFAULT 0,
                    reconciliation_date DATE,
                    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id)
                )
            """)
    
        # Check if cashbook table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cashbook'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cashbook (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_date DATE,
                    transaction_type TEXT,
                    receipt_no TEXT,
                    payment_no TEXT,
                    description TEXT,
                    account_id INTEGER,
                    amount REAL,
                    reference TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES chart_of_accounts (id)
                )
            """)
    
        # Check if dashboard_settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_settings'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    widget_name TEXT,
                    widget_position INTEGER,
                    is_visible BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
    
        # Check if permissions column exists in users
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]
    
        if 'permissions' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN permissions TEXT")
    
        # Check if kra_pin exists in customers
        cursor.execute("PRAGMA table_info(customers)")
        customer_columns = [col[1] for col in cursor.fetchall()]
    
        if 'kra_pin' not in customer_columns:
            cursor.execute("ALTER TABLE customers ADD COLUMN kra_pin TEXT")
    
        # Check if kra_pin exists in suppliers
        cursor.execute("PRAGMA table_info(suppliers)")
        supplier_columns = [col[1] for col in cursor.fetchall()]
    
        if 'kra_pin' not in supplier_columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN kra_pin TEXT")
    
        conn.commit()
        conn.close()    


class BarcodeGenerator:
    @staticmethod
    def generate_barcode(item_code, name):
        """Generate a barcode for a product"""
        # Simple barcode generation (in real app, use proper barcode lib)
        import hashlib
        barcode_hash = hashlib.md5(f"{item_code}{name}".encode()).hexdigest()[:12]
        return barcode_hash.upper()
    
    @staticmethod
    def create_barcode_image(barcode_number, size=(200, 100)):
        """Create a barcode image using QR code as fallback"""
        qr = qrcode.QRCode(version=1, box_size=2, border=2)
        qr.add_data(barcode_number)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert PIL Image to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()


class LoginDialog(QDialog):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("SuperBusiness ERP - Login")
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
        
        title = QLabel("✨ SuperBusiness ERP ✨")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin: 20px;")
        layout.addWidget(title)
        
        subtitle = QLabel("by Glamour Cosmetics")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 16px; color: #FFE0E0; margin-bottom: 30px;")
        layout.addWidget(subtitle)
        
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
        
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)
        
        info_label = QLabel("Contact your administrator for login credentials.")
        info_label.setStyleSheet("font-size: 11px; color: #FFE0E0; margin-top: 10px;")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        self.setLayout(layout)
        
        self.password_input.returnPressed.connect(self.login)
    
    def login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password")
            return
        
        password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), b"glamour_static_salt", 260000).hex()
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, role, permissions, email 
            FROM users 
            WHERE username = ? AND password_hash = ?
        """, (username, password_hash))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            permissions = json.loads(user[3]) if user[3] else {}
            self.user_data = {
                'id': user[0],
                'username': user[1],
                'role': user[2],
                'permissions': permissions,
                'email': user[4]
            }
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid username or password")


class ReceiptPrinter:
    @staticmethod
    def generate_html_receipt(sale_data, company_data, cart_items, sale_type):
        """Generate beautiful HTML receipt with very large fonts and logo"""
        
        if sale_type == "invoice":
            vat_rate = company_data.get('vat_rate', 16)
            for item in cart_items:
                item['price_excl_vat'] = item['price'] / (1 + vat_rate/100)
                item['vat_amount'] = item['price'] - item['price_excl_vat']
        
        logo_html = ""
        logo_path = company_data.get('logo_path', '')
        if logo_path and os.path.exists(logo_path):
            try:
                with open(logo_path, 'rb') as img_file:
                    img_data = base64.b64encode(img_file.read()).decode()
                
                ext = os.path.splitext(logo_path)[1].lower()
                mime_type = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.bmp': 'image/bmp',
                    '.gif': 'image/gif'
                }.get(ext, 'image/png')
                
                logo_html = f'<img src="data:{mime_type};base64,{img_data}" style="max-width: 200px; max-height: 100px; margin-bottom: 10px;" alt="Logo">'
            except Exception as e:
                print(f"Error loading logo: {e}")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{'TAX INVOICE' if sale_type == 'invoice' else 'PROFORMA' if sale_type == 'proforma' else 'CONSIGNMENT NOTE'}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                @page {{ size: 80mm auto; margin: 3mm; }}
                body {{
                    font-family: 'Helvetica', 'Arial', sans-serif;
                    font-size: 11pt;
                    line-height: 1.5;
                    margin: 0;
                    padding: 10px;
                    background: white;
                    width: 100%;
                }}
                .container {{ width: 100%; max-width: 100%; }}
                .header {{ text-align: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 4px solid #FF69B4; }}
                .company-name {{ font-size: 18pt; font-weight: bold; color: #FF1493; margin: 15px 0 10px 0; }}
                .company-details {{ font-size: 9pt; color: #555; line-height: 1.6; }}
                .receipt-title {{ font-size: 16pt; font-weight: bold; text-align: center; margin: 20px 0; padding: 15px; background: #FF69B4; color: white; border-radius: 8px; }}
                .info-section {{ margin: 20px 0; padding: 15px; background: #F9F9F9; border-left: 6px solid #FF69B4; border-radius: 8px; }}
                .info-row {{ margin: 4px 0; font-size: 10pt; }}
                .items-table {{ width: 100%; border-collapse: collapse; margin: 25px 0; }}
                .items-table th {{ background: #FF69B4; color: white; padding: 6px 5px; font-size: 10pt; text-align: left; }}
                .items-table td {{ padding: 5px; border-bottom: 1px solid #EEE; font-size: 10pt; }}
                .totals {{ margin-top: 25px; padding-top: 20px; border-top: 4px solid #FF69B4; text-align: right; }}
                .total-row {{ margin: 5px 0; font-size: 11pt; }}
                .grand-total {{ font-size: 15pt; color: #FF1493; margin-top: 20px; font-weight: bold; }}
                .footer {{ margin-top: 35px; padding-top: 20px; border-top: 2px dashed #CCC; text-align: center; font-size: 16px; color: #888; }}
                .payment-details {{ margin: 10px 0; padding: 8px; background: #F0F8FF; border-radius: 6px; font-size: 10pt; }}
                .thankyou {{ text-align: center; margin-top: 15px; font-size: 13pt; font-weight: bold; color: #FF1493; }}
                .etr-info {{ font-size: 8pt; text-align: center; margin-top: 10px; color: #666; }}
                @media print {{ body {{ margin: 0; padding: 5px; }} }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    {logo_html}
                    <div class="company-name">✨ {company_data.get('company_name', 'Glamour Cosmetics')} ✨</div>
                    <div class="company-details">
                        {company_data.get('company_address', '')}<br>
                        📞 {company_data.get('company_phone', '')}<br>
                        ✉️ {company_data.get('company_email', '')}<br>
                        🔑 PIN: {company_data.get('kra_pin', '')}<br>
                        🌐 {company_data.get('company_website', '')}
                    </div>
                </div>
                
                <div class="receipt-title">
                    {'🧾 TAX INVOICE' if sale_type == 'invoice' else '📄 PROFORMA INVOICE' if sale_type == 'proforma' else '📦 CONSIGNMENT NOTE'}
                </div>
                
                <div class="info-section">
                    <div class="info-row"><strong>📄 Document No:</strong> {sale_data['invoice_number']}</div>
                    <div class="info-row"><strong>📅 Date:</strong> {sale_data['date']}</div>
                    <div class="info-row"><strong>👤 Salesperson:</strong> {sale_data['salesperson']}</div>
                    <div class="info-row"><strong>👤 Customer:</strong> {sale_data.get('customer_name', 'Walk-in Customer')}</div>
                    <div class="info-row"><strong>📞 Phone:</strong> {sale_data.get('customer_phone', 'N/A')}</div>
                    {f'<div class="info-row"><strong>🔑 Customer KRA PIN:</strong> {sale_data.get("customer_kra_pin", "N/A")}</div>' if sale_data.get("customer_kra_pin") else ''}
                </div>
                
                <table class="items-table">
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th style="text-align: center;">Qty</th>
                            <th style="text-align: right;">Price</th>
                            <th style="text-align: right;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for item in cart_items:
            html += f"""
                        <tr>
                            <td>
                                <div class="item-name">{item['name']}</div>
                                <div class="item-brand">{item.get('brand', '')}</div>
                            </td>
                            <td style="text-align: center; font-size: 10pt; font-weight: bold;">{item['quantity']}</td>
                            <td style="text-align: right; font-size: 10pt;">KES {item['price']:.2f}</td>
                            <td style="text-align: right; font-size: 10pt; font-weight: bold;">KES {item['total']:.2f}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
        """
        
        if sale_type == "invoice":
            html += f"""
                <div class="totals">
                    <div class="total-row"><strong>Subtotal:</strong> KES {sale_data['subtotal']:.2f}</div>
                    <div class="total-row"><strong>VAT ({company_data.get('vat_rate', 16)}%):</strong> KES {sale_data['vat_amount']:.2f}</div>
                    <div class="grand-total"><strong>TOTAL: KES {sale_data['total']:.2f}</strong></div>
                </div>
                
                <div class="payment-details">
                    <strong>💳 PAYMENT DETAILS</strong><br>
                    <strong>Method:</strong> {sale_data.get('payment_method', 'Cash')}<br>
                    <strong>Amount Paid:</strong> KES {sale_data.get('amount_paid', 0):.2f}<br>
                    <strong>Change:</strong> KES {sale_data.get('change', 0):.2f}
                </div>
            """
        else:
            html += f"""
                <div class="totals">
                    <div class="grand-total"><strong>TOTAL AMOUNT: KES {sale_data['total']:.2f}</strong></div>
                    <div style="font-size: 18px; color: #FF0000; margin-top: 15px; text-align: center; padding: 15px; background: #FFF3CD; border-radius: 8px;">
                        ⚠️ This is a {'proforma invoice' if sale_type == 'proforma' else 'consignment note'}<br>
                        No tax applied
                    </div>
                </div>
            """
        
        html += f"""
                <div class="footer">
                    {company_data.get('receipt_footer', 'Thank you for shopping with us!')}<br>
                    <span style="font-size: 14px;">{company_data.get('company_website', '')}</span>
                </div>
                
                <div class="thankyou">
                    ✨ THANK YOU! ✨<br>
                    <span style="font-size: 16px;">We appreciate your business</span>
                </div>
                
                <div class="etr-info">
                    ETR Device: {company_data.get('etr_device_id', 'N/A')}<br>
                    Serial: {company_data.get('etr_serial_number', 'N/A')}
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def print_receipt(html_content):
        try:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)

            dialog = QPrintDialog(printer)
            if dialog.exec_() != QPrintDialog.Accepted:
                return False

            doc = QTextDocument()
            dpi_scale = printer.resolution() / 96.0
            scaled_html = html_content.replace(
                "<body",
                f'<body style="zoom:{1/dpi_scale:.4f}; -webkit-text-size-adjust:none;"',
                1
            )
            doc.setHtml(scaled_html)
            page_rect_mm = printer.pageRect(QPrinter.Millimeter)
            page_width_px = page_rect_mm.width() * 96 / 25.4
            doc.setPageSize(QSizeF(page_width_px, doc.pageSize().height()))
            doc.setDefaultStyleSheet("body { font-size: 12pt; }")
            doc.print_(printer)
            return True
        except Exception as e:
            print(f"Printing error: {e}")
            return False

    @staticmethod
    def preview_receipt(html_content, parent=None):
        try:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)

            preview = QPrintPreviewDialog(printer, parent)

            def render(p):
                doc = QTextDocument()
                dpi_scale = p.resolution() / 96.0
                scaled_html = html_content.replace(
                    "<body",
                    f'<body style="zoom:{1/dpi_scale:.4f}; -webkit-text-size-adjust:none;"',
                    1
                )
                doc.setHtml(scaled_html)
                page_rect_mm = p.pageRect(QPrinter.Millimeter)
                page_width_px = page_rect_mm.width() * 96 / 25.4
                doc.setPageSize(QSizeF(page_width_px, doc.pageSize().height()))
                doc.print_(p)

            preview.paintRequested.connect(render)
            preview.exec_()
            return True
        except Exception as e:
            print(f"Preview error: {e}")
            return False


class DashboardWidget(QWidget):
    """Dashboard with analytics widgets"""
    
    def __init__(self, db_manager, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.init_ui()
        self.load_dashboard_data()
        
        # Refresh timer (every 30 seconds)
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_dashboard_data)
        self.timer.start(30000)
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("📊 Dashboard Analytics")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FF1493; padding: 10px;")
        layout.addWidget(title_label)
        
        # Stats cards layout
        stats_layout = QGridLayout()
        
        # Today's Sales Card
        self.today_sales_card = self.create_stats_card("Today's Sales", "KES 0")
        stats_layout.addWidget(self.today_sales_card, 0, 0)
        
        # Week Sales Card
        self.week_sales_card = self.create_stats_card("This Week", "KES 0")
        stats_layout.addWidget(self.week_sales_card, 0, 1)
        
        # Month Sales Card
        self.month_sales_card = self.create_stats_card("This Month", "KES 0")
        stats_layout.addWidget(self.month_sales_card, 0, 2)
        
        # Low Stock Card
        self.low_stock_card = self.create_stats_card("Low Stock Items", "0")
        stats_layout.addWidget(self.low_stock_card, 0, 3)
        
        # Expiring Soon Card
        self.expiring_card = self.create_stats_card("Expiring Soon", "0")
        stats_layout.addWidget(self.expiring_card, 1, 0)
        
        # Today's Transactions Card
        self.transactions_card = self.create_stats_card("Today's Transactions", "0")
        stats_layout.addWidget(self.transactions_card, 1, 1)
        
        # Pending Invoices Card
        self.pending_card = self.create_stats_card("Pending Payments", "KES 0")
        stats_layout.addWidget(self.pending_card, 1, 2)
        
        # Total Customers Card
        self.customers_card = self.create_stats_card("Total Customers", "0")
        stats_layout.addWidget(self.customers_card, 1, 3)
        
        layout.addLayout(stats_layout)
        
        # Charts section
        charts_layout = QHBoxLayout()
        
        # Sales chart (simplified)
        self.sales_chart = QTableWidget()
        self.sales_chart.setColumnCount(2)
        self.sales_chart.setHorizontalHeaderLabels(["Day", "Sales"])
        self.sales_chart.horizontalHeader().setStretchLastSection(True)
        self.sales_chart.setMaximumHeight(300)
        charts_layout.addWidget(self.sales_chart)
        
        # Top products
        self.top_products = QTableWidget()
        self.top_products.setColumnCount(3)
        self.top_products.setHorizontalHeaderLabels(["Product", "Units Sold", "Revenue"])
        self.top_products.horizontalHeader().setStretchLastSection(True)
        self.top_products.setMaximumHeight(300)
        charts_layout.addWidget(self.top_products)
        
        layout.addLayout(charts_layout)
        
        # Recent activity
        recent_label = QLabel("🔄 Recent Activity")
        recent_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(recent_label)
        
        self.recent_activity = QTableWidget()
        self.recent_activity.setColumnCount(4)
        self.recent_activity.setHorizontalHeaderLabels(["Time", "User", "Action", "Details"])
        self.recent_activity.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.recent_activity)
        
        self.setLayout(layout)
    
    def create_stats_card(self, title, value):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
                border: 1px solid #e0e0e0;
            }
        """)
        card_layout = QVBoxLayout()
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; color: #666;")
        card_layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FF1493;")
        card_layout.addWidget(value_label)
        
        card.setLayout(card_layout)
        card.value_label = value_label
        return card
    
    def load_dashboard_data(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Today's sales
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE DATE(created_at) = ? AND sale_type = 'invoice'", (today,))
        today_sales = cursor.fetchone()[0]
        self.today_sales_card.value_label.setText(f"KES {today_sales:,.2f}")
        
        # Week sales
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE DATE(created_at) >= ? AND sale_type = 'invoice'", (week_ago,))
        week_sales = cursor.fetchone()[0]
        self.week_sales_card.value_label.setText(f"KES {week_sales:,.2f}")
        
        # Month sales
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE DATE(created_at) >= ? AND sale_type = 'invoice'", (month_ago,))
        month_sales = cursor.fetchone()[0]
        self.month_sales_card.value_label.setText(f"KES {month_sales:,.2f}")
        
        # Low stock items
        cursor.execute("SELECT COUNT(*) FROM items WHERE stock_quantity <= reorder_level")
        low_stock = cursor.fetchone()[0]
        self.low_stock_card.value_label.setText(str(low_stock))
        
        # Expiring soon (within 90 days)
        cursor.execute("""
            SELECT COUNT(DISTINCT i.id) FROM items i
            JOIN batches b ON b.item_id = i.id
            WHERE b.expiry_date <= DATE('now', '+90 days') AND b.remaining_quantity > 0
        """)
        expiring = cursor.fetchone()[0]
        self.expiring_card.value_label.setText(str(expiring))
        
        # Today's transactions
        cursor.execute("SELECT COUNT(*) FROM sales WHERE DATE(created_at) = ?", (today,))
        transactions = cursor.fetchone()[0]
        self.transactions_card.value_label.setText(str(transactions))
        
        # Pending payments
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE payment_status = 'pending'")
        pending = cursor.fetchone()[0]
        self.pending_card.value_label.setText(f"KES {pending:,.2f}")
        
        # Total customers
        cursor.execute("SELECT COUNT(*) FROM customers")
        customers = cursor.fetchone()[0]
        self.customers_card.value_label.setText(str(customers))
        
        # Weekly sales chart (last 7 days)
        self.sales_chart.setRowCount(7)
        for i in range(7):
            day = (datetime.now() - timedelta(days=6-i)).strftime("%Y-%m-%d")
            cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE DATE(created_at) = ? AND sale_type = 'invoice'", (day,))
            amount = cursor.fetchone()[0]
            self.sales_chart.setItem(i, 0, QTableWidgetItem(day[5:]))
            self.sales_chart.setItem(i, 1, QTableWidgetItem(f"KES {amount:,.2f}"))
        
        # Top 5 products
        cursor.execute("""
            SELECT i.name, SUM(si.quantity) as total_qty, SUM(si.total_price) as total_revenue
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            JOIN sales s ON si.sale_id = s.id
            WHERE DATE(s.created_at) >= ?
            GROUP BY i.id
            ORDER BY total_revenue DESC
            LIMIT 5
        """, (month_ago,))
        
        top_products = cursor.fetchall()
        self.top_products.setRowCount(len(top_products))
        for row, product in enumerate(top_products):
            self.top_products.setItem(row, 0, QTableWidgetItem(product[0]))
            self.top_products.setItem(row, 1, QTableWidgetItem(str(product[1])))
            self.top_products.setItem(row, 2, QTableWidgetItem(f"KES {product[2]:,.2f}"))
        
        # Recent activity
        cursor.execute("""
            SELECT a.timestamp, u.username, a.action, a.details
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.timestamp DESC
            LIMIT 20
        """)
        
        activities = cursor.fetchall()
        self.recent_activity.setRowCount(len(activities))
        for row, act in enumerate(activities):
            self.recent_activity.setItem(row, 0, QTableWidgetItem(act[0][:19] if act[0] else ""))
            self.recent_activity.setItem(row, 1, QTableWidgetItem(act[1] or ""))
            self.recent_activity.setItem(row, 2, QTableWidgetItem(act[2] or ""))
            self.recent_activity.setItem(row, 3, QTableWidgetItem((act[3] or "")[:50]))
        
        conn.close()


class MainWindow(QMainWindow):
    def __init__(self, db_manager, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.init_ui()
        
    def has_permission(self, module, action):
        """Check if user has permission for a specific action"""
        permissions = self.user_data.get('permissions', {})
        module_perms = permissions.get(module, [])
        return action in module_perms or self.user_data['role'] == 'admin'
        
    def init_ui(self):
        self.setWindowTitle(f"SuperBusiness ERP - {self.user_data['username']} ({self.user_data['role']})")
        self.setGeometry(100, 100, 1400, 900)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QTabWidget::pane { border: 1px solid #c0c0c0; background-color: white; }
            QTabBar::tab { background-color: #e0e0e0; padding: 10px 20px; margin-right: 2px; }
            QTabBar::tab:selected { background-color: #FF69B4; color: white; }
            QTableWidget { gridline-color: #e0e0e0; selection-background-color: #ffe0f0; }
            QHeaderView::section { background-color: #FF69B4; color: white; padding: 8px; font-weight: bold; }
            QPushButton { background-color: #FF69B4; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #FF1493; }
            QPushButton:pressed { background-color: #DB0D6B; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 8px; border: 2px solid #ddd; border-radius: 4px; }
            QLineEdit:focus, QComboBox:focus { border-color: #FF69B4; }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Create tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Dashboard tab
        self.tabs.addTab(DashboardWidget(self.db_manager, self.user_data), "📊 Dashboard")
        
        # Add tabs based on permissions
        if self.has_permission('inventory', 'view'):
            self.tabs.addTab(self.create_inventory_tab(), "📦 Inventory")
            self.tabs.addTab(self.create_batch_tracking_tab(), "🔢 Batch Tracking")
        
        if self.has_permission('purchases', 'view'):
            self.tabs.addTab(self.create_purchase_tab(), "📥 Purchase Orders")
        
        if self.has_permission('sales', 'view'):
            self.tabs.addTab(self.create_sales_tab(), "💰 Sales")
        
        if self.has_permission('customers', 'view'):
            self.tabs.addTab(self.create_customers_tab(), "👤 Customers")
        
        if self.has_permission('suppliers', 'view'):
            self.tabs.addTab(self.create_suppliers_tab(), "🏭 Suppliers")
        
        if self.has_permission('accounting', 'view'):
            self.tabs.addTab(self.create_accounting_tab(), "📚 Accounting")
            self.tabs.addTab(self.create_kra_tab(), "📄 KRA Documents")
        
        if self.has_permission('reports', 'view'):
            self.tabs.addTab(self.create_reports_tab(), "📊 Reports")
        
        if self.user_data['role'] == 'admin':
            self.tabs.addTab(self.create_expenses_tab(), "💸 Expenses")
            self.tabs.addTab(self.create_users_tab(), "👥 Users")
            self.tabs.addTab(self.create_audit_tab(), "🔍 Audit Log")
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
        
        if self.has_permission('inventory', 'add'):
            add_item_btn = QPushButton("➕ Add Item")
            add_item_btn.clicked.connect(self.add_item)
            controls_layout.addWidget(add_item_btn)
        
        if self.has_permission('inventory', 'edit'):
            edit_item_btn = QPushButton("✏️ Edit Item")
            edit_item_btn.clicked.connect(self.edit_item)
            controls_layout.addWidget(edit_item_btn)
        
        if self.has_permission('inventory', 'delete'):
            delete_item_btn = QPushButton("🗑️ Delete Item")
            delete_item_btn.clicked.connect(self.delete_item)
            controls_layout.addWidget(delete_item_btn)
        
        generate_barcode_btn = QPushButton("📱 Generate Barcode")
        generate_barcode_btn.clicked.connect(self.generate_item_barcode)
        controls_layout.addWidget(generate_barcode_btn)
        
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
        self.inventory_table.setColumnCount(11)
        self.inventory_table.setHorizontalHeaderLabels([
            "Code", "Barcode", "Product", "Brand", "Category", "Stock", "Cost", "Selling", "Reorder", "Expiry", "Status"
        ])
        self.inventory_table.horizontalHeader().setStretchLastSection(True)
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inventory_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.inventory_table)
        
        widget.setLayout(layout)
        
        self.load_inventory()
        
        return widget
    
    def create_batch_tracking_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Batch selection
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Product:"))
        self.batch_product_combo = QComboBox()
        self.load_items_combo(self.batch_product_combo)
        self.batch_product_combo.currentTextChanged.connect(self.load_batches)
        select_layout.addWidget(self.batch_product_combo)
        
        select_layout.addStretch()
        
        if self.has_permission('purchases', 'add'):
            add_batch_btn = QPushButton("➕ Add Batch")
            add_batch_btn.clicked.connect(self.add_batch)
            select_layout.addWidget(add_batch_btn)
        
        layout.addLayout(select_layout)
        
        # Batches table
        self.batches_table = QTableWidget()
        self.batches_table.setColumnCount(9)
        self.batches_table.setHorizontalHeaderLabels([
            "Batch #", "Quantity", "Remaining", "Cost Price", "Manufactured", "Expiry", "Supplier Invoice", "Status", "Action"
        ])
        self.batches_table.horizontalHeader().setStretchLastSection(True)
        self.batches_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.batches_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.batches_table)
        
        widget.setLayout(layout)
        
        return widget
    
    def create_sales_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Sales controls
        sales_controls = QHBoxLayout()
        
        if self.has_permission('sales', 'add'):
            new_sale_btn = QPushButton("💰 New Sale (Invoice)")
            new_sale_btn.clicked.connect(self.new_sale)
            sales_controls.addWidget(new_sale_btn)
            
            proforma_btn = QPushButton("📄 Proforma Invoice")
            proforma_btn.clicked.connect(self.new_proforma)
            sales_controls.addWidget(proforma_btn)
            
            consignment_btn = QPushButton("📦 Consignment Note")
            consignment_btn.clicked.connect(self.new_consignment)
            sales_controls.addWidget(consignment_btn)

        if self.has_permission('sales', 'edit'):
            edit_sale_btn = QPushButton("✏️ Edit Sale")
            edit_sale_btn.clicked.connect(self.edit_sale)
            edit_sale_btn.setStyleSheet("background-color: #FF8C00;")
            sales_controls.addWidget(edit_sale_btn)

        if self.has_permission('sales', 'void'):
            void_sale_btn = QPushButton("🚫 Void Sale")
            void_sale_btn.clicked.connect(self.void_sale)
            void_sale_btn.setStyleSheet("background-color: #DC143C;")
            sales_controls.addWidget(void_sale_btn)
        
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
        self.sales_table.setColumnCount(10)
        self.sales_table.setHorizontalHeaderLabels([
            "Invoice #", "Type", "Customer", "Customer KRA", "Subtotal", "VAT", "Total", "Status", "Date", "Salesperson"
        ])
        self.sales_table.horizontalHeader().setStretchLastSection(True)
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sales_table.setAlternatingRowColors(True)
        self.sales_table.doubleClicked.connect(self.view_sale_details)
        
        layout.addWidget(self.sales_table)
        
        widget.setLayout(layout)
        
        self.load_sales()
        
        return widget
    
    def create_purchase_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Purchase controls
        purchase_controls = QHBoxLayout()
        
        if self.has_permission('purchases', 'add'):
            new_po_btn = QPushButton("📋 New Purchase Order")
            new_po_btn.clicked.connect(self.new_purchase_order)
            purchase_controls.addWidget(new_po_btn)
            
            receive_goods_btn = QPushButton("📦 Receive Goods")
            receive_goods_btn.clicked.connect(self.receive_goods)
            purchase_controls.addWidget(receive_goods_btn)
            
            make_payment_btn = QPushButton("💰 Make Payment")
            make_payment_btn.clicked.connect(self.make_po_payment)
            purchase_controls.addWidget(make_payment_btn)
        
        export_po_btn = QPushButton("📎 Export to Excel")
        export_po_btn.clicked.connect(self.export_purchase_orders)
        purchase_controls.addWidget(export_po_btn)
        
        purchase_controls.addStretch()
        
        # PO Filter
        po_filter_layout = QHBoxLayout()
        po_filter_layout.addWidget(QLabel("Status:"))
        self.po_status_filter = QComboBox()
        self.po_status_filter.addItems(["All", "pending", "partial", "completed"])
        self.po_status_filter.currentTextChanged.connect(self.load_purchase_orders)
        po_filter_layout.addWidget(self.po_status_filter)
        
        purchase_controls.addLayout(po_filter_layout)
        
        layout.addLayout(purchase_controls)
        
        # Purchase orders table
        self.purchase_table = QTableWidget()
        self.purchase_table.setColumnCount(8)
        self.purchase_table.setHorizontalHeaderLabels([
            "PO Number", "Supplier", "Type", "Total", "Paid", "Balance", "Status", "Order Date"
        ])
        self.purchase_table.horizontalHeader().setStretchLastSection(True)
        self.purchase_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.purchase_table.setAlternatingRowColors(True)
        self.purchase_table.doubleClicked.connect(self.view_po_details)
        
        layout.addWidget(self.purchase_table)
        
        widget.setLayout(layout)
        
        self.load_purchase_orders()
        
        return widget
    
    def create_accounting_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Accounting buttons
        acct_controls = QHBoxLayout()
        
        if self.has_permission('accounting', 'add'):
            journal_entry_btn = QPushButton("📝 New Journal Entry")
            journal_entry_btn.clicked.connect(self.new_journal_entry)
            acct_controls.addWidget(journal_entry_btn)
        
        if self.has_permission('accounting', 'view'):
            trial_balance_btn = QPushButton("⚖️ Trial Balance")
            trial_balance_btn.clicked.connect(self.show_trial_balance)
            acct_controls.addWidget(trial_balance_btn)
            
            pnl_btn = QPushButton("📈 Profit & Loss")
            pnl_btn.clicked.connect(self.show_profit_loss)
            acct_controls.addWidget(pnl_btn)
            
            balance_sheet_btn = QPushButton("📊 Balance Sheet")
            balance_sheet_btn.clicked.connect(self.show_balance_sheet)
            acct_controls.addWidget(balance_sheet_btn)
            
            cash_flow_btn = QPushButton("💰 Cash Flow")
            cash_flow_btn.clicked.connect(self.show_cash_flow)
            acct_controls.addWidget(cash_flow_btn)
            
            bank_reconcile_btn = QPushButton("🏦 Bank Reconciliation")
            bank_reconcile_btn.clicked.connect(self.show_bank_reconciliation)
            acct_controls.addWidget(bank_reconcile_btn)
        
        acct_controls.addStretch()
        layout.addLayout(acct_controls)
        
        # Date range
        date_widget = QWidget()
        date_widget.setStyleSheet("background-color: #F0F0F0; padding: 10px; border-radius: 5px;")
        date_layout = QHBoxLayout(date_widget)
        date_layout.addWidget(QLabel("📅 From:"))
        self.acct_date_from = QDateEdit()
        self.acct_date_from.setDate(QDate.currentDate().addDays(-30))
        date_layout.addWidget(self.acct_date_from)
        
        date_layout.addWidget(QLabel("To:"))
        self.acct_date_to = QDateEdit()
        self.acct_date_to.setDate(QDate.currentDate())
        date_layout.addWidget(self.acct_date_to)
        
        date_layout.addStretch()
        
        layout.addWidget(date_widget)
        
        # ── Sub-tabs: Journal Entries | Sales Ledger ──────────────────────
        acct_tabs = QTabWidget()
 
        # ── Tab 1: Journal Entries ──────────────────────────────────────
        je_tab = QWidget()
        je_layout = QVBoxLayout(je_tab)
 
        self.journal_table = QTableWidget()
        self.journal_table.setColumnCount(6)
        self.journal_table.setHorizontalHeaderLabels(
            ["Journal #", "Date", "Description", "Reference", "Status", "Actions"])
        self.journal_table.horizontalHeader().setStretchLastSection(True)
        self.journal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.journal_table.setAlternatingRowColors(True)
        self.journal_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        je_layout.addWidget(self.journal_table)
        acct_tabs.addTab(je_tab, "📋 Journal Entries")
 
        # ── Tab 2: Sales Ledger ─────────────────────────────────────────
        sl_tab = QWidget()
        sl_layout = QVBoxLayout(sl_tab)
 
        # Summary bar
        self.sl_summary_lbl = QLabel("")
        self.sl_summary_lbl.setStyleSheet(
            "font-weight:bold; font-size:13px; padding:6px; background:#fff0f8; border-radius:4px;")
        sl_layout.addWidget(self.sl_summary_lbl)
 
        # Filter row
        sl_filter = QHBoxLayout()
        sl_filter.addWidget(QLabel("Filter by date range above  ↑  then click:"))
        refresh_sl_btn = QPushButton("🔄 Refresh Sales Ledger")
        refresh_sl_btn.clicked.connect(self.load_sales_ledger)
        sl_filter.addWidget(refresh_sl_btn)
        sl_filter.addStretch()
        sl_layout.addLayout(sl_filter)
 
        self.sales_ledger_table = QTableWidget()
        self.sales_ledger_table.setColumnCount(10)
        self.sales_ledger_table.setHorizontalHeaderLabels([
            "Invoice #", "Type", "Customer", "KRA PIN",
            "Subtotal", "VAT", "Total", "Status", "Method", "Date"
        ])
        self.sales_ledger_table.horizontalHeader().setStretchLastSection(True)
        self.sales_ledger_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sales_ledger_table.setAlternatingRowColors(True)
        self.sales_ledger_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        sl_layout.addWidget(self.sales_ledger_table)
        acct_tabs.addTab(sl_tab, "💰 Sales Ledger")
 
        layout.addWidget(acct_tabs)
 
        self.load_journal_entries()
        self.load_sales_ledger()
 
        widget.setLayout(layout)
 
        return widget
    
    
    
    def create_kra_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # KRA controls
        kra_controls = QHBoxLayout()
        
        if self.has_permission('accounting', 'add'):
            add_kra_doc_btn = QPushButton("📄 Add KRA Document")
            add_kra_doc_btn.clicked.connect(self.add_kra_document)
            kra_controls.addWidget(add_kra_doc_btn)
        
        kra_controls.addStretch()
        
        layout.addLayout(kra_controls)
        
        # KRA documents table
        self.kra_table = QTableWidget()
        self.kra_table.setColumnCount(9)
        self.kra_table.setHorizontalHeaderLabels([
            "Doc #", "Type", "Tax Period", "Amount", "Issue Date", "Due Date", "Status", "Path", "Actions"
        ])
        self.kra_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.kra_table)
        
        self.load_kra_documents()
        
        widget.setLayout(layout)
        
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
        
        if self.has_permission('users', 'add'):
            add_user_btn = QPushButton("👤 Add User")
            add_user_btn.clicked.connect(self.add_user)
            user_controls.addWidget(add_user_btn)
        
        if self.has_permission('users', 'edit'):
            edit_user_btn = QPushButton("✏️ Edit User")
            edit_user_btn.clicked.connect(self.edit_user)
            user_controls.addWidget(edit_user_btn)
        
        if self.has_permission('users', 'delete'):
            delete_user_btn = QPushButton("🗑️ Delete User")
            delete_user_btn.clicked.connect(self.delete_user)
            user_controls.addWidget(delete_user_btn)
        
        user_controls.addStretch()
        
        layout.addLayout(user_controls)
        
        # Users table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(5)
        self.users_table.setHorizontalHeaderLabels([
            "Username", "Role", "Email", "Created", "Permissions"
        ])
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.users_table)
        
        widget.setLayout(layout)
        
        self.load_users()
        
        return widget
    
    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Tab widget for settings categories
        settings_tabs = QTabWidget()
        
        # Company settings tab
        company_tab = QWidget()
        company_layout = QVBoxLayout(company_tab)
        
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
        self.vat_rate.setValue(16)
        form_layout.addRow("💰 VAT Rate:", self.vat_rate)
        
        # ETR Settings
        etr_group = QGroupBox("ETR (Electronic Tax Register) Settings")
        etr_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; }")
        etr_layout = QFormLayout(etr_group)
        
        self.etr_device_id = QLineEdit()
        self.etr_device_id.setPlaceholderText("ETR Device ID")
        etr_layout.addRow("Device ID:", self.etr_device_id)
        
        self.etr_serial_number = QLineEdit()
        self.etr_serial_number.setPlaceholderText("ETR Serial Number")
        etr_layout.addRow("Serial Number:", self.etr_serial_number)
        
        self.tin_number = QLineEdit()
        self.tin_number.setPlaceholderText("Taxpayer Identification Number")
        etr_layout.addRow("TIN Number:", self.tin_number)
        
        form_layout.addRow(etr_group)
        
        self.invoice_prefix = QLineEdit()
        self.invoice_prefix.setText("INV")
        form_layout.addRow("📄 Invoice Prefix:", self.invoice_prefix)
        
        self.receipt_prefix = QLineEdit()
        self.receipt_prefix.setText("RCP")
        form_layout.addRow("🧾 Receipt Prefix:", self.receipt_prefix)
        
        self.receipt_footer = QTextEdit()
        self.receipt_footer.setMaximumHeight(80)
        form_layout.addRow("📝 Receipt Footer:", self.receipt_footer)
        
        company_layout.addWidget(scroll_area)
        scroll_area.setWidget(scroll_widget)
        
        # Logo selection
        logo_group = QGroupBox("Company Logo")
        logo_layout = QVBoxLayout()
        
        logo_file_layout = QHBoxLayout()
        self.logo_path = QLineEdit()
        self.logo_path.setPlaceholderText("Select logo image file...")
        logo_file_layout.addWidget(self.logo_path)
        
        browse_logo_btn = QPushButton("📁 Browse")
        browse_logo_btn.clicked.connect(self.browse_logo)
        logo_file_layout.addWidget(browse_logo_btn)
        
        logo_layout.addLayout(logo_file_layout)
        
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(150, 80)
        self.logo_preview.setStyleSheet("border: 1px solid #ccc; background: white;")
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setText("No logo selected")
        logo_layout.addWidget(self.logo_preview, alignment=Qt.AlignCenter)
        
        logo_group.setLayout(logo_layout)
        company_layout.addWidget(logo_group)
        
        settings_tabs.addTab(company_tab, "Company Settings")
        
        # Permissions tab (Admin only)
        if self.user_data['role'] == 'admin':
            perms_tab = QWidget()
            perms_layout = QVBoxLayout(perms_tab)
            
            perms_label = QLabel("🔐 Granular Permissions Configuration")
            perms_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            perms_layout.addWidget(perms_label)
            
            self.permissions_table = QTableWidget()
            self.permissions_table.setColumnCount(3)
            self.permissions_table.setHorizontalHeaderLabels(["User", "Module", "Permissions"])
            self.permissions_table.horizontalHeader().setStretchLastSection(True)
            perms_layout.addWidget(self.permissions_table)
            
            save_perms_btn = QPushButton("💾 Save Permissions")
            save_perms_btn.clicked.connect(self.save_user_permissions)
            perms_layout.addWidget(save_perms_btn)
            
            self.load_permissions_table()
            
            settings_tabs.addTab(perms_tab, "Permissions")
        
        layout.addWidget(settings_tabs)
        
        # Save settings button
        save_settings_btn = QPushButton("💾 Save All Settings")
        save_settings_btn.clicked.connect(self.save_settings)
        save_settings_btn.setStyleSheet("background-color: #4CAF50; font-size: 14px; padding: 10px; margin-top: 10px;")
        layout.addWidget(save_settings_btn)
        
        widget.setLayout(layout)
        
        self.load_settings()
        
        return widget
    
    def load_inventory(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT i.item_code, i.barcode, i.name, i.brand, c.name, i.stock_quantity, 
                   i.cost_price, i.selling_price, i.reorder_level, 
                   (SELECT MIN(b.expiry_date) FROM batches b WHERE b.item_id = i.id AND b.remaining_quantity > 0) as expiry_date
            FROM items i
            LEFT JOIN categories c ON i.category_id = c.id
            ORDER BY i.name
        """)
        
        items = cursor.fetchall()
        conn.close()
        
        self.inventory_table.setRowCount(len(items))
        
        for row, item in enumerate(items):
            status = "✅ In Stock"
            status_color = QColor(200, 255, 200)
            
            if item[5] <= item[8]:
                status = "⚠️ Low Stock"
                status_color = QColor(255, 255, 200)
            
            if item[9]:
                expiry_date = datetime.strptime(item[9], "%Y-%m-%d")
                if expiry_date < datetime.now():
                    status = "❌ Expired"
                    status_color = QColor(255, 200, 200)
                elif expiry_date < datetime.now() + timedelta(days=90):
                    status = "⚠️ Expiring Soon"
                    status_color = QColor(255, 255, 200)
            
            for col, value in enumerate(item[:9]):
                cell_item = QTableWidgetItem(str(value) if value is not None else "")
                self.inventory_table.setItem(row, col, cell_item)
            
            # Status column
            status_item = QTableWidgetItem(status)
            status_item.setBackground(status_color)
            self.inventory_table.setItem(row, 10, status_item)
    
    def load_sales(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.invoice_number, s.sale_type, s.customer_name, s.customer_kra_pin,
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
                if col == 8:  # Date column
                    try:
                        date_obj = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                        value = date_obj.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        pass
                
                cell_item = QTableWidgetItem(str(value) if value is not None else "")
                self.sales_table.setItem(row, col, cell_item)
    
    def load_purchase_orders(self):
        status_filter = self.po_status_filter.currentText()
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        if status_filter != "All":
            cursor.execute("""
                SELECT po_number, supplier_name, order_type, total_amount, 
                       paid_amount, (total_amount - paid_amount) as balance, status, order_date
                FROM purchase_orders
                WHERE status = ?
                ORDER BY order_date DESC
            """, (status_filter,))
        else:
            cursor.execute("""
                SELECT po_number, supplier_name, order_type, total_amount, 
                       paid_amount, (total_amount - paid_amount) as balance, status, order_date
                FROM purchase_orders
                ORDER BY order_date DESC
            """)
        
        orders = cursor.fetchall()
        conn.close()
        
        self.purchase_table.setRowCount(len(orders))
        
        for row, order in enumerate(orders):
            for col, value in enumerate(order):
                if col == 7:  # Date column
                    try:
                        date_obj = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                        value = date_obj.strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass
                
                cell_item = QTableWidgetItem(str(value) if value is not None else "")
                self.purchase_table.setItem(row, col, cell_item)
    
    def load_users(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT username, role, email, created_at, permissions
            FROM users
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        conn.close()
        
        self.users_table.setRowCount(len(users))
        
        for row, user in enumerate(users):
            self.users_table.setItem(row, 0, QTableWidgetItem(user[0]))
            self.users_table.setItem(row, 1, QTableWidgetItem(user[1]))
            self.users_table.setItem(row, 2, QTableWidgetItem(user[2] or ""))
            self.users_table.setItem(row, 3, QTableWidgetItem(user[3][:10] if user[3] else ""))
            
            # Show permissions summary
            perms = json.loads(user[4]) if user[4] else {}
            perm_summary = ", ".join([f"{k}:{len(v)}" for k, v in perms.items()])[:50]
            self.users_table.setItem(row, 4, QTableWidgetItem(perm_summary))
    
    def load_categories_combo(self, combo_box):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM categories ORDER BY name")
        categories = cursor.fetchall()
        conn.close()
        
        for category in categories:
            combo_box.addItem(category[0])
    
    def load_items_combo(self, combo_box):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM items ORDER BY name")
        items = cursor.fetchall()
        conn.close()
        
        combo_box.clear()
        combo_box.addItem("Select Product", None)
        for item in items:
            combo_box.addItem(item[1], item[0])
    
    def load_batches(self):
        item_id = self.batch_product_combo.currentData()
        if not item_id:
            return
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT batch_number, quantity, remaining_quantity, cost_price, 
                   manufacture_date, expiry_date, supplier_invoice,
                   CASE WHEN expiry_date < DATE('now') THEN 'Expired'
                        WHEN expiry_date < DATE('now', '+90 days') THEN 'Expiring Soon'
                        ELSE 'Good' END as status
            FROM batches
            WHERE item_id = ?
            ORDER BY expiry_date ASC
        """, (item_id,))
        
        batches = cursor.fetchall()
        conn.close()
        
        self.batches_table.setRowCount(len(batches))
        
        for row, batch in enumerate(batches):
            for col, value in enumerate(batch[:7]):
                self.batches_table.setItem(row, col, QTableWidgetItem(str(value) if value is not None else ""))
            
            status_item = QTableWidgetItem(batch[7])
            if batch[7] == "Expired":
                status_item.setBackground(QColor(255, 200, 200))
            elif batch[7] == "Expiring Soon":
                status_item.setBackground(QColor(255, 255, 200))
            self.batches_table.setItem(row, 7, status_item)
            
            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            use_btn = QPushButton("Use")
            use_btn.setMaximumWidth(50)
            use_btn.clicked.connect(lambda checked, r=row: self.use_batch(r))
            action_layout.addWidget(use_btn)
            
            self.batches_table.setCellWidget(row, 8, action_widget)
    
    def load_journal_entries(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT journal_number, entry_date, description, reference, is_posted
            FROM journal_entries
            ORDER BY entry_date DESC
            LIMIT 50
        """)
        
        entries = cursor.fetchall()
        conn.close()
        
        self.journal_table.setRowCount(len(entries))
        
        for row, entry in enumerate(entries):
            self.journal_table.setItem(row, 0, QTableWidgetItem(entry[0]))
            self.journal_table.setItem(row, 1, QTableWidgetItem(entry[1]))
            self.journal_table.setItem(row, 2, QTableWidgetItem(entry[2][:50] if entry[2] else ""))
            self.journal_table.setItem(row, 3, QTableWidgetItem(entry[3] or ""))
            self.journal_table.setItem(row, 4, QTableWidgetItem("Posted" if entry[4] else "Draft"))
            
            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            view_btn = QPushButton("View")
            view_btn.setMaximumWidth(50)
            view_btn.clicked.connect(lambda checked, jn=entry[0]: self.view_journal_entry(jn))
            action_layout.addWidget(view_btn)
            
            if not entry[4]:
                post_btn = QPushButton("Post")
                post_btn.setMaximumWidth(50)
                post_btn.clicked.connect(lambda checked, jn=entry[0]: self.post_journal_entry(jn))
                action_layout.addWidget(post_btn)
            
            self.journal_table.setCellWidget(row, 5, action_widget)
    
    def load_kra_documents(self):
        if not hasattr(self, "kra_table"):
            return
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT document_number, document_type, tax_period, amount,
                   issue_date, due_date, status, document_path
            FROM kra_documents
            ORDER BY due_date ASC
        """)
        docs = cursor.fetchall()
        conn.close()
        self.kra_table.setRowCount(len(docs))
        for row, doc in enumerate(docs):
            for col, value in enumerate(doc[:8]):
                self.kra_table.setItem(row, col, QTableWidgetItem(str(value) if value is not None else ""))
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            if doc[6] == "pending":
                mark_btn = QPushButton("Mark Paid")
                mark_btn.setMaximumWidth(80)
                mark_btn.clicked.connect(lambda checked, dn=doc[0]: self.mark_kra_paid(dn))
                action_layout.addWidget(mark_btn)
            if doc[7]:
                view_btn = QPushButton("View")
                view_btn.setMaximumWidth(50)
                view_btn.clicked.connect(lambda checked, path=doc[7]: self.open_document(path))
                action_layout.addWidget(view_btn)
            self.kra_table.setCellWidget(row, 8, action_widget)

    def load_sales_ledger(self):
        """Populate the Sales Ledger sub-tab in the Accounting page."""
        from_date = self.acct_date_from.date().toString("yyyy-MM-dd")
        to_date   = self.acct_date_to.date().toString("yyyy-MM-dd")
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.invoice_number, s.sale_type, s.customer_name, s.customer_kra_pin,
                   s.subtotal, s.vat_amount, s.total_amount,
                   s.payment_status, s.payment_method, s.created_at
            FROM sales s
            WHERE DATE(s.created_at) BETWEEN ? AND ?
              AND s.payment_status != 'void'
            ORDER BY s.created_at DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
 
        # Totals
        cursor.execute("""
            SELECT COALESCE(SUM(subtotal),0), COALESCE(SUM(vat_amount),0),
                   COALESCE(SUM(total_amount),0), COUNT(*)
            FROM sales
            WHERE DATE(created_at) BETWEEN ? AND ?
              AND payment_status != 'void'
        """, (from_date, to_date))
        totals = cursor.fetchone()
        conn.close()
 
        self.sl_summary_lbl.setText(
            f"Period: {from_date} → {to_date}  |  "
            f"Transactions: {totals[3]}  |  "
            f"Subtotal: KES {totals[0]:,.2f}  |  "
            f"VAT: KES {totals[1]:,.2f}  |  "
            f"Total Revenue: KES {totals[2]:,.2f}"
        )
 
        self.sales_ledger_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                text = str(val) if val is not None else ""
                if c in (4, 5, 6):          # currency columns
                    try:
                        text = f"KES {float(val):,.2f}"
                    except (TypeError, ValueError):
                        pass
                elif c == 9:                 # date — trim seconds
                    text = str(val)[:16] if val else ""
                item = QTableWidgetItem(text)
                if c in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.sales_ledger_table.setItem(r, c, item)
 
            # Colour-code by status
            status = str(row[7]).lower()
            color_map = {
                'completed': QColor(220, 255, 220),
                'paid':      QColor(220, 255, 220),
                'pending':   QColor(255, 255, 200),
                'partial':   QColor(255, 240, 200),
                'credit':    QColor(200, 220, 255),
            }
            bg = color_map.get(status, QColor(255, 255, 255))
            for c in range(self.sales_ledger_table.columnCount()):
                item = self.sales_ledger_table.item(r, c)
                if item:
                    item.setBackground(bg)
                    
    
    def load_permissions_table(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, username, role, permissions FROM users WHERE role != 'admin'")
        users = cursor.fetchall()
        conn.close()
        
        modules = ['inventory', 'sales', 'purchases', 'customers', 'suppliers', 'reports', 'accounting']
        actions = ['view', 'add', 'edit', 'delete']
        
        self.permissions_table.setRowCount(len(users))
        self.permissions_table.setColumnCount(2 + len(modules) * len(actions))
        
        headers = ["User ID", "Username"]
        for module in modules:
            for action in actions:
                headers.append(f"{module}.{action}")
        self.permissions_table.setHorizontalHeaderLabels(headers)
        
        for row, user in enumerate(users):
            self.permissions_table.setItem(row, 0, QTableWidgetItem(str(user[0])))
            self.permissions_table.setItem(row, 1, QTableWidgetItem(user[1]))
            
            perms = json.loads(user[3]) if user[3] else {}
            
            col = 2
            for module in modules:
                for action in actions:
                    has_perm = action in perms.get(module, [])
                    cb = QCheckBox()
                    cb.setChecked(has_perm)
                    self.permissions_table.setCellWidget(row, col, cb)
                    col += 1
    
    def load_settings(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM company_settings LIMIT 1")
        settings = cursor.fetchone()
        conn.close()
        
        if settings:
            # Column order: id[0] name[1] address[2] phone[3] email[4] website[5]
            # kra_pin[6] vat_registration[7] vat_rate[8] logo_path[9]
            # invoice_prefix[10] receipt_prefix[11] receipt_footer[12]
            # printer_settings[13] etr_device_id[14] etr_serial_number[15]
            # business_certificate[16] tin_number[17]
            self.company_name.setText(str(settings[1] or ""))
            self.company_address.setText(str(settings[2] or ""))
            self.company_phone.setText(str(settings[3] or ""))
            self.company_email.setText(str(settings[4] or ""))
            self.company_website.setText(str(settings[5] or ""))
            self.kra_pin.setText(str(settings[6] or ""))
            self.vat_rate.setValue(float(settings[8] or 16.0))   # index 8, not 7
            self.logo_path.setText(str(settings[9] or ""))        # index 9, not 8
            self.invoice_prefix.setText(str(settings[10] or "INV"))
            self.receipt_prefix.setText(str(settings[11] or "RCP"))
            self.receipt_footer.setText(str(settings[12] or ""))
            
            # ETR settings
            self.etr_device_id.setText(str(settings[14]) if len(settings) > 14 and settings[14] else "")
            self.etr_serial_number.setText(str(settings[15]) if len(settings) > 15 and settings[15] else "")
            self.tin_number.setText(str(settings[17]) if len(settings) > 17 and settings[17] else "")
            
            logo = settings[9] if len(settings) > 9 else None
            if logo and os.path.exists(str(logo)):
                pixmap = QPixmap(str(logo))
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(150, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.logo_preview.setPixmap(scaled_pixmap)
                    self.logo_preview.setText("")
   
    
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
                'vat_rate': settings[8] if len(settings) > 8 else 16.0,
                'logo_path': settings[9] if len(settings) > 9 else "",
                'invoice_prefix': settings[10] if len(settings) > 10 else "INV",
                'receipt_prefix': settings[11] if len(settings) > 11 else "RCP",
                'receipt_footer': settings[12] if len(settings) > 12 else "",
                'etr_device_id': settings[14] if len(settings) > 14 else "",
                'etr_serial_number': settings[15] if len(settings) > 15 else "",
                'tin_number': settings[17] if len(settings) > 17 else ""
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
        
        cursor.execute("""
            SELECT DISTINCT i.name, i.brand, b.expiry_date 
            FROM items i
            JOIN batches b ON b.item_id = i.id
            WHERE b.expiry_date <= DATE('now', '+90 days') AND b.remaining_quantity > 0
        """)
        
        expiring_items = cursor.fetchall()
        conn.close()
        
        alert_msg = ""
        
        if low_stock_items:
            alert_msg += "⚠️ LOW STOCK ALERT ⚠️\n\n"
            for item in low_stock_items:
                alert_msg += f"• {item[0]} ({item[1]}): {item[2]} units left (Reorder at {item[3]})\n"
        
        if expiring_items:
            alert_msg += "\n⚠️ EXPIRING PRODUCTS ⚠️\n\n"
            for item in expiring_items:
                alert_msg += f"• {item[0]} ({item[1]}) - Expires on {item[2]}\n"
        
        if alert_msg:
            QMessageBox.warning(self, "Inventory Alerts", alert_msg)
    
    def filter_inventory(self):
        search_text = self.inventory_search.text().lower()
        
        for row in range(self.inventory_table.rowCount()):
            show_row = False
            for col in range(10):
                item = self.inventory_table.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            
            self.inventory_table.setRowHidden(row, not show_row)
    
    def filter_sales(self):
        search_text = self.sales_search.text().lower()
        
        for row in range(self.sales_table.rowCount()):
            show_row = False
            for col in range(9):
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
            item_name = self.inventory_table.item(current_row, 2).text()
            
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
    
    def generate_item_barcode(self):
        current_row = self.inventory_table.currentRow()
        if current_row >= 0:
            item_code = self.inventory_table.item(current_row, 0).text()
            item_name = self.inventory_table.item(current_row, 2).text()
            barcode = self.inventory_table.item(current_row, 1).text()
            
            if not barcode:
                barcode = BarcodeGenerator.generate_barcode(item_code, item_name)
            
            # Show barcode dialog
            dialog = BarcodeDialog(barcode, item_name)
            dialog.exec_()
        else:
            QMessageBox.warning(self, "Warning", "Please select an item")
    
    def add_batch(self):
        item_id = self.batch_product_combo.currentData()
        if not item_id:
            QMessageBox.warning(self, "Warning", "Please select a product")
            return
        
        dialog = BatchDialog(self.db_manager, item_id)
        if dialog.exec_() == QDialog.Accepted:
            self.load_batches()
    
    def use_batch(self, row):
        batch_number = self.batches_table.item(row, 0).text()
        QMessageBox.information(self, "Info", f"Using batch {batch_number}. This will be applied when making a sale.")
    
    def new_sale(self):
        dialog = EnhancedSalesDialog(self.db_manager, self.user_data, "invoice")
        if dialog.exec_() == QDialog.Accepted:
            self.load_sales()
            self.load_inventory()
    
    def new_proforma(self):
        dialog = EnhancedSalesDialog(self.db_manager, self.user_data, "proforma")
        if dialog.exec_() == QDialog.Accepted:
            self.load_sales()
    
    def new_consignment(self):
        dialog = EnhancedSalesDialog(self.db_manager, self.user_data, "consignment")
        if dialog.exec_() == QDialog.Accepted:
            self.load_sales()
    
    def view_sale_details(self):
        current_row = self.sales_table.currentRow()
        if current_row >= 0:
            invoice_number = self.sales_table.item(current_row, 0).text()
            dialog = SaleDetailsDialog(self.db_manager, invoice_number)
            dialog.exec_()
    
    def edit_sale(self):
        current_row = self.sales_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a sale to edit")
            return
        invoice_number = self.sales_table.item(current_row, 0).text()
        status = self.sales_table.item(current_row, 7).text()
        if status.lower() == 'void':
            QMessageBox.warning(self, "Cannot Edit", "Voided sales cannot be edited.")
            return
        dialog = EditSaleDialog(self.db_manager, invoice_number, self.user_data)
        if dialog.exec_() == QDialog.Accepted:
            self.load_sales()
            self.load_inventory()

    def void_sale(self):
        current_row = self.sales_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a sale to void")
            return
        invoice_number = self.sales_table.item(current_row, 0).text()
        sale_type = self.sales_table.item(current_row, 1).text()
        status = self.sales_table.item(current_row, 7).text()
        if status.lower() == 'void':
            QMessageBox.information(self, "Already Voided", "This sale is already voided.")
            return
        reply = QMessageBox.question(
            self, "Confirm Void",
            f"Void sale {invoice_number}?\n\nThis will reverse stock changes for invoices and cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sales WHERE invoice_number = ?", (invoice_number,))
            sale_row = cursor.fetchone()
            if not sale_row:
                return
            sale_id = sale_row[0]
            if sale_type.lower() == 'invoice':
                cursor.execute("SELECT item_id, quantity FROM sale_items WHERE sale_id = ?", (sale_id,))
                for item_id, qty in cursor.fetchall():
                    cursor.execute("UPDATE items SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty, item_id))
            
            cursor.execute("""
                INSERT INTO audit_log (action, table_name, record_id, details, user_id)
                VALUES ('VOID', 'sales', ?, ?, ?)
            """, (str(sale_id), f"Sale {invoice_number} voided by {self.user_data['username']}", self.user_data['id']))
            cursor.execute("UPDATE sales SET payment_status = 'void' WHERE id = ?", (sale_id,))
            conn.commit()
            QMessageBox.information(self, "Voided", f"Sale {invoice_number} has been voided.")
            self.load_sales()
            self.load_inventory()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to void sale: {e}")
        finally:
            conn.close()

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
    
    def make_po_payment(self):
        current_row = self.purchase_table.currentRow()
        if current_row >= 0:
            po_number = self.purchase_table.item(current_row, 0).text()
            total = float(self.purchase_table.item(current_row, 3).text().replace("KES", "").replace(",", ""))
            paid = float(self.purchase_table.item(current_row, 4).text().replace("KES", "").replace(",", ""))
            balance = total - paid
            
            dialog = POPaymentDialog(self.db_manager, po_number, balance, self.user_data)
            if dialog.exec_() == QDialog.Accepted:
                self.load_purchase_orders()
        else:
            QMessageBox.warning(self, "Warning", "Please select a purchase order")
    
    def export_purchase_orders(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Purchase Orders to Excel", 
                                                  f"purchase_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                                  "Excel Files (*.xlsx)")
        
        if file_path:
            try:
                conn = self.db_manager.get_connection()
                po_df = pd.read_sql_query("""
                    SELECT po_number, supplier_name, order_type, total_amount, paid_amount, 
                           (total_amount - paid_amount) as balance, status, order_date, expected_delivery
                    FROM purchase_orders
                    ORDER BY order_date DESC
                """, conn)
                conn.close()
                
                po_df.to_excel(file_path, index=False)
                QMessageBox.information(self, "Success", f"Purchase orders exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
    
    def view_po_details(self):
        current_row = self.purchase_table.currentRow()
        if current_row >= 0:
            po_number = self.purchase_table.item(current_row, 0).text()
            dialog = PODetailsDialog(self.db_manager, po_number)
            dialog.exec_()
    
    def new_journal_entry(self):
        dialog = JournalEntryDialog(self.db_manager, self.user_data)
        if dialog.exec_() == QDialog.Accepted:
            self.load_journal_entries()
    
    def show_trial_balance(self):
        from_date = self.acct_date_from.date().toString("yyyy-MM-dd")
        to_date = self.acct_date_to.date().toString("yyyy-MM-dd")
        dialog = TrialBalanceDialog(self.db_manager, from_date, to_date)
        dialog.exec_()
    
    def show_profit_loss(self):
        from_date = self.acct_date_from.date().toString("yyyy-MM-dd")
        to_date = self.acct_date_to.date().toString("yyyy-MM-dd")
        dialog = ProfitLossDialog(self.db_manager, from_date, to_date)
        dialog.exec_()
    
    def show_balance_sheet(self):
        as_at_date = self.acct_date_to.date().toString("yyyy-MM-dd")
        dialog = BalanceSheetDialog(self.db_manager, as_at_date)
        dialog.exec_()
    
    def show_cash_flow(self):
        from_date = self.acct_date_from.date().toString("yyyy-MM-dd")
        to_date = self.acct_date_to.date().toString("yyyy-MM-dd")
        dialog = CashFlowDialog(self.db_manager, from_date, to_date)
        dialog.exec_()
    
    def show_bank_reconciliation(self):
        dialog = BankReconciliationDialog(self.db_manager)
        dialog.exec_()
    
    def view_journal_entry(self, journal_number):
        dialog = JournalEntryViewDialog(self.db_manager, journal_number)
        dialog.exec_()
    
    def post_journal_entry(self, journal_number):
        reply = QMessageBox.question(self, "Confirm Post", 
                                   f"Post journal entry {journal_number}? This action cannot be undone.",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            conn = self.db_manager.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE journal_entries SET is_posted = 1 WHERE journal_number = ?", (journal_number,))
                conn.commit()
                QMessageBox.information(self, "Success", "Journal entry posted successfully")
                self.load_journal_entries()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to post: {e}")
            finally:
                conn.close()
    
    def add_kra_document(self):
        dialog = KRADocumentDialog(self.db_manager, self.user_data)
        if dialog.exec_() == QDialog.Accepted:
            self.load_kra_documents()
    
    def mark_kra_paid(self, document_number):
        reply = QMessageBox.question(self, "Confirm Payment", 
                                   f"Mark KRA document {document_number} as paid?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            conn = self.db_manager.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE kra_documents SET status = 'paid' WHERE document_number = ?", (document_number,))
                conn.commit()
                QMessageBox.information(self, "Success", "Document marked as paid")
                self.load_kra_documents()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update: {e}")
            finally:
                conn.close()
    
    def open_document(self, path):
        if os.path.exists(path):
            os.startfile(path) if sys.platform == 'win32' else os.system(f'open "{path}"')
        else:
            QMessageBox.warning(self, "Error", "Document file not found")
    
    def add_user(self):
        dialog = EnhancedUserDialog(self.db_manager)
        if dialog.exec_() == QDialog.Accepted:
            self.load_users()
    
    def edit_user(self):
        current_row = self.users_table.currentRow()
        if current_row >= 0:
            username = self.users_table.item(current_row, 0).text()
            dialog = EnhancedUserDialog(self.db_manager, username)
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
    
    def save_user_permissions(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        modules = ['inventory', 'sales', 'purchases', 'customers', 'suppliers', 'reports', 'accounting']
        actions = ['view', 'add', 'edit', 'delete']
        
        for row in range(self.permissions_table.rowCount()):
            user_id = int(self.permissions_table.item(row, 0).text())
            permissions = {}
            
            col = 2
            for module in modules:
                module_perms = []
                for action in actions:
                    cb = self.permissions_table.cellWidget(row, col)
                    if cb and cb.isChecked():
                        module_perms.append(action)
                    col += 1
                if module_perms:
                    permissions[module] = module_perms
            
            cursor.execute("UPDATE users SET permissions = ? WHERE id = ?", (json.dumps(permissions), user_id))
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(self, "Success", "Permissions saved successfully")
    
    def browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", 
                                                  "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_path:
            self.logo_path.setText(file_path)
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(150, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_preview.setPixmap(scaled_pixmap)
                self.logo_preview.setText("")
            else:
                self.logo_preview.setText("Invalid image file")
    
    def save_settings(self):
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            # Get current settings to preserve existing data
            cursor.execute("SELECT * FROM company_settings LIMIT 1")
            existing = cursor.fetchone()

            if existing and len(existing) >= 15:
                # Update all columns
                cursor.execute("""
                    UPDATE company_settings SET
                        company_name = ?,
                        company_address = ?,
                        company_phone = ?,
                        company_email = ?,
                        company_website = ?,
                        kra_pin = ?,
                        vat_rate = ?,
                        logo_path = ?,
                        invoice_prefix = ?,
                        receipt_prefix = ?,
                        receipt_footer = ?,
                        etr_device_id = ?,
                        etr_serial_number = ?,
                        tin_number = ?
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
                    self.receipt_footer.toPlainText(),
                    self.etr_device_id.text(),
                    self.etr_serial_number.text(),
                    self.tin_number.text()
                ))
            else:
                # Insert new record
                cursor.execute("""
                    INSERT OR REPLACE INTO company_settings
                    (
                        id,
                        company_name,
                        company_address,
                        company_phone,
                        company_email,
                        company_website,
                        kra_pin,
                        vat_rate,
                        logo_path,
                        invoice_prefix,
                        receipt_prefix,
                        receipt_footer,
                        etr_device_id,
                        etr_serial_number,
                        tin_number
                    )
                    VALUES
                    (
                        1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
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
                    self.receipt_footer.toPlainText(),
                    self.etr_device_id.text(),
                    self.etr_serial_number.text(),
                    self.tin_number.text()
                ))

            conn.commit()
            conn.close()

            QMessageBox.information(
                self,
                "Success",
                "Settings saved successfully!"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}"
            )
    
    def _filter_table(self, table, text, col_count):
        """Generic table filter by text across all columns."""
        text = text.lower()
        for row in range(table.rowCount()):
            show = any(
                text in (table.item(row, c).text().lower() if table.item(row, c) else "")
                for c in range(col_count)
            )
            table.setRowHidden(row, not show)

    def create_customers_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        controls = QHBoxLayout()

        if self.has_permission('customers', 'add'):
            add_btn = QPushButton("➕ Add Customer")
            add_btn.clicked.connect(self.add_customer)
            controls.addWidget(add_btn)

        if self.has_permission('customers', 'edit'):
            edit_btn = QPushButton("✏️ Edit Customer")
            edit_btn.clicked.connect(self.edit_customer)
            controls.addWidget(edit_btn)

        controls.addStretch()

        search = QLineEdit()
        search.setPlaceholderText("🔍 Search customers...")
        controls.addWidget(search)
        layout.addLayout(controls)

        self.customers_table = QTableWidget()
        self.customers_table.setColumnCount(8)
        self.customers_table.setHorizontalHeaderLabels([
            "Name", "Phone", "Email", "Address", "KRA PIN", "Credit Limit", "Balance", "Loyalty Pts"
        ])
        self.customers_table.horizontalHeader().setStretchLastSection(True)
        self.customers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.customers_table.setAlternatingRowColors(True)
        layout.addWidget(self.customers_table)
        widget.setLayout(layout)

        search.textChanged.connect(lambda t: self._filter_table(self.customers_table, t, 7))
        self.load_customers()
        return widget

    def load_customers(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, phone, email, address, kra_pin, credit_limit, outstanding_balance, loyalty_points FROM customers ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        self.customers_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.customers_table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))

    def add_customer(self):
        dlg = EnhancedCustomerDialog(self.db_manager)
        if dlg.exec_() == QDialog.Accepted:
            self.load_customers()

    def edit_customer(self):
        row = self.customers_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a customer")
            return
        name = self.customers_table.item(row, 0).text()
        dlg = EnhancedCustomerDialog(self.db_manager, name)
        if dlg.exec_() == QDialog.Accepted:
            self.load_customers()

    def create_suppliers_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        controls = QHBoxLayout()

        if self.has_permission('suppliers', 'add'):
            add_btn = QPushButton("➕ Add Supplier")
            add_btn.clicked.connect(self.add_supplier)
            controls.addWidget(add_btn)

        if self.has_permission('suppliers', 'edit'):
            edit_btn = QPushButton("✏️ Edit Supplier")
            edit_btn.clicked.connect(self.edit_supplier)
            controls.addWidget(edit_btn)

        contract_btn = QPushButton("📄 Supplier Contracts")
        contract_btn.clicked.connect(self.manage_supplier_contracts)
        controls.addWidget(contract_btn)

        controls.addStretch()
        layout.addLayout(controls)

        self.suppliers_table = QTableWidget()
        self.suppliers_table.setColumnCount(8)
        self.suppliers_table.setHorizontalHeaderLabels([
            "Supplier", "Contact Person", "Phone", "Email", "KRA PIN", "Payment Terms", "Balance", "Actions"
        ])
        self.suppliers_table.horizontalHeader().setStretchLastSection(True)
        self.suppliers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.suppliers_table.setAlternatingRowColors(True)
        layout.addWidget(self.suppliers_table)
        widget.setLayout(layout)
        self.load_suppliers()
        return widget

    def load_suppliers(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, contact_person, phone, email, kra_pin, payment_terms, outstanding_balance FROM suppliers ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        self.suppliers_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.suppliers_table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))
            
            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            pay_btn = QPushButton("Pay")
            pay_btn.setMaximumWidth(50)
            pay_btn.clicked.connect(lambda checked, name=row[0]: self.pay_supplier(name))
            action_layout.addWidget(pay_btn)
            
            self.suppliers_table.setCellWidget(r, 7, action_widget)

    def add_supplier(self):
        dlg = EnhancedSupplierDialog(self.db_manager)
        if dlg.exec_() == QDialog.Accepted:
            self.load_suppliers()

    def edit_supplier(self):
        row = self.suppliers_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a supplier")
            return
        name = self.suppliers_table.item(row, 0).text()
        dlg = EnhancedSupplierDialog(self.db_manager, name)
        if dlg.exec_() == QDialog.Accepted:
            self.load_suppliers()
    
    def pay_supplier(self, supplier_name):
        dlg = SupplierPaymentDialog(self.db_manager, supplier_name, self.user_data)
        if dlg.exec_() == QDialog.Accepted:
            self.load_suppliers()
    
    def manage_supplier_contracts(self):
        dlg = SupplierContractsDialog(self.db_manager)
        dlg.exec_()

    def create_expenses_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        controls = QHBoxLayout()

        add_btn = QPushButton("➕ Add Expense")
        add_btn.clicked.connect(self.add_expense)
        controls.addWidget(add_btn)

        controls.addStretch()

        controls.addWidget(QLabel("From:"))
        self.exp_date_from = QDateEdit()
        self.exp_date_from.setDate(QDate.currentDate().addDays(-30))
        controls.addWidget(self.exp_date_from)
        controls.addWidget(QLabel("To:"))
        self.exp_date_to = QDateEdit()
        self.exp_date_to.setDate(QDate.currentDate())
        controls.addWidget(self.exp_date_to)

        filter_btn = QPushButton("🔍 Filter")
        filter_btn.clicked.connect(self.load_expenses)
        controls.addWidget(filter_btn)

        layout.addLayout(controls)

        self.expenses_table = QTableWidget()
        self.expenses_table.setColumnCount(6)
        self.expenses_table.setHorizontalHeaderLabels([
            "Date", "Category", "Description", "Amount (KES)", "Method", "Ref"
        ])
        self.expenses_table.horizontalHeader().setStretchLastSection(True)
        self.expenses_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.expenses_table.setAlternatingRowColors(True)
        layout.addWidget(self.expenses_table)

        self.expenses_total_label = QLabel("Total: KES 0.00")
        self.expenses_total_label.setStyleSheet("font-weight:bold; font-size:14px; padding:5px;")
        layout.addWidget(self.expenses_total_label)

        widget.setLayout(layout)
        self.load_expenses()
        return widget

    def load_expenses(self):
        from_date = self.exp_date_from.date().toString("yyyy-MM-dd")
        to_date = self.exp_date_to.date().toString("yyyy-MM-dd")
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT expense_date, category, description, amount, payment_method, reference
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            ORDER BY expense_date DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        self.expenses_table.setRowCount(len(rows))
        total = 0
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.expenses_table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))
            try:
                total += float(row[3])
            except (TypeError, ValueError):
                pass
        self.expenses_total_label.setText(f"Total Expenses: KES {total:,.2f}")

    def add_expense(self):
        dlg = ExpenseDialog(self.db_manager, self.user_data)
        if dlg.exec_() == QDialog.Accepted:
            self.load_expenses()

    def create_audit_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        controls = QHBoxLayout()
        controls.addWidget(QLabel("From:"))
        self.audit_date_from = QDateEdit()
        self.audit_date_from.setDate(QDate.currentDate().addDays(-7))
        controls.addWidget(self.audit_date_from)
        controls.addWidget(QLabel("To:"))
        self.audit_date_to = QDateEdit()
        self.audit_date_to.setDate(QDate.currentDate())
        controls.addWidget(self.audit_date_to)
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_audit_log)
        controls.addWidget(refresh_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(6)
        self.audit_table.setHorizontalHeaderLabels([
            "Timestamp", "User", "Action", "Table", "Record ID", "Details"
        ])
        self.audit_table.horizontalHeader().setStretchLastSection(True)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.audit_table.setAlternatingRowColors(True)
        layout.addWidget(self.audit_table)
        widget.setLayout(layout)
        self.load_audit_log()
        return widget

    def load_audit_log(self):
        from_date = self.audit_date_from.date().toString("yyyy-MM-dd")
        to_date = self.audit_date_to.date().toString("yyyy-MM-dd")
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.timestamp, u.username, a.action, a.table_name, a.record_id, a.details
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            WHERE DATE(a.timestamp) BETWEEN ? AND ?
            ORDER BY a.timestamp DESC
            LIMIT 500
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        self.audit_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.audit_table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))

    def generate_sales_report(self):
        from_date = self.date_from.date().toString("yyyy-MM-dd")
        to_date = self.date_to.date().toString("yyyy-MM-dd")
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.invoice_number, s.sale_type, s.customer_name, 
                   s.subtotal, s.vat_amount, s.total_amount, s.payment_status, 
                   s.payment_method, s.created_at, u.username
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
              AND s.payment_status != 'void'
            ORDER BY s.created_at DESC
        """, (from_date, to_date))
 
        sales = cursor.fetchall()
 
        total_sales    = sum(sale[5] for sale in sales)
        total_vat      = sum(sale[4] for sale in sales)
        total_subtotal = sum(sale[3] for sale in sales)
 
        cursor.execute("""
            SELECT payment_method, COUNT(*), SUM(total_amount)
            FROM sales
            WHERE DATE(created_at) BETWEEN ? AND ?
              AND payment_status != 'void'
            GROUP BY payment_method
        """, (from_date, to_date))
        
        payment_breakdown = cursor.fetchall()
        
        cursor.execute("""
            SELECT DATE(created_at), COUNT(*), SUM(total_amount)
            FROM sales
            WHERE DATE(created_at) BETWEEN ? AND ?
              AND payment_status != 'void'
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
        """, (from_date, to_date))
        
        daily_trend = cursor.fetchall()
        
        conn.close()
        
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
                   i.cost_price, i.selling_price, i.reorder_level,
                   COALESCE(SUM(b.quantity), 0) as total_batch_qty,
                   MIN(b.expiry_date) as earliest_expiry
            FROM items i
            LEFT JOIN categories c ON i.category_id = c.id
            LEFT JOIN batches b ON b.item_id = i.id
            GROUP BY i.id
            ORDER BY i.name
        """)
        
        items = cursor.fetchall()
        conn.close()
        
        total_items = len(items)
        total_stock_value = sum((item[5] or 0) * (item[4] or 0) for item in items)
        low_stock_items = [item for item in items if item[4] <= item[7]]
        
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
│ Low Stock Items:         {len(low_stock_items):>15}                            │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           LOW STOCK ALERTS                                     │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        
        for item in low_stock_items[:20]:
            report += f"│ {item[1]} ({item[2]}): {item[4]} units left (Reorder at {item[7]})│\n"
        
        if not low_stock_items:
            report += "│ No low stock items                                                      │\n"
        
        report += """
└──────────────────────────────────────────────────────────────────────────────┘
"""
        
        self.report_display.setText(report)
    
    def generate_daily_summary(self):
        today = datetime.now().strftime('%Y-%m-%d')
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
 
        # Today's sales totals
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(total_amount),0),
                   COALESCE(SUM(vat_amount),0), COALESCE(SUM(subtotal),0)
            FROM sales
            WHERE DATE(created_at) = ?
              AND payment_status != 'void'
              AND sale_type = 'invoice'
        """, (today,))
        sales_data = cursor.fetchone()
 
        # Payment status breakdown
        cursor.execute("""
            SELECT payment_status, COUNT(*), COALESCE(SUM(total_amount),0)
            FROM sales
            WHERE DATE(created_at) = ?
              AND payment_status != 'void'
            GROUP BY payment_status
        """, (today,))
        payment_breakdown = cursor.fetchall()
 
        # Top 10 items sold today
        cursor.execute("""
            SELECT i.name, i.brand, SUM(si.quantity) as qty_sold,
                   SUM(si.total_price) as revenue
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            JOIN sales s ON si.sale_id = s.id
            WHERE DATE(s.created_at) = ?
              AND s.payment_status != 'void'
            GROUP BY i.id
            ORDER BY qty_sold DESC
            LIMIT 10
        """, (today,))
        top_items = cursor.fetchall()
 
        # Payment method breakdown
        cursor.execute("""
            SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount),0)
            FROM sales
            WHERE DATE(created_at) = ?
              AND payment_status != 'void'
            GROUP BY payment_method
        """, (today,))
        method_breakdown = cursor.fetchall()
 
        # Today's expenses
        cursor.execute("""
            SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date = ?
        """, (today,))
        expenses_today = cursor.fetchone()[0]
 
        conn.close()
 
        count     = sales_data[0] or 0
        revenue   = sales_data[1] or 0
        vat       = sales_data[2] or 0
        subtotal  = sales_data[3] or 0
        net_cash  = revenue - expenses_today
 
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          DAILY SUMMARY REPORT                                  ║
║                              {today}                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
 
┌──────────────────────────────────────────────────────────────────────────────┐
│                             TODAY'S SALES SUMMARY                             │
├──────────────────────────────────────────────────────────────────────────────┤
│ Number of Invoices:     {count:>15}                                           │
│ Total Revenue:          KES {revenue:>15,.2f}                                 │
│ VAT Collected:          KES {vat:>15,.2f}                                 │
│ Subtotal (excl. VAT):   KES {subtotal:>15,.2f}                                 │
│ Expenses Today:         KES {expenses_today:>15,.2f}                                 │
│ Net Cash Position:      KES {net_cash:>15,.2f}                                 │
└──────────────────────────────────────────────────────────────────────────────┘
 
┌──────────────────────────────────────────────────────────────────────────────┐
│                          PAYMENT STATUS BREAKDOWN                             │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        for status, cnt, amt in payment_breakdown:
            report += f"│  {(status or 'N/A'):<20}  {cnt:>4} transactions   KES {amt:>12,.2f}          │\n"
        if not payment_breakdown:
            report += "│  No sales recorded today                                                 │\n"
 
        report += f"""└──────────────────────────────────────────────────────────────────────────────┘
 
┌──────────────────────────────────────────────────────────────────────────────┐
│                          PAYMENT METHOD BREAKDOWN                             │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        for method, cnt, amt in method_breakdown:
            pct = (amt / revenue * 100) if revenue else 0
            report += f"│  {(method or 'N/A'):<20}  {cnt:>4} sales   KES {amt:>12,.2f}  ({pct:.1f}%)    │\n"
        if not method_breakdown:
            report += "│  No payment data                                                         │\n"
 
        report += f"""└──────────────────────────────────────────────────────────────────────────────┘
 
┌──────────────────────────────────────────────────────────────────────────────┐
│                         TOP 10 SELLING PRODUCTS TODAY                         │
├──────────────────────────────────────────────────────────────────────────────┤
"""
        for idx, item in enumerate(top_items, 1):
            report += f"│  {idx:2}. {item[0]} ({item[1] or '—'})  \n"
            report += f"│       Sold: {item[2]} units   Revenue: KES {item[3]:>12,.2f}             │\n"
        if not top_items:
            report += "│  No items sold today                                                     │\n"
 
        report += "└──────────────────────────────────────────────────────────────────────────────┘\n"
 
        self.report_display.setText(report)
    
    def generate_profit_report(self):
        from_date = self.date_from.date().toString("yyyy-MM-dd")
        to_date = self.date_to.date().toString("yyyy-MM-dd")
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT i.name, i.brand, i.cost_price, i.selling_price, 
                   SUM(si.quantity) as total_sold,
                   (i.selling_price - i.cost_price) * SUM(si.quantity) as total_profit
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            JOIN sales s ON si.sale_id = s.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
              AND s.payment_status != 'void'
            GROUP BY i.id
            ORDER BY total_profit DESC
        """, (from_date, to_date))
        
        profit_items = cursor.fetchall()
        
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
                    
                    inventory_df = pd.read_sql_query("""
                        SELECT i.item_code, i.name, i.brand, c.name as category, 
                               i.stock_quantity, i.cost_price, i.selling_price, 
                               i.reorder_level, i.supplier
                        FROM items i
                        LEFT JOIN categories c ON i.category_id = c.id
                        ORDER BY i.name
                    """, conn)
                    inventory_df.to_excel(writer, sheet_name='Inventory', index=False)
                    
                    sales_df = pd.read_sql_query("""
                        SELECT s.invoice_number, s.sale_type, s.customer_name, s.customer_kra_pin,
                               s.subtotal, s.vat_amount, s.total_amount, 
                               s.payment_status, s.payment_method, s.created_at, u.username as salesperson
                        FROM sales s
                        LEFT JOIN users u ON s.user_id = u.id
                        ORDER BY s.created_at DESC
                    """, conn)
                    sales_df.to_excel(writer, sheet_name='Sales', index=False)
                    
                    customers_df = pd.read_sql_query(
                        "SELECT name, phone, email, address, kra_pin, credit_limit, outstanding_balance, loyalty_points FROM customers ORDER BY name",
                        conn
                    )
                    customers_df.to_excel(writer, sheet_name='Customers', index=False)
                    
                    suppliers_df = pd.read_sql_query(
                        "SELECT name, contact_person, phone, email, kra_pin, payment_terms, outstanding_balance FROM suppliers ORDER BY name",
                        conn
                    )
                    suppliers_df.to_excel(writer, sheet_name='Suppliers', index=False)
                    
                    purchase_df = pd.read_sql_query("""
                        SELECT po_number, supplier_name, order_type, total_amount, paid_amount,
                               (total_amount - paid_amount) as balance, status, order_date
                        FROM purchase_orders
                        ORDER BY order_date DESC
                    """, conn)
                    purchase_df.to_excel(writer, sheet_name='Purchase Orders', index=False)
                    
                    expenses_df = pd.read_sql_query(
                        "SELECT expense_date, category, description, amount, payment_method, reference FROM expenses ORDER BY expense_date DESC",
                        conn
                    )
                    expenses_df.to_excel(writer, sheet_name='Expenses', index=False)
                    
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
                         "✨ SuperBusiness ERP ✨\n\n"
                         "Version 3.0\n"
                         "Built with PyQt5\n\n"
                         "Features:\n"
                         "• User authentication with role-based access\n"
                         "• Granular permissions per user\n"
                         "• Inventory management with batch tracking\n"
                         "• Barcode generation and scanning\n"
                         "• Beautiful HTML receipts with company branding\n"
                         "• VAT inclusive pricing with automatic calculation\n"
                         "• Invoice, Proforma, and Consignment support\n"
                         "• Customer KRA PIN for ETR compliance\n"
                         "• Supplier contract management\n"
                         "• Full accounting suite (GL, Journal, Trial Balance, P&L, Balance Sheet, Cash Flow)\n"
                         "• Bank reconciliation\n"
                         "• KRA document tracking\n"
                         "• Comprehensive reports with profit analysis\n"
                         "• Excel export and database backup\n\n"
                         "© 2025 Glamour Cosmetics. All rights reserved.\n\nPowered by SuperBusiness ERP")


# Additional Dialog Classes (simplified versions - expand as needed)

class BarcodeDialog(QDialog):
    def __init__(self, barcode, product_name):
        super().__init__()
        self.barcode = barcode
        self.product_name = product_name
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle(f"Barcode for {self.product_name}")
        self.setFixedSize(300, 250)
        
        layout = QVBoxLayout()
        
        label = QLabel(self.product_name)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(label)
        
        # Generate barcode image
        barcode_img_data = BarcodeGenerator.create_barcode_image(self.barcode)
        pixmap = QPixmap()
        pixmap.loadFromData(barcode_img_data)
        
        barcode_label = QLabel()
        barcode_label.setPixmap(pixmap.scaled(250, 100, Qt.KeepAspectRatio))
        barcode_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(barcode_label)
        
        code_label = QLabel(f"Code: {self.barcode}")
        code_label.setAlignment(Qt.AlignCenter)
        code_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(code_label)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)


class BatchDialog(QDialog):
    def __init__(self, db_manager, item_id):
        super().__init__()
        self.db_manager = db_manager
        self.item_id = item_id
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Add Batch")
        self.setFixedSize(400, 350)
        
        layout = QFormLayout()
        
        self.batch_number = QLineEdit()
        self.batch_number.setPlaceholderText("e.g., BATCH001")
        layout.addRow("Batch Number:", self.batch_number)
        
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 99999)
        layout.addRow("Quantity:", self.quantity)
        
        self.cost_price = QDoubleSpinBox()
        self.cost_price.setRange(0, 999999)
        self.cost_price.setPrefix("KES ")
        layout.addRow("Cost Price:", self.cost_price)
        
        self.manufacture_date = QDateEdit()
        self.manufacture_date.setDate(QDate.currentDate())
        self.manufacture_date.setCalendarPopup(True)
        layout.addRow("Manufacture Date:", self.manufacture_date)
        
        self.expiry_date = QDateEdit()
        self.expiry_date.setDate(QDate.currentDate().addDays(365))
        self.expiry_date.setCalendarPopup(True)
        layout.addRow("Expiry Date:", self.expiry_date)
        
        self.supplier_invoice = QLineEdit()
        layout.addRow("Supplier Invoice:", self.supplier_invoice)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        self.setLayout(layout)
    
    def save(self):
        if not self.batch_number.text().strip():
            QMessageBox.warning(self, "Error", "Please enter batch number")
            return
        
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO batches (item_id, batch_number, quantity, remaining_quantity, 
                                   cost_price, manufacture_date, expiry_date, supplier_invoice)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.item_id, self.batch_number.text(), self.quantity.value(), self.quantity.value(),
                  self.cost_price.value(), self.manufacture_date.date().toString("yyyy-MM-dd"),
                  self.expiry_date.date().toString("yyyy-MM-dd"), self.supplier_invoice.text()))
            
            # Update item stock quantity
            cursor.execute("UPDATE items SET stock_quantity = stock_quantity + ? WHERE id = ?",
                          (self.quantity.value(), self.item_id))
            
            conn.commit()
            QMessageBox.information(self, "Success", "Batch added successfully")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to add batch: {e}")
        finally:
            conn.close()


class EnhancedSalesDialog(QDialog):
    def __init__(self, db_manager, user_data, sale_type):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.sale_type = sale_type
        self.cart_items = []
        self.init_ui()
        self.load_items()
    
    def init_ui(self):
        self.setWindowTitle(f"New {self.sale_type.title()}")
        self.setGeometry(100, 100, 1100, 750)
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        # Customer info with KRA PIN
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
        
        self.customer_kra_pin = QLineEdit()
        self.customer_kra_pin.setPlaceholderText("KRA PIN (for ETR)")
        customer_layout.addRow("KRA PIN:", self.customer_kra_pin)
        
        customer_group.setLayout(customer_layout)
        layout.addWidget(customer_group)
        
        # Item selection (same as before)
        item_group = QGroupBox("Add Items")
        item_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        item_layout = QHBoxLayout()
        
        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(400)
        self.item_combo.setEditable(True)
        self.item_combo.setInsertPolicy(QComboBox.NoInsert)
        self.item_combo.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.item_combo.completer().setFilterMode(Qt.MatchContains)
        self.item_combo.lineEdit().setPlaceholderText("🔍 Type to search product...")
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
        
        # Cart table
        cart_group = QGroupBox("Shopping Cart")
        cart_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cart_layout = QVBoxLayout()
        
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(6)
        self.cart_table.setHorizontalHeaderLabels(["Product", "Brand", "Quantity", "Unit Price", "Total", "Action"])
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
        totals_form.addRow(f"VAT:", self.vat_label)
        
        self.total_label = QLabel("KES 0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #FF1493;")
        totals_form.addRow("TOTAL:", self.total_label)
        
        totals_layout.addLayout(totals_form)
        
        # Payment section
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
        
        process_btn = QPushButton("✅ Complete Sale & Print Receipt")
        process_btn.clicked.connect(self.process_sale)
        process_btn.setStyleSheet("background-color: #FF1493; font-size: 14px; padding: 10px;")
        button_layout.addWidget(process_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
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
        
        # Get VAT rate
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT vat_rate FROM company_settings LIMIT 1")
        settings = cursor.fetchone()
        conn.close()
        vat_rate = settings[0] if settings else 16
        
        if self.sale_type == "invoice":
            vat = subtotal * (vat_rate / (100 + vat_rate))
            total = subtotal
        else:
            vat = 0
            total = subtotal
        
        self.subtotal_label.setText(f"KES {subtotal:.2f}")
        self.vat_label.setText(f"KES {vat:.2f}")
        self.total_label.setText(f"KES {total:.2f}")
        
        self.amount_paid.setMaximum(total + 1000)
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
        paid = self.amount_paid.value()
        
        if paid < total:
            QMessageBox.warning(self, "Error", f"Insufficient payment! Amount short by KES {total - paid:.2f}")
            return
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            prefix = {"invoice": "INV", "proforma": "PRO", "consignment": "CON"}[self.sale_type]
            cursor.execute("SELECT COUNT(*) FROM sales")
            count = cursor.fetchone()[0] + 1
            invoice_number = f"{prefix}{datetime.now().strftime('%Y%m%d')}{count:04d}"
            
            subtotal = sum(item['total'] for item in self.cart_items)
            
            cursor.execute("SELECT vat_rate FROM company_settings LIMIT 1")
            vat_setting = cursor.fetchone()
            vat_rate = vat_setting[0] if vat_setting else 16
            
            if self.sale_type == "invoice":
                vat = subtotal * (vat_rate / (100 + vat_rate))
                total_amount = subtotal
            else:
                vat = 0
                total_amount = subtotal
            
            cursor.execute("""
                INSERT INTO sales 
                (invoice_number, sale_type, customer_name, customer_phone, customer_address, customer_kra_pin,
                 subtotal, vat_amount, total_amount, payment_status, payment_method, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_number, self.sale_type, self.customer_name.text(), self.customer_phone.text(),
                  self.customer_address.toPlainText(), self.customer_kra_pin.text(),
                  subtotal, vat, total_amount, "completed", self.payment_method.currentText(), self.user_data['id']))
            
            sale_id = cursor.lastrowid
            
            for item in self.cart_items:
                cursor.execute("""
                    INSERT INTO sale_items (sale_id, item_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, (sale_id, item['id'], item['quantity'], item['price'], item['total']))
                
                if self.sale_type == "invoice":
                    cursor.execute("UPDATE items SET stock_quantity = stock_quantity - ? WHERE id = ?",
                                  (item['quantity'], item['id']))
            
            conn.commit()
            
            if self.sale_type == "invoice":
                try:
                    cursor.execute("SELECT COUNT(*) FROM journal_entries")
                    jcount = cursor.fetchone()[0] + 1
                    jnum = f"JNL-SALE-{datetime.now().strftime('%Y%m%d')}{jcount:04d}"
 
                    # Lookup account IDs
                    cursor.execute("SELECT id FROM chart_of_accounts WHERE account_code = '1100'")  # A/R
                    ar_row = cursor.fetchone()
                    cursor.execute("SELECT id FROM chart_of_accounts WHERE account_code = '4000'")  # Sales Revenue
                    rev_row = cursor.fetchone()
                    cursor.execute("SELECT id FROM chart_of_accounts WHERE account_code = '2100'")  # VAT Payable
                    vat_row = cursor.fetchone()
 
                    if ar_row and rev_row:
                        cursor.execute("""
                            INSERT INTO journal_entries
                            (journal_number, entry_date, description, reference, is_posted, created_by)
                            VALUES (?, DATE('now'), ?, ?, 1, ?)
                        """, (jnum,
                              f"Sale {invoice_number} — {self.customer_name.text() or 'Walk-in'}",
                              invoice_number,
                              self.user_data['id']))
                        jid = cursor.lastrowid
 
                        # Dr Accounts Receivable (full amount)
                        cursor.execute("""
                            INSERT INTO journal_entry_lines
                            (journal_id, account_id, debit_amount, credit_amount, description)
                            VALUES (?, ?, ?, 0, ?)
                        """, (jid, ar_row[0], total_amount, f"Sale {invoice_number}"))
 
                        # Cr Sales Revenue (subtotal excl. VAT)
                        cursor.execute("""
                            INSERT INTO journal_entry_lines
                            (journal_id, account_id, debit_amount, credit_amount, description)
                            VALUES (?, ?, 0, ?, ?)
                        """, (jid, rev_row[0], subtotal - vat, f"Revenue {invoice_number}"))
 
                        # Cr VAT Payable (if any)
                        if vat > 0 and vat_row:
                            cursor.execute("""
                                INSERT INTO journal_entry_lines
                                (journal_id, account_id, debit_amount, credit_amount, description)
                                VALUES (?, ?, 0, ?, ?)
                            """, (jid, vat_row[0], vat, f"VAT {invoice_number}"))
 
                        conn.commit()
                except Exception:
                    pass  # journal failure must not block the sale
        
            
            cursor.execute("SELECT * FROM company_settings LIMIT 1")
            company = cursor.fetchone()
            company_data = {
                'company_name': company[1] if company else "Glamour Cosmetics",
                'company_address': company[2] if company else "",
                'company_phone': company[3] if company else "",
                'company_email': company[4] if company else "",
                'company_website': company[5] if company else "",
                'kra_pin': company[6] if company else "",
                'vat_rate': company[8] if company and len(company) > 8 else 16,
                'logo_path': company[9] if company and len(company) > 9 else "",
                'receipt_footer': company[12] if company and len(company) > 12 else "",
                'etr_device_id': company[14] if company and len(company) > 14 else "",
                'etr_serial_number': company[15] if company and len(company) > 15 else ""
            }
            
            conn.close()
            
            sale_data = {
                'invoice_number': invoice_number,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'salesperson': self.user_data['username'],
                'customer_name': self.customer_name.text(),
                'customer_phone': self.customer_phone.text(),
                'customer_kra_pin': self.customer_kra_pin.text(),
                'subtotal': subtotal,
                'vat_amount': vat,
                'total': total_amount,
                'payment_method': self.payment_method.currentText(),
                'amount_paid': paid,
                'change': paid - total_amount
            }
            
            html_receipt = ReceiptPrinter.generate_html_receipt(sale_data, company_data, self.cart_items, self.sale_type)
            reply = QMessageBox.question(self, "Print Receipt", "Would you like to preview the receipt before printing?",
                                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                ReceiptPrinter.preview_receipt(html_receipt, self)
            elif reply == QMessageBox.No:
                ReceiptPrinter.print_receipt(html_receipt)
            
            QMessageBox.information(self, "Success", 
                f"{self.sale_type.title()} completed successfully!\n\n"
                f"Document Number: {invoice_number}\n"
                f"Total Amount: KES {total_amount:,.2f}")
            
            self.accept()
            
        except Exception as e:
            conn.rollback()
            conn.close()
            QMessageBox.critical(self, "Error", f"Failed to process sale: {str(e)}")


# Additional dialog classes
class ReceiveGoodsDialog(QDialog):
    """Mark a pending PO as received and update stock quantities."""
 
    def __init__(self, db_manager, po_number):
        super().__init__()
        self.db_manager = db_manager
        self.po_number = po_number
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Receive Goods — {self.po_number}")
        self.setMinimumSize(700, 450)
        layout = QVBoxLayout(self)
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT supplier_name, total_amount, status FROM purchase_orders WHERE po_number = ?",
            (self.po_number,)
        )
        po = cursor.fetchone()
        cursor.execute(
            "SELECT item_description, quantity, unit_price, total_price, batch_number FROM purchase_order_items WHERE po_id = (SELECT id FROM purchase_orders WHERE po_number = ?)",
            (self.po_number,)
        )
        items = cursor.fetchall()
        conn.close()
 
        if po:
            info = QLabel(
                f"PO: {self.po_number}  |  Supplier: {po[0]}  |  "
                f"Total: KES {po[1]:,.2f}  |  Status: {po[2].upper()}"
            )
            info.setStyleSheet("font-weight:bold; padding:6px; background:#f5f5f5;")
            layout.addWidget(info)
 
        layout.addWidget(QLabel("Items on this order:"))
        tbl = QTableWidget(len(items), 6)
        tbl.setHorizontalHeaderLabels(["Description", "Ordered Qty", "Receive Qty", "Unit Price", "Total", "Batch #"])
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.recv_spinboxes = []
        for r, it in enumerate(items):
            tbl.setItem(r, 0, QTableWidgetItem(str(it[0])))
            tbl.setItem(r, 1, QTableWidgetItem(str(it[1])))
            sp = QSpinBox()
            sp.setRange(0, it[1])
            sp.setValue(it[1])
            tbl.setCellWidget(r, 2, sp)
            self.recv_spinboxes.append(sp)
            tbl.setItem(r, 3, QTableWidgetItem(f"{it[2]:,.2f}"))
            tbl.setItem(r, 4, QTableWidgetItem(f"{it[3]:,.2f}"))
            tbl.setItem(r, 5, QTableWidgetItem(str(it[4] or "")))
        layout.addWidget(tbl)
        self._tbl = tbl
        self._items = items
 
        self.received_date = QDateEdit(QDate.currentDate())
        self.received_date.setCalendarPopup(True)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Received Date:"))
        hl.addWidget(self.received_date)
        hl.addStretch()
        layout.addLayout(hl)
 
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("✅ Confirm Receipt")
        save_btn.setStyleSheet("background:#4CAF50; color:white; padding:8px 20px; font-weight:bold;")
        save_btn.clicked.connect(self._confirm)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(QPushButton("Cancel", clicked=self.reject))
        layout.addLayout(btn_layout)
 
    def _confirm(self):
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            recv_date = self.received_date.date().toString("yyyy-MM-dd")
            cursor.execute(
                "SELECT id FROM purchase_orders WHERE po_number = ?", (self.po_number,)
            )
            po_id = cursor.fetchone()[0]
 
            cursor.execute(
                "SELECT id, item_id, quantity, batch_number FROM purchase_order_items WHERE po_id = ?",
                (po_id,)
            )
            po_items = cursor.fetchall()
 
            for idx, poi in enumerate(po_items):
                recv_qty = self.recv_spinboxes[idx].value()
                if recv_qty <= 0:
                    continue
                # Update item stock
                cursor.execute(
                    "UPDATE items SET stock_quantity = stock_quantity + ? WHERE id = ?",
                    (recv_qty, poi[1])
                )
                # Update batch received_date and remaining_quantity
                cursor.execute(
                    """UPDATE batches SET received_date = ?, remaining_quantity = remaining_quantity + ?
                       WHERE item_id = ? AND batch_number = ?""",
                    (recv_date, recv_qty, poi[1], poi[3])
                )
 
            cursor.execute(
                "UPDATE purchase_orders SET status = 'received' WHERE po_number = ?",
                (self.po_number,)
            )
            conn.commit()
            QMessageBox.information(self, "Success", "Goods received and stock updated.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed: {e}")
        finally:
            conn.close()
 
 
class POPaymentDialog(QDialog):
    """Record a payment against a purchase order."""
 
    def __init__(self, db_manager, po_number, balance, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.po_number = po_number
        self.balance = balance
        self.user_data = user_data
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Make Payment — {self.po_number}")
        self.setFixedSize(420, 300)
        layout = QFormLayout(self)
 
        layout.addRow(QLabel(f"<b>PO Number:</b> {self.po_number}"))
        layout.addRow(QLabel(f"<b>Balance Due:</b> KES {self.balance:,.2f}"))
 
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, self.balance)
        self.amount_spin.setValue(self.balance)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("KES ")
        layout.addRow("Payment Amount:", self.amount_spin)
 
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Cash", "Bank Transfer", "Cheque", "M-Pesa", "Other"])
        layout.addRow("Payment Method:", self.method_combo)
 
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Cheque no., transaction ID…")
        layout.addRow("Reference:", self.reference)
 
        self.pay_date = QDateEdit(QDate.currentDate())
        self.pay_date.setCalendarPopup(True)
        layout.addRow("Payment Date:", self.pay_date)
 
        self.notes = QLineEdit()
        layout.addRow("Notes:", self.notes)
 
        btn = QPushButton("💳 Record Payment")
        btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold; padding:8px;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        amount = self.amount_spin.value()
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE purchase_orders SET paid_amount = paid_amount + ?, "
                "status = CASE WHEN (paid_amount + ?) >= total_amount THEN 'paid' ELSE 'partial' END "
                "WHERE po_number = ?",
                (amount, amount, self.po_number)
            )
            cursor.execute("""
                INSERT INTO cashbook (transaction_date, transaction_type, payment_no,
                    description, amount, reference, created_by)
                VALUES (?, 'payment', ?, ?, ?, ?, ?)
            """, (
                self.pay_date.date().toString("yyyy-MM-dd"),
                f"PAY-{self.po_number}",
                f"Payment to supplier for {self.po_number} via {self.method_combo.currentText()}",
                amount,
                self.reference.text(),
                self.user_data['id']
            ))
            conn.commit()
            QMessageBox.information(self, "Success", f"Payment of KES {amount:,.2f} recorded.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed: {e}")
        finally:
            conn.close()
 
 
class PODetailsDialog(QDialog):
    """Read-only view of a purchase order and its line items."""
 
    def __init__(self, db_manager, po_number):
        super().__init__()
        self.db_manager = db_manager
        self.po_number = po_number
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"PO Details — {self.po_number}")
        self.setMinimumSize(700, 500)
        layout = QVBoxLayout(self)
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT po_number, supplier_name, order_type, total_amount, paid_amount, status, order_date, expected_delivery, notes "
            "FROM purchase_orders WHERE po_number = ?", (self.po_number,)
        )
        po = cursor.fetchone()
        cursor.execute(
            "SELECT item_description, quantity, unit_price, total_price, batch_number "
            "FROM purchase_order_items WHERE po_id = (SELECT id FROM purchase_orders WHERE po_number = ?)",
            (self.po_number,)
        )
        items = cursor.fetchall()
        conn.close()
 
        if po:
            info = QTextEdit()
            info.setReadOnly(True)
            info.setMaximumHeight(130)
            info.setHtml(f"""
                <b>PO Number:</b> {po[0]}<br>
                <b>Supplier:</b> {po[1]}  &nbsp;&nbsp; <b>Type:</b> {po[2]}<br>
                <b>Total:</b> KES {po[3]:,.2f} &nbsp;&nbsp;
                <b>Paid:</b> KES {po[4]:,.2f} &nbsp;&nbsp;
                <b>Balance:</b> KES {(po[3]-po[4]):,.2f}<br>
                <b>Status:</b> {po[5].upper()} &nbsp;&nbsp;
                <b>Order Date:</b> {po[6][:10] if po[6] else ''} &nbsp;&nbsp;
                <b>Expected Delivery:</b> {po[7] or 'N/A'}<br>
                <b>Notes:</b> {po[8] or '—'}
            """)
            layout.addWidget(info)
 
        tbl = QTableWidget(len(items), 5)
        tbl.setHorizontalHeaderLabels(["Description", "Qty", "Unit Price", "Total", "Batch #"])
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        for r, it in enumerate(items):
            for c, v in enumerate(it):
                tbl.setItem(r, c, QTableWidgetItem(str(v) if v is not None else ""))
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(tbl)
 
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
 
 
class SupplierPaymentDialog(QDialog):
    """Record a payment to a supplier (not tied to a specific PO)."""
 
    def __init__(self, db_manager, supplier_name, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.supplier_name = supplier_name
        self.user_data = user_data
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Pay Supplier — {self.supplier_name}")
        self.setFixedSize(400, 280)
        layout = QFormLayout(self)
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT outstanding_balance FROM suppliers WHERE name = ?", (self.supplier_name,))
        row = cursor.fetchone()
        conn.close()
        balance = row[0] if row else 0
 
        layout.addRow(QLabel(f"<b>Supplier:</b> {self.supplier_name}"))
        layout.addRow(QLabel(f"<b>Outstanding Balance:</b> KES {balance:,.2f}"))
 
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0.01, 9999999)
        self.amount.setValue(min(balance, 9999999))
        self.amount.setPrefix("KES ")
        layout.addRow("Amount:", self.amount)
 
        self.method = QComboBox()
        self.method.addItems(["Cash", "Bank Transfer", "Cheque", "M-Pesa", "Other"])
        layout.addRow("Method:", self.method)
 
        self.ref = QLineEdit()
        layout.addRow("Reference:", self.ref)
 
        self.pay_date = QDateEdit(QDate.currentDate())
        self.pay_date.setCalendarPopup(True)
        layout.addRow("Date:", self.pay_date)
 
        btn = QPushButton("💳 Record Payment")
        btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        amount = self.amount.value()
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE suppliers SET outstanding_balance = MAX(0, outstanding_balance - ?) WHERE name = ?",
                (amount, self.supplier_name)
            )
            cursor.execute("""
                INSERT INTO cashbook (transaction_date, transaction_type, payment_no,
                    description, amount, reference, created_by)
                VALUES (?, 'payment', ?, ?, ?, ?, ?)
            """, (
                self.pay_date.date().toString("yyyy-MM-dd"),
                f"SUP-{self.supplier_name[:6].upper()}-{datetime.now().strftime('%H%M%S')}",
                f"Payment to {self.supplier_name} via {self.method.currentText()}",
                amount, self.ref.text(), self.user_data['id']
            ))
            conn.commit()
            QMessageBox.information(self, "Success", f"KES {amount:,.2f} payment recorded.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class EnhancedCustomerDialog(QDialog):
    """Add or edit a customer record."""
 
    def __init__(self, db_manager, customer_name=None):
        super().__init__()
        self.db_manager = db_manager
        self.customer_name = customer_name   # None → Add mode
        self.init_ui()
 
    def init_ui(self):
        mode = "Edit Customer" if self.customer_name else "Add Customer"
        self.setWindowTitle(mode)
        self.setFixedSize(430, 380)
        layout = QFormLayout(self)
 
        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QLineEdit()
        self.kra_pin = QLineEdit()
        self.credit_limit = QDoubleSpinBox()
        self.credit_limit.setRange(0, 9999999)
        self.credit_limit.setPrefix("KES ")
 
        layout.addRow("Full Name *:", self.name)
        layout.addRow("Phone:", self.phone)
        layout.addRow("Email:", self.email)
        layout.addRow("Address:", self.address)
        layout.addRow("KRA PIN:", self.kra_pin)
        layout.addRow("Credit Limit:", self.credit_limit)
 
        if self.customer_name:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, phone, email, address, kra_pin, credit_limit FROM customers WHERE name = ?",
                (self.customer_name,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                self.name.setText(row[0])
                self.phone.setText(row[1] or "")
                self.email.setText(row[2] or "")
                self.address.setText(row[3] or "")
                self.kra_pin.setText(row[4] or "")
                self.credit_limit.setValue(row[5] or 0)
 
        btn = QPushButton("💾 Save Customer")
        btn.setStyleSheet("background:#FF69B4; color:white; font-weight:bold; padding:8px;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Required", "Customer name is required.")
            return
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            if self.customer_name:
                cursor.execute("""
                    UPDATE customers SET name=?, phone=?, email=?, address=?, kra_pin=?, credit_limit=?
                    WHERE name=?
                """, (name, self.phone.text(), self.email.text(), self.address.text(),
                      self.kra_pin.text(), self.credit_limit.value(), self.customer_name))
            else:
                cursor.execute("""
                    INSERT INTO customers (name, phone, email, address, kra_pin, credit_limit)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, self.phone.text(), self.email.text(), self.address.text(),
                      self.kra_pin.text(), self.credit_limit.value()))
            conn.commit()
            QMessageBox.information(self, "Saved", "Customer saved successfully.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class EnhancedSupplierDialog(QDialog):
    """Add or edit a supplier record."""
 
    def __init__(self, db_manager, supplier_name=None):
        super().__init__()
        self.db_manager = db_manager
        self.supplier_name = supplier_name
        self.init_ui()
 
    def init_ui(self):
        mode = "Edit Supplier" if self.supplier_name else "Add Supplier"
        self.setWindowTitle(mode)
        self.setFixedSize(430, 360)
        layout = QFormLayout(self)
 
        self.name = QLineEdit()
        self.contact = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QLineEdit()
        self.kra_pin = QLineEdit()
        self.payment_terms = QComboBox()
        self.payment_terms.addItems(["Cash on delivery", "Net 7", "Net 14", "Net 30", "Net 60", "Other"])
 
        layout.addRow("Supplier Name *:", self.name)
        layout.addRow("Contact Person:", self.contact)
        layout.addRow("Phone:", self.phone)
        layout.addRow("Email:", self.email)
        layout.addRow("Address:", self.address)
        layout.addRow("KRA PIN:", self.kra_pin)
        layout.addRow("Payment Terms:", self.payment_terms)
 
        if self.supplier_name:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, contact_person, phone, email, address, kra_pin, payment_terms FROM suppliers WHERE name = ?",
                (self.supplier_name,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                self.name.setText(row[0])
                self.contact.setText(row[1] or "")
                self.phone.setText(row[2] or "")
                self.email.setText(row[3] or "")
                self.address.setText(row[4] or "")
                self.kra_pin.setText(row[5] or "")
                idx = self.payment_terms.findText(row[6] or "")
                if idx >= 0:
                    self.payment_terms.setCurrentIndex(idx)
 
        btn = QPushButton("💾 Save Supplier")
        btn.setStyleSheet("background:#FF69B4; color:white; font-weight:bold; padding:8px;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Required", "Supplier name is required.")
            return
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            if self.supplier_name:
                cursor.execute("""
                    UPDATE suppliers SET name=?, contact_person=?, phone=?, email=?, address=?,
                    kra_pin=?, payment_terms=? WHERE name=?
                """, (name, self.contact.text(), self.phone.text(), self.email.text(),
                      self.address.text(), self.kra_pin.text(), self.payment_terms.currentText(),
                      self.supplier_name))
            else:
                cursor.execute("""
                    INSERT INTO suppliers (name, contact_person, phone, email, address, kra_pin, payment_terms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, self.contact.text(), self.phone.text(), self.email.text(),
                      self.address.text(), self.kra_pin.text(), self.payment_terms.currentText()))
            conn.commit()
            QMessageBox.information(self, "Saved", "Supplier saved successfully.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class SupplierContractsDialog(QDialog):
    """View, add and manage supplier contracts."""
 
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle("Supplier Contracts")
        self.setMinimumSize(800, 500)
        layout = QVBoxLayout(self)
 
        ctrl = QHBoxLayout()
        add_btn = QPushButton("➕ New Contract")
        add_btn.setStyleSheet("background:#FF69B4; color:white; font-weight:bold;")
        add_btn.clicked.connect(self._add_contract)
        ctrl.addWidget(add_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)
 
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(8)
        self.tbl.setHorizontalHeaderLabels([
            "Contract #", "Supplier", "Start", "End", "Amount (KES)", "Status", "Terms", "Document"
        ])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.tbl)
 
        layout.addWidget(QPushButton("Close", clicked=self.accept), alignment=Qt.AlignRight)
        self._load()
 
    def _load(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT contract_number, supplier_name, start_date, end_date, amount, status, terms, document_path "
            "FROM supplier_contracts ORDER BY start_date DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        self.tbl.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                self.tbl.setItem(r, c, QTableWidgetItem(str(v) if v is not None else ""))
 
    def _add_contract(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("New Supplier Contract")
        dlg.setFixedSize(420, 360)
        frm = QFormLayout(dlg)
 
        suppliers_combo = QComboBox()
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM suppliers ORDER BY name")
        for s in cursor.fetchall():
            suppliers_combo.addItem(s[0])
        conn.close()
 
        contract_no = QLineEdit()
        start = QDateEdit(QDate.currentDate())
        start.setCalendarPopup(True)
        end = QDateEdit(QDate.currentDate().addDays(365))
        end.setCalendarPopup(True)
        amount = QDoubleSpinBox()
        amount.setRange(0, 99999999)
        amount.setPrefix("KES ")
        terms = QTextEdit()
        terms.setMaximumHeight(70)
        doc_path = QLineEdit()
        browse = QPushButton("Browse")
        browse.clicked.connect(lambda: doc_path.setText(
            QFileDialog.getOpenFileName(dlg, "Select Document", "", "All Files (*.*)")[0]
        ))
 
        frm.addRow("Supplier:", suppliers_combo)
        frm.addRow("Contract #:", contract_no)
        frm.addRow("Start Date:", start)
        frm.addRow("End Date:", end)
        frm.addRow("Amount:", amount)
        frm.addRow("Terms:", terms)
        hl = QHBoxLayout()
        hl.addWidget(doc_path)
        hl.addWidget(browse)
        frm.addRow("Document:", hl)
 
        save = QPushButton("💾 Save")
        save.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        frm.addRow(save)
 
        def do_save():
            conn2 = self.db_manager.get_connection()
            try:
                cursor2 = conn2.cursor()
                cursor2.execute("""
                    INSERT INTO supplier_contracts
                    (contract_number, supplier_name, start_date, end_date, amount, terms, document_path, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                """, (
                    contract_no.text() or f"CON-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    suppliers_combo.currentText(),
                    start.date().toString("yyyy-MM-dd"),
                    end.date().toString("yyyy-MM-dd"),
                    amount.value(),
                    terms.toPlainText(),
                    doc_path.text()
                ))
                conn2.commit()
                self._load()
                dlg.accept()
            except Exception as e:
                conn2.rollback()
                QMessageBox.critical(dlg, "Error", str(e))
            finally:
                conn2.close()
 
        save.clicked.connect(do_save)
        dlg.exec_()
 
 
class ItemDialog(QDialog):
    """Add or edit an inventory item."""
 
    def __init__(self, db_manager, item_code=None):
        super().__init__()
        self.db_manager = db_manager
        self.item_code = item_code
        self.init_ui()
 
    def init_ui(self):
        mode = "Edit Item" if self.item_code else "Add New Item"
        self.setWindowTitle(mode)
        self.setMinimumSize(480, 520)
        layout = QFormLayout(self)
 
        self.item_code_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.brand_edit = QLineEdit()
        self.desc_edit = QLineEdit()
        self.barcode_edit = QLineEdit()
 
        self.category_combo = QComboBox()
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM categories ORDER BY name")
        self._categories = cursor.fetchall()
        for cat in self._categories:
            self.category_combo.addItem(cat[1], cat[0])
 
        self.cost_price = QDoubleSpinBox()
        self.cost_price.setRange(0, 9999999)
        self.cost_price.setDecimals(2)
        self.cost_price.setPrefix("KES ")
 
        self.selling_price = QDoubleSpinBox()
        self.selling_price.setRange(0, 9999999)
        self.selling_price.setDecimals(2)
        self.selling_price.setPrefix("KES ")
 
        self.stock_qty = QSpinBox()
        self.stock_qty.setRange(0, 999999)
 
        self.reorder_level = QSpinBox()
        self.reorder_level.setRange(0, 99999)
        self.reorder_level.setValue(10)
 
        self.supplier_edit = QLineEdit()
 
        layout.addRow("Item Code *:", self.item_code_edit)
        layout.addRow("Product Name *:", self.name_edit)
        layout.addRow("Brand:", self.brand_edit)
        layout.addRow("Description:", self.desc_edit)
        layout.addRow("Barcode:", self.barcode_edit)
        layout.addRow("Category:", self.category_combo)
        layout.addRow("Cost Price:", self.cost_price)
        layout.addRow("Selling Price:", self.selling_price)
        layout.addRow("Stock Quantity:", self.stock_qty)
        layout.addRow("Reorder Level:", self.reorder_level)
        layout.addRow("Default Supplier:", self.supplier_edit)
 
        if self.item_code:
            self.item_code_edit.setReadOnly(True)
            cursor.execute(
                "SELECT item_code, name, brand, description, barcode, category_id, "
                "cost_price, selling_price, stock_quantity, reorder_level, supplier "
                "FROM items WHERE item_code = ?", (self.item_code,)
            )
            row = cursor.fetchone()
            if row:
                self.item_code_edit.setText(row[0])
                self.name_edit.setText(row[1])
                self.brand_edit.setText(row[2] or "")
                self.desc_edit.setText(row[3] or "")
                self.barcode_edit.setText(row[4] or "")
                idx = self.category_combo.findData(row[5])
                if idx >= 0:
                    self.category_combo.setCurrentIndex(idx)
                self.cost_price.setValue(row[6] or 0)
                self.selling_price.setValue(row[7] or 0)
                self.stock_qty.setValue(row[8] or 0)
                self.reorder_level.setValue(row[9] or 10)
                self.supplier_edit.setText(row[10] or "")
        conn.close()
 
        btn = QPushButton("💾 Save Item")
        btn.setStyleSheet("background:#FF69B4; color:white; font-weight:bold; padding:8px;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        code = self.item_code_edit.text().strip()
        name = self.name_edit.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Required", "Item code and name are required.")
            return
        cat_id = self.category_combo.currentData()
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            if self.item_code:
                cursor.execute("""
                    UPDATE items SET name=?, brand=?, description=?, barcode=?, category_id=?,
                    cost_price=?, selling_price=?, stock_quantity=?, reorder_level=?, supplier=?
                    WHERE item_code=?
                """, (name, self.brand_edit.text(), self.desc_edit.text(),
                      self.barcode_edit.text(), cat_id,
                      self.cost_price.value(), self.selling_price.value(),
                      self.stock_qty.value(), self.reorder_level.value(),
                      self.supplier_edit.text(), self.item_code))
            else:
                cursor.execute("""
                    INSERT INTO items (item_code, name, brand, description, barcode, category_id,
                    cost_price, selling_price, stock_quantity, reorder_level, supplier)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (code, name, self.brand_edit.text(), self.desc_edit.text(),
                      self.barcode_edit.text(), cat_id,
                      self.cost_price.value(), self.selling_price.value(),
                      self.stock_qty.value(), self.reorder_level.value(),
                      self.supplier_edit.text()))
            conn.commit()
            QMessageBox.information(self, "Saved", f"Item '{name}' saved.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class ExpenseDialog(QDialog):
    """Record a business expense."""
 
    def __init__(self, db_manager, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle("Add Expense")
        self.setFixedSize(400, 320)
        layout = QFormLayout(self)
 
        self.category = QComboBox()
        self.category.addItems([
            "Rent", "Utilities", "Salaries", "Transport", "Marketing",
            "Supplies", "Maintenance", "Insurance", "Taxes", "Other"
        ])
        self.category.setEditable(True)
 
        self.description = QLineEdit()
        self.description.setPlaceholderText("Brief description…")
 
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0.01, 9999999)
        self.amount.setDecimals(2)
        self.amount.setPrefix("KES ")
 
        self.method = QComboBox()
        self.method.addItems(["Cash", "Bank Transfer", "M-Pesa", "Cheque", "Other"])
 
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Receipt no., transaction ID…")
 
        self.exp_date = QDateEdit(QDate.currentDate())
        self.exp_date.setCalendarPopup(True)
 
        layout.addRow("Category:", self.category)
        layout.addRow("Description:", self.description)
        layout.addRow("Amount:", self.amount)
        layout.addRow("Payment Method:", self.method)
        layout.addRow("Reference:", self.reference)
        layout.addRow("Date:", self.exp_date)
 
        btn = QPushButton("💾 Save Expense")
        btn.setStyleSheet("background:#FF69B4; color:white; font-weight:bold; padding:8px;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expenses (category, description, amount, payment_method,
                    reference, expense_date, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.category.currentText(),
                self.description.text(),
                self.amount.value(),
                self.method.currentText(),
                self.reference.text(),
                self.exp_date.date().toString("yyyy-MM-dd"),
                self.user_data['id']
            ))
            conn.commit()
            QMessageBox.information(self, "Saved", "Expense recorded.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class KRADocumentDialog(QDialog):
    """Add a KRA tax document (return, payment, certificate, etc.)."""
 
    def __init__(self, db_manager, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle("Add KRA Document")
        self.setFixedSize(440, 400)
        layout = QFormLayout(self)
 
        self.doc_type = QComboBox()
        self.doc_type.addItems([
            "VAT Return", "Income Tax Return", "PAYE Return",
            "Withholding Tax", "Tax Compliance Certificate",
            "Penalty Notice", "Assessment Notice", "Other"
        ])
 
        self.doc_number = QLineEdit()
        self.doc_number.setPlaceholderText("e.g. VAT2025-01")
 
        self.tax_period = QLineEdit()
        self.tax_period.setPlaceholderText("e.g. Jan 2025 or Q1 2025")
 
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 99999999)
        self.amount.setDecimals(2)
        self.amount.setPrefix("KES ")
 
        self.issue_date = QDateEdit(QDate.currentDate())
        self.issue_date.setCalendarPopup(True)
 
        self.due_date = QDateEdit(QDate.currentDate().addDays(30))
        self.due_date.setCalendarPopup(True)
 
        self.status_combo = QComboBox()
        self.status_combo.addItems(["pending", "filed", "paid", "overdue"])
 
        self.doc_path = QLineEdit()
        self.doc_path.setPlaceholderText("Optional: path to scanned document")
        browse = QPushButton("📁 Browse")
        browse.clicked.connect(lambda: self.doc_path.setText(
            QFileDialog.getOpenFileName(self, "Select Document", "", "All Files (*.*)")[0]
        ))
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.doc_path)
        path_layout.addWidget(browse)
 
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
 
        layout.addRow("Document Type:", self.doc_type)
        layout.addRow("Document #:", self.doc_number)
        layout.addRow("Tax Period:", self.tax_period)
        layout.addRow("Amount:", self.amount)
        layout.addRow("Issue Date:", self.issue_date)
        layout.addRow("Due Date:", self.due_date)
        layout.addRow("Status:", self.status_combo)
        layout.addRow("Document File:", path_layout)
        layout.addRow("Notes:", self.notes)
 
        btn = QPushButton("💾 Save Document")
        btn.setStyleSheet("background:#FF69B4; color:white; font-weight:bold; padding:8px;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO kra_documents
                (document_number, document_type, tax_period, amount, issue_date, due_date, status, document_path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.doc_number.text() or f"KRA-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                self.doc_type.currentText(),
                self.tax_period.text(),
                self.amount.value(),
                self.issue_date.date().toString("yyyy-MM-dd"),
                self.due_date.date().toString("yyyy-MM-dd"),
                self.status_combo.currentText(),
                self.doc_path.text(),
                self.notes.toPlainText()
            ))
            conn.commit()
            QMessageBox.information(self, "Saved", "KRA document saved.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class EnhancedUserDialog(QDialog):
    """Add or edit a system user with role and module permissions."""
 
    MODULES = ['inventory', 'sales', 'purchases', 'customers', 'suppliers',
               'reports', 'accounting', 'users', 'settings', 'dashboard']
    ACTIONS = ['view', 'add', 'edit', 'delete']
 
    def __init__(self, db_manager, username=None):
        super().__init__()
        self.db_manager = db_manager
        self.username = username
        self.init_ui()
 
    def init_ui(self):
        mode = "Edit User" if self.username else "Add User"
        self.setWindowTitle(mode)
        self.setMinimumSize(600, 580)
        main = QVBoxLayout(self)
 
        # ── Credentials ───────────────────────────────────────────────────────
        cred = QGroupBox("Credentials")
        frm = QFormLayout(cred)
 
        self.username_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.role_combo = QComboBox()
        self.role_combo.addItems(["admin", "manager", "salesperson", "cashier", "viewer"])
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Leave blank to keep existing password" if self.username else "Required")
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.Password)
 
        frm.addRow("Username *:", self.username_edit)
        frm.addRow("Email:", self.email_edit)
        frm.addRow("Role:", self.role_combo)
        frm.addRow("Password:", self.password_edit)
        frm.addRow("Confirm Password:", self.confirm_edit)
        main.addWidget(cred)
 
        # ── Permissions grid ──────────────────────────────────────────────────
        perm_group = QGroupBox("Module Permissions")
        perm_layout = QVBoxLayout(perm_group)
 
        # Header row
        header = QHBoxLayout()
        header.addWidget(QLabel("Module"), 2)
        for a in self.ACTIONS:
            lbl = QLabel(a.capitalize())
            lbl.setAlignment(Qt.AlignCenter)
            header.addWidget(lbl, 1)
        perm_layout.addLayout(header)
 
        self._perm_checks = {}
        for mod in self.MODULES:
            row = QHBoxLayout()
            row.addWidget(QLabel(mod.capitalize()), 2)
            self._perm_checks[mod] = {}
            for act in self.ACTIONS:
                cb = QCheckBox()
                cb.setEnabled(not (mod == 'dashboard' and act != 'view'))
                row.addWidget(cb, 1, alignment=Qt.AlignCenter)
                self._perm_checks[mod][act] = cb
            perm_layout.addLayout(row)
 
        # Quick-set buttons
        ql = QHBoxLayout()
        all_btn = QPushButton("✅ Grant All")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn = QPushButton("❌ Revoke All")
        none_btn.clicked.connect(lambda: self._set_all(False))
        ql.addWidget(all_btn)
        ql.addWidget(none_btn)
        ql.addStretch()
        perm_layout.addLayout(ql)
 
        main.addWidget(perm_group)
 
        # Load existing user data
        if self.username:
            self.username_edit.setReadOnly(True)
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username, email, role, permissions FROM users WHERE username = ?",
                           (self.username,))
            row = cursor.fetchone()
            conn.close()
            if row:
                self.username_edit.setText(row[0])
                self.email_edit.setText(row[1] or "")
                idx = self.role_combo.findText(row[2])
                if idx >= 0:
                    self.role_combo.setCurrentIndex(idx)
                perms = json.loads(row[3]) if row[3] else {}
                for mod, actions in perms.items():
                    if mod in self._perm_checks:
                        for act in actions:
                            if act in self._perm_checks[mod]:
                                self._perm_checks[mod][act].setChecked(True)
        else:
            # Default: view-only on all modules
            for mod in self.MODULES:
                self._perm_checks[mod]['view'].setChecked(True)
 
        # Save button
        btn = QPushButton("💾 Save User")
        btn.setStyleSheet("background:#FF69B4; color:white; font-weight:bold; padding:10px;")
        btn.clicked.connect(self._save)
        main.addWidget(btn)
 
    def _set_all(self, state):
        for mod in self._perm_checks.values():
            for cb in mod.values():
                if cb.isEnabled():
                    cb.setChecked(state)
 
    def _save(self):
        uname = self.username_edit.text().strip()
        if not uname:
            QMessageBox.warning(self, "Required", "Username is required.")
            return
        pwd = self.password_edit.text()
        cpwd = self.confirm_edit.text()
        if not self.username and not pwd:
            QMessageBox.warning(self, "Required", "Password is required for new users.")
            return
        if pwd and pwd != cpwd:
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
 
        perms = {}
        for mod in self.MODULES:
            acts = [a for a in self.ACTIONS if self._perm_checks[mod][a].isChecked()]
            if acts:
                perms[mod] = acts
 
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            if self.username:
                if pwd:
                    pwd_hash = hashlib.pbkdf2_hmac("sha256", pwd.encode(), b"glamour_static_salt", 260000).hex()
                    cursor.execute(
                        "UPDATE users SET email=?, role=?, permissions=?, password_hash=? WHERE username=?",
                        (self.email_edit.text(), self.role_combo.currentText(),
                         json.dumps(perms), pwd_hash, self.username)
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET email=?, role=?, permissions=? WHERE username=?",
                        (self.email_edit.text(), self.role_combo.currentText(),
                         json.dumps(perms), self.username)
                    )
            else:
                pwd_hash = hashlib.pbkdf2_hmac("sha256", pwd.encode(), b"glamour_static_salt", 260000).hex()
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, permissions, email)
                    VALUES (?, ?, ?, ?, ?)
                """, (uname, pwd_hash, self.role_combo.currentText(),
                      json.dumps(perms), self.email_edit.text()))
            conn.commit()
            QMessageBox.information(self, "Saved", f"User '{uname}' saved.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class JournalEntryDialog(QDialog):
    """Create a double-entry journal entry."""
 
    def __init__(self, db_manager, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.user_data = user_data
        self._lines = []
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle("New Journal Entry")
        self.setMinimumSize(750, 550)
        layout = QVBoxLayout(self)
 
        hdr = QFormLayout()
        self.description = QLineEdit()
        self.description.setPlaceholderText("e.g. Monthly rent payment")
        self.reference = QLineEdit()
        self.entry_date = QDateEdit(QDate.currentDate())
        self.entry_date.setCalendarPopup(True)
        hdr.addRow("Description:", self.description)
        hdr.addRow("Reference:", self.reference)
        hdr.addRow("Entry Date:", self.entry_date)
        layout.addLayout(hdr)
 
        layout.addWidget(QLabel("Journal Lines (must balance — total debits = total credits):"))
 
        # Lines table
        self.lines_tbl = QTableWidget(0, 4)
        self.lines_tbl.setHorizontalHeaderLabels(["Account", "Description", "Debit (KES)", "Credit (KES)"])
        self.lines_tbl.horizontalHeader().setStretchLastSection(True)
        self.lines_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.lines_tbl)
 
        # Totals
        self.totals_lbl = QLabel("Debits: KES 0.00   |   Credits: KES 0.00   |   ⚠️ Not balanced")
        self.totals_lbl.setStyleSheet("font-weight:bold; padding:4px;")
        layout.addWidget(self.totals_lbl)
 
        # Add line button
        add_line_btn = QPushButton("➕ Add Line")
        add_line_btn.clicked.connect(self._add_line)
        layout.addWidget(add_line_btn, alignment=Qt.AlignLeft)
 
        # Load accounts
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, account_code, account_name FROM chart_of_accounts WHERE is_active=1 ORDER BY account_code")
        self._accounts = cursor.fetchall()
        conn.close()
 
        # Add 2 blank lines to start
        self._add_line()
        self._add_line()
 
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Journal Entry")
        save_btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold; padding:8px 20px;")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(QPushButton("Cancel", clicked=self.reject))
        layout.addLayout(btn_row)
 
    def _add_line(self):
        row = self.lines_tbl.rowCount()
        self.lines_tbl.insertRow(row)
 
        acct_combo = QComboBox()
        acct_combo.addItem("— Select account —", None)
        for acct in self._accounts:
            acct_combo.addItem(f"{acct[1]}  {acct[2]}", acct[0])
        self.lines_tbl.setCellWidget(row, 0, acct_combo)
 
        self.lines_tbl.setItem(row, 1, QTableWidgetItem(""))
 
        debit = QDoubleSpinBox()
        debit.setRange(0, 99999999)
        debit.setDecimals(2)
        debit.valueChanged.connect(self._update_totals)
        self.lines_tbl.setCellWidget(row, 2, debit)
 
        credit = QDoubleSpinBox()
        credit.setRange(0, 99999999)
        credit.setDecimals(2)
        credit.valueChanged.connect(self._update_totals)
        self.lines_tbl.setCellWidget(row, 3, credit)
 
    def _update_totals(self):
        total_debit = sum(
            self.lines_tbl.cellWidget(r, 2).value()
            for r in range(self.lines_tbl.rowCount())
            if self.lines_tbl.cellWidget(r, 2)
        )
        total_credit = sum(
            self.lines_tbl.cellWidget(r, 3).value()
            for r in range(self.lines_tbl.rowCount())
            if self.lines_tbl.cellWidget(r, 3)
        )
        balanced = abs(total_debit - total_credit) < 0.01 and total_debit > 0
        status = "✅ Balanced" if balanced else "⚠️ Not balanced"
        color = "green" if balanced else "red"
        self.totals_lbl.setText(
            f"Debits: KES {total_debit:,.2f}   |   Credits: KES {total_credit:,.2f}   |   "
            f"<span style='color:{color}'>{status}</span>"
        )
 
    def _save(self):
        # Validate balance
        total_debit = sum(
            self.lines_tbl.cellWidget(r, 2).value()
            for r in range(self.lines_tbl.rowCount())
            if self.lines_tbl.cellWidget(r, 2)
        )
        total_credit = sum(
            self.lines_tbl.cellWidget(r, 3).value()
            for r in range(self.lines_tbl.rowCount())
            if self.lines_tbl.cellWidget(r, 3)
        )
        if abs(total_debit - total_credit) >= 0.01 or total_debit == 0:
            QMessageBox.warning(self, "Not Balanced",
                                "Journal entry must be balanced (total debits = total credits) and non-zero.")
            return
 
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM journal_entries")
            count = cursor.fetchone()[0] + 1
            jnum = f"JNL{datetime.now().strftime('%Y%m%d')}{count:04d}"
 
            cursor.execute("""
                INSERT INTO journal_entries (journal_number, entry_date, description, reference, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (jnum, self.entry_date.date().toString("yyyy-MM-dd"),
                  self.description.text(), self.reference.text(), self.user_data['id']))
            jid = cursor.lastrowid
 
            for r in range(self.lines_tbl.rowCount()):
                acct_combo = self.lines_tbl.cellWidget(r, 0)
                acct_id = acct_combo.currentData() if acct_combo else None
                if not acct_id:
                    continue
                desc_item = self.lines_tbl.item(r, 1)
                line_desc = desc_item.text() if desc_item else ""
                debit = self.lines_tbl.cellWidget(r, 2).value()
                credit = self.lines_tbl.cellWidget(r, 3).value()
                if debit == 0 and credit == 0:
                    continue
                cursor.execute("""
                    INSERT INTO journal_entry_lines (journal_id, account_id, debit_amount, credit_amount, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (jid, acct_id, debit, credit, line_desc))
 
            conn.commit()
            QMessageBox.information(self, "Saved", f"Journal Entry {jnum} saved.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class JournalEntryViewDialog(QDialog):
    """Read-only view of a posted journal entry."""
 
    def __init__(self, db_manager, journal_number):
        super().__init__()
        self.db_manager = db_manager
        self.journal_number = journal_number
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Journal Entry — {self.journal_number}")
        self.setMinimumSize(650, 400)
        layout = QVBoxLayout(self)
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT journal_number, entry_date, description, reference, is_posted FROM journal_entries WHERE journal_number = ?",
            (self.journal_number,)
        )
        je = cursor.fetchone()
        cursor.execute("""
            SELECT ca.account_code, ca.account_name, jl.description, jl.debit_amount, jl.credit_amount
            FROM journal_entry_lines jl
            JOIN chart_of_accounts ca ON jl.account_id = ca.id
            JOIN journal_entries je ON jl.journal_id = je.id
            WHERE je.journal_number = ?
        """, (self.journal_number,))
        lines = cursor.fetchall()
        conn.close()
 
        if je:
            info = QLabel(
                f"<b>{je[0]}</b>  |  Date: {je[1]}  |  Ref: {je[3] or '—'}  |  "
                f"Status: {'Posted ✅' if je[4] else 'Draft'}<br>{je[2] or ''}"
            )
            info.setStyleSheet("padding:6px; background:#f5f5f5;")
            layout.addWidget(info)
 
        tbl = QTableWidget(len(lines), 5)
        tbl.setHorizontalHeaderLabels(["Code", "Account", "Description", "Debit", "Credit"])
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        total_d = total_c = 0
        for r, line in enumerate(lines):
            for c, v in enumerate(line):
                tbl.setItem(r, c, QTableWidgetItem(
                    f"KES {v:,.2f}" if c in (3, 4) else str(v or "")
                ))
            total_d += line[3]
            total_c += line[4]
        layout.addWidget(tbl)
        layout.addWidget(QLabel(f"<b>Totals — Debit: KES {total_d:,.2f}   Credit: KES {total_c:,.2f}</b>"))
        layout.addWidget(QPushButton("Close", clicked=self.accept), alignment=Qt.AlignRight)
 
 
class TrialBalanceDialog(QDialog):
    """Generate and display a trial balance for a date range."""
 
    def __init__(self, db_manager, from_date, to_date):
        super().__init__()
        self.db_manager = db_manager
        self.from_date = from_date
        self.to_date = to_date
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Trial Balance  {self.from_date} to {self.to_date}")
        self.setMinimumSize(700, 500)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Trial Balance  |  {self.from_date} — {self.to_date}</b>"))
 
        tbl = QTableWidget()
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["Account Code", "Account Name", "Debit (KES)", "Credit (KES)"])
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ca.account_code, ca.account_name,
                   COALESCE(SUM(jl.debit_amount),0)  AS total_debit,
                   COALESCE(SUM(jl.credit_amount),0) AS total_credit
            FROM chart_of_accounts ca
            LEFT JOIN journal_entry_lines jl ON jl.account_id = ca.id
            LEFT JOIN journal_entries je ON jl.journal_id = je.id
                AND je.entry_date BETWEEN ? AND ? AND je.is_posted = 1
            GROUP BY ca.id
            ORDER BY ca.account_code
        """, (self.from_date, self.to_date))
        rows = cursor.fetchall()
        conn.close()
 
        tbl.setRowCount(len(rows))
        total_d = total_c = 0
        for r, row in enumerate(rows):
            tbl.setItem(r, 0, QTableWidgetItem(row[0]))
            tbl.setItem(r, 1, QTableWidgetItem(row[1]))
            tbl.setItem(r, 2, QTableWidgetItem(f"{row[2]:,.2f}" if row[2] else ""))
            tbl.setItem(r, 3, QTableWidgetItem(f"{row[3]:,.2f}" if row[3] else ""))
            total_d += row[2]
            total_c += row[3]
        layout.addWidget(tbl)
 
        balanced = abs(total_d - total_c) < 0.01
        color = "green" if balanced else "red"
        layout.addWidget(QLabel(
            f"<span style='color:{color}; font-weight:bold;'>"
            f"Total Debits: KES {total_d:,.2f}   |   Total Credits: KES {total_c:,.2f}   |   "
            f"{'✅ Balanced' if balanced else '⚠️ OUT OF BALANCE'}</span>"
        ))
        layout.addWidget(QPushButton("Close", clicked=self.accept), alignment=Qt.AlignRight)
 
 
class ProfitLossDialog(QDialog):
    """Profit & Loss statement derived from journal entries + sales + expenses."""
 
    def __init__(self, db_manager, from_date, to_date):
        super().__init__()
        self.db_manager = db_manager
        self.from_date = from_date
        self.to_date = to_date
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Profit & Loss  {self.from_date} to {self.to_date}")
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"<b style='font-size:16px;'>Profit & Loss Statement</b><br>"
            f"Period: {self.from_date} — {self.to_date}"
        ))
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
 
        # Revenue from sales
        cursor.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM sales WHERE created_at BETWEEN ? AND ? AND payment_status != 'void'",
            (self.from_date, self.to_date)
        )
        revenue = cursor.fetchone()[0]
 
        # Cost of goods sold (cost_price × qty from sale_items)
        cursor.execute("""
            SELECT COALESCE(SUM(si.quantity * i.cost_price), 0)
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.created_at BETWEEN ? AND ? AND s.payment_status != 'void'
        """, (self.from_date, self.to_date))
        cogs = cursor.fetchone()[0]
 
        # Expenses by category
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount),0)
            FROM expenses WHERE expense_date BETWEEN ? AND ?
            GROUP BY category ORDER BY category
        """, (self.from_date, self.to_date))
        exp_rows = cursor.fetchall()
        total_expenses = sum(r[1] for r in exp_rows)
        conn.close()
 
        gross_profit = revenue - cogs
        net_profit = gross_profit - total_expenses
 
        report = QTextEdit()
        report.setReadOnly(True)
        html = f"""
        <style>
            table {{ width:100%; border-collapse:collapse; font-size:13px; }}
            td, th {{ padding:5px 10px; }}
            .section {{ background:#f0f0f0; font-weight:bold; font-size:14px; }}
            .indent {{ padding-left:30px; }}
            .total {{ font-weight:bold; border-top:2px solid #333; }}
            .positive {{ color:green; }}
            .negative {{ color:red; }}
        </style>
        <table>
        <tr class='section'><td colspan=2>REVENUE</td></tr>
        <tr><td class='indent'>Sales Revenue</td><td align='right'>KES {revenue:,.2f}</td></tr>
        <tr class='total'><td>TOTAL REVENUE</td><td align='right'>KES {revenue:,.2f}</td></tr>
 
        <tr><td colspan=2>&nbsp;</td></tr>
        <tr class='section'><td colspan=2>COST OF GOODS SOLD</td></tr>
        <tr><td class='indent'>Direct Cost of Sales</td><td align='right'>KES {cogs:,.2f}</td></tr>
        <tr class='total'><td>GROSS PROFIT</td>
            <td align='right' class='{"positive" if gross_profit>=0 else "negative"}'>KES {gross_profit:,.2f}</td></tr>
 
        <tr><td colspan=2>&nbsp;</td></tr>
        <tr class='section'><td colspan=2>OPERATING EXPENSES</td></tr>
        """
        for cat, amt in exp_rows:
            html += f"<tr><td class='indent'>{cat}</td><td align='right'>KES {amt:,.2f}</td></tr>"
        pn_class = "positive" if net_profit >= 0 else "negative"
        html += f"""
        <tr class='total'><td>TOTAL EXPENSES</td><td align='right'>KES {total_expenses:,.2f}</td></tr>
        <tr><td colspan=2>&nbsp;</td></tr>
        <tr class='total' style='font-size:15px;'>
            <td>NET {'PROFIT' if net_profit>=0 else 'LOSS'}</td>
            <td align='right' class='{pn_class}'>KES {abs(net_profit):,.2f}</td>
        </tr>
        </table>
        """
        report.setHtml(html)
        layout.addWidget(report)
        layout.addWidget(QPushButton("Close", clicked=self.accept), alignment=Qt.AlignRight)
 
 
class BalanceSheetDialog(QDialog):
    """Simple balance sheet as at a given date."""
 
    def __init__(self, db_manager, as_at_date):
        super().__init__()
        self.db_manager = db_manager
        self.as_at_date = as_at_date
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Balance Sheet as at {self.as_at_date}")
        self.setMinimumSize(600, 550)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b style='font-size:16px;'>Balance Sheet</b><br>As at {self.as_at_date}"))
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
 
        def acct_balance(acct_type):
            cursor.execute("""
                SELECT ca.account_name,
                       COALESCE(SUM(jl.debit_amount) - SUM(jl.credit_amount), 0) AS balance
                FROM chart_of_accounts ca
                LEFT JOIN journal_entry_lines jl ON jl.account_id = ca.id
                LEFT JOIN journal_entries je ON jl.journal_id = je.id
                    AND je.entry_date <= ? AND je.is_posted = 1
                WHERE ca.account_type = ?
                GROUP BY ca.id
                ORDER BY ca.account_code
            """, (self.as_at_date, acct_type))
            return cursor.fetchall()
 
        assets = acct_balance('Asset')
        liabilities = acct_balance('Liability')
        equity = acct_balance('Equity')
 
        # Add inventory value
        cursor.execute("SELECT COALESCE(SUM(cost_price * stock_quantity),0) FROM items")
        inv_value = cursor.fetchone()[0]
 
        # Add outstanding receivables
        cursor.execute("SELECT COALESCE(SUM(outstanding_balance),0) FROM customers")
        receivables = cursor.fetchone()[0]
 
        # Add outstanding payables
        cursor.execute("SELECT COALESCE(SUM(outstanding_balance),0) FROM suppliers")
        payables = cursor.fetchone()[0]
 
        conn.close()
 
        total_assets = sum(r[1] for r in assets) + inv_value + receivables
        total_liabilities = sum(abs(r[1]) for r in liabilities) + payables
        total_equity = total_assets - total_liabilities
 
        report = QTextEdit()
        report.setReadOnly(True)
 
        def section(title, rows, extra_rows=None):
            html = f"<tr class='section'><td colspan=2>{title}</td></tr>"
            total = 0
            for name, bal in rows:
                if abs(bal) > 0.01:
                    html += f"<tr><td class='indent'>{name}</td><td align='right'>KES {abs(bal):,.2f}</td></tr>"
                    total += abs(bal)
            if extra_rows:
                for name, val in extra_rows:
                    html += f"<tr><td class='indent'>{name}</td><td align='right'>KES {val:,.2f}</td></tr>"
                    total += val
            html += f"<tr class='total'><td>Total {title}</td><td align='right'>KES {total:,.2f}</td></tr>"
            return html, total
 
        html = """<style>
            table { width:100%; border-collapse:collapse; font-size:13px; }
            td { padding:4px 10px; }
            .section { background:#e8f4f8; font-weight:bold; font-size:14px; }
            .indent { padding-left:30px; }
            .total { font-weight:bold; border-top:1px solid #aaa; }
        </style><table>"""
 
        asset_html, _ = section("ASSETS", assets, [("Inventory (at cost)", inv_value), ("Accounts Receivable", receivables)])
        liab_html, _ = section("LIABILITIES", liabilities, [("Accounts Payable (Suppliers)", payables)])
        eq_html = (
            f"<tr class='section'><td colspan=2>EQUITY</td></tr>"
            f"<tr><td class='indent'>Net Equity</td><td align='right'>KES {total_equity:,.2f}</td></tr>"
            f"<tr class='total'><td>Total Equity</td><td align='right'>KES {total_equity:,.2f}</td></tr>"
        )
        html += asset_html + "<tr><td colspan=2>&nbsp;</td></tr>" + liab_html + "<tr><td colspan=2>&nbsp;</td></tr>" + eq_html
        html += f"""<tr><td colspan=2>&nbsp;</td></tr>
        <tr style='background:#fffde7; font-weight:bold; font-size:14px;'>
            <td>TOTAL LIABILITIES + EQUITY</td>
            <td align='right'>KES {(total_liabilities + total_equity):,.2f}</td>
        </tr></table>"""
 
        report.setHtml(html)
        layout.addWidget(report)
        layout.addWidget(QPushButton("Close", clicked=self.accept), alignment=Qt.AlignRight)
 
 
class CashFlowDialog(QDialog):
    """Cash flow statement from cashbook entries."""
 
    def __init__(self, db_manager, from_date, to_date):
        super().__init__()
        self.db_manager = db_manager
        self.from_date = from_date
        self.to_date = to_date
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Cash Flow  {self.from_date} to {self.to_date}")
        self.setMinimumSize(650, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"<b style='font-size:16px;'>Cash Flow Statement</b><br>Period: {self.from_date} — {self.to_date}"
        ))
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
 
        # Cash inflows: sales
        cursor.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM sales WHERE created_at BETWEEN ? AND ? AND payment_status='paid'",
            (self.from_date, self.to_date)
        )
        sales_cash = cursor.fetchone()[0]
 
        # Cash outflows: PO payments
        cursor.execute(
            "SELECT COALESCE(SUM(amount),0) FROM cashbook WHERE transaction_type='payment' AND transaction_date BETWEEN ? AND ?",
            (self.from_date, self.to_date)
        )
        payments_out = cursor.fetchone()[0]
 
        # Cash outflows: expenses
        cursor.execute(
            "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date BETWEEN ? AND ?",
            (self.from_date, self.to_date)
        )
        expenses_out = cursor.fetchone()[0]
 
        # Cashbook detail
        cursor.execute("""
            SELECT transaction_date, transaction_type, description, amount, reference
            FROM cashbook WHERE transaction_date BETWEEN ? AND ?
            ORDER BY transaction_date DESC
        """, (self.from_date, self.to_date))
        cb_rows = cursor.fetchall()
        conn.close()
 
        net_cash = sales_cash - payments_out - expenses_out
 
        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setMaximumHeight(160)
        pn = "positive" if net_cash >= 0 else "negative"
        summary.setHtml(f"""
        <style>td{{padding:4px 12px;}} .pos{{color:green;font-weight:bold;}} .neg{{color:red;font-weight:bold;}}</style>
        <table>
        <tr><td><b>Cash from Sales</b></td><td align='right' class='pos'>+ KES {sales_cash:,.2f}</td></tr>
        <tr><td><b>Payments to Suppliers</b></td><td align='right' class='neg'>- KES {payments_out:,.2f}</td></tr>
        <tr><td><b>Business Expenses</b></td><td align='right' class='neg'>- KES {expenses_out:,.2f}</td></tr>
        <tr style='border-top:2px solid #333;'><td><b>NET CASH {'IN' if net_cash>=0 else 'OUT'}</b></td>
            <td align='right' class='{pn}'>KES {abs(net_cash):,.2f}</td></tr>
        </table>
        """)
        layout.addWidget(summary)
 
        layout.addWidget(QLabel("<b>Cashbook Transactions:</b>"))
        tbl = QTableWidget(len(cb_rows), 5)
        tbl.setHorizontalHeaderLabels(["Date", "Type", "Description", "Amount", "Reference"])
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        for r, row in enumerate(cb_rows):
            for c, v in enumerate(row):
                tbl.setItem(r, c, QTableWidgetItem(str(v) if v is not None else ""))
        layout.addWidget(tbl)
        layout.addWidget(QPushButton("Close", clicked=self.accept), alignment=Qt.AlignRight)
 
 
class BankReconciliationDialog(QDialog):
    """Reconcile bank transactions against statement."""
 
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle("Bank Reconciliation")
        self.setMinimumSize(850, 580)
        layout = QVBoxLayout(self)
 
        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Bank Account:"))
        self.acct_combo = QComboBox()
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, account_name, account_number FROM bank_accounts WHERE is_active=1")
        self._bank_accounts = cursor.fetchall()
        conn.close()
        for ba in self._bank_accounts:
            self.acct_combo.addItem(f"{ba[1]}  ({ba[2]})", ba[0])
        ctrl.addWidget(self.acct_combo)
 
        ctrl.addWidget(QLabel("Statement Balance (KES):"))
        self.stmt_balance = QDoubleSpinBox()
        self.stmt_balance.setRange(-9999999, 9999999)
        self.stmt_balance.setDecimals(2)
        ctrl.addWidget(self.stmt_balance)
 
        load_btn = QPushButton("🔍 Load Transactions")
        load_btn.clicked.connect(self._load)
        ctrl.addWidget(load_btn)
        layout.addLayout(ctrl)
 
        self.summary_lbl = QLabel("")
        self.summary_lbl.setStyleSheet("font-weight:bold; padding:6px; background:#f0f8ff;")
        layout.addWidget(self.summary_lbl)
 
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(["Date", "Type", "Description", "Amount", "Reference", "✅ Reconciled"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setAlternatingRowColors(True)
        layout.addWidget(self.tbl)
 
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Reconciliation")
        save_btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(QPushButton("Close", clicked=self.accept))
        layout.addLayout(btn_row)
 
        if self._bank_accounts:
            self._load()
 
    def _load(self):
        acct_id = self.acct_combo.currentData()
        if not acct_id:
            return
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, transaction_date, transaction_type, description, amount, reference, reconciled
            FROM bank_transactions WHERE bank_account_id = ? ORDER BY transaction_date DESC
        """, (acct_id,))
        rows = cursor.fetchall()
        cursor.execute("SELECT current_balance FROM bank_accounts WHERE id = ?", (acct_id,))
        bal_row = cursor.fetchone()
        conn.close()
 
        book_balance = bal_row[0] if bal_row else 0
        self.tbl.setRowCount(len(rows))
        self._row_ids = []
        for r, row in enumerate(rows):
            self._row_ids.append(row[0])
            for c, v in enumerate(row[1:6]):
                self.tbl.setItem(r, c, QTableWidgetItem(str(v) if v is not None else ""))
            cb = QCheckBox()
            cb.setChecked(bool(row[6]))
            self.tbl.setCellWidget(r, 5, cb)
 
        self.summary_lbl.setText(
            f"Book Balance: KES {book_balance:,.2f}   |   "
            f"Statement Balance: KES {self.stmt_balance.value():,.2f}   |   "
            f"Difference: KES {(self.stmt_balance.value() - book_balance):,.2f}"
        )
 
    def _save(self):
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            for r, txn_id in enumerate(self._row_ids):
                cb = self.tbl.cellWidget(r, 5)
                reconciled = 1 if (cb and cb.isChecked()) else 0
                cursor.execute(
                    "UPDATE bank_transactions SET reconciled = ?, reconciliation_date = ? WHERE id = ?",
                    (reconciled, datetime.now().strftime("%Y-%m-%d") if reconciled else None, txn_id)
                )
            conn.commit()
            QMessageBox.information(self, "Saved", "Reconciliation saved.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class EditSaleDialog(QDialog):
    """Edit a non-voided sale's customer info, payment method and status."""
 
    def __init__(self, db_manager, invoice_number, user_data):
        super().__init__()
        self.db_manager = db_manager
        self.invoice_number = invoice_number
        self.user_data = user_data
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Edit Sale — {self.invoice_number}")
        self.setFixedSize(430, 340)
        layout = QFormLayout(self)
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT customer_name, customer_phone, customer_address, customer_kra_pin, payment_method, payment_status "
            "FROM sales WHERE invoice_number = ?", (self.invoice_number,)
        )
        row = cursor.fetchone()
        conn.close()
 
        self.cust_name = QLineEdit(row[0] or "" if row else "")
        self.cust_phone = QLineEdit(row[1] or "" if row else "")
        self.cust_address = QLineEdit(row[2] or "" if row else "")
        self.cust_kra = QLineEdit(row[3] or "" if row else "")
 
        self.pay_method = QComboBox()
        self.pay_method.addItems(["Cash", "M-Pesa", "Bank Transfer", "Credit", "Cheque"])
        if row and row[4]:
            idx = self.pay_method.findText(row[4])
            if idx >= 0:
                self.pay_method.setCurrentIndex(idx)
 
        self.pay_status = QComboBox()
        self.pay_status.addItems(["paid", "pending", "partial", "credit"])
        if row and row[5]:
            idx = self.pay_status.findText(row[5])
            if idx >= 0:
                self.pay_status.setCurrentIndex(idx)
 
        layout.addRow("Customer Name:", self.cust_name)
        layout.addRow("Customer Phone:", self.cust_phone)
        layout.addRow("Customer Address:", self.cust_address)
        layout.addRow("Customer KRA PIN:", self.cust_kra)
        layout.addRow("Payment Method:", self.pay_method)
        layout.addRow("Payment Status:", self.pay_status)
 
        btn = QPushButton("💾 Save Changes")
        btn.setStyleSheet("background:#FF8C00; color:white; font-weight:bold; padding:8px;")
        btn.clicked.connect(self._save)
        layout.addRow(btn)
 
    def _save(self):
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sales SET customer_name=?, customer_phone=?, customer_address=?,
                customer_kra_pin=?, payment_method=?, payment_status=?
                WHERE invoice_number=?
            """, (
                self.cust_name.text(), self.cust_phone.text(),
                self.cust_address.text(), self.cust_kra.text(),
                self.pay_method.currentText(), self.pay_status.currentText(),
                self.invoice_number
            ))
            conn.commit()
            QMessageBox.information(self, "Saved", "Sale updated.")
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
 
 
class SaleDetailsDialog(QDialog):
    """Read-only detail view for a sale including line items."""
 
    def __init__(self, db_manager, invoice_number):
        super().__init__()
        self.db_manager = db_manager
        self.invoice_number = invoice_number
        self.init_ui()
 
    def init_ui(self):
        self.setWindowTitle(f"Sale Details — {self.invoice_number}")
        self.setMinimumSize(680, 500)
        layout = QVBoxLayout(self)
 
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.invoice_number, s.sale_type, s.customer_name, s.customer_phone,
                   s.customer_kra_pin, s.subtotal, s.vat_amount, s.total_amount,
                   s.payment_status, s.payment_method, s.created_at, u.username
            FROM sales s LEFT JOIN users u ON s.user_id = u.id
            WHERE s.invoice_number = ?
        """, (self.invoice_number,))
        sale = cursor.fetchone()
        cursor.execute("""
            SELECT i.name, si.quantity, si.unit_price, si.total_price
            FROM sale_items si JOIN items i ON si.item_id = i.id
            WHERE si.sale_id = (SELECT id FROM sales WHERE invoice_number = ?)
        """, (self.invoice_number,))
        items = cursor.fetchall()
        conn.close()
 
        if sale:
            info = QTextEdit()
            info.setReadOnly(True)
            info.setMaximumHeight(130)
            info.setHtml(f"""
                <b>Invoice:</b> {sale[0]}  &nbsp; <b>Type:</b> {sale[1].upper()}
                &nbsp; <b>Status:</b> {sale[8].upper()}<br>
                <b>Customer:</b> {sale[2] or 'Walk-in'}  &nbsp; <b>Phone:</b> {sale[3] or '—'}
                &nbsp; <b>KRA PIN:</b> {sale[4] or '—'}<br>
                <b>Subtotal:</b> KES {sale[5]:,.2f}  &nbsp;
                <b>VAT:</b> KES {sale[6]:,.2f}  &nbsp;
                <b>Total:</b> KES {sale[7]:,.2f}<br>
                <b>Payment:</b> {sale[9] or '—'}  &nbsp;
                <b>Date:</b> {sale[10][:16] if sale[10] else ''}  &nbsp;
                <b>Served by:</b> {sale[11] or '—'}
            """)
            layout.addWidget(info)
 
        tbl = QTableWidget(len(items), 4)
        tbl.setHorizontalHeaderLabels(["Product", "Qty", "Unit Price (KES)", "Total (KES)"])
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for r, it in enumerate(items):
            for c, v in enumerate(it):
                tbl.setItem(r, c, QTableWidgetItem(
                    f"KES {v:,.2f}" if c in (2, 3) else str(v)
                ))
        layout.addWidget(tbl)
        layout.addWidget(QPushButton("Close", clicked=self.accept), alignment=Qt.AlignRight)


# Main execution
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    db_manager = DatabaseManager()
    
    login_dialog = LoginDialog(db_manager)
    if login_dialog.exec_() == QDialog.Accepted:
        main_window = MainWindow(db_manager, login_dialog.user_data)
        main_window.show()
        sys.exit(app.exec_())
    else:
        sys.exit()