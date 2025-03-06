from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path("signup/", views.CreateUserView.as_view(), name='signup'),
    path("login/", views.LoginView.as_view(), name='login'),
    path("logout/", views.LogoutView.as_view(), name='logout'),

    path("token/refresh/", TokenRefreshView.as_view(), name='token_refresh'),

    path("users/<str:username>/", views.UserDetailView.as_view(), name='user-detail'),
    path('auth/', views.auth_page, name='auth-page'),
]