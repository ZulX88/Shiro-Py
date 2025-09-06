# utils/serialize.py

from neonize.utils import get_message_type
from neonize.aioze.client import NewAClient
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message as RawMessage
from typing import Optional, List


class QuotedMess:
    def __init__(self, client: NewAClient, context_info):
        self.client = client
        self.context_info = context_info
        self.message = context_info.quotedMessage
        self.sender = self.context_info.participant
        self.id = self.context_info.stanzaID

        # Handle viewOnceMessage
        if self.message.HasField("viewOnceMessage"):
            self.message = self.message.viewOnceMessage.message
        elif self.message.HasField("viewOnceMessageV2"):
            self.message = self.message.viewOnceMessageV2.message

    @property
    def text(self) -> str:
        msg_fields = self.message.ListFields()
        if msg_fields:
            _, field_value = msg_fields[0]
            if isinstance(field_value, str):
                return field_value
            text_attrs = ["text", "caption", "name", "conversation"]
            for attr in text_attrs:
                if hasattr(field_value, attr):
                    val = getattr(field_value, attr)
                    if isinstance(val, str) and val.strip():
                        return val
        return ""

    @property
    def is_media(self) -> bool:
        msg_fields = self.message.ListFields()
        if not msg_fields:
            return False
        field_name = msg_fields[0][0].name
        return field_name in (
            "imageMessage", "videoMessage", "audioMessage",
            "documentMessage", "stickerMessage", "contactMessage",
            "locationMessage", "liveLocationMessage"
        )

    @property
    def media_type(self) -> Optional[str]:
        if not self.is_media:
            return None
        msg_fields = self.message.ListFields()
        if not msg_fields:  # guard tambahan biar aman
            return None
        field_name = msg_fields[0][0].name
        return field_name.replace("Message", "")

    async def reply(self, text):
        if not isinstance(text, str):
            if isinstance(text, (list, tuple)):
                text = ", ".join(map(str, text))
            else:
                text = str(text)
        return await self.client.reply_message(text, self.message)

    async def download(self):
        return await self.client.download_any(self.message)

    @property
    def media_info(self) -> dict:
        msg_fields = self.message.ListFields()
        if not msg_fields:
            return {}

        field_desc, field_value = msg_fields[0]
        media_type = field_desc.name.replace("Message", "")

        info = {
            "type": media_type,
            # Umum
            "seconds": getattr(field_value, "seconds", None),
            "caption": getattr(field_value, "caption", None),
            "mimetype": getattr(field_value, "mimetype", None),
            "fileLength": getattr(field_value, "fileLength", None),
            "height": getattr(field_value, "height", None),
            "width": getattr(field_value, "width", None),
            "fileName": getattr(field_value, "fileName", None),
            "isAnimated": getattr(field_value, "isAnimated", None),
            "pageCount": getattr(field_value, "pageCount", None),
            "jpegThumbnail": getattr(field_value, "JPEGThumbnail", None),

            # Enkripsi & Download
            "mediaKey": getattr(field_value, "mediaKey", None),
            "fileSHA256": getattr(field_value, "fileSHA256", None),
            "fileEncSHA256": getattr(field_value, "fileEncSHA256", None),
            "directPath": getattr(field_value, "directPath", None),
            "URL": getattr(field_value, "URL", None),
            "mediaKeyTimestamp": getattr(field_value, "mediaKeyTimestamp", None),

            # Tambahan khusus
            "streamingSidecar": getattr(field_value, "streamingSidecar", None),
            "scansSidecar": getattr(field_value, "scansSidecar", None),
            "scanLengths": list(getattr(field_value, "scanLengths", [])) or None,
            "midQualityFileSHA256": getattr(field_value, "midQualityFileSHA256", None),
            "externalShareFullVideoDurationInSeconds": getattr(field_value, "externalShareFullVideoDurationInSeconds", None),
            "contextInfo": getattr(field_value, "contextInfo", None),
        }

        return {k: v for k, v in info.items() if v is not None}

    @property
    def mentioned_jid(self) -> List[str]:
        msg = self.message
        msg_fields = msg.ListFields()
        if not msg_fields:
            return []

        _, field_value = msg_fields[0]
        field_name = msg_fields[0][0].name
        if field_name in ("stickerMessage", "locationMessage"):
            return []

        if not hasattr(field_value, "contextInfo"):
            return []

        context_info = field_value.contextInfo
        mentioned_jid_list = getattr(context_info, "mentionedJID", [])
        return list(mentioned_jid_list) if mentioned_jid_list else []


class Mess:
    def __init__(self, client: NewAClient, message):
        self.client = client
        self.message = message  # Neonize_pb2.Message
        self.info = message.Info
        self.source = self.info.MessageSource
        self.get_msg_type = get_message_type(message)
        self.sender = self.source.Sender
        self.sender_alt = getattr(self.source, "SenderAlt", None)
        self.chat = self.source.Chat
        self.from_me = self.source.IsFromMe
        self.is_group = self.source.IsGroup or self.chat.Server == "g.us"
        self.addressing = "LID" if self.source.AddressingMode == 2 else "PN" if self.source.AddressingMode == 1 else None
        self.id = self.info.ID
        self.pushname = self.info.Pushname
        self.is_edit = message.IsEdit

    @property
    def is_media(self) -> bool:
        msg_fields = self.message.Message.ListFields()
        if not msg_fields:
            return False
        field_name = msg_fields[0][0].name
        return field_name in (
            "imageMessage", "videoMessage", "audioMessage",
            "documentMessage", "stickerMessage", "contactMessage",
            "locationMessage", "liveLocationMessage"
        )

    @property
    def media_type(self) -> Optional[str]:
        # Prioritaskan MediaType dari info (karena bisa ada label khusus seperti "gif")
        if self.info.MediaType:
            return self.info.MediaType

        # Fallback: baca dari field protobuf
        msg_fields = self.message.Message.ListFields()
        if not msg_fields:
            return None

        field_name = msg_fields[0][0].name
        return field_name.replace("Message", "")

    @property
    def text(self) -> str:
        msg_fields = self.message.Message.ListFields()
        if msg_fields:
            _, field_value = msg_fields[0]
            if isinstance(field_value, str):
                return field_value
            text_attrs = ["text", "caption", "name", "conversation"]
            for attr in text_attrs:
                if hasattr(field_value, attr):
                    val = getattr(field_value, attr)
                    if isinstance(val, str) and val.strip():
                        return val
        return ""

    async def reply(self, text):
        if not isinstance(text, str):
            if isinstance(text, (list, tuple)):
                text = ", ".join(map(str, text))
            else:
                text = str(text)
        return await self.client.reply_message(text, self.message)

    async def download(self):
        return await self.client.download_any(self.message.Message)

    @property
    def quoted(self) -> Optional[QuotedMess]:
        msg_fields = self.message.Message.ListFields()
        if not msg_fields:
            return None

        _, field_value = msg_fields[0]
        if not hasattr(field_value, "contextInfo"):
            return None

        context_info = field_value.contextInfo
        if not hasattr(context_info, "quotedMessage") or not context_info.quotedMessage.ListFields():
            return None

        return QuotedMess(self.client, context_info)

    @property
    def mentioned_jid(self) -> List[str]:
        msg = self.message.Message
        msg_fields = msg.ListFields()
        if not msg_fields:
            return []

        _, field_value = msg_fields[0]
        field_name = msg_fields[0][0].name
        if field_name in ("stickerMessage", "locationMessage"):
            return []

        if not hasattr(field_value, "contextInfo"):
            return []

        context_info = field_value.contextInfo
        mentioned_jid_list = getattr(context_info, "mentionedJID", [])
        return list(mentioned_jid_list) if mentioned_jid_list else []

    @property
    def media_info(self) -> dict:
        msg_fields = self.message.Message.ListFields()
        if not msg_fields:
            return {}

        field_desc, field_value = msg_fields[0]
        media_type = field_desc.name.replace("Message", "")

        info = {
            "type": media_type,
            # Umum
            "seconds": getattr(field_value, "seconds", None),
            "caption": getattr(field_value, "caption", None),
            "mimetype": getattr(field_value, "mimetype", None),
            "fileLength": getattr(field_value, "fileLength", None),
            "height": getattr(field_value, "height", None),
            "width": getattr(field_value, "width", None),
            "fileName": getattr(field_value, "fileName", None),
            "isAnimated": getattr(field_value, "isAnimated", None),
            "pageCount": getattr(field_value, "pageCount", None),  # PDF
            "jpegThumbnail": getattr(field_value, "JPEGThumbnail", None),

            # Enkripsi & Download
            "mediaKey": getattr(field_value, "mediaKey", None),
            "fileSHA256": getattr(field_value, "fileSHA256", None),
            "fileEncSHA256": getattr(field_value, "fileEncSHA256", None),
            "directPath": getattr(field_value, "directPath", None),
            "URL": getattr(field_value, "URL", None),
            "mediaKeyTimestamp": getattr(field_value, "mediaKeyTimestamp", None),

            # Tambahan khusus
            "streamingSidecar": getattr(field_value, "streamingSidecar", None),
            "scansSidecar": getattr(field_value, "scansSidecar", None),
            "scanLengths": list(getattr(field_value, "scanLengths", [])) or None,
            "midQualityFileSHA256": getattr(field_value, "midQualityFileSHA256", None),
            "externalShareFullVideoDurationInSeconds": getattr(field_value, "externalShareFullVideoDurationInSeconds", None),
            "contextInfo": getattr(field_value, "contextInfo", None),
        }

        return {k: v for k, v in info.items() if v is not None}

    @property
    def raw_message(self) -> RawMessage:
        return self.message.Message