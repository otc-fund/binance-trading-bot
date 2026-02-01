"""
Database module for trading bot
Handles all database operations for trade history and performance metrics
"""

import sqlite3
import csv
from datetime import datetime
from typing import Dict, List


class DatabaseManager:
    def __init__(self, db_path: str = 'trading_bot.db'):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Connect to the database"""
        self.connection = sqlite3.connect(self.db_path)
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        if not self.connection:
            return
        
        cursor = self.connection.cursor()
        
        # Create trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL NOT NULL,
                pnl REAL,
                pnl_percent REAL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                total_pnl REAL,
                win_rate REAL,
                avg_win REAL,
                avg_loss REAL,
                largest_win REAL,
                largest_loss REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                profit_factor REAL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.connection.commit()
    
    def insert_trade(self, symbol: str, signal: str, entry_price: float, quantity: float, 
                     exit_price: float, pnl: float, reason: str = ""):
        """Insert a trade record into the database"""
        if not self.connection:
            return
        
        timestamp = datetime.now().isoformat()
        pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price != 0 else 0
        
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT INTO trades (timestamp, symbol, signal, entry_price, exit_price, quantity, pnl, pnl_percent, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, symbol, signal, entry_price, exit_price, quantity, pnl, pnl_percent, reason))
        
        self.connection.commit()
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """Retrieve trade history from database"""
        if not self.connection:
            return []
        
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM trades 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        
        trades = []
        for row in rows:
            trade = dict(zip(columns, row))
            trades.append(trade)
        
        return trades
    
    def get_latest_performance_metrics(self) -> Dict:
        """Retrieve latest performance metrics from database"""
        if not self.connection:
            return {}
        
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM performance_metrics 
            ORDER BY recorded_at DESC 
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        
        return {}
    
    def save_performance_snapshot(self, metrics: Dict):
        """Save current performance metrics to database"""
        if not self.connection:
            return
        
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT INTO performance_metrics (
                total_trades, winning_trades, losing_trades, 
                total_pnl, win_rate, avg_win, avg_loss, 
                largest_win, largest_loss, sharpe_ratio, 
                max_drawdown, profit_factor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metrics.get('total_trades', 0),
            metrics.get('winning_trades', 0),
            metrics.get('losing_trades', 0),
            metrics.get('total_pnl', 0.0),
            metrics.get('win_rate', 0.0),
            metrics.get('avg_win', 0.0),
            metrics.get('avg_loss', 0.0),
            metrics.get('largest_win', 0.0),
            metrics.get('largest_loss', 0.0),
            metrics.get('sharpe_ratio', 0.0),
            metrics.get('max_drawdown', 0.0),
            metrics.get('profit_factor', 0.0)
        ))
        
        self.connection.commit()
    
    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
    
    def export_to_csv(self, filename: str = None):
        """Export trade history to CSV file"""
        if not filename:
            filename = f"trade_history_{datetime.now().strftime('%Y-%m-%d')}.csv"
        
        trades = self.get_trade_history(limit=10000)  # Get all trades
        
        if not trades:
            return
        
        file_exists = False
        try:
            file_exists = __import__('os').path.isfile(filename)
        except:
            pass
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'symbol', 'signal', 'entry_price', 'exit_price', 'quantity', 'pnl', 'pnl_percent', 'reason']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for trade in trades:
                # Only write the fields we need
                filtered_trade = {k: v for k, v in trade.items() if k in fieldnames}
                writer.writerow(filtered_trade)