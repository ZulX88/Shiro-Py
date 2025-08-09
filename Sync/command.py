from neonize.client import NewClient, ClientFactory, ContactStore
from neonize.events import MessageEv, event
from neonize.utils import get_message_type, build_jid
from neonize.utils.enum import ReceiptType, VoteType, ParticipantChange
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    Message,
    FutureProofMessage,
    InteractiveMessage,
    MessageContextInfo,
    DeviceListMetadata,
)
from neonize.types import MessageServerID
from urllib.parse import quote, urlparse
from scrape.copilot import send_copilot_request
from scrape.zerochan import zerochan
from scrape.fb import fb_download
from utils.serialize import Mess
import re
import config
import json
import requests 
import urllib.parse 



def handler(client: NewClient, message: MessageEv):
    try:
        m = Mess.create(client, message)
        budy = (message.Message.conversation
                or getattr(message.Message, "extendedTextMessage", None)
                and message.Message.extendedTextMessage.text or "")
        # prefix_match = re.match(r"^[°•π÷×¶∆£¢€¥®™✓_=|~!?#$%^&.+\-,/\\©^]", budy)
        # prefix = prefix_match.group() if prefix_match else "!"
        prefix = "!"
        is_cmd = budy.startswith(prefix)
        command = ""
        text = ""
        if is_cmd:
            parts = budy[len(prefix):].strip().split(" ", 1)
            command = parts[0].lower()
            if len(parts) > 1:
                text = parts[1]
        is_group = m.is_group
        groupMetadata = client.get_group_info(m.chat) if is_group else None
        is_owner = m.sender.User in config.owner if m.sender.Server == "s.whatsapp.net" else m.senderAlt.User if m.sender.Server == "lid" else None
        is_admin = False
        isBotAdmin = False
            
        if is_group and groupMetadata:
            for participant in groupMetadata.Participants:
                if participant.JID.User == m.sender.User and (
                        participant.IsAdmin or participant.IsSuperAdmin):
                    is_admin = True
                if participant.JID.User == m.user.JID.User and (
                        participant.IsAdmin or participant.IsSuperAdmin):
                    isBotAdmin = True
                if is_admin and isBotAdmin:
                    break
        if not is_group and not is_owner:
            return 
        def Example(teks):
            return f"*Contoh* : {prefix}{command} " + str(teks)
    
        match command:            
            case "fbdl" | "fb" | "facebook" | "fesnuk": 
                if not text:
                    return m.reply(Example("link"))
                efbe_linko = fb_download(text)
                client.send_video(m.chat, efbe_linko, quoted=message)
            case "brat":
                if not text:
                    return m.reply(Example("halo"))
                client.send_sticker(m.chat, f"https://brat.siputzx.my.id/image?text={urllib.parse.quote(text)}",quoted=message)            
            case "getme":
                mek = client.get_me()
                m.reply(mek.__str__())
            case "join":
                if not is_owner: 
                    return m.reply("Only owner!")
                if not text:
                    return m.reply(Example("link")) 
                    
                client.join_group_with_link(text)
                m.reply("Success")
    
            case "leave":
                if not is_owner: 
                    return m.reply("Only owner!")
                                
                if not is_group:
                    return m.reply("Perintah ini hanya bisa digunakan di dalam grup.")
                
                client.send_message(m.chat, "Bye")
                client.leave_group(m.chat) 
                                                    
            case "get_l":
                #jeaidi = build_jid("108070571118660",server="lid")
                #h = client.get_pn_from_lid(m.senderAlt)
                h = None
                if m.sender.Server == "lid":
                    #h = client.get_pn_from_lid(m.sender)
                    return client.reply_message(m.sender.__str__(), message)
                elif m.senderAlt.Server == "lid":
                    # h = client.get_pn_from_lid(m.senderAlt)
                    return client.reply_message(m.senderAlt.__str__(),
                                                      message)
    
            case "get_p":
                #jeaidi = build_jid("108070571118660",server="lid")
                #h = client.get_pn_from_lid(m.senderAlt)
                h = None
                if m.sender.Server == "lid":
                    h = client.get_pn_from_lid(m.sender)
                    return client.reply_message(h.__str__(), message)
                elif m.senderAlt.Server == "lid":
                    h = client.get_pn_from_lid(m.senderAlt)
                    return client.reply_message(h.__str__(), message)
    
            case "hidetag":
                if not is_admin and not is_owner:
                    return client.reply_message("Only admin!", message)
                if not text:
                    return client.reply_message(Example("teks"), message)
                tagged = ""
                for user in groupMetadata.Participants:
                    tagged += f"@{user.JID.User} "
                client.send_message(m.chat,
                                          message=str(text),
                                          ghost_mentions=tagged)
            case "mtype":
                typek = get_message_type(message)
                client.reply_message(str(typek), message)
            case "tt" | "tiktok":
                if not text:
                    return client.reply_message(
                        "Masukkan link video/foto TikTok", message)
    
                try:
                    parsed = urlparse(text)
                    if not all([parsed.scheme, parsed.netloc]):
                        return client.reply_message("URL tidak valid",message)
                    encoded_url = quote(text, safe='')
                    api_url = f"https://tikwm.com/api/?hd=1&url={encoded_url}"
    
                    response = requests.get(api_url, timeout=10).json()
    
                    if not response.get("data"):
                        return client.reply_message("Gagal memproses video",
                                                          message)
    
                    data = response["data"]
    
                    if data.get("images"):
                        for image_url in data["images"]:
                            return client.send_image(m.chat, str(image_url))
                    client.send_video(
                        m.chat, data["play"], quoted=message)
    
                except requests.exceptions.RequestException:
                    client.reply_message("Error saat menghubungi server",
                                               message)
                except ValueError:
                    client.reply_message("Response tidak valid", message)
            case "zero":
                if not text:
                    return client.reply_message(Example("shiroko"), message)
                linkz = zerochan(text)
                #client.send_message(m.chat,linkz)
                client.send_album(m.chat,linkz)
    
            case "copilot":
                if not text:
                    return client.reply_message(
                        Example("bagaimana cara ngoding"), message)
    
                result = json.loads(send_copilot_request(text))
                client.send_message(m.chat, str(result["text"]))
    
            case "cekadmin":
                if not is_admin:
                    return client.reply_message("False", message)
                client.send_message(m.chat, f"True")
            case "ping":
                client.reply_message("pong", message)
            case "stop":
                print("Stopping client...")
                client.stop()
            case "_test_link_preview":
                client.send_message(
                    m.chat,
                    "Test https://github.com/krypton-byte/neonize",
                    link_preview=True)
            case "_sticker":
                client.send_sticker(
                    m.chat,
                    "https://mystickermania.com/cdn/stickers/anime/spy-family-anya-smirk-512x512.png",
                )
            case "_sticker_exif":
                client.send_sticker(
                    m.chat,
                    "https://mystickermania.com/cdn/stickers/anime/spy-family-anya-smirk-512x512.png",
                    name="@Neonize",
                    packname="2024",
                )
            case "_image":
                client.send_image(
                    m.chat,
                    "https://download.samplelib.com/png/sample-boat-400x300.png",
                    caption="Test",
                    quoted=message,
                )
            case "_video":
                client.send_video(
                    m.chat,
                    "https://download.samplelib.com/mp4/sample-5s.mp4",
                    caption="Test",
                    quoted=message,
                )
            case "_audio":
                client.send_audio(
                    m.chat,
                    "https://download.samplelib.com/mp3/sample-12s.mp3",
                    quoted=message,
                )
            case "_ptt":
                client.send_audio(
                    m.chat,
                    "https://download.samplelib.com/mp3/sample-12s.mp3",
                    ptt=True,
                    quoted=message,
                )
            case "_doc":
                client.send_document(
                    m.chat,
                    "https://download.samplelib.com/xls/sample-heavy-1.xls",
                    caption="Test",
                    filename="test.xls",
                    quoted=message,
                )
            case "debug":
                client.send_message(build_jid("601164899724"),
                                          message.__str__())
            case "viewonce":
                client.send_image(
                    m.chat,
                    "https://pbs.twimg.com/media/GC3ywBMb0AAAEWO?format=jpg&name=medium",
                    viewonce=True,
                )
            case "profile_pict":
                client.send_message(m.chat,
                                          (
                                           client.get_profile_picture(m.chat
                                                                      )).__str__())
            case "status_privacy":
                client.send_message(m.chat,
                                          (
                                           client.get_status_privacy()).__str__())
            case "read":
                client.send_message(
                    m.chat,
                    (client.mark_read(
                        message.Info.ID,
                        chat=message.Info.MessageSource.Chat,
                        sender=message.Info.MessageSource.Sender,
                        receipt=ReceiptType.READ,
                    )).__str__(),
                )
            case "read_channel":
                metadata = client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M")
                err = client.follow_newsletter(metadata.ID)
                client.send_message(m.chat, "error: " + err.__str__())
                resp = client.newsletter_mark_viewed(metadata.ID,
                                                           [MessageServerID(0)])
                client.send_message(
                    m.chat,
                    resp.__str__() + "\n" + metadata.__str__())
            case "logout":
                client.logout()
            case "send_react_channel":
                metadata = client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M")
                data_msg = client.get_newsletter_messages(
                    metadata.ID, 2, MessageServerID(0))
                client.send_message(m.chat, data_msg.__str__())
                for _ in data_msg:
                    client.newsletter_send_reaction(metadata.ID,
                                                          MessageServerID(0), "🗿",
                                                          "")
            case "subscribe_channel_updates":
                metadata = client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M")
                result = client.newsletter_subscribe_live_updates(metadata.ID
                                                                        )
                client.send_message(m.chat, result.__str__())
            case "mute_channel":
                metadata = client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M")
                client.send_message(
                    m.chat,
                    (client.newsletter_toggle_mute(metadata.ID,
                                                         False)).__str__(),
                )
            case "set_diseapearing":
                client.send_message(
                    m.chat,
                    (client.set_default_disappearing_timer(timedelta(days=7)
                                                                 )).__str__(),
                )
            case "test_contacts":
                client.send_message(
                    m.chat, (client.contact.get_all_contacts()).__str__())
            case "build_sticker":
                client.send_message(
                    m.chat,
                    client.build_sticker_message(
                        "https://mystickermania.com/cdn/stickers/anime/spy-family-anya-smirk-512x512.png",
                        message,
                        "2024",
                        "neonize",
                    ),
                )
            case "build_video":
                client.send_message(
                    m.chat,
                    client.build_video_message(
                        "https://download.samplelib.com/mp4/sample-5s.mp4", "Test",
                        message),
                )
            case "build_image":
                client.send_message(
                    m.chat,
                    client.build_image_message(
                        "https://download.samplelib.com/png/sample-boat-400x300.png",
                        "Test",
                        message,
                    ),
                )
            case "build_document":
                client.send_message(
                    m.chat,
                    client.build_document_message(
                        "https://download.samplelib.com/xls/sample-heavy-1.xls",
                        "Test",
                        "title",
                        "sample-heavy-1.xls",
                        quoted=message,
                    ),
                )
            # ChatSettingsStore
            case "put_muted_until":
                client.chat_settings.put_muted_until(m.chat,
                                                           timedelta(seconds=5))
            case "put_pinned_enable":
                client.chat_settings.put_pinned(m.chat, True)
            case "put_pinned_disable":
                client.chat_settings.put_pinned(m.chat, False)
            case "put_archived_enable":
                client.chat_settings.put_archived(m.chat, True)
            case "put_archived_disable":
                client.chat_settings.put_archived(m.chat, False)
            case "get_chat_settings":
                client.send_message(m.chat,
                                          (
                                           client.chat_settings.get_chat_settings(
                                               m.chat)).__str__())
            case "poll_vote":
                client.send_message(
                    m.chat,
                    client.build_poll_vote_creation(
                        "Food",
                        ["Pizza", "Burger", "Sushi"],
                        VoteType.SINGLE,
                    ),
                )
            case "wait":
                client.send_message(m.chat, "Waiting for 5 seconds...")
                asyncio.sleep(5)
                client.send_message(m.chat, "Done waiting!")
            case "shutdown":
                event.set()
            case "send_react":
                client.send_message(
                    m.chat,
                    client.build_reaction(m.chat,
                                                message.Info.MessageSource.Sender,
                                                message.Info.ID,
                                                reaction="🗿"),
                )
                
            
            case "edit_message":
                text = "Hello World"
                id_msg = None
                for i in range(1, len(text) + 1):
                    if id_msg is None:
                        msg = client.send_message(
                            message.Info.MessageSource.Chat,
                            Message(conversation=text[:i]))
                        id_msg = msg.ID
                    client.edit_message(message.Info.MessageSource.Chat,
                                              id_msg,
                                              Message(conversation=text[:i]))       
    except Exception as e:
        print(f"{e}")
