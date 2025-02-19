import base64
import json
import typing

from channels.db import database_sync_to_async

from common.consumers import CommonConsumer
from messenger.services import (
    create_chat,
    create_message,
    edit_message,
    get_chat,
    get_chats,
    get_current_user,
    get_message,
    get_messages_in_chat,
    get_new_chat_entity,
    mark_chat,
    mark_message,
    set_user_offline,
)


class MessengerConsumer(CommonConsumer):
    chats: typing.List[str]
    user: "User"

    async def connect(self):
        self.chats = []
        await self.accept()

    async def disconnect(self, close_code):
        from users.serializers import UserDefaultSerializer

        if not hasattr(self, "user"):
            return

        self.user = await database_sync_to_async(set_user_offline)(self.user)
        for chat in self.chats:
            await self.channel_layer.group_send(
                chat, {"type": "user_offline", "user": UserDefaultSerializer(instance=self.user).data}
            )
            await self.channel_layer.group_discard(chat, self.channel_name)

    async def create_group(self, user_id: int):
        self.user = await database_sync_to_async(get_current_user)(user_id, True)
        await self.channel_layer.group_add(f"user_{self.user.id}_messenger", self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        data = json.loads(text_data)
        type_ = data.get("type")

        match type_:
            case "authenticate":
                await self.authenticate(data.get("token"), data.get("user_id"))
            case "connect_to_chats":
                await self.connect_to_chats()
            case "get_chat_history":
                await self.get_chat_history(data)
            case "start_chat":
                await self.start_chat(data)
            case "send_message":
                await self.send_message(data)
            case "read_chat":
                chat = await self.mark_as(data, mark_chat, is_read=True)
                await self.channel_layer.group_send(
                    f"chat_{chat.pk}",  # noqa
                    {
                        "type": "send_read_chat",
                        "chat": chat.id,
                    },
                )
            case "delete_message":
                message = await self.mark_as(data, mark_message, is_delete=True)
                await self.send(text_data=json.dumps({"success": True}))
                await self.channel_layer.group_send(
                    f"chat_{message.chat.pk}",  # noqa
                    {
                        "type": "send_delete_message",
                        "message": message.id,
                    },
                )
            case "edit_message":
                message = await self.edit_message(data)
                await self.send(text_data=json.dumps({"success": True}))
                await self.channel_layer.group_send(
                    f"chat_{message.chat.id}", {"type": "send_edit_message", "message": message.id}
                )
            case "delete_chat":
                chat = await self.mark_as(data, mark_chat, is_delete=True)
                await self.send(text_data=json.dumps({"success": True}))
                await self.channel_layer.group_send(
                    f"chat_{chat.pk}",  # noqa
                    {
                        "type": "send_delete_chat",
                        "chat": chat.id,
                    },
                )

    async def send_read_chat(self, event):
        await self.send(text_data=json.dumps({"type": "send_read_chat", "chat": event["chat"]}))

    async def send_delete_message(self, event):
        from messenger.serializers import ChatSerializer

        new_chat_entity = await database_sync_to_async(get_new_chat_entity)(event["message"])
        await self.send(
            text_data=json.dumps(
                {
                    "type": "send_delete_message",
                    "message": event["message"],
                    "chat": await database_sync_to_async(
                        lambda: ChatSerializer(instance=new_chat_entity, context={"user": self.user}).data
                    )(),
                }
            )
        )

    async def send_edit_message(self, event):
        from messenger.serializers import MessageSerializer

        message = await database_sync_to_async(get_message)(event["message"])
        await self.send(
            text_data=json.dumps(
                {
                    "type": "send_edit_message",
                    "message": MessageSerializer(instance=message, context={"user": self.user}).data,
                }
            )
        )

    async def send_delete_chat(self, event):
        await self.send(text_data=json.dumps({"type": "send_delete_chat", "chat": event["chat"]}))

    async def connect_to_chats(self):
        from messenger.serializers import ChatSerializer
        from users.serializers import UserDefaultSerializer

        chats = await database_sync_to_async(get_chats)(self.user)

        for chat in chats:
            self.chats.append(f"chat_{chat.id}")
            await self.channel_layer.group_add(f"chat_{chat.id}", self.channel_name)
            await self.channel_layer.group_send(
                f"chat_{chat.id}", {"type": "user_online", "user": UserDefaultSerializer(instance=self.user).data}
            )

        payload = await database_sync_to_async(
            lambda: ChatSerializer(chats, many=True, context={"user": self.user}).data
        )()

        await self.send(text_data=json.dumps({"type": "connect_to_chats", "payload": payload}))

    async def user_online(self, event):
        if self.user.id != event["user"]["id"]:
            await self.send(text_data=json.dumps({"type": "user_online", "user": event["user"]}))

    async def user_offline(self, event):
        if self.user.id != event["user"]["id"]:
            await self.send(text_data=json.dumps({"type": "user_offline", "user": event["user"]}))

    async def get_chat_history(self, data: dict):
        from messenger.serializers import MessageSerializer

        chat = data["chat"]
        messages = await database_sync_to_async(get_messages_in_chat)(chat)
        payload = MessageSerializer(messages, many=True, context={"user": self.user}).data
        await self.send(text_data=json.dumps({"type": "get_chat_history", "chat": chat, "payload": payload}))

    async def start_chat(self, data: dict):
        from messenger.serializers import ChatSerializer

        chat, receiver = await database_sync_to_async(create_chat)(data["receiver"], self.user)

        if not chat and not receiver:
            await self.send(
                text_data=json.dumps({"type": "chat_started", "payload": {"error_get_user": data["receiver"]}})
            )
            return

        self.chats.append(f"chat_{chat.id}")
        await self.channel_layer.group_add(f"chat_{chat.id}", self.channel_name)
        await self.channel_layer.group_send(
            f"user_{receiver.id}_messenger", {"type": "connect_to_chat", "chat": chat.id}
        )
        payload = await database_sync_to_async(
            lambda: ChatSerializer(instance=chat, context={"user": self.user}).data
        )()
        await self.send(text_data=json.dumps({"type": "chat_started", "payload": payload}))

    async def connect_to_chat(self, event):
        from messenger.serializers import ChatSerializer

        chat = event["chat"]
        self.chats.append(f"chat_{chat}")
        await self.channel_layer.group_add(f"chat_{chat}", self.channel_name)
        chat = await database_sync_to_async(get_chat)(chat)
        payload = await database_sync_to_async(lambda: ChatSerializer(chat, context={"user": self.user}).data)()
        await self.send(text_data=json.dumps({"type": "connect_to_chat", "payload": payload}))

    async def send_message(self, data: dict):
        chat_id = data["chat_id"]
        receiver = data["receiver"]
        body = data.get("body", None)
        attachment = base64.b64decode(data["attachment"]) if data.get("attachment", None) else None
        name = data.get("attachment_name", None)
        message = await database_sync_to_async(create_message)(chat_id, receiver, body, attachment, name, self.user)
        await self.send(text_data=json.dumps({"success": True}))
        await self.channel_layer.group_send(
            f"chat_{chat_id}",
            {
                "type": "on_message",
                "message": message.id,
            },
        )

    async def edit_message(self, data: dict):
        message = data["message"]
        body = data["body"]
        attachment = base64.b64decode(data["attachment"]) if data.get("attachment", None) else None
        name = data.get("attachment_name", None)
        return await database_sync_to_async(edit_message)(message, body, attachment, name)

    async def on_message(self, event: dict):
        from messenger.serializers import MessageSerializer

        message = await database_sync_to_async(get_message)(event["message"])
        payload = MessageSerializer(instance=message, context={"user": self.user}).data
        await self.send(text_data=json.dumps({"type": "on_message", "payload": payload}))

    async def mark_as(self, data: dict, callback: typing.Callable, **kwargs):
        pk = data["id"]
        return await database_sync_to_async(callback)(pk, **kwargs)
