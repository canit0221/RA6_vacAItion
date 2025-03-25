from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path("signup/", views.CreateUserView.as_view()),
    path("login/", views.LoginView.as_view()),
    path("logout/", views.LogoutView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("users/<str:username>/", views.UserDetailView.as_view()),
    path("change-password/", views.ChangePasswordView.as_view()),
    path('request-password-reset/', views.RequestPasswordResetView.as_view()), #이메일 인증 요청청
    path('reset-password/', views.ResetPasswordView.as_view()),
]
