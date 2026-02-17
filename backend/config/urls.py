
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/validator/', include('validator.urls')),
    # Mount validator URLs at root for legacy frontend compatibility
    path('', include('validator.urls')),
]
