"""
URL configuration for Chat project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


from django.contrib import admin
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)





from functools import partial
from Security.views import errors

# Ye mat karna because aayegi TypeError: the first argument must be callable! 
# handler400 = partial("Security.views.errors", status_code=400)

# Yeh bilkul sahi hai! 
"""
handler400 = partial(errors, status_code=400)
handler403 = partial(errors, status_code=403)
handler404 = partial(errors, status_code=404)
handler500 = partial(errors, status_code=500)
"""




# from .views_for_google import google_onetap_popup_login as google_onetap

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('Home.urls')),
    
    # me chahta hu ki kevel profile dekhne ke liye vo accounts/profile/ pe jaye but jayega to vo security app par hi
    # path('accounts/profile/<int:user_id>/', include('Security.urls.profile')),
    path('security/', include('Security.urls')),
    path('chat/', include('Auto.urls')),
    path("messaging/", include("messaging.urls")),



    
    # path("ckeditor/", include("ckeditor_uploader.urls")),
    
    # all auth - google, facebook, github
    # path("accounts/", include("allauth.urls")),  # Normal Google Login
    # path("security/google-onetap-popup-login/", google_onetap, name="google_login_popup"),
]



from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import re_path

# 1
# ye possibally work na kare agar aapne debug=true se false pe le gye hon taki 404 page dikh ske! 
# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 2
# ye tab jab aapko 404 page wali setting v karne ho or uploads se files v access karna ho, 
# if settings.DEBUG:
# urlpatterns += [
#         path(
#             f"{settings.MEDIA_URL.lstrip('/')}" "<path:path>",
#             serve, {"document_root": settings.MEDIA_ROOT},
#         ),
# ]


# 3
# Yeh tareeqa local testing me DEBUG=False par bhi chalega aur secure rahega
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Live/Local testing jab DEBUG=False ho, to re_path use karein jo secure hai
    urlpatterns += [
        re_path(r'^_uploads/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

