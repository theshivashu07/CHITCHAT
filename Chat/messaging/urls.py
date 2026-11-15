from django.urls import path
from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path(
        "start/<int:user_id>/",
        views.start_direct_chat,
        name="start_direct_chat",
    ),
    path(
        "sync/<int:conversation_id>/",
        views.sync_messages,
        name="sync_messages",
    ),
    path(
        "<int:conversation_id>/",
        views.conversation_detail,
        name="conversation_detail",
    ),
]