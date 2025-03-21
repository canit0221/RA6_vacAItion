from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path("signup/", views.CreateUserView.as_view()),
    path("login/", views.LoginView.as_view()),
    path("logout/", views.LogoutView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("users/<str:username>/", views.UserDetailView.as_view()),
]
