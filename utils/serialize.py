from neonize.utils import build_jid, get_message_type


class Mess:
    def __init__(self, client, message, user):
        self.client = client
        self.message = message
        self.user = user
        self.get_msg_type = get_message_type(message)
        self.sender = message.Info.MessageSource.Sender
        self.senderAlt = message.Info.MessageSource.SenderAlt
        self.chat = message.Info.MessageSource.Chat
        self.from_me = message.Info.MessageSource.IsFromMe
        self.is_group = message.Info.MessageSource.IsGroup or self.chat.Server == "g.us"
        self.id = message.Info.ID

    @classmethod
    async def create(cls, client, message):
        user = await client.get_me()
        return cls(client, message, user)

    async def reply(self, text):
        await self.client.reply_message(text.__str__(), self.message)
