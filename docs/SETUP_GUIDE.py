#!/usr/bin/env python3
"""
Complete setup and troubleshooting guide for MLR UI Authentication
"""

import sys
import os

def print_section(title):
    """Print a formatted section header"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()

def main():
    print_section("MLR UI - Authentication Setup Checklist")
    
    print("Follow these steps to get authentication working:")
    print()
    
    print("STEP 1: Restart FastAPI Server")
    print("   • Stop the running FastAPI server (Ctrl+C)")
    print("   • Then run: python app.py")
    print("   • This ensures the updated security.py is loaded")
    print()
    
    print("STEP 2: Database Information")
    print("   ✓ Database Table: users")
    print("   ✓ Columns:")
    print("      - id (SERIAL PRIMARY KEY)")
    print("      - email (VARCHAR(255) UNIQUE NOT NULL)")
    print("      - password_hash (VARCHAR(255) NOT NULL)")
    print("        └─ Stores bcrypt hashes (~60 chars)")
    print("      - full_name (VARCHAR(255))")
    print("      - created_at (TIMESTAMP)")
    print("      - updated_at (TIMESTAMP)")
    print()
    
    print("STEP 3: Password Requirements")
    print("   ✓ Min length: 6 characters")
    print("   ✓ Max length: 72 bytes (enforced by validation)")
    print("   ✓ Auto-truncates at 72 bytes if longer")
    print("   ✓ Examples that work:")
    print("      - Aditya@6699")
    print("      - MyPassword123!")
    print("      - Test@12345")
    print()
    
    print("STEP 4: Test Signup")
    print("   1. Open browser: http://localhost:5173")
    print("   2. Click Signup")
    print("   3. Enter:")
    print("      Email: your-email@example.com")
    print("      Password: Aditya@6699")
    print("      Full Name: Your Name")
    print("   4. Click Signup button")
    print()
    
    print("STEP 5: If Still Getting Error")
    print("   Try these troubleshooting steps:")
    print()
    print("   A. Clear old data and reinitialize database:")
    print("      • Open PostgreSQL: psql -U postgres")
    print("      • Drop table: DROP TABLE IF EXISTS users CASCADE;")
    print("      • Exit: \\q")
    print("      • Reinitialize: python init_db.py")
    print()
    print("   B. Check if bcrypt is properly installed:")
    print("      python -c \"import bcrypt; print('bcrypt OK')\"")
    print()
    print("   C. Verify password encoding:")
    print("      python -c \"print(len('Aditya@6699'.encode('utf-8')), 'bytes')\"")
    print()
    
    print("STEP 6: Database Schema (No Changes Needed)")
    print("   The current schema is correct:")
    print("   • password_hash VARCHAR(255) - Sufficient for bcrypt hashes")
    print("   • No migration needed")
    print()
    
    print_section("Quick Commands")
    print("Restart FastAPI:     python app.py")
    print("Initialize Database: python init_db.py")
    print("Check PostgreSQL:    psql -U postgres")
    print("Test bcrypt:         python -c \"from security import hash_password; print(hash_password('Test@123'))\"")
    print()
    
if __name__ == "__main__":
    main()
