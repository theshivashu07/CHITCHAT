from django.contrib import messages as flash_messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Conversation,
    ConversationMember,
    Message,
    MessageReceipt,
)

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from django.db.models import Max
from django.utils import timezone


from collections import defaultdict
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Q





User = get_user_model()




@login_required
def inbox(request):
    
    '''
    memberships = (
        ConversationMember.objects
        .filter(user=request.user, left_at__isnull=True)
        .select_related("conversation")
        .order_by("-conversation__created_at")
    )
    '''
    memberships = (
        ConversationMember.objects
        .filter(user=request.user, left_at__isnull=True)
        .select_related("conversation")
        .annotate(
            unread_count=Count(
                "conversation__messages__receipts",
                filter=(
                    Q(
                        conversation__messages__receipts__recipient_id=request.user.pk,
                        conversation__messages__receipts__seen_at__isnull=True,
                    )
                    & ~Q(conversation__messages__sender_id=request.user.pk)
                ),
                distinct=True,
            )
        )
        .order_by("-conversation__created_at")
    )

    other_users = (
        User.objects
        .filter(is_active=True)
        .exclude(pk=request.user.pk)
        .order_by("username")
    )

    return render(
        request,
        "messaging/inbox.html",
        {
            "memberships": memberships,
            "other_users": other_users,
        },
    )


@login_required
@require_POST
def start_direct_chat(request, user_id):
    other_user = get_object_or_404(
        User,
        pk=user_id,
        is_active=True,
    )

    if other_user.pk == request.user.pk:
        flash_messages.error(
            request,
            "You cannot start a chat with yourself.",
        )
        return redirect("messaging:inbox")

    with transaction.atomic():
        conversation = (
            Conversation.objects
            .filter(kind=Conversation.Kind.DIRECT)
            .filter(
                members__user=request.user,
                members__left_at__isnull=True,
            )
            .filter(
                members__user=other_user,
                members__left_at__isnull=True,
            )
            .first()
        )

        if conversation is None:
            conversation = Conversation.objects.create(
                kind=Conversation.Kind.DIRECT,
                created_by=request.user,
            )

            ConversationMember.objects.bulk_create([
                ConversationMember(
                    conversation=conversation,
                    user=request.user,
                    username_snapshot=request.user.username,
                ),
                ConversationMember(
                    conversation=conversation,
                    user=other_user,
                    username_snapshot=other_user.username,
                ),
            ])

    return redirect(
        "messaging:conversation_detail",
        conversation_id=conversation.pk,
    )


@login_required
def conversation_detail(request, conversation_id):
    
    conversation = get_object_or_404(
        Conversation.objects.filter(
            members__user=request.user,
            members__left_at__isnull=True,
        ).distinct(),
        pk=conversation_id,
    )

    if request.method == "POST":
        body = request.POST.get("body", "").strip()

        if not body:
            flash_messages.error(request, "Message cannot be empty.")
        else:
            with transaction.atomic():
                message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    sender_username=request.user.username,
                    sender_display_name=(
                        request.user.get_full_name().strip()
                        or request.user.username
                    ),
                    body=body,
                )

                recipients = (
                    ConversationMember.objects
                    .filter(
                        conversation=conversation,
                        left_at__isnull=True,
                    )
                    .exclude(user=request.user)
                    .exclude(user__isnull=True)
                    .select_related("user")
                )

                MessageReceipt.objects.bulk_create([
                    MessageReceipt(
                        message=message,
                        recipient=member.user,
                        recipient_username=(
                            member.username_snapshot
                            or member.user.username
                        ),
                    )
                    for member in recipients
                ])

            # Delivery/seen timestamps abhi set nahi kar rahe.
            # Actual acknowledgements agle real-time step me aayenge.

        return redirect(
            "messaging:conversation_detail",
            conversation_id=conversation.pk,
        )
        
    
    incoming_receipts = (
        MessageReceipt.objects
        .filter(
            message__conversation=conversation,
            recipient=request.user,
            message__sender__isnull=False,
            seen_at__isnull=True,
        )
        .exclude(message__sender=request.user)
        .exclude(
            message__user_states__user=request.user,
            message__user_states__deleted_for_me_at__isnull=False,
        )
    )

    last_seen_message_id = incoming_receipts.aggregate(
        last_id=Max("message_id")
    )["last_id"]

    if last_seen_message_id is not None:
        now = timezone.now()

        incoming_receipts.filter(
            delivered_at__isnull=True
        ).update(delivered_at=now)

        incoming_receipts.update(seen_at=now)
    
    
    mark_conversation_seen(request, conversation)


    """
    chat_messages = (
        Message.objects
        .filter(conversation=conversation)
        .exclude(
            user_states__user=request.user,
            user_states__deleted_for_me_at__isnull=False,
        )
        .order_by("created_at")
    )
    """
    
    chat_messages = (
        Message.objects
        .filter(conversation=conversation)
        .exclude(
            user_states__user=request.user,
            user_states__deleted_for_me_at__isnull=False,
        )
        .prefetch_related("receipts")
        .order_by("created_at")
    )



    members = (
        ConversationMember.objects
        .filter(
            conversation=conversation,
            left_at__isnull=True,
        )
        .exclude(user=request.user)
    )

    return render(
        request,
        "messaging/conversation_detail.html",
        {
            "conversation": conversation,
            "chat_messages": chat_messages,
            "members": members,
        },
    )
    
    

    
    
    
@login_required
@require_GET
def sync_messages(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.filter(
            members__user=request.user,
            members__left_at__isnull=True,
        ).distinct(),
        pk=conversation_id,
    )

    try:
        after_id = max(0, int(request.GET.get("after_id", "0")))
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid after_id."},
            status=400,
        )

    messages_qs = (
        Message.objects
        .filter(
            conversation=conversation,
            pk__gt=after_id,
        )
        .exclude(
            user_states__user=request.user,
            user_states__deleted_for_me_at__isnull=False,
        )
        .select_related("sender")
        .order_by("pk")[:200]
    )

    results = []

    for message in messages_qs:
        deleted = message.deleted_for_everyone_at is not None

        results.append({
            "id": message.pk,
            "conversation_id": conversation.pk,
            "sender_id": message.sender_id,
            "sender_username": message.sender_username,
            "sender_display_name": message.sender_display_name,
            "body": (
                "This message was deleted."
                if deleted else message.body
            ),
            "created_at": message.created_at.isoformat(),
            "client_message_id": (
                str(message.client_message_id)
                if message.client_message_id else None
            ),
            "deleted_for_everyone": deleted,
        })

    return JsonResponse({
        "messages": results,
        "has_more": len(results) == 200,
    })
    
    


def mark_conversation_seen(request, conversation):
    """Batch-mark unseen incoming messages and emit one event per sender."""
    with transaction.atomic():
        pending = MessageReceipt.objects.filter(
            recipient=request.user,
            message__conversation=conversation,
            seen_at__isnull=True,
        ).exclude(message__sender=request.user).exclude(
            message__user_states__user=request.user,
            message__user_states__deleted_for_me_at__isnull=False,
        )
        rows = list(pending.values("message_id", "message__sender_id"))
        if not rows:
            return

        message_ids = [row["message_id"] for row in rows]
        now = timezone.now()
        pending.filter(delivered_at__isnull=True).update(delivered_at=now)
        pending.update(seen_at=now)

    ids_by_sender = defaultdict(list)
    for row in rows:
        if row["message__sender_id"] is not None:
            ids_by_sender[row["message__sender_id"]].append(row["message_id"])

    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{request.user.pk}",
            {"type": "user.event", "payload": {"type": "refresh_unread_counts"}},
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Could not refresh unread counts for user %s", request.user.pk
        )

    for sender_id, ids in ids_by_sender.items():
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{sender_id}",
                {
                    "type": "user.event",
                    "payload": {
                        "type": "receipt_batch_update",
                        "sender_id": sender_id,
                        "recipient_id": request.user.pk,
                        "conversation_id": conversation.pk,
                        "status": "seen",
                        "message_ids": ids,
                        "last_message_id": max(ids),
                        "timestamp": now.isoformat(),
                    },
                },
            )
        except Exception:
            # DB state remains correct; next page load still renders the saved status.
            import logging
            logging.getLogger(__name__).exception(
                "Could not broadcast seen batch for conversation %s", conversation.pk
            )



