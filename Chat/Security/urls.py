from django.urls import path
from . import views

urlpatterns = [
    path('',views.index,name='index'),
    # path('index',views.index,name='index'),
    
    path('login/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    # path('signin/', views.signin, name='signin'),
    # path('register/', views.register, name='register'),
    path('signout/', views.signout, name='signout'),

    path('users/', views.users, name='users'),

    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password/accounts/', views.forgot_password_accounts, name='forgot_password_accounts'),
    path('forgot-password/otp/', views.forgot_password_otp, name='forgot_password_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),

]

