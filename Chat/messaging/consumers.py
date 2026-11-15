from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import Conversation, ConversationMember, Message, MessageReceipt
from .presence import is_user_online, remove_connection, touch_connection

logger = logging.getLogger(__name__)


def user_group(user_id: int) -> str:
    return f"user_{user_id}"


def validate_ids(raw_ids, limit=100):
    if not isinstance(raw_ids, list) or len(raw_ids) > limit:
        return []
    result = []
    for value in raw_ids:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            result.append(value)
    return list(dict.fromkeys(result))




class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Per-conversation socket: send new messages and mark only new activity."""


    async def connect(self):
        self.user = self.scope["user"]
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        if not self.user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self.is_conversation_member():
            await self.close(code=4403)
            return

        self.group_name = f"chat_{self.conversation_id}"
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.send_json({
                "type": "connection_established",
                "conversation_id": self.conversation_id,
            })
        except Exception:
            logger.exception("Chat WebSocket connection setup failed.")
            await self.close(code=1011)



    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            except Exception:
                logger.exception("Chat WebSocket group cleanup failed.")
                
                
                
    @database_sync_to_async
    def get_receipt_resync_updates(self, requested_statuses):
        """
        Compare frontend message statuses with the authoritative DB status.

        Return only statuses that have advanced:
        {
            "delivered": [...],
            "seen": [...]
        }
        """
        ranks = {
            "sent": 0,
            "delivered": 1,
            "seen": 2,
        }

        updates = {
            "delivered": [],
            "seen": [],
        }

        if not isinstance(requested_statuses, dict):
            return updates

        client_status_by_id = {}

        # Accept only IDs currently marked sent or delivered in the frontend.
        for client_status in ("sent", "delivered"):
            raw_ids = requested_statuses.get(client_status, [])

            if not isinstance(raw_ids, (list, tuple, set)):
                continue

            for message_id in validate_ids(raw_ids, limit=5000):
                client_status_by_id[int(message_id)] = client_status

        message_ids = list(client_status_by_id.keys())

        if not message_ids:
            return updates

        # Read the current receipt status from the database.
        rows = list(
            MessageReceipt.objects.filter(
                message_id__in=message_ids,
                message__conversation_id=self.conversation_id,
                message__sender_id=self.user.pk,
            )
            .exclude(recipient_id=self.user.pk)
            .values(
                "message_id",
                "delivered_at",
                "seen_at",
            )
        )

        # Determine the highest DB status for each message.
        db_status_by_id = {}

        for row in rows:
            message_id = row["message_id"]

            if row["seen_at"] is not None:
                db_status = "seen"
            elif row["delivered_at"] is not None:
                db_status = "delivered"
            else:
                db_status = "sent"

            existing_status = db_status_by_id.get(message_id, "sent")

            if ranks[db_status] > ranks[existing_status]:
                db_status_by_id[message_id] = db_status

        # Include only statuses that advanced beyond the frontend's status.
        for message_id, client_status in client_status_by_id.items():
            db_status = db_status_by_id.get(message_id, "sent")

            if ranks[db_status] > ranks[client_status]:
                updates[db_status].append(message_id)

        # Keep the result clean and predictable.
        updates["delivered"] = sorted(set(updates["delivered"]))
        updates["seen"] = sorted(set(updates["seen"]))

        return updates




    async def receive_json(self, content, **kwargs):
        action = content.get("type")

        if action == "send_message":
            body = content.get("body", "")

            try:
                client_message_id = uuid.UUID(
                    str(content.get("client_message_id"))
                )
            except (ValueError, TypeError, AttributeError):
                await self.send_json({
                    "type": "error",
                    "message": "Invalid message request ID.",
                })
                return

            if not isinstance(body, str) or not body.strip():
                await self.send_json({
                    "type": "error",
                    "message": "Message cannot be empty.",
                })
                return

            body = body.strip()

            if len(body) > 10000:
                await self.send_json({
                    "type": "error",
                    "message": "Message is too long.",
                })
                return

            # Save message in the database.
            try:
                saved = await self.save_message(
                    body,
                    client_message_id,
                )
            except ValueError:
                await self.send_json({
                    "type": "error",
                    "message": "You are no longer a member of this chat.",
                })
                return
            except Exception:
                logger.exception(
                    "Message database save failed. conversation_id=%s user_id=%s",
                    self.conversation_id,
                    self.user.pk,
                )
                await self.send_json({
                    "type": "error",
                    "message": "Message save failed. Please try again.",
                })
                return

            message_data = saved["message"]

            # Confirm to sender only after database save succeeds.
            await self.send_json({
                "type": "message_ack",
                "client_message_id": str(client_message_id),
                "message": message_data,
            })

            # Broadcast to users connected to this conversation.
            try:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "chat.message",
                        "payload": {
                            "type": "message",
                            "message": message_data,
                        },
                    },
                )
            except Exception:
                logger.exception(
                    "Chat broadcast failed; message remains saved. message_id=%s",
                    message_data["id"],
                )

            # Notify recipients connected elsewhere.
            for recipient_id in saved["recipient_ids"]:
                try:
                    if await is_user_online(recipient_id):
                        await self.channel_layer.group_send(
                            user_group(recipient_id),
                            {
                                "type": "user.event",
                                "payload": {
                                    "type": "new_message_notification",
                                    "message": message_data,
                                },
                            },
                        )
                except Exception:
                    logger.exception(
                        "Notification push failed. recipient_id=%s message_id=%s",
                        recipient_id,
                        message_data["id"],
                    )
            return

        if action in ("mark_delivered", "mark_seen"):
            message_id = content.get("message_id")

            if (
                not isinstance(message_id, int)
                or isinstance(message_id, bool)
                or message_id < 1
            ):
                return

            updates = await self.update_receipt_ids(
                [message_id],
                mark_seen=(action == "mark_seen"),
                conversation_id=self.conversation_id,
            )
            await self.broadcast_receipt_updates(updates)
            return
        
        
        # if action == "reconcile_active_conversation":
        #     await self.reconcile_active_conversation(content)
        #     return
        
        if action == "reconcile_active_conversation":
            updates = await self.mark_all_incoming_seen()
            await self.broadcast_receipt_updates(updates)
            return




        if action == "mark_through":
            last_message_id = content.get("last_message_id")
            status = content.get("status", "delivered")

            if (
                not isinstance(last_message_id, int)
                or isinstance(last_message_id, bool)
                or last_message_id < 1
                or status not in ("delivered", "seen")
            ):
                return

            ids = await self.incoming_receipt_ids_through(
                last_message_id
            )
            updates = await self.update_receipt_ids(
                ids,
                mark_seen=(status == "seen"),
                conversation_id=self.conversation_id,
            )
            await self.broadcast_receipt_updates(updates)



        if action == "resync_receipts":
            try:
                requested_statuses = content.get("statuses", {})
                request_id = content.get("request_id")

                updates = await self.get_receipt_resync_updates(
                    requested_statuses
                )

                # Respond only to the client that requested the resync.
                # Do not broadcast this response to other clients.
                await self.send_json({
                    "type": "receipt_resync_result",
                    "request_id": request_id,
                    "sender_id": self.user.pk,
                    "conversation_id": self.conversation_id,
                    "updates": updates,
                })

            except Exception:
                logger.exception("Receipt resync failed")

                # Always respond so the frontend can release its in-progress lock.
                await self.send_json({
                    "type": "receipt_resync_result",
                    "request_id": request_id,
                    "sender_id": self.user.pk,
                    "conversation_id": self.conversation_id,
                    "updates": {
                        "delivered": [],
                        "seen": [],
                    },
                })

            return



        return

    # batch seen handler add karo - newly added 
    async def reconcile_active_conversation(self, content):
        conversation_id = content.get("conversation_id")

        if (
            not isinstance(conversation_id, int)
            or isinstance(conversation_id, bool)
            or conversation_id != self.conversation_id
        ):
            return

        # Mark every eligible incoming receipt in this conversation as seen.
        ids = await self.incoming_receipt_ids_through(
            last_message_id=2147483647
        )
        updates = await self.update_receipt_ids(
            ids,
            mark_seen=True,
            conversation_id=self.conversation_id,
        )
        await self.broadcast_receipt_updates(updates)



    async def chat_message(self, event):
        await self.send_json(event["payload"])



    @database_sync_to_async
    def is_conversation_member(self):
        return ConversationMember.objects.filter(
            conversation_id=self.conversation_id,
            user_id=self.user.pk,
            left_at__isnull=True,
        ).exists()



    @database_sync_to_async
    def save_message(self, body, client_message_id):
        with transaction.atomic():
            conversation = Conversation.objects.filter(pk=self.conversation_id).first()
            if conversation is None or not ConversationMember.objects.filter(
                conversation_id=self.conversation_id,
                user_id=self.user.pk,
                left_at__isnull=True,
            ).exists():
                raise ValueError("Not a member.")

            display_name = self.user.get_full_name().strip() or self.user.username
            message, created = Message.objects.get_or_create(
                conversation=conversation,
                sender=self.user,
                client_message_id=client_message_id,
                defaults={
                    "sender_username": self.user.username,
                    "sender_display_name": display_name,
                    "body": body,
                },
            )

            if created:
                members = list(
                    ConversationMember.objects.filter(
                        conversation=conversation,
                        left_at__isnull=True,
                        user__isnull=False,
                    ).exclude(user_id=self.user.pk).select_related("user")
                )
                MessageReceipt.objects.bulk_create([
                    MessageReceipt(
                        message=message,
                        recipient=member.user,
                        recipient_username=member.username_snapshot or member.user.username,
                    )
                    for member in members
                ])
                recipient_ids = [member.user_id for member in members]
            else:
                recipient_ids = list(
                    MessageReceipt.objects.filter(message=message).values_list("recipient_id", flat=True)
                )

            return {
                "message": {
                    "id": message.pk,
                    "conversation_id": conversation.pk,
                    "sender_id": message.sender_id,
                    "sender_username": message.sender_username,
                    "sender_display_name": message.sender_display_name,
                    "body": "This message was deleted." if message.deleted_for_everyone_at else message.body,
                    "created_at": message.created_at.isoformat(),
                    "client_message_id": str(message.client_message_id),
                    "deleted_for_everyone": message.deleted_for_everyone_at is not None,
                },
                "recipient_ids": [uid for uid in recipient_ids if uid is not None],
            }


    @database_sync_to_async
    def incoming_receipt_ids_through(self, last_message_id):
        return list(
            MessageReceipt.objects.filter(
                recipient_id=self.user.pk,
                message__conversation_id=self.conversation_id,
                message_id__lte=last_message_id,
                seen_at__isnull=True,
            ).exclude(message__sender_id=self.user.pk).exclude(
                message__user_states__user=self.user,
                message__user_states__deleted_for_me_at__isnull=False,
            ).values_list("message_id", flat=True)
        )


    @database_sync_to_async
    def update_receipt_ids(self, message_ids, mark_seen=False, conversation_id=None):
        message_ids = validate_ids(message_ids)
        if not message_ids:
            return []
        with transaction.atomic():
            qs = MessageReceipt.objects.filter(
                recipient_id=self.user.pk,
                message_id__in=message_ids,
            ).exclude(message__sender_id=self.user.pk)
            if conversation_id is not None:
                qs = qs.filter(message__conversation_id=conversation_id)

            rows = list(qs.values(
                "message_id", "message__sender_id", "message__conversation_id",
                "delivered_at", "seen_at",
            ))
            now = timezone.now()
            if mark_seen:
                changed_ids = [row["message_id"] for row in rows if row["seen_at"] is None]
                if not changed_ids:
                    return []
                qs.filter(message_id__in=changed_ids, delivered_at__isnull=True).update(delivered_at=now)
                qs.filter(message_id__in=changed_ids, seen_at__isnull=True).update(seen_at=now)
                final_status = "seen"
            else:
                changed_ids = [row["message_id"] for row in rows if row["delivered_at"] is None and row["seen_at"] is None]
                if not changed_ids:
                    return []
                qs.filter(message_id__in=changed_ids, delivered_at__isnull=True).update(delivered_at=now)
                final_status = "delivered"

            groups = defaultdict(list)
            changed_set = set(changed_ids)
            for row in rows:
                mid = row["message_id"]
                if mid not in changed_set:
                    continue
                status = "seen" if final_status == "seen" or row["seen_at"] is not None else "delivered"
                groups[(row["message__sender_id"], row["message__conversation_id"], status)].append(mid)

            return [
                {
                    "sender_id": sender_id,
                    "conversation_id": conv_id,
                    "status": status,
                    "message_ids": sorted(ids),
                    "last_message_id": max(ids),
                    "recipient_id": self.user.pk,
                    "timestamp": now.isoformat(),
                }
                for (sender_id, conv_id, status), ids in groups.items()
                if sender_id is not None
            ]



    # @database_sync_to_async
    # def mark_all_incoming_seen(self):
    #     with transaction.atomic():
    #         now = timezone.now()

    #         receipts = MessageReceipt.objects.filter(
    #             recipient_id=self.user.pk,
    #             message__conversation_id=self.conversation_id,
    #             seen_at__isnull=True,
    #         ).exclude(
    #             message__sender_id=self.user.pk
    #         ).exclude(
    #             message__user_states__user=self.user,
    #             message__user_states__deleted_for_me_at__isnull=False,
    #         )

    #         rows = list(
    #             receipts.values(
    #                 "message_id",
    #                 "message__sender_id",
    #                 "message__conversation_id",
    #             )
    #         )

    #         if not rows:
    #             return []

    #         receipts.filter(delivered_at__isnull=True).update(
    #             delivered_at=now
    #         )
    #         receipts.update(seen_at=now)

    #         groups = defaultdict(list)
    #         for row in rows:
    #             groups[
    #                 (
    #                     row["message__sender_id"],
    #                     row["message__conversation_id"],
    #                 )
    #             ].append(row["message_id"])

    #         return [
    #             {
    #                 "sender_id": sender_id,
    #                 "conversation_id": conv_id,
    #                 "status": "seen",
    #                 "message_ids": sorted(ids),
    #                 "last_message_id": max(ids),
    #                 "recipient_id": self.user.pk,
    #                 "timestamp": now.isoformat(),
    #             }
    #             for (sender_id, conv_id), ids in groups.items()
    #             if sender_id is not None
    #         ]

    
    @database_sync_to_async
    def mark_all_incoming_seen(self):
        with transaction.atomic():
            now = timezone.now()

            receipts = MessageReceipt.objects.filter(
                recipient_id=self.user.pk,
                message__conversation_id=self.conversation_id,
            ).exclude(
                message__sender_id=self.user.pk
            ).exclude(
                message__user_states__user=self.user,
                message__user_states__deleted_for_me_at__isnull=False,
            )

            rows = list(
                receipts.values(
                    "pk",
                    "message_id",
                    "message__sender_id",
                    "message__conversation_id",
                ).distinct()
            )

            if not rows:
                return []

            receipt_pks = list({
                row["pk"] for row in rows
            })

            MessageReceipt.objects.filter(
                pk__in=receipt_pks,
                delivered_at__isnull=True,
            ).update(delivered_at=now)

            MessageReceipt.objects.filter(
                pk__in=receipt_pks,
                seen_at__isnull=True,
            ).update(seen_at=now)

            groups = defaultdict(set)

            for row in rows:
                sender_id = row["message__sender_id"]
                conversation_id = row["message__conversation_id"]

                if sender_id is not None:
                    groups[
                        (sender_id, conversation_id)
                    ].add(row["message_id"])

            return [
                {
                    "sender_id": sender_id,
                    "conversation_id": conversation_id,
                    "status": "seen",
                    "message_ids": sorted(message_ids),
                    "last_message_id": max(message_ids),
                    "recipient_id": self.user.pk,
                    "timestamp": now.isoformat(),
                }
                for (sender_id, conversation_id), message_ids
                in groups.items()
            ]



    async def broadcast_receipt_updates(self, updates):
        for item in updates:
            try:
                await self.channel_layer.group_send(
                    user_group(item["sender_id"]),
                    {"type": "user.event", "payload": {"type": "receipt_batch_update", **item}},
                )
            except Exception:
                logger.exception("Receipt event broadcast failed for messages %s", item["message_ids"])
        if any(item["status"] == "seen" for item in updates):
            try:
                await self.channel_layer.group_send(
                    user_group(self.user.pk),
                    {"type": "user.event", "payload": {"type": "refresh_unread_counts"}},
                )
            except Exception:
                logger.exception("Unread-count refresh broadcast failed for user %s", self.user.pk)



class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """One user-level socket per authenticated page for notifications and presence."""

    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_group_name = user_group(self.user.pk)
        self.presence_connection_id = uuid.uuid4().hex
        await self.accept()
        try:
            await self.channel_layer.group_add(self.user_group_name, self.channel_name)
            await touch_connection(self.user.pk, self.presence_connection_id)
        except Exception:
            logger.exception("Notification socket setup/presence failed for user %s", self.user.pk)
        await self.send_json({"type": "connection_established"})
        await self.send_unread_counts()
        await self.send_pending_notifications()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group_name"):
            try:
                await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
            except Exception:
                logger.exception("Notification group cleanup failed.")
        if hasattr(self, "presence_connection_id") and getattr(self, "user", None) and self.user.is_authenticated:
            try:
                await remove_connection(self.user.pk, self.presence_connection_id)
            except Exception:
                logger.exception("Presence cleanup failed for user %s", self.user.pk)

    async def receive_json(self, content, **kwargs):
        action = content.get("type")
        if action == "heartbeat":
            try:
                # A suspended browser can miss heartbeats without closing its socket.
                # If its TTL expired, refresh presence and replay durable pending notifications.
                was_online = await is_user_online(self.user.pk)
                await touch_connection(self.user.pk, self.presence_connection_id)
                if not was_online:
                    await self.send_unread_counts()
                    await self.send_pending_notifications()
            except Exception:
                logger.exception("Presence heartbeat failed for user %s", self.user.pk)
            return

        if action == "request_unread_counts":
            await self.send_unread_counts()
            return

        if action in ("mark_delivered", "mark_seen"):
            message_id = content.get("message_id")
            if not isinstance(message_id, int) or isinstance(message_id, bool) or message_id < 1:
                return
            updates = await self.update_receipt_ids([message_id], mark_seen=(action == "mark_seen"))
            await self.broadcast_receipt_updates(updates)
            return

        if action == "acknowledge_notifications":
            message_ids = validate_ids(content.get("message_ids"), limit=100)
            updates = await self.update_receipt_ids(message_ids, mark_seen=False)
            await self.broadcast_receipt_updates(updates)
            await self.send_pending_notifications()

    async def user_event(self, event):
        payload = event["payload"]
        if payload.get("type") == "refresh_unread_counts":
            await self.send_unread_counts()
            return
        await self.send_json(payload)

    async def send_unread_counts(self):
        counts, total = await self.get_unread_counts()
        await self.send_json({"type": "unread_counts", "counts": counts, "total": total})

    async def send_pending_notifications(self):
        pending = await self.get_pending_notifications()
        if pending:
            await self.send_json({"type": "pending_notifications", "messages": pending})

    @database_sync_to_async
    def get_unread_counts(self):
        rows = list(
            MessageReceipt.objects.filter(
                recipient_id=self.user.pk,
                seen_at__isnull=True,
            ).exclude(message__sender_id=self.user.pk)
            .exclude(
                message__user_states__user=self.user,
                message__user_states__deleted_for_me_at__isnull=False,
            )
            .values("message__conversation_id")
            .annotate(unread_count=Count("pk"))
            .order_by()
        )
        counts = {str(row["message__conversation_id"]): row["unread_count"] for row in rows}
        return counts, sum(counts.values())

    @database_sync_to_async
    def get_pending_notifications(self):
        receipts = (
            MessageReceipt.objects.filter(
                recipient_id=self.user.pk,
                delivered_at__isnull=True,
            ).exclude(message__sender_id=self.user.pk)
            .exclude(
                message__user_states__user=self.user,
                message__user_states__deleted_for_me_at__isnull=False,
            )
            .select_related("message", "message__sender")
            .order_by("message_id")[:100]
        )
        payload = []
        for receipt in receipts:
            message = receipt.message
            payload.append({
                "id": message.pk,
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "sender_username": message.sender_username,
                "sender_display_name": message.sender_display_name,
                "body": "This message was deleted." if message.deleted_for_everyone_at else message.body,
                "created_at": message.created_at.isoformat(),
                "client_message_id": str(message.client_message_id) if message.client_message_id else None,
                "deleted_for_everyone": message.deleted_for_everyone_at is not None,
            })
        return payload

    @database_sync_to_async
    def update_receipt_ids(self, message_ids, mark_seen=False, conversation_id=None):
        message_ids = validate_ids(message_ids)
        if not message_ids:
            return []
        with transaction.atomic():
            qs = MessageReceipt.objects.filter(
                recipient_id=self.user.pk,
                message_id__in=message_ids,
            ).exclude(message__sender_id=self.user.pk)
            if conversation_id is not None:
                qs = qs.filter(message__conversation_id=conversation_id)
            rows = list(qs.values(
                "message_id", "message__sender_id", "message__conversation_id",
                "delivered_at", "seen_at",
            ))
            now = timezone.now()
            if mark_seen:
                changed_ids = [row["message_id"] for row in rows if row["seen_at"] is None]
                if not changed_ids:
                    return []
                qs.filter(message_id__in=changed_ids, delivered_at__isnull=True).update(delivered_at=now)
                qs.filter(message_id__in=changed_ids, seen_at__isnull=True).update(seen_at=now)
                final_status = "seen"
            else:
                changed_ids = [row["message_id"] for row in rows if row["delivered_at"] is None and row["seen_at"] is None]
                if not changed_ids:
                    return []
                qs.filter(message_id__in=changed_ids, delivered_at__isnull=True).update(delivered_at=now)
                final_status = "delivered"
            changed_set = set(changed_ids)
            groups = defaultdict(list)
            for row in rows:
                mid = row["message_id"]
                if mid not in changed_set:
                    continue
                status = "seen" if final_status == "seen" or row["seen_at"] is not None else "delivered"
                groups[(row["message__sender_id"], row["message__conversation_id"], status)].append(mid)
            return [
                {
                    "sender_id": sender_id,
                    "conversation_id": conv_id,
                    "status": status,
                    "message_ids": sorted(ids),
                    "last_message_id": max(ids),
                    "recipient_id": self.user.pk,
                    "timestamp": now.isoformat(),
                }
                for (sender_id, conv_id, status), ids in groups.items()
                if sender_id is not None
            ]

    async def broadcast_receipt_updates(self, updates):
        for item in updates:
            try:
                await self.channel_layer.group_send(
                    user_group(item["sender_id"]),
                    {"type": "user.event", "payload": {"type": "receipt_batch_update", **item}},
                )
            except Exception:
                logger.exception("Receipt event broadcast failed for messages %s", item["message_ids"])
        if any(item["status"] == "seen" for item in updates):
            try:
                await self.channel_layer.group_send(
                    user_group(self.user.pk),
                    {"type": "user.event", "payload": {"type": "refresh_unread_counts"}},
                )
            except Exception:
                logger.exception("Unread-count refresh broadcast failed for user %s", self.user.pk)
