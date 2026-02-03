"""
Monitor script to show real-time console output of the trading bot
"""
import subprocess
import sys
import threading
import time
from datetime import datetime

def monitor_process_output():
    """
    Monitor the trading bot process output in real-time
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting trading bot output monitor...")
    print("="*60)
    
    # Start the trading bot with the run_ui.py script
    cmd = [sys.executable, "run_ui.py"]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
        cwd="."
    )
    
    # Print header for enhanced logging
    print("\n[ENHANCED LOGGING ACTIVE]")
    print("- [KLINE REQUEST] - When klines are fetched")
    print("- [KLINE RESPONSE] - When klines are received") 
    print("- [KLINE DETAILS] - Details about candlesticks")
    print("- [STRATEGY] - When strategy runs for symbols")
    print("="*60)
    
    # Monitor output in real-time
    for line in iter(process.stdout.readline, ''):
        line = line.rstrip()
        if '[KLINE' in line or '[STRATEGY' in line or 'ERROR' in line:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
        elif any(port in line for port in ['5000', '5001']):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
    
    process.wait()

if __name__ == "__main__":
    monitor_process_output()