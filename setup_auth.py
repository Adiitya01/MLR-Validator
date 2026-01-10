#!/usr/bin/env python3
"""
Setup script to initialize the MLR authentication system
Runs the /init-db endpoint to create database tables
"""

import requests
import sys
import time

def init_database(backend_url="http://localhost:8000"):
    """Initialize database tables"""
    try:
        print("🔧 Initializing authentication database...")
        response = requests.post(f"{backend_url}/init-db")
        
        if response.status_code == 200:
            print("✅ Database initialized successfully!")
            data = response.json()
            print(f"   Message: {data.get('message', 'Database ready')}")
            return True
        else:
            print(f"❌ Database initialization failed: {response.status_code}")
            print(f"   Response: {response.json()}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to backend at {backend_url}")
        print("   Make sure FastAPI server is running: python app.py")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    print("\n" + "="*50)
    print("MLR Authentication System Setup")
    print("="*50 + "\n")
    
    # Try to initialize database
    success = init_database()
    
    if success:
        print("\n✅ Setup complete! You can now:")
        print("   1. Start the React app: npm run dev")
        print("   2. Open http://localhost:5173")
        print("   3. Create a new account or log in")
    else:
        print("\n⚠️  Setup incomplete. Please ensure:")
        print("   1. FastAPI backend is running: python app.py")
        print("   2. PostgreSQL database is accessible")
        print("   3. Environment variables are set (DATABASE_URL, SECRET_KEY)")
        sys.exit(1)

if __name__ == "__main__":
    main()
