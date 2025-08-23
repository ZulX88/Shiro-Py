from neonize.utils import build_jid, get_message_type
from neonize.aioze.client import NewAClient

class QuotedMess:
    def __init__(self, client: NewAClient,context_info):
        self.client = client
        self.context_info = context_info
        self.message = context_info.quotedMessage
        self.sender = self.context_info.participant
        self.id = self.context_info.stanzaID

    @property
    def text(self) -> str:
        msg_fields = self.context_info.quotedMessage.ListFields()
        if msg_fields:
            _, field_value = msg_fields[0]
            if isinstance(field_value, str):
                return field_value
            text_attrs = ["text", "caption", "name"]
            for attr in text_attrs:
                if hasattr(field_value, attr):
                    return getattr(field_value, attr)
        return ""

    async def reply(self, text):
        return await self.client.reply_message(text, self.message)

    async def download(self):
        return await self.client.download_any(self.context_info.quotedMessage)

    @property
    def mentioned_jid(self) -> list[str]:
        msg_fields = self.context_info.quotedMessage.ListFields()
        if msg_fields:
            _, field_value = msg_fields[0]
            if hasattr(field_value, "contextInfo"):
                return getattr(field_value, "contextInfo").mentionedJID
        return []

class Mess:
    def __init__(self, client: NewAClient, message):
        self.client = client
        self.message = message
        self.info = message.Info
        self.source = self.info.MessageSource
        self.get_msg_type = get_message_type(message)
        self.sender = self.source.Sender
        self.sender_alt = self.source.SenderAlt
        self.chat = self.source.Chat
        self.from_me = self.source.IsFromMe
        self.is_group = self.source.IsGroup or self.chat.Server == "g.us"
        self.id = self.info.ID
        self.pushname = self.info.Pushname

    @property
    def text(self) -> str:
        msg_fields = self.message.Message.ListFields()
        if msg_fields:
            _, field_value = msg_fields[0]
            if isinstance(field_value, str):
                return field_value
            text_attrs = ["text", "caption", "name"]
            for attr in text_attrs:
                if hasattr(field_value, attr):
                    return getattr(field_value, attr)
        return ""

    async def reply(self, text):
        return await self.client.reply_message(text, self.message)

    async def download(self):
        return await self.client.download_any(self.message.Message)

    @property
    def quoted(self) -> QuotedMess | None:
        if msg_fields := self.message.Message.ListFields():
            _, field_value = msg_fields[0]
            if hasattr(field_value, "contextInfo"):
                context_info = getattr(field_value, "contextInfo")
                if hasattr(context_info, "quotedMessage"):
                    return QuotedMess(self.client, context_info)
        return None

    @property
    def mentioned_jid(self) -> list[str]:
        msg_fields = self.message.Message.ListFields()
        if msg_fields:
            _, field_value = msg_fields[0]
            if hasattr(field_value, "contextInfo"):
                return getattr(field_value, "contextInfo").mentionedJID
        return []