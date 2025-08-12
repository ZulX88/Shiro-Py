from neonize.proto.Neonize_pb2 import JID ,Device 
from dataclasses import dataclass
import neonize.proto.waE2E.WAWebProtobufsE2E_pb2 as waE2E
from typing import List, Optional

@dataclass
class Messages:
    chat: JID
    id: str  
    sender: JID
    sender_alt: JID
    pushname: str
    is_group: bool
    message: waE2E.Message  
    quoted: Optional['Messages'] = None 
    mentioned_jid: List[JID] = None
    
    def __post_init__(self):
        if self.mentioned_jid is None:
            self.mentioned_jid = []