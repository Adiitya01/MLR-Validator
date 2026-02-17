import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

try:
    user = User.objects.get(email='adityapasare158@gmail.com')
    user.set_password('password123')
    user.save()
    print("SUCCESS: Password for adityapasare158@gmail.com set to password123")
except User.DoesNotExist:
    print("ERROR: User adityapasare158@gmail.com not found")
except Exception as e:
    print(f"ERROR: {str(e)}")
