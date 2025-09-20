import asyncio
import io
import json
import os
import re
import re
import sys
import traceback
import urllib.parse
from datetime import timedelta
from typing import Any
from urllib.parse import quote, urlparse

import requests
from neonize.aioze.client import NewAClient
from neonize.aioze.events import MessageEv, event
from neonize.proto import Neonize_pb2
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message
from neonize.types import MessageServerID
from neonize.utils import get_message_type
from neonize.utils.enum import ReceiptType, VoteType, ParticipantChange 

import config
from scrape import copilot, fesnuk, zerochan
from utils.serialize import Mess

async def aexec(code: str, client: NewAClient, m: Mess) -> Any:
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


async def handler(client: NewAClient, message: Neonize_pb2.Message):
    try:
        async def check_owner(sender):
            if sender.Server == "s.whatsapp.net":
                return sender.User in config.owner
            elif sender.Server == "lid":
                pn = await client.get_pn_from_lid(sender)
                return pn.User in config.owner

        m = Mess(client,message)

        budy = m.text
        prefix = config.prefix
        is_cmd = budy.startswith(prefix)
        command = ""
        text = ""
        if is_cmd:
            parts = budy[len(prefix):].strip().split(" ", 1)
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
                if (participant.JID.User == m.sender.User or participant.LID.User == m.sender.User) and (
                    participant.IsAdmin or participant.IsSuperAdmin
                ):
                    is_admin = True
                if participant.LID.User == user_bot.LID.User and (
                    participant.IsAdmin or participant.IsSuperAdmin
                ):
                    isBotAdmin = True
                if is_admin and isBotAdmin:
                    break

        if not is_owner and not is_group:
            return

        def Example(teks):
            return f"*Contoh* : {prefix}{command} " + str(teks)

        match command:
            case "translate"|"tr":
                if not text:
                    return await m.reply(Example("id/en/jp"))
                if not m.quoted.text:
                    return await m.reply("Reply pesan yang mau ditranslate")
                data = requests.get(f"https://yrizzz.my.id/api/v1/tool/translate?from=auto&to{text}&data={urllib.parse.quote(m.quoted.text)}").json()
                await m.reply(f"""*Detected*: {data.data.detect}
*To*: {text}
*Result*: `{data.data.translated}`""")
            case "rvo"|"readviewonce":
                if not m.quoted.is_media:
                    return await m.reply("Reply view once message to read it!")
            
                mediad = await m.quoted.download()
                media_type = m.quoted.media_type
                caption = m.quoted.media_info["caption"]
            
                if media_type == "image":
                    await client.send_image(m.chat, mediad, caption=caption)
                elif media_type == "video":
                    await client.send_video(m.chat, mediad, caption=caption)
                else:
                    return await m.reply("Unsupported media type for read-view-once.")
            case "fbdl" | "fb" | "facebook" | "fesnuk":
                if not text:
                    return await m.reply(Example("link"))
                efbe_linko = fesnuk(text)
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
                    return await m.reply("Perintah ini hanya bisa digunakan di dalam grup.")
                await client.send_message(m.chat, "Bye")
                await client.leave_group(m.chat)
            case "hidetag":
                if not is_admin and not is_owner:
                    return await client.reply_message("Only admin!", message)
                if not text:
                    return await client.reply_message(Example("teks"), message)
                tagged = ""
                for user in groupMetadata.Participants:
                    tagged += f"@{user.JID.User} "
                await client.send_message(
                    m.chat, Message(conversation=text), ghost_mentions=tagged, mentions_are_lids=True
                )
            case "tt" | "tiktok":
                if not text:
                    return await client.reply_message("Masukkan link video/foto TikTok", message)
                try:
                    parsed = urlparse(text)
                    if not all([parsed.scheme, parsed.netloc]):
                        return await client.reply_message("URL tidak valid", message)
                    encoded_url = quote(text, safe="")
                    api_url = f"https://tikwm.com/api/?hd=1&url={encoded_url}"
                    response = requests.get(api_url, timeout=10).json()
                    if not response.get("data"):
                        return await client.reply_message("Gagal memproses video", message)
                    data = response["data"]
                    if data.get("images"):
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
                await client.send_album(m.chat, linkz)
            case "copilot":
                if not text:
                    return await client.reply_message(Example("bagaimana cara ngoding"), message)
                result = json.loads(copilot(text))
                await client.send_message(m.chat, str(result["text"]))
            case "ilping":
                await client.reply_message("pong", message)
            case "debug":
                await client.send_message(m.chat, message.__str__())
            case _:
                if budy.startswith("=>"):
                    if not is_owner:
                        await m.reply("❌ Only owner can use eval!")
                        return
                    cmd = budy[2:].strip()
                    if not cmd:
                        await m.reply("❌ Please provide code to evaluate. Usage: `!=> print('Hello')`")
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
                elif budy.startswith("&"):
                    if not is_owner:
                        return await m.reply("Only owner!")
                    command = budy[1:].strip()
                    process = await asyncio.create_subprocess_shell(
                        f"zsh -c {repr(command)}",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await process.communicate()
                    if stdout:
                        await m.reply(stdout.decode())
                    if stderr:
                        await m.reply(stderr.decode()) 
    except Exception as e:
        print(f"[Handler Error] {e}")
        traceback.print_exc()