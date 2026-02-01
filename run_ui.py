"""
Script to run both the bot API and the UI
"""

import subprocess
import sys
import os
import threading
import time

def run_bot_api():
    """Run the bot API server"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    cmd = [sys.executable, 'bot_api.py']
    subprocess.run(cmd)

def run_ui():
    """Run the UI server"""
    ui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui')
    os.chdir(ui_dir)
    cmd = [sys.executable, 'app.py']
    subprocess.run(cmd)

if __name__ == '__main__':
    print("Starting Binance Trading Bot with UI...")
    print("Bot API will run on http://localhost:5001")
    print("UI will run on http://localhost:5000")
    print("Please make sure you have installed the required packages:")
    print("  pip install -r ui/requirements.txt")
    print("")
    print("Press Ctrl+C to stop both servers")
    print("")
    
    # Start bot API in a separate thread
    bot_thread = threading.Thread(target=run_bot_api, daemon=True)
    bot_thread.start()
    
    # Small delay to ensure bot API starts first
    time.sleep(2)
    
    # Run UI in main thread
    run_ui()