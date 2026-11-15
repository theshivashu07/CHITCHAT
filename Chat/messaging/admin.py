from django.contrib import admin
from .models import (
    Conversation,
    ConversationMember,
    Message,
    MessageReceipt,
    MessageUserState,
    ConversationPin,
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "title",
        "created_by",
        "created_at",
    )
    list_filter = ("kind", "created_at")
    search_fields = ("title", "created_by__username")
    list_select_related = ("created_by",)


@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "user",
        "username_snapshot",
        "joined_at",
        "left_at",
    )
    list_filter = ("joined_at", "left_at")
    search_fields = (
        "username_snapshot",
        "user__username",
    )
    list_select_related = ("conversation", "user")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender_username",
        "created_at",
        "edited_at",
        "deleted_for_everyone_at",
    )
    list_filter = (
        "created_at",
        "edited_at",
        "deleted_for_everyone_at",
    )
    search_fields = ("body", "sender_username")
    readonly_fields = ("created_at",)
    list_select_related = ("conversation", "sender")
    date_hierarchy = "created_at"


@admin.register(MessageReceipt)
class MessageReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "recipient_username",
        "delivered_at",
        "seen_at",
    )
    list_filter = ("delivered_at", "seen_at")
    search_fields = (
        "recipient_username",
        "recipient__username",
    )
    list_select_related = ("message", "recipient")


@admin.register(MessageUserState)
class MessageUserStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "username_snapshot",
        "is_starred",
        "starred_at",
        "deleted_for_me_at",
    )
    list_filter = ("is_starred", "starred_at")
    search_fields = (
        "username_snapshot",
        "user__username",
    )
    list_select_related = ("message", "user")


@admin.register(ConversationPin)
class ConversationPinAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "message",
        "pinned_by_username",
        "pinned_at",
        "is_active",
    )
    list_filter = ("is_active", "pinned_at")
    search_fields = ("pinned_by_username",)
    list_select_related = (
        "conversation",
        "message",
        "pinned_by",
    )
    
    
    
