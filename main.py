import asyncio
import logging
import os
import config
import sys
from neonize.aioze.client import NewAClient
from neonize.aioze.events import ConnectedEv, MessageEv, PairStatusEv, ReceiptEv, CallOfferEv
from command import handler
from neonize.utils import log
import signal

sys.path.insert(0, os.getcwd())

log.setLevel(logging.DEBUG)


client = NewAClient(config.namedb)

@client.event(ConnectedEv)
def on_connected(_: NewAClient, __: ConnectedEv):
    print("\n⚡ Connected")
    connected.set() 
    
@client.event(ReceiptEv)
def on_receipt(_: NewAClient, receipt: ReceiptEv):
    print(receipt)

@client.event(CallOfferEv)
def on_call(_: NewAClient, call: CallOfferEv):
    log.debug(call)

@client.event(MessageEv)
def on_message(client: NewAClient, message: MessageEv):
    handler(client, message)

@client.event(PairStatusEv)
def PairStatusMessage(_: NewAClient, message: PairStatusEv):
    print(f"\n✅ Logged in as {message.ID.User}")
    pairing_completed.set() 
    
async def connect():
    await client.connect()
    # Do something else
    await client.idle()  # Necessary to keep receiving events


if __name__ == "__main__":
    client.loop.run_until_complete(connect())