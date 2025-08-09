import asyncio
import logging
import os
import config
import re
import string
import random
import sys
import requests 
import json
from urllib.parse import quote, urlparse
from datetime import timedelta
from neonize.client import NewClient 
from neonize.client import NewClient, ClientFactory,ContactStore
from neonize.events import ConnectedEv, MessageEv, PairStatusEv, ReceiptEv, CallOfferEv, event, GroupInfoEv
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    Message,
    FutureProofMessage,
    InteractiveMessage,
    MessageContextInfo,
    DeviceListMetadata,
)
from command import handler
from neonize.types import MessageServerID
from neonize.utils import log, build_jid,get_message_type 
from neonize.utils.enum import ReceiptType, VoteType,ParticipantChange
import signal


sys.path.insert(0, os.getcwd())


def interrupted(*_):
    loop = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(ClientFactory.stop(), loop)


log.setLevel(logging.DEBUG)
signal.signal(signal.SIGINT, interrupted)


client = NewClient(config.namedb)
@client.event(ConnectedEv)
def on_connected(_: NewClient, __: ConnectedEv):
    print("⚡ Connected")

@client.event(ReceiptEv)
def on_receipt(_: NewClient, receipt: ReceiptEv):
    print(receipt)


@client.event(CallOfferEv)
def on_call(_: NewClient, call: CallOfferEv):
    log.debug(call)

# @client.event(GroupInfoEv)
# def greetz(client: NewClient, greet: GroupInfoEv):
    # user_obj = (
        # greet.Join[0] if greet.Join else
        # greet.Leave[0] if greet.Leave else
        # greet.Promote[0] if greet.Promote else
        # greet.Demote[0] if greet.Demote else
        # None
    # )
    # user = None
    # if user_obj and user_obj.Server == "lid":
        # user = client.get_pn_from_lid(user_obj)
    # else:
        # user = (
            # greet.Join[0].User if greet.Join
            # else greet.Leave[0].User if greet.Leave
            # else greet.Promote[0].User if greet.Promote
            # else greet.Demote[0].User if greet.Demote
            # else None
        # )       
        
    # contekto = client.contact.get_contact(
        # greet.Join[0] if greet.Join        
        # else greet.Leave[0] if greet.Leave
        # else greet.Promote[0] if greet.Promote
        # else greet.Demote[0] if greet.Demote       
        # else None
    # )
    # pushname = contekto.PushName
    # senderc = client.contact.get_contact(
        
    # )
    # if greet.Leave:
        # if greet.Sender.User == user:
            # return client.send_message(greet.JID,f"Good bye @{pushname} 🥀")
        # else:
            # return client.send_message(greet.JID,f"Stupid nigga got kicked @{pushname} 🤓")
    # elif greet.Join:
        # return client.send_message(greet.JID, f"Welcome @{pushname}! 🌹")
    # elif greet.Promote:
        # return client.send_message(greet.JID, f"Congrats! @{pushname} has been promoted to admin by @{sender_pushname} 🥳")
    # elif greet.Demote:
        # return client.send_message(greet.JID, f"Oops! @{user} has been demoted from admin by @{greet.Sender.User} 🤐")    
            
@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    handler(client, message)

@client.event(PairStatusEv)
def PairStatusMessage(_: NewClient, message: PairStatusEv):
    print(f"logged as {message.ID.User}")



def connect():
    client.connect()
    # Do something else
    client.idle()  # Necessary to keep receiving events


if __name__ == "__main__":
    if not client.is_logged_in:
        nomor = input("Nomor WA : ")
        client.PairPhone(nomor,show_push_notification=True)
    else:
        connect()