#!/usr/bin/env python3
"""
Initialize the PostgreSQL database tables for the MLR UI application
Run this once after setting up your PostgreSQL connection
"""

import requests
import sys
import time

def init_database(backend_url="http://localhost:8000"):
    """Call the /init-db endpoint to create database tables"""
    try:
        print("🔧 Initializing database tables...")
        response = requests.post(f"{backend_url}/init-db")
        
        if response.status_code == 200:
            print("✅ Database tables created successfully!")
            print(f"   Message: {response.json().get('message', 'Database ready')}")
            return True
        else:
            print(f"❌ Database initialization failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to backend at {backend_url}")
        print("   Make sure your FastAPI server is running (python app.py)")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MLR UI - Database Initialization Script")
    print("=" * 60)
    print()
    
    # Initialize database
    success = init_database()
    
    if success:
        print()
        print("✅ Your database is now ready to use!")
    else:
        print()
        print("⚠️  Database initialization failed. Please check:")
        print("   1. FastAPI server is running on http://localhost:8000")
        print("   2. PostgreSQL is running and accessible")
        print("   3. DATABASE_URL in .env is correct")
        sys.exit(1)
