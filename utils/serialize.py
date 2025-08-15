from neonize.utils import build_jid, get_message_type

class Mess:
    def __init__(self, client, message):
        self.client = client
        self.message = message
        self.info = message.Info  # bukan self.message.Info
        self.source = self.info.MessageSource  # bukan self.Info
        self.get_msg_type = get_message_type(message)
        self.sender = self.source.Sender
        self.sender_alt = self.source.SenderAlt
        self.chat = self.source.Chat
        self.from_me = self.source.IsFromMe
        self.is_group = self.source.IsGroup or self.chat.Server == "g.us"
        self.id = self.info.ID

    @classmethod
    async def create(cls, client, message):
        return cls(client, message)
        

    async def reply(self, text):
        await self.client.reply_message(str(text), self.message)