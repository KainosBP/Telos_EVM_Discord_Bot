import discord
from discord.ext import commands, tasks
import requests
import json
import logging
from typing import Dict, Any
import os
import atexit
import logging

# Set up logging
logging.basicConfig(filename='bot.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# Now, you can log messages with:
logging.info('This is an info message')
logging.warning('This is a warning message')
logging.error('This is an error message')


# Create a bot instance with a specified command prefix and intents
bot_token = 'MTEwOTgzOTcxMjgyNDM0ODc2Mg.GkER8F.w76m_DzoR6eQ1QRMP5C0NW5cntUqPail4T7V-8'
intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Define a dictionary to store user addresses for monitoring
addresses: Dict[str, Dict[str, Any]] = {}

# If there's an existing 'addresses.json' file, load its contents into the addresses dictionary
if os.path.exists('addresses.json'):
    with open('addresses.json', 'r') as f:
        addresses = json.load(f)

# When the bot script ends, write the current state of the addresses dictionary to 'addresses.json'
def save_addresses():
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f)
atexit.register(save_addresses)

# Function to fetch the latest transaction hash from Telos EVM API
def get_latest_transaction(address):
    response = requests.get(f"https://api.teloscan.io/v1/address/{address}/transactions?limit=1&offset=0&includeAbi=false&includePagination=false")
    if response.status_code != 200:
        raise Exception(f"Request failed with status {response.status_code}")
    data = response.json()
    if data['results']:  # Check if the results list is not empty
        latest_transaction = data['results'][0]['hash']
        return latest_transaction
    else:
        return None  # Return None if no transactions are available


bot.remove_command('help')  # Remove the built-in help command

@bot.command()
async def help(ctx):
    """
    Sends a message listing the bot's commands and how to use them.
    """
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
    """
    Monitor a given address for the user who invokes the command.
    """
    # Access the global addresses variable
    global addresses

    # Convert the address to lowercase for consistency
    address = address.lower()

    # Fetch the latest transaction at the time of adding the address for monitoring
    latest_transaction = get_latest_transaction(address)

    # If the user has no addresses being monitored yet, initialize their entry in the dictionary
    if str(ctx.author.id) not in addresses:
        addresses[str(ctx.author.id)] = []

    # Check if the address is already being monitored by the user
    for info in addresses[str(ctx.author.id)]:
        if info['address'] == address:
            # If it is, send a message and stop the command here
            await ctx.send(f'You are already monitoring address {address}.')
            return

    # Add the address to the user's list of monitored addresses
    addresses[str(ctx.author.id)].append({
        'address': address,
        'last_tx': latest_transaction,
    })

    # Save the updated addresses dictionary to the file
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f)

    # Send a confirmation message
    await ctx.send(f'Started monitoring address {address} for you.')

    # Log the monitoring request, including the user's ID
    logging.info(f"Started monitoring address {address} for user {ctx.author.id}")


@bot.command(name='stop_monitoring')
async def stop_monitoring(ctx, address):
    """
    Stop monitoring a given address for the user who invokes the command.
    """
    # Access the global addresses variable
    global addresses

    # Convert the address to lowercase for consistency
    address = address.lower()

    # Check if the user is monitoring any addresses
    if str(ctx.author.id) in addresses:
        # If they are, find the specific address they want to stop monitoring
        for info in addresses[str(ctx.author.id)]:
            if info['address'] == address:
                # Remove the address from the user's list
                addresses[str(ctx.author.id)].remove(info)

                # Save the updated addresses dictionary to the file
                with open('addresses.json', 'w') as f:
                    json.dump(addresses, f)

                # Send a confirmation message
                await ctx.send(f'Stopped monitoring address {address} for you.')

                # Log the stop monitoring request, including the user's ID
                logging.info(f"Stopped monitoring address {address} for user {ctx.author.id}")
                return

    # If the user was not monitoring the requested address, send a message
    await ctx.send(f"You're not currently monitoring address {address}.")


@bot.command(name='monitored_addresses')
async def monitored_addresses(ctx):
    """
    Command to display all addresses currently being monitored by a user.

    :param ctx: The context of the command. Contains information about who sent the command, etc.
    """
    user_id = str(ctx.author.id)  # The ID of the user who sent the command
    if user_id in addresses:  # Check if the user is monitoring any addresses
        user_addresses = [info['address'] for info in addresses[user_id]]
        await ctx.send(f'You are currently monitoring the following addresses: {", ".join(user_addresses)}')
    else:
        await ctx.send('You are not currently monitoring any addresses.')


@tasks.loop(seconds=10)
async def check_transactions():
    """
    Check for new transactions every 10 seconds for all monitored addresses.
    """
    # We still need to access our global addresses dictionary
    global addresses

    # For each user we're monitoring addresses for...
    for user, infos in addresses.items():
        # ...and for each address that user is monitoring...
        for info in infos:
            # ...fetch the latest transaction for that address...
            latest_transaction = get_latest_transaction(info['address'])

            # ...and if it's different from the last one we saw...
            if info['last_tx'] != latest_transaction:
                # ...update our record of the last transaction we saw...
                info['last_tx'] = latest_transaction

                # ...fetch the user object so we can DM them...
                user_object = await bot.fetch_user(user)

                # ...and send them a DM with the transaction link.
                await user_object.send(f"New transaction for address {info['address']}: https://www.teloscan.io/tx/{latest_transaction}")

    # Write our updated dictionary back to the JSON file on disk
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f)

    # Log that we've checked the transactions
    logging.info('Done checking transactions.')

@bot.event
async def on_ready():
    """
    Start the transaction checking task when the bot is ready.
    """
    check_transactions.start()

# Start the bot with the specified token
bot.run(bot_token)
