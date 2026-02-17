import os
import django
import psycopg2
from urllib.parse import urlparse

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

def migrate_users():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return

    # Parse database URL for psycopg2
    if 'postgresql+psycopg2' in database_url:
        database_url = database_url.replace('postgresql+psycopg2', 'postgres')
    
    url = urlparse(database_url)
    
    try:
        conn = psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        
        # Check if legacy users table exists
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
        if not cur.fetchone()[0]:
            print("❌ Legacy 'users' table not found.")
            return

        # Fetch users from legacy table
        cur.execute("SELECT email, password_hash FROM users")
        legacy_users = cur.fetchall()
        
        print(f"🔄 Found {len(legacy_users)} users in legacy table. Migrating...")
        
        migrated_count = 0
        for email, pwd_hash in legacy_users:
            if not User.objects.filter(email=email).exists():
                # Create user
                # Note: We store the bcrypt hash directly in the password field. 
                # Django can verify bcrypt if it's in its PASSWORD_HASHERS list.
                # However, to ensure they can at least use "Forgot Password" or 
                # if the user knows their password, we just need the record there.
                user = User.objects.create_user(email=email)
                user.password = pwd_hash # Store the hash directly
                user.is_email_verified = True # Assume legacy users are verified or let them reset
                user.save()
                migrated_count += 1
                print(f"✅ Migrated: {email}")
            else:
                print(f"⏭️  Skipped (already exists): {email}")
        
        print(f"\n✨ Successfully migrated {migrated_count} users to the new system!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")

if __name__ == "__main__":
    migrate_users()
