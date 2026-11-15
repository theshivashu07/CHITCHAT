from django.db import models
from django.db.models import Q

# Create your models here.


from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    class Kind(models.TextChoices):
        DIRECT = "direct", "Direct Chat"
        GROUP = "group", "Group Chat"

    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        default=Kind.DIRECT,
    )
    title = models.CharField(max_length=150, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Conversation #{self.pk}"


class ConversationMember(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_memberships",
    )

    # Account delete hone par historical identity preserve hogi.
    username_snapshot = models.CharField(max_length=150, blank=True)

    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="uniq_conv_member",
            )
        ]

    def __str__(self):
        return f"{self.conversation_id} - {self.username_snapshot}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.PROTECT,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
    )

    # Sender ki historical identity.
    sender_username = models.CharField(max_length=150, blank=True)
    sender_display_name = models.CharField(max_length=150, blank=True)

    body = models.TextField(blank=True)
    client_message_id = models.UUIDField(
        null=True,
        blank=True,
        editable=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )

    # Delete-for-everyone: message row physically delete nahi hogi.
    deleted_for_everyone_at = models.DateTimeField(
        null=True, blank=True
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["conversation", "created_at"],
                name="msg_conv_created_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "sender", "client_message_id"],
                condition=Q(client_message_id__isnull=False),
                name="uniq_msg_client_request",
            )
        ]

    @property
    def is_deleted_for_everyone(self):
        return self.deleted_for_everyone_at is not None

    @property
    def editable_until(self):
        return self.created_at + timedelta(minutes=5)

    def can_edit(self, user):
        return (
            user.is_authenticated
            and self.sender_id == user.pk
            and not self.is_deleted_for_everyone
            and timezone.now() <= self.editable_until
        )
        
    
    @property
    def delivery_status(self):
        receipts = list(self.receipts.all())

        if not receipts:
            return "sent"

        if all(receipt.seen_at is not None for receipt in receipts):
            return "seen"

        if all(receipt.delivered_at is not None for receipt in receipts):
            return "delivered"

        return "sent"
    


    @property
    def delivered_at(self):
        receipts = list(self.receipts.all())
        timestamps = [
            receipt.delivered_at
            for receipt in receipts
            if receipt.delivered_at
        ]
        return max(timestamps, default=None)

    @property
    def seen_at(self):
        receipts = list(self.receipts.all())
        timestamps = [
            receipt.seen_at
            for receipt in receipts
            if receipt.seen_at
        ]
        return max(timestamps, default=None)

    
    def __str__(self):
        return f"Message #{self.pk}"
    
    
    
    

class MessageReceipt(models.Model):
    """Ek message ke ek recipient ki delivery/read tracking."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="message_receipts",
    )
    recipient_username = models.CharField(
        max_length=150, blank=True
    )

    delivered_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "recipient"],
                name="uniq_msg_receipt_user",
            )
        ]


class MessageUserState(models.Model):
    """Har user ke liye personal star/delete settings."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="user_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="message_states",
    )
    username_snapshot = models.CharField(
        max_length=150, blank=True
    )

    is_starred = models.BooleanField(default=False)
    starred_at = models.DateTimeField(null=True, blank=True)

    # Non-null hone par message sirf is user se hidden hoga.
    deleted_for_me_at = models.DateTimeField(
        null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"],
                name="uniq_msg_user_state",
            )
        ]


class ConversationPin(models.Model):
    """Chat members ko dikhne wala pinned message."""

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="pins",
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="pins",
    )
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    pinned_by_username = models.CharField(
        max_length=150, blank=True
    )

    pinned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "message"],
                name="uniq_conversation_pin",
            )
        ]