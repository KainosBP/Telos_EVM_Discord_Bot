import discord
from discord.ext import commands, tasks
import requests
import json
import logging
from typing import Dict, Any
import os
import atexit
import time

logging.basicConfig(filename='bot.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

bot_token = 'YOUR BOT TOKEN HERE'
intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

addresses: Dict[str, Dict[str, Any]] = {}

if os.path.exists('addresses.json'):
    with open('addresses.json', 'r') as f:
        addresses = json.load(f)

def save_addresses():
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f)
atexit.register(save_addresses)

def get_latest_transaction(address):
    while True:
        try:
            response = requests.get(f"https://api.teloscan.io/v1/address/{address}/transactions?limit=1&offset=0&includeAbi=false&includePagination=false")
            if response.status_code != 200:
                raise Exception(f"Request failed with status {response.status_code}")
            data = response.json()
            if data['results']:
                latest_transaction = data['results'][0]['hash']
                return latest_transaction
            else:
                return None
        except Exception as e:
            logging.error(f"API connection error occurred: {e}. Retrying in 10 seconds...")
            time.sleep(10)

bot.remove_command('help')

@bot.command()
async def help(ctx):
    help_message = """
**This Telos EVM Bot service provided for free by Kainos Block Producers. Please vote for kainosblkpro!**
**Commands**
`!monitor <address>`: Start monitoring the specified address. The bot will DM you whenever a new transaction occurs.
`!stop_monitoring <address>`: Stop monitoring the specified address.
`!monitored_addresses`: Lists any addresses currently being monitored linked to your Discord user.
`!help`: This Output
"""
    await ctx.send(help_message)

@bot.command(name='monitor')
async def monitor(ctx, address):
    global addresses
    address = address.lower()
    latest_transaction = get_latest_transaction(address)
    if str(ctx.author.id) not in addresses:
        addresses[str(ctx.author.id)] = []
    for info in addresses[str(ctx.author.id)]:
        if info['address'] == address:
            await ctx.send(f'You are already monitoring address {address}.')
            return
    addresses[str(ctx.author.id)].append({
        'address': address,
        'last_tx': latest_transaction,
    })
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f)
    await ctx.send(f'Started monitoring address {address} for you.')
    logging.info(f"Started monitoring address {address} for user {ctx.author.id}")

@bot.command(name='stop_monitoring')
async def stop_monitoring(ctx, address):
    global addresses
    address = address.lower()
    if str(ctx.author.id) in addresses:
        for info in addresses[str(ctx.author.id)]:
            if info['address'] == address:
                addresses[str(ctx.author.id)].remove(info)
                with open('addresses.json', 'w') as f:
                    json.dump(addresses, f)
                await ctx.send(f'Stopped monitoring address {address} for you.')
                logging.info(f"Stopped monitoring address {address} for user {ctx.author.id}")
                return
    await ctx.send(f"You're not currently monitoring address {address}.")

@bot.command(name='monitored_addresses')
async def monitored_addresses(ctx):
    user_id = str(ctx.author.id)
    if user_id in addresses:
        user_addresses = [info['address'] for info in addresses[user_id]]
        await ctx.send(f'You are currently monitoring the following addresses: {", ".join(user_addresses)}')
    else:
        await ctx.send('You are not currently monitoring any addresses.')

@tasks.loop(seconds=10)
async def check_transactions():
    global addresses
    for user, infos in addresses.items():
        for info in infos:
            latest_transaction = get_latest_transaction(info['address'])
            if info['last_tx'] != latest_transaction:
                info['last_tx'] = latest_transaction
                user_object = await bot.fetch_user(user)
                await user_object.send(f"New transaction for address {info['address']}: https://www.teloscan.io/tx/{latest_transaction}")
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f)
    logging.info('Done checking transactions.')

@bot.event
async def on_ready():
    while True:
        try:
            check_transactions.start()
            break
        except Exception as e:
            logging.error(f"Discord connection error occurred: {e}. Retrying in 10 seconds...")
            time.sleep(10)

bot.run(bot_token)
