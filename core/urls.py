from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='delete-user')  

urlpatterns = [
    path('users/', include(router.urls)), 
]