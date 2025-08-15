import asyncio
import io
import json
import os
import re
import sys
import traceback
import urllib.parse
from urllib.parse import quote, urlparse
import requests
from neonize.aioze.client import ClientFactory, ContactStore, NewAClient
from neonize.aioze.events import MessageEv, event
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    DeviceListMetadata,
    FutureProofMessage,
    InteractiveMessage,
    Message,
    MessageContextInfo,
)
from neonize.types import MessageServerID
from neonize.utils import build_jid, get_message_type
from neonize.utils.enum import ParticipantChange, ReceiptType, VoteType

import config
from scrape.copilot import send_copilot_request
from scrape.fb import fb_download
from scrape.zerochan import zerochan
from utils.serialize import Mess


async def aexec(code: str, client: NewAClient, m: Mess):
    """
    Mengeksekusi string kode Python secara asynchronous dalam lingkungan
    yang memiliki akses ke `client` (NewAClient) dan `m` (Mess).
    """
    local_namespace = {}
    func_code = f"""
async def __eval_exec(client, m):
{chr(10).join(f'    {line}' for line in code.splitlines())}
"""

    try:
        exec(func_code, globals(), local_namespace)
    except SyntaxError as se:
        raise RuntimeError(
            f"Syntax Error in code:\n{se.text}\n{' ' * (se.offset - 1)}^\n{type(se).__name__}: {se.msg}"
        )

    eval_func = local_namespace.get("__eval_exec")
    if not eval_func:
        raise RuntimeError("Failed to compile code into a function.")

    return await eval_func(client, m)


async def eval_message(m: Mess, cmd: str, client: NewAClient):
    """
    Mengevaluasi dan mengeksekusi kode Python dalam konteks bot.
    Memberikan akses ke `client` dan `m` (objek pesan Mess) dalam kode yang dieksekusi.

    USAGE:
        Kirim pesan: !=> await client.send_message(m.chat, "Halo dari eval!")
        Akses info: !=> print(m.sender.User)
        Kirim hasil: !=> hasil = 2 + 2; await m.reply(f"Hasil: {hasil}")
    """
    status_msg_info = None
    temp_file_name = "neonize_eval_output.txt"

    try:
        status_msg_info = await client.send_message(
            m.chat, "🔄 Processing eval command..."
        )
        status_msg_id = status_msg_info.ID

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = io.StringIO()
        redirected_error = io.StringIO()
        sys.stdout = redirected_output
        sys.stderr = redirected_error

        stdout_data = ""
        stderr_data = ""
        exception_data = ""
        execution_result = None

        try:
            execution_result = await aexec(cmd, client, m)
        except Exception as e:
            exception_data = traceback.format_exc()

        stdout_data = redirected_output.getvalue()
        stderr_data = redirected_error.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        final_output_parts = [f"```python\n{cmd}\n```"]

        if exception_data:
            final_output_parts.append(f"```python\nException:\n{exception_data}\n```")
        elif stderr_data:
            final_output_parts.append(f"```stderr\n{stderr_data}\n```")
        elif stdout_data:
            final_output_parts.append(f"```stdout\n{stdout_data}\n```")
        else:
            if execution_result is not None:
                try:
                    result_str = str(execution_result)
                except Exception:
                    result_str = f"<{type(execution_result).__name__} object>"
                final_output_parts.append(f"```Result:\n{result_str}\n```")
            else:
                final_output_parts.append(
                    "```Result:\n✅ Code executed successfully (no output).\n```"
                )

        final_output = "\n".join(final_output_parts)

        max_message_length = 4000
        if len(final_output) > max_message_length:
            try:
                with open(temp_file_name, "w", encoding="utf-8") as f:
                    f.write(final_output)

                await client.send_document(
                    m.chat,
                    temp_file_name,
                    filename="eval_output.txt",
                    caption=f"📝 Eval output (too long):\n```python\n{cmd[:50]}{'...' if len(cmd) > 50 else ''}\n```",
                    quoted=m.message,
                )
                await client.edit_message(
                    m.chat,
                    status_msg_id,
                    Message(conversation="✅ Eval done. Output sent as file."),
                )
            finally:
                if os.path.exists(temp_file_name):
                    try:
                        os.remove(temp_file_name)
                    except Exception as remove_err:
                        print(
                            f"Warning: Could not delete temp file {temp_file_name}: {remove_err}"
                        )
        else:
            await client.edit_message(
                m.chat, status_msg_id, Message(conversation=final_output)
            )

    except Exception as outer_error:
        error_trace = traceback.format_exc()
        print(f"[Eval Error - Outer] {outer_error}\n{error_trace}")
        if sys.stdout != old_stdout:
            sys.stdout = old_stdout
        if sys.stderr != old_stderr:
            sys.stderr = old_stderr
        if os.path.exists(temp_file_name):
            try:
                os.remove(temp_file_name)
            except:
                pass
        # Batasi traceback
        error_msg = f"💥 *Eval Error (Outer):*\n```python\n{str(outer_error)}\n```\n```traceback\n{error_trace[-1000:]}\n```"
        try:
            if status_msg_info:
                await client.edit_message(
                    m.chat, status_msg_info.ID, Message(conversation=error_msg)
                )
            else:
                await client.send_message(m.chat, error_msg)
        except:
            pass


async def handler(client: NewAClient, message: MessageEv):
    try:
        async def check_owner(sender):
            if sender.Server == "s.whatsapp.net":
                return sender.User in config.owner 
            elif sender.Server == "lid":
                pn = await client.get_pn_from_lid(sender)
                return pn.User in config.owner 
        m = await Mess.create(client, message)
        budy = (
            message.Message.conversation
            or getattr(message.Message, "extendedTextMessage", None)
            and message.Message.extendedTextMessage.text
            or ""
        )
        # prefix_match = re.match(r"^[°•π÷×¶∆£¢€¥®™✓_=|~!?#$%^&.+\-,/\\©^]", budy)
        # prefix = prefix_match.group() if prefix_match else "!"
        prefix = "!"
        is_cmd = budy.startswith(prefix)
        command = ""
        text = ""
        if is_cmd:
            parts = budy[len(prefix) :].strip().split(" ", 1)
            command = parts[0].lower()
            if len(parts) > 1:
                text = parts[1]
        is_group = m.is_group
        groupMetadata = await client.get_group_info(m.chat) if is_group else None
        is_owner = await check_owner(m.sender)
        is_admin = False
        isBotAdmin = False
        user_bot = await client.get_me()
        if is_group and groupMetadata:
            for participant in groupMetadata.Participants:
                if participant.JID.User == m.sender.User and (
                    participant.IsAdmin or participant.IsSuperAdmin
                ):
                    is_admin = True
                if participant.JID.User == user_bot.JID.User and (
                    participant.IsAdmin or participant.IsSuperAdmin
                ):
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
                    return await m.reply(Example("link"))
                efbe_linko = fb_download(text)
                await client.send_video(m.chat, efbe_linko, quoted=message)
            case "brat":
                if not text:
                    return await m.reply(Example("halo"))
                await client.send_sticker(
                    m.chat,
                    f"https://brat.siputzx.my.id/image?text={urllib.parse.quote(text)}",
                    quoted=message,
                )
            case "getme":
                mek = await client.get_me()
                await m.reply(mek.__str__())
            case "join":
                if not is_owner:
                    return await m.reply("Only owner!")
                if not text:
                    return await m.reply(Example("link"))

                await client.join_group_with_link(text)
                await m.reply("Success")

            case "leave":
                if not is_owner:
                    return await m.reply("Only owner!")

                if not is_group:
                    return await m.reply(
                        "Perintah ini hanya bisa digunakan di dalam grup."
                    )

                await client.send_message(m.chat, "Bye")
                await client.leave_group(m.chat)

            case "get_l":
                # jeaidi = build_jid("108070571118660",server="lid")
                # h = await client.get_pn_from_lid(m.senderAlt)
                h = None
                if m.sender.Server == "lid":
                    # h = await client.get_pn_from_lid(m.sender)
                    return await client.reply_message(m.sender.__str__(), message)
                elif m.senderAlt.Server == "lid":
                    # h = await client.get_pn_from_lid(m.senderAlt)
                    return await client.reply_message(m.senderAlt.__str__(), message)

            case "get_p":
                # jeaidi = build_jid("108070571118660",server="lid")
                # h = await client.get_pn_from_lid(m.senderAlt)
                h = None
                if m.sender.Server == "lid":
                    h = await client.get_pn_from_lid(m.sender)
                    return await client.reply_message(h.__str__(), message)
                elif m.senderAlt.Server == "lid":
                    h = await client.get_pn_from_lid(m.senderAlt)
                    return await client.reply_message(h.__str__(), message)

            case "hidetag":
                if not is_admin and not is_owner:
                    return await client.reply_message("Only admin!", message)
                if not text:
                    return await client.reply_message(Example("teks"), message)
                tagged = ""
                for user in groupMetadata.Participants:
                    tagged += f"@{user.JID.User} "
                await client.send_message(
                    m.chat, message=str(text), ghost_mentions=tagged,mentions_are_lids=True
                )
            case "mtype":
                typek = get_message_type(message)
                await client.reply_message(str(typek), message)
            case "tt" | "tiktok":
                if not text:
                    return await client.reply_message(
                        "Masukkan link video/foto TikTok", message
                    )

                try:
                    parsed = urlparse(text)
                    if not all([parsed.scheme, parsed.netloc]):
                        return await client.reply_message("URL tidak valid", message)
                    encoded_url = quote(text, safe="")
                    api_url = f"https://tikwm.com/api/?hd=1&url={encoded_url}"

                    response = requests.get(api_url, timeout=10).json()

                    if not response.get("data"):
                        return await client.reply_message(
                            "Gagal memproses video", message
                        )

                    data = response["data"]

                    if data.get("images"):
                        for image_url in data["images"]:
                            return await client.send_album(m.chat, data["images"])
                    await client.send_video(m.chat, data["play"], quoted=message)

                except requests.exceptions.RequestException:
                    await client.reply_message("Error saat menghubungi server", message)
                except ValueError:
                    await client.reply_message("Response tidak valid", message)
            case "zero":
                if not text:
                    return await client.reply_message(Example("shiroko"), message)
                linkz = zerochan(text)
                # await client.send_message(m.chat,linkz)
                await client.send_album(m.chat, linkz)

            case "copilot":
                if not text:
                    return await client.reply_message(
                        Example("bagaimana cara ngoding"), message
                    )

                result = json.loads(send_copilot_request(text))
                await client.send_message(m.chat, str(result["text"]))

            case "cekadmin":
                if not is_admin:
                    return await client.reply_message("False", message)
                await client.send_message(m.chat, f"True")
            case "ping":
                await client.reply_message("pong", message)
            case "stop":
                print("Stopping client...")
                await client.stop()
            case "_test_link_preview":
                await client.send_message(
                    m.chat,
                    "Test https://github.com/krypton-byte/neonize",
                    link_preview=True,
                )
            case "_sticker":
                await client.send_sticker(
                    m.chat,
                    "https://mystickermania.com/cdn/stickers/anime/spy-family-anya-smirk-512x512.png",
                )
            case "_sticker_exif":
                await client.send_sticker(
                    m.chat,
                    "https://mystickermania.com/cdn/stickers/anime/spy-family-anya-smirk-512x512.png",
                    name="@Neonize",
                    packname="2024",
                )
            case "_image":
                await client.send_image(
                    m.chat,
                    "https://download.samplelib.com/png/sample-boat-400x300.png",
                    caption="Test",
                    quoted=message,
                )
            case "_video":
                await client.send_video(
                    m.chat,
                    "https://download.samplelib.com/mp4/sample-5s.mp4",
                    caption="Test",
                    quoted=message,
                )
            case "_audio":
                await client.send_audio(
                    m.chat,
                    "https://download.samplelib.com/mp3/sample-12s.mp3",
                    quoted=message,
                )
            case "_ptt":
                await client.send_audio(
                    m.chat,
                    "https://download.samplelib.com/mp3/sample-12s.mp3",
                    ptt=True,
                    quoted=message,
                )
            case "_doc":
                await client.send_document(
                    m.chat,
                    "https://download.samplelib.com/xls/sample-heavy-1.xls",
                    caption="Test",
                    filename="test.xls",
                    quoted=message,
                )
            case "debug":
                await client.send_message(m.chat, message.__str__())
            case "viewonce":
                await client.send_image(
                    m.chat,
                    "https://pbs.twimg.com/media/GC3ywBMb0AAAEWO?format=jpg&name=medium",
                    viewonce=True,
                )
            case "profile_pict":
                await client.send_message(
                    m.chat, (await client.get_profile_picture(m.chat)).__str__()
                )
            case "status_privacy":
                await client.send_message(
                    m.chat, (await client.get_status_privacy()).__str__()
                )
            case "read":
                await client.send_message(
                    m.chat,
                    (
                        await client.mark_read(
                            message.Info.ID,
                            chat=message.Info.MessageSource.Chat,
                            sender=message.Info.MessageSource.Sender,
                            receipt=ReceiptType.READ,
                        )
                    ).__str__(),
                )
            case "read_channel":
                metadata = await client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M"
                )
                err = await client.follow_newsletter(metadata.ID)
                await client.send_message(m.chat, "error: " + err.__str__())
                resp = await client.newsletter_mark_viewed(
                    metadata.ID, [MessageServerID(0)]
                )
                await client.send_message(
                    m.chat, resp.__str__() + "\n" + metadata.__str__()
                )
            case "logout":
                await client.logout()
            case "send_react_channel":
                metadata = await client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M"
                )
                data_msg = await client.get_newsletter_messages(
                    metadata.ID, 2, MessageServerID(0)
                )
                await client.send_message(m.chat, data_msg.__str__())
                for _ in data_msg:
                    await client.newsletter_send_reaction(
                        metadata.ID, MessageServerID(0), "🗿", ""
                    )
            case "subscribe_channel_updates":
                metadata = await client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M"
                )
                result = await client.newsletter_subscribe_live_updates(metadata.ID)
                await client.send_message(m.chat, result.__str__())
            case "mute_channel":
                metadata = await client.get_newsletter_info_with_invite(
                    "https://whatsapp.com/channel/0029Va4K0PZ5a245NkngBA2M"
                )
                await client.send_message(
                    m.chat,
                    (await client.newsletter_toggle_mute(metadata.ID, False)).__str__(),
                )
            case "set_diseapearing":
                await client.send_message(
                    m.chat,
                    (
                        await client.set_default_disappearing_timer(timedelta(days=7))
                    ).__str__(),
                )
            case "test_contacts":
                await client.send_message(
                    m.chat, (await client.contact.get_all_contacts()).__str__()
                )
            case "build_sticker":
                await client.send_message(
                    m.chat,
                    await client.build_sticker_message(
                        "https://mystickermania.com/cdn/stickers/anime/spy-family-anya-smirk-512x512.png",
                        message,
                        "2024",
                        "neonize",
                    ),
                )
            case "build_video":
                await client.send_message(
                    m.chat,
                    await client.build_video_message(
                        "https://download.samplelib.com/mp4/sample-5s.mp4",
                        "Test",
                        message,
                    ),
                )
            case "build_image":
                await client.send_message(
                    m.chat,
                    await client.build_image_message(
                        "https://download.samplelib.com/png/sample-boat-400x300.png",
                        "Test",
                        message,
                    ),
                )
            case "build_document":
                await client.send_message(
                    m.chat,
                    await client.build_document_message(
                        "https://download.samplelib.com/xls/sample-heavy-1.xls",
                        "Test",
                        "title",
                        "sample-heavy-1.xls",
                        quoted=message,
                    ),
                )
            # ChatSettingsStore
            case "put_muted_until":
                await client.chat_settings.put_muted_until(m.chat, timedelta(seconds=5))
            case "put_pinned_enable":
                await client.chat_settings.put_pinned(m.chat, True)
            case "put_pinned_disable":
                await client.chat_settings.put_pinned(m.chat, False)
            case "put_archived_enable":
                await client.chat_settings.put_archived(m.chat, True)
            case "put_archived_disable":
                await client.chat_settings.put_archived(m.chat, False)
            case "get_chat_settings":
                await client.send_message(
                    m.chat,
                    (await client.chat_settings.get_chat_settings(m.chat)).__str__(),
                )
            case "poll_vote":
                await client.send_message(
                    m.chat,
                    await client.build_poll_vote_creation(
                        "Food",
                        ["Pizza", "Burger", "Sushi"],
                        VoteType.SINGLE,
                    ),
                )
            case "wait":
                await client.send_message(m.chat, "Waiting for 5 seconds...")
                await asyncio.sleep(5)
                await client.send_message(m.chat, "Done waiting!")
            case "shutdown":
                event.set()
            case "send_react":
                await client.send_message(
                    m.chat,
                    await client.build_reaction(
                        m.chat,
                        message.Info.MessageSource.Sender,
                        message.Info.ID,
                        reaction="🗿",
                    ),
                )

            case "edit_message":
                text = "Hello World"
                id_msg = None
                for i in range(1, len(text) + 1):
                    if id_msg is None:
                        msg = await client.send_message(
                            message.Info.MessageSource.Chat,
                            Message(conversation=text[:i]),
                        )
                        id_msg = msg.ID
                    await client.edit_message(
                        message.Info.MessageSource.Chat,
                        id_msg,
                        Message(conversation=text[:i]),
                    )

            case _:
                if budy.startswith("=>"):
                    if not is_owner:
                        await m.reply("❌ Only owner can use eval!")
                        return
                    cmd = budy[2:].strip()
                    if not cmd:
                        await m.reply(
                            "❌ Please provide code to evaluate. Usage: `!=> print('Hello')`"
                        )
                        return
                    try:
                        await eval_message(m, cmd, client)
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        print(f"[Eval Handler Error] {e}\n{error_trace}")
                        await client.send_message(
                            m.chat,
                            f"💥 *Error in eval handler setup:*\n```python\n{str(e)}\n```\n```traceback\n{error_trace[-500:]}\n```",
                        )
    except Exception as e:
        print(f"{e}")
