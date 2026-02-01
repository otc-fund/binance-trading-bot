"""
Performance Tracker Module
Manages performance metrics and reporting for the trading bot
"""

from datetime import datetime
from typing import Dict, List
import sys
import os

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.database import DatabaseManager
from modules.notifications import NotificationSystem


class PerformanceTracker:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.trade_history = []  # Track all trades in memory
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'current_streak': 0,
            'max_streak': 0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0
        }
    
    def track_trade(self, symbol: str, signal: str, entry_price: float, quantity: float, 
                   exit_price: float, pnl: float, reason: str = ""):
        """
        Track completed trade and update performance metrics
        
        Args:
            symbol: Trading pair
            signal: Trading signal ('BUY' or 'SELL')
            entry_price: Price at which trade was entered
            quantity: Quantity traded
            exit_price: Price at which trade was exited
            pnl: Profit or loss in USDT
            reason: Reason for exit ('stop_loss', 'take_profit', 'manual')
        """
        # Insert trade into database
        self.db_manager.insert_trade(symbol, signal, entry_price, quantity, exit_price, pnl, reason)
        
        # Update in-memory tracking
        timestamp = datetime.now().isoformat()
        pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price != 0 else 0
        
        trade = {
            'timestamp': timestamp,
            'symbol': symbol,
            'signal': signal,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'reason': reason
        }
        
        self.trade_history.append(trade)
        self.performance_metrics['total_trades'] += 1
        
        # Update win/loss counts
        if pnl > 0:
            self.performance_metrics['winning_trades'] += 1
        else:
            self.performance_metrics['losing_trades'] += 1
        
        # Update total PnL
        self.performance_metrics['total_pnl'] += pnl
        
        # Update largest win/loss
        if pnl > self.performance_metrics['largest_win']:
            self.performance_metrics['largest_win'] = pnl
        if pnl < self.performance_metrics['largest_loss']:
            self.performance_metrics['largest_loss'] = pnl
        
        # Update averages
        wins = self.performance_metrics['winning_trades']
        losses = self.performance_metrics['losing_trades']
        
        if wins > 0:
            total_wins = sum([t['pnl'] for t in self.trade_history if t['pnl'] > 0])
            self.performance_metrics['avg_win'] = total_wins / wins
        
        if losses > 0:
            total_losses = sum([t['pnl'] for t in self.trade_history if t['pnl'] < 0])
            self.performance_metrics['avg_loss'] = total_losses / losses
        
        # Update win rate
        if self.performance_metrics['total_trades'] > 0:
            self.performance_metrics['win_rate'] = (wins / self.performance_metrics['total_trades']) * 100
        
        # TODO: Add notification sending here when the trading bot instance is available
        # For now, this is handled in the main trading bot class
    
    def calculate_performance_metrics(self):
        """Calculate comprehensive performance metrics"""
        if not self.trade_history:
            return
        
        # Calculate additional metrics
        pnl_values = [trade['pnl'] for trade in self.trade_history]
        
        # Calculate Sharpe Ratio (simplified)
        if len(pnl_values) > 1:
            avg_return = sum(pnl_values) / len(pnl_values)
            std_dev = (sum([(x - avg_return) ** 2 for x in pnl_values]) / len(pnl_values)) ** 0.5 if len(pnl_values) > 1 else 0
            self.performance_metrics['sharpe_ratio'] = avg_return / std_dev if std_dev != 0 else 0
        
        # Calculate Max Drawdown (simplified)
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0
        
        for trade in self.trade_history:
            cumulative_pnl += trade['pnl']
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        self.performance_metrics['max_drawdown'] = max_drawdown
        
        # Calculate Profit Factor
        gross_profits = sum([trade['pnl'] for trade in self.trade_history if trade['pnl'] > 0])
        gross_losses = abs(sum([trade['pnl'] for trade in self.trade_history if trade['pnl'] < 0]))
        self.performance_metrics['profit_factor'] = gross_profits / gross_losses if gross_losses != 0 else float('inf')
    
    def print_performance_report(self):
        """Print a comprehensive performance report"""
        self.calculate_performance_metrics()
        
        print("\n" + "="*60)
        print("TRADING PERFORMANCE REPORT")
        print("="*60)
        print(f"Total Trades: {self.performance_metrics['total_trades']}")
        print(f"Winning Trades: {self.performance_metrics['winning_trades']}")
        print(f"Losing Trades: {self.performance_metrics['losing_trades']}")
        print(f"Win Rate: {self.performance_metrics['win_rate']:.2f}%")
        print(f"Total PnL: {self.performance_metrics['total_pnl']:.4f} USDT")
        print(f"Avg Win: {self.performance_metrics['avg_win']:.4f} USDT")
        print(f"Avg Loss: {self.performance_metrics['avg_loss']:.4f} USDT")
        print(f"Largest Win: {self.performance_metrics['largest_win']:.4f} USDT")
        print(f"Largest Loss: {self.performance_metrics['largest_loss']:.4f} USDT")
        print(f"Sharpe Ratio: {self.performance_metrics['sharpe_ratio']:.4f}")
        print(f"Max Drawdown: {self.performance_metrics['max_drawdown']:.4f} USDT")
        print(f"Profit Factor: {self.performance_metrics['profit_factor']:.4f}")
        print("="*60)
    
    def save_performance_snapshot(self):
        """Save current performance metrics to database"""
        self.db_manager.save_performance_snapshot(self.performance_metrics)
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """Get trade history from database"""
        return self.db_manager.get_trade_history(limit)