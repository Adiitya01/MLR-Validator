from uuid import uuid4
from sqlalchemy import text
from db import SessionLocal

db = SessionLocal()

db.execute(
    text("""
        INSERT INTO users (id, email, password_hash)
        VALUES (:id, :email, :password)
    """),
    {
        "id": str(uuid4()),
        "email": "test@example.com",
        "password": "hashed_password"
    }
)

db.commit()
db.close()

print("User inserted successfully")
