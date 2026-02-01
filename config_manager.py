"""
Secure Configuration Manager
Handles encrypted loading and saving of config files with API keys
"""
import os
import json
from cryptography.fernet import Fernet
import base64


class SecureConfigManager:
    def __init__(self, config_path='binance-trading-bot/config.json', key_path='config.key'):
        self.config_path = config_path
        self.key_path = key_path
        self.cipher = None
        
    def generate_key(self):
        """Generate a new encryption key"""
        return Fernet.generate_key()
    
    def save_key(self, key):
        """Save the encryption key to file"""
        with open(self.key_path, 'wb') as key_file:
            key_file.write(key)
    
    def load_key(self):
        """Load the encryption key from file"""
        if not os.path.exists(self.key_path):
            raise FileNotFoundError(f"Key file {self.key_path} not found")
        return open(self.key_path, 'rb').read()
    
    def initialize_cipher(self):
        """Initialize the cipher with the key"""
        key = self.load_key()
        self.cipher = Fernet(key)
    
    def encrypt_config(self, config_data=None):
        """Encrypt the config file"""
        if config_data is None:
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Config file {self.config_path} not found")
            with open(self.config_path, 'r') as f:
                config_data = f.read()
        
        # Generate and save key
        key = self.generate_key()
        self.save_key(key)
        
        # Initialize cipher
        self.cipher = Fernet(key)
        
        # Encrypt config data
        encrypted_data = self.cipher.encrypt(config_data.encode())
        
        # Save encrypted data
        with open(self.config_path, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"Config file encrypted and saved: {self.config_path}")
        print(f"Encryption key saved: {self.key_path}")
        print("⚠️  KEEP THE KEY FILE SECURE - YOU NEED IT TO DECRYPT!")
    
    def decrypt_config(self):
        """Decrypt and return config data"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file {self.config_path} not found")
        
        # Initialize cipher
        self.initialize_cipher()
        
        # Read encrypted data
        with open(self.config_path, 'rb') as f:
            encrypted_data = f.read()
        
        # Decrypt data
        decrypted_data = self.cipher.decrypt(encrypted_data)
        
        return json.loads(decrypted_data.decode())
    
    def load_config(self):
        """Load config - handles both encrypted and unencrypted configs"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file {self.config_path} not found")
        
        # Try to determine if file is encrypted by attempting to read it
        try:
            # Try reading as JSON first (unencrypted)
            with open(self.config_path, 'r') as f:
                content = f.read()
                # Try parsing as JSON
                return json.loads(content)
        except:
            # If that fails, assume it's encrypted
            try:
                return self.decrypt_config()
            except Exception as e:
                raise Exception(f"Could not load config - it may be encrypted but decryption failed: {str(e)}")
    
    def is_encrypted(self):
        """Check if config file is encrypted"""
        try:
            # Try to read as JSON
            with open(self.config_path, 'r') as f:
                content = f.read()
                json.loads(content)
            return False  # If it parses as JSON, it's not encrypted
        except:
            # If it doesn't parse as JSON, it might be encrypted
            return True


def encrypt_existing_config():
    """Function to encrypt the existing config file"""
    manager = SecureConfigManager()
    
    if not os.path.exists(manager.config_path):
        print(f"No config file found at {manager.config_path}")
        return False
    
    # Check if already encrypted
    if manager.is_encrypted():
        print("Config file is already encrypted!")
        return True
    
    try:
        manager.encrypt_config()
        print("Config file encrypted successfully!")
        return True
    except Exception as e:
        print(f"Error encrypting config: {str(e)}")
        return False


def main():
    """Main function to demonstrate usage"""
    print("Secure Config Manager")
    print("1. Encrypt existing config")
    print("2. Test loading config")
    
    choice = input("Enter choice (1 or 2): ")
    
    if choice == "1":
        encrypt_existing_config()
    elif choice == "2":
        manager = SecureConfigManager()
        try:
            config = manager.load_config()
            print("Config loaded successfully:")
            print(json.dumps(config, indent=2))
        except Exception as e:
            print(f"Error loading config: {str(e)}")


if __name__ == "__main__":
    main()