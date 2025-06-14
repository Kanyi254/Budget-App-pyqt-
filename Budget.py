import sys
import sqlite3
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
import numpy as np

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('budget_tracker.db')
        self.setup_database()
    
    def setup_database(self):
        cursor = self.conn.cursor()
        
        # Accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL DEFAULT 0
            )
        ''')
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                account_id INTEGER,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts (id)
            )
        ''')
        
        # Budget categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budget_categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                budgeted_amount REAL DEFAULT 0,
                spent_amount REAL DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    def add_account(self, name, account_type, balance=0):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO accounts (name, type, balance) VALUES (?, ?, ?)',
                      (name, account_type, balance))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_accounts(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM accounts')
        return cursor.fetchall()
    
    def update_account_balance(self, account_id, new_balance):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_balance, account_id))
        self.conn.commit()
    
    def add_transaction(self, account_id, amount, category, description, transaction_type):
        cursor = self.conn.cursor()
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''INSERT INTO transactions 
                         (account_id, amount, category, description, date, type) 
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (account_id, amount, category, description, date, transaction_type))
        self.conn.commit()
        
        # Update account balance
        cursor.execute('SELECT balance FROM accounts WHERE id = ?', (account_id,))
        current_balance = cursor.fetchone()[0]
        new_balance = current_balance + amount if transaction_type == 'income' else current_balance - amount
        self.update_account_balance(account_id, new_balance)
    
    def get_transactions(self, limit=None, account_id=None):
        cursor = self.conn.cursor()
        query = '''SELECT t.*, a.name as account_name 
                   FROM transactions t 
                   JOIN accounts a ON t.account_id = a.id 
                   ORDER BY t.date DESC'''
        
        if account_id:
            query = query.replace('ORDER BY', 'WHERE t.account_id = ? ORDER BY')
            cursor.execute(query + (f' LIMIT {limit}' if limit else ''), (account_id,))
        else:
            cursor.execute(query + (f' LIMIT {limit}' if limit else ''))
        
        return cursor.fetchall()
    
    def get_spending_by_category(self, days=30):
        cursor = self.conn.cursor()
        date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        cursor.execute('''SELECT category, SUM(amount) as total 
                         FROM transactions 
                         WHERE type = 'expense' AND date >= ? 
                         GROUP BY category''', (date_limit,))
        return cursor.fetchall()
    
    def get_monthly_summary(self):
        cursor = self.conn.cursor()
        current_month = datetime.now().strftime('%Y-%m')
        cursor.execute('''SELECT type, SUM(amount) as total 
                         FROM transactions 
                         WHERE date LIKE ? 
                         GROUP BY type''', (current_month + '%',))
        return cursor.fetchall()

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        
    def plot_spending_pie(self, data):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        if data:
            categories, amounts = zip(*data)
            ax.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=90)
            ax.set_title('Spending by Category (Last 30 Days)')
        else:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center')
            ax.set_title('Spending by Category')
        
        self.draw()
    
    def plot_monthly_trend(self, db):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        # Get last 6 months data
        months = []
        income_data = []
        expense_data = []
        
        for i in range(6):
            date = (datetime.now() - timedelta(days=30*i)).strftime('%Y-%m')
            months.append(date)
            
            cursor = db.conn.cursor()
            cursor.execute('''SELECT type, SUM(amount) as total 
                             FROM transactions 
                             WHERE date LIKE ? 
                             GROUP BY type''', (date + '%',))
            month_data = dict(cursor.fetchall())
            
            income_data.append(month_data.get('income', 0))
            expense_data.append(month_data.get('expense', 0))
        
        months.reverse()
        income_data.reverse()
        expense_data.reverse()
        
        x = range(len(months))
        ax.bar([i - 0.2 for i in x], income_data, 0.4, label='Income', color='green', alpha=0.7)
        ax.bar([i + 0.2 for i in x], expense_data, 0.4, label='Expenses', color='red', alpha=0.7)
        
        ax.set_xlabel('Month')
        ax.set_ylabel('Amount')
        ax.set_title('Income vs Expenses (Last 6 Months)')
        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=45)
        ax.legend()
        
        self.fig.tight_layout()
        self.draw()

class AddTransactionDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle('Add Transaction')
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout()
        
        # Account selection
        layout.addWidget(QLabel('Account:'))
        self.account_combo = QComboBox()
        accounts = self.db.get_accounts()
        for account in accounts:
            self.account_combo.addItem(f"{account[1]} ({account[2]})", account[0])
        layout.addWidget(self.account_combo)
        
        # Transaction type
        layout.addWidget(QLabel('Type:'))
        self.type_combo = QComboBox()
        self.type_combo.addItems(['expense', 'income'])
        layout.addWidget(self.type_combo)
        
        # Amount
        layout.addWidget(QLabel('Amount:'))
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 999999.99)
        self.amount_input.setDecimals(2)
        layout.addWidget(self.amount_input)
        
        # Category
        layout.addWidget(QLabel('Category:'))
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        categories = ['Food', 'Transportation', 'Entertainment', 'Bills', 'Shopping', 
                     'Healthcare', 'Miscellaneous', 'Salary', 'Investment', 'Savings']
        self.category_input.addItems(categories)
        layout.addWidget(self.category_input)
        
        # Description
        layout.addWidget(QLabel('Description:'))
        self.description_input = QLineEdit()
        layout.addWidget(self.description_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton('Add Transaction')
        self.cancel_button = QPushButton('Cancel')
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def get_transaction_data(self):
        return {
            'account_id': self.account_combo.currentData(),
            'amount': self.amount_input.value(),
            'category': self.category_input.currentText(),
            'description': self.description_input.text(),
            'type': self.type_combo.currentText()
        }

class AddAccountDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle('Add Account')
        self.setModal(True)
        self.resize(300, 200)
        
        layout = QVBoxLayout()
        
        # Account name
        layout.addWidget(QLabel('Account Name:'))
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)
        
        # Account type
        layout.addWidget(QLabel('Account Type:'))
        self.type_combo = QComboBox()
        self.type_combo.addItems(['Checking', 'Savings', 'Credit Card', 'Investment'])
        layout.addWidget(self.type_combo)
        
        # Initial balance
        layout.addWidget(QLabel('Initial Balance:'))
        self.balance_input = QDoubleSpinBox()
        self.balance_input.setRange(-999999.99, 999999.99)
        self.balance_input.setDecimals(2)
        layout.addWidget(self.balance_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton('Add Account')
        self.cancel_button = QPushButton('Cancel')
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def get_account_data(self):
        return {
            'name': self.name_input.text(),
            'type': self.type_combo.currentText(),
            'balance': self.balance_input.value()
        }

class BudgetTracker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.setup_ui()
        self.refresh_data()
    
    def setup_ui(self):
        self.setWindowTitle('Personal Budget Tracker')
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Dashboard tab
        self.setup_dashboard_tab()
        
        # Transactions tab
        self.setup_transactions_tab()
        
        # Accounts tab
        self.setup_accounts_tab()
        
        # Analytics tab
        self.setup_analytics_tab()
        
        # Menu bar
        self.setup_menu_bar()
        
        # Status bar
        self.statusBar().showMessage('Ready')
    
    def setup_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        export_action = QAction('Export Data', self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        add_transaction_action = QAction('Add Transaction', self)
        add_transaction_action.triggered.connect(self.add_transaction)
        tools_menu.addAction(add_transaction_action)
        
        add_account_action = QAction('Add Account', self)
        add_account_action.triggered.connect(self.add_account)
        tools_menu.addAction(add_account_action)
    
    def setup_dashboard_tab(self):
        dashboard = QWidget()
        self.tabs.addTab(dashboard, 'Dashboard')
        
        layout = QVBoxLayout(dashboard)
        
        # Summary cards
        cards_layout = QHBoxLayout()
        
        # Total balance card
        self.balance_card = self.create_summary_card('Total Balance', '$0.00', 'green')
        cards_layout.addWidget(self.balance_card)
        
        # Monthly income card
        self.income_card = self.create_summary_card('Monthly Income', '$0.00', 'blue')
        cards_layout.addWidget(self.income_card)
        
        # Monthly expenses card
        self.expense_card = self.create_summary_card('Monthly Expenses', '$0.00', 'red')
        cards_layout.addWidget(self.expense_card)
        
        layout.addLayout(cards_layout)
        
        # Recent transactions
        layout.addWidget(QLabel('Recent Transactions:'))
        self.recent_transactions = QTableWidget()
        self.recent_transactions.setColumnCount(5)
        self.recent_transactions.setHorizontalHeaderLabels(['Date', 'Account', 'Category', 'Amount', 'Description'])
        self.recent_transactions.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.recent_transactions)
    
    def create_summary_card(self, title, value, color):
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet(f"""
            QFrame {{
                border: 2px solid {color};
                border-radius: 10px;
                padding: 10px;
                background-color: #f0f0f0;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setStyleSheet('font-weight: bold; font-size: 14px;')
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f'color: {color}; font-size: 24px; font-weight: bold;')
        layout.addWidget(value_label)
        
        card.value_label = value_label  # Store reference for updates
        return card
    
    def setup_transactions_tab(self):
        transactions = QWidget()
        self.tabs.addTab(transactions, 'Transactions')
        
        layout = QVBoxLayout(transactions)
        
        # Add transaction button
        add_btn = QPushButton('Add Transaction')
        add_btn.clicked.connect(self.add_transaction)
        layout.addWidget(add_btn)
        
        # Transactions table
        self.transactions_table = QTableWidget()
        self.transactions_table.setColumnCount(6)
        self.transactions_table.setHorizontalHeaderLabels(['Date', 'Account', 'Type', 'Category', 'Amount', 'Description'])
        self.transactions_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.transactions_table)
    
    def setup_accounts_tab(self):
        accounts = QWidget()
        self.tabs.addTab(accounts, 'Accounts')
        
        layout = QVBoxLayout(accounts)
        
        # Add account button
        add_btn = QPushButton('Add Account')
        add_btn.clicked.connect(self.add_account)
        layout.addWidget(add_btn)
        
        # Accounts table
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(3)
        self.accounts_table.setHorizontalHeaderLabels(['Name', 'Type', 'Balance'])
        self.accounts_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.accounts_table)
    
    def setup_analytics_tab(self):
        analytics = QWidget()
        self.tabs.addTab(analytics, 'Analytics')
        
        layout = QVBoxLayout(analytics)
        
        # Charts container
        charts_layout = QHBoxLayout()
        
        # Spending pie chart
        self.spending_chart = PlotCanvas(self, width=6, height=4)
        charts_layout.addWidget(self.spending_chart)
        
        # Monthly trend chart
        self.trend_chart = PlotCanvas(self, width=6, height=4)
        charts_layout.addWidget(self.trend_chart)
        
        layout.addLayout(charts_layout)
        
        # Refresh charts button
        refresh_btn = QPushButton('Refresh Charts')
        refresh_btn.clicked.connect(self.refresh_charts)
        layout.addWidget(refresh_btn)
    
    def add_transaction(self):
        if not self.db.get_accounts():
            QMessageBox.warning(self, 'Warning', 'Please add at least one account first.')
            return
            
        dialog = AddTransactionDialog(self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_transaction_data()
            self.db.add_transaction(
                data['account_id'], data['amount'], data['category'],
                data['description'], data['type']
            )
            self.refresh_data()
            self.statusBar().showMessage('Transaction added successfully', 3000)
    
    def add_account(self):
        dialog = AddAccountDialog(self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_account_data()
            if data['name']:
                self.db.add_account(data['name'], data['type'], data['balance'])
                self.refresh_data()
                self.statusBar().showMessage('Account added successfully', 3000)
            else:
                QMessageBox.warning(self, 'Warning', 'Account name cannot be empty.')
    
    def refresh_data(self):
        self.refresh_dashboard()
        self.refresh_transactions()
        self.refresh_accounts()
        self.refresh_charts()
    
    def refresh_dashboard(self):
        # Update summary cards
        accounts = self.db.get_accounts()
        total_balance = sum(account[3] for account in accounts)
        self.balance_card.value_label.setText(f'${total_balance:,.2f}')
        
        # Monthly summary
        monthly_data = dict(self.db.get_monthly_summary())
        monthly_income = monthly_data.get('income', 0)
        monthly_expenses = monthly_data.get('expense', 0)
        
        self.income_card.value_label.setText(f'${monthly_income:,.2f}')
        self.expense_card.value_label.setText(f'${monthly_expenses:,.2f}')
        
        # Recent transactions
        recent = self.db.get_transactions(limit=10)
        self.recent_transactions.setRowCount(len(recent))
        
        for i, transaction in enumerate(recent):
            self.recent_transactions.setItem(i, 0, QTableWidgetItem(transaction[5][:10]))
            self.recent_transactions.setItem(i, 1, QTableWidgetItem(transaction[7]))
            self.recent_transactions.setItem(i, 2, QTableWidgetItem(transaction[3]))
            amount_color = 'green' if transaction[6] == 'income' else 'red'
            amount_item = QTableWidgetItem(f'${transaction[2]:,.2f}')
            amount_item.setForeground(QColor(amount_color))
            self.recent_transactions.setItem(i, 3, amount_item)
            self.recent_transactions.setItem(i, 4, QTableWidgetItem(transaction[4] or ''))
    
    def refresh_transactions(self):
        transactions = self.db.get_transactions()
        self.transactions_table.setRowCount(len(transactions))
        
        for i, transaction in enumerate(transactions):
            self.transactions_table.setItem(i, 0, QTableWidgetItem(transaction[5][:10]))
            self.transactions_table.setItem(i, 1, QTableWidgetItem(transaction[7]))
            self.transactions_table.setItem(i, 2, QTableWidgetItem(transaction[6].title()))
            self.transactions_table.setItem(i, 3, QTableWidgetItem(transaction[3]))
            amount_color = 'green' if transaction[6] == 'income' else 'red'
            amount_item = QTableWidgetItem(f'${transaction[2]:,.2f}')
            amount_item.setForeground(QColor(amount_color))
            self.transactions_table.setItem(i, 4, amount_item)
            self.transactions_table.setItem(i, 5, QTableWidgetItem(transaction[4] or ''))
    
    def refresh_accounts(self):
        accounts = self.db.get_accounts()
        self.accounts_table.setRowCount(len(accounts))
        
        for i, account in enumerate(accounts):
            self.accounts_table.setItem(i, 0, QTableWidgetItem(account[1]))
            self.accounts_table.setItem(i, 1, QTableWidgetItem(account[2]))
            balance_color = 'green' if account[3] >= 0 else 'red'
            balance_item = QTableWidgetItem(f'${account[3]:,.2f}')
            balance_item.setForeground(QColor(balance_color))
            self.accounts_table.setItem(i, 2, balance_item)
    
    def refresh_charts(self):
        # Spending pie chart
        spending_data = self.db.get_spending_by_category()
        self.spending_chart.plot_spending_pie(spending_data)
        
        # Monthly trend chart
        self.trend_chart.plot_monthly_trend(self.db)
    
    def export_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, 'Export Data', 'budget_data.csv', 'CSV Files (*.csv)')
        if file_path:
            try:
                transactions = self.db.get_transactions()
                df = pd.DataFrame(transactions, columns=['ID', 'Account_ID', 'Amount', 'Category', 'Description', 'Date', 'Type', 'Account_Name'])
                df.to_csv(file_path, index=False)
                QMessageBox.information(self, 'Success', 'Data exported successfully!')
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to export data: {str(e)}')

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    # Set application icon and name
    app.setApplicationName('Budget Tracker')
    
    window = BudgetTracker()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()