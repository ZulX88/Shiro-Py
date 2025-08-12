from neonize.utils import build_jid, get_message_type
from typerist.message import Messages

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
        instance = cls(client, message)  # simpan instance
        return Messages(  # tambahkan field yang kurang
            chat=instance.chat,
            id=instance.id,
            sender=instance.sender,
            sender_alt=instance.sender_alt,
            pushname="",  # tambahkan field yang diperlukan
            is_group=instance.is_group,
            mentioned_jid=[],  # tambahkan field yang diperlukan
            message=message  # tambahkan field yang diperlukan
        )

    async def reply(self, text):
        await self.client.reply_message(str(text), self.message)