from django.urls import path
from . import views

urlpatterns = [
    path('',views.index,name='index'),
    # path('index',views.index,name='index'),


    path('profile/',views.profile,name='profile'),
    path('profile-setups/',views.profile_setups,name='profile_setups'),
    path('profile/setups/',views.profile_setups,name='profile_setups'),
    path('profile/edits/',views.profile_edits,name='profile_edits'),
    path('profile/update/',views.profile_edits,name='profile_update'),
    path('notifications/',views.notifications,name='notifications'),

]



