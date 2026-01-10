#!/usr/bin/env python3
"""Quick database check script"""

from sqlalchemy import text
from database import SessionLocal as AuthSessionLocal

db = AuthSessionLocal()

print("=" * 70)
print("DATABASE CONTENT CHECK")
print("=" * 70)

try:
    # Check all users
    users = db.execute(text("SELECT id, email, full_name, created_at FROM users ORDER BY created_at DESC")).fetchall()
    
    print(f"\nTotal users in database: {len(users)}")
    print("-" * 70)
    
    if users:
        for user in users:
            print(f"ID: {user[0]}")
            print(f"Email: '{user[1]}'")
            print(f"Full Name: {user[2]}")
            print(f"Created: {user[3]}")
            print("-" * 70)
    else:
        print("NO USERS IN DATABASE!")
        
except Exception as e:
    print(f"ERROR: {str(e)}")
finally:
    db.close()

print("\nDone!")
