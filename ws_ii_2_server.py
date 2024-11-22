import sys
import time
from datetime import datetime
import random
import string
import hashlib
import asyncio
import websockets
import redis.asyncio as redis

# ===== CONSTANTS =====
REDIS_USERS_KEY = "user:"
REDIS_MESSAGES_KEY = "message:"
REDIS_MESSAGES_SORTED_LIST_KEY = REDIS_MESSAGES_KEY + "timestamps"

HISTORY_TOP_DESIGN = f"{'*' * 10} HISTORY {'*' * 10}"
HISTORY_BOTTOM_DESIGN = "*" * len(HISTORY_TOP_DESIGN)

MSG_JOIN_CHAT = "ʕっ•ᴥ•ʔっ ( {} as join ! )"
MSG_LEAVE_CHAT = "ʕっ•ᴥ•ʔっ ( {} as left ! )"
MSG_SEND_CHAT = "{} : {}"
MSG_PSEUDO_UNAVAILABLE = "Name {} is already registered"
MSG_WRONG_PASSWORD = "ʕノ•̀ᴥ•́ʔノ ( Wrong password )"
MSG_PASSWORD_NOT_SET = "ʕ¬ᴥ¬ʔ ( Please define your password )"
MSG_WRONG_SESSION = "ʕ°ᴥ°ʔ ( Session error )"
MSG_REGISTER = "ʕᵔᴥᵔʔノ ( You are registered, welcome ! )"
MSG_LOGIN = "ʕᵔᴥᵔʔノ ( Welcome back {} ! )"
MSG_ERROR = "ʕ°ᴥ°ʔ ( An error occured ! )"
MSG_ALREADY_CONNECTED = "ʕಠᴥಠʔ ( This name is already connected )"

HEADER_NEWPASS = "NEWPASS"
HEADER_PASS = "PASS"
HEADER_HELLO = "HELLO"

SYS_NEWPASS_TOKEN = HEADER_NEWPASS + "|{}"
SYS_PASS_TOKEN = HEADER_PASS + "|{}"


# ===== GLOBAL FUNCTIONS =====
def generate_token():
    """
    Return a 16 length string with random [A-Z][a-z][0-9]
    """
    return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))

def generate_random_rgb_hexa():
    """
    Return a random color in hexadecimal format #RRGGBB
    """
    color = random.randrange(0, 2**24)
    hex_color = hex(color)
    return f"#{hex_color[2:]}"

def get_pseudo_colored(pseudo: str, rgb: str):
    """
    Return a formatted string for color in terminal
    """
    return f"&{rgb}&l{pseudo}&r&f"

def hash_string(password):
    """
    Return hashed string password in SHA256
    """
    return hashlib.sha256(password.encode()).hexdigest()

async def check_password(password, hashed_password):
    """
    Compare password with hash
    """
    return hash_string(password) == hashed_password


# ===== MESSAGES FUNCTIONS =====
async def send_to_clients(redis_client, message: str, addr: str, clients_websocket: dict, *args: tuple, exclude_self=True):
    """
    Send message to all clients
    """
    date_time = datetime.now().strftime("[%m/%d/%Y, %H:%M:%S] ")
    string_formatted = date_time + message.format(*args) + "&r"
    await save_message(redis_client, string_formatted)

    for other_key, other_ws in clients_websocket.items():
        if exclude_self and other_key == addr:
            continue
        await other_ws.send(string_formatted)

async def send_to_client(ws, message: str, *args: tuple):
    """
    Send message to specific client
    """
    string_formatted = message.format(*args)
    await ws.send(string_formatted)

async def save_message(redis_client, message):
    """
    Save message to history
    """
    message_data = {
        "content": message,
        "time": time.time()
    }

    message_id = hash_string(message)
    await redis_client.hset(REDIS_MESSAGES_KEY + message_id, mapping=message_data)
    await redis_client.zadd(REDIS_MESSAGES_SORTED_LIST_KEY, {message_id: message_data["time"]})

async def get_last_messages(redis_client, count=10):
    """
    Get last <count> messages of chat
    """
    message_ids = await redis_client.zrange(REDIS_MESSAGES_SORTED_LIST_KEY, 0, count - 1)

    messages = []
    for message_id in message_ids:
        message_data = await redis_client.hgetall(REDIS_MESSAGES_KEY + message_id)
        messages.append(message_data["content"])

    return messages

async def handle_client_msg(websocket, redis_client, clients_websocket):
    """
    Handle all message from clients
    """

    addr = websocket.remote_address
    print(f"Nouvelle connexion de {addr}")

    try:
        clients_websocket[addr] = websocket

        message = await websocket.recv()
        print(f"Message from {addr} : {message}")

        current_client_pseudo = ''

        if f"{HEADER_HELLO}|" in message and len(message.split(f"{HEADER_HELLO}|")) > 1:
            auth_token = generate_token()
            current_client_pseudo = message.split(f"{HEADER_HELLO}|")[1].lower()
            current_client = {}

            user_exists = await redis_client.exists(REDIS_USERS_KEY + current_client_pseudo)
            if user_exists == 1:
                pseudo_account = await redis_client.hgetall(REDIS_USERS_KEY + current_client_pseudo)
                if not bool(int(pseudo_account.get("connected", 0))):
                    pseudo_account["auth_token"] = auth_token
                    await redis_client.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=pseudo_account)
                    await send_to_client(websocket, SYS_PASS_TOKEN, pseudo_account["auth_token"])
                else:
                    await send_to_client(websocket, MSG_ALREADY_CONNECTED)
            else:
                current_client["pseudo"] = current_client_pseudo
                current_client["color"] = generate_random_rgb_hexa()
                current_client["auth_token"] = auth_token
                current_client["connected"] = int(False)

                await redis_client.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=current_client)
                await send_to_client(websocket, SYS_NEWPASS_TOKEN, current_client["auth_token"])

        current_client = await redis_client.hgetall(REDIS_USERS_KEY + current_client_pseudo)
        current_client_color = current_client.get("color")
        current_client_isConnected = bool(int(current_client.get("connected", 0)))

        print("supra test ", current_client_color)
        current_client_pseudoColored = get_pseudo_colored(current_client_pseudo, current_client_color)

        while True:
            message = await websocket.recv()
            if not current_client_isConnected and (HEADER_NEWPASS in message or HEADER_PASS in message):
                message_data = message.split("|")
                if len(message_data) == 3: # NEWPASS/PASS | auth_token | password
                    client_header, client_auth_token, client_password = message_data

                    if not client_password:
                        await send_to_client(websocket, MSG_PASSWORD_NOT_SET)
                        token_msg = SYS_NEWPASS_TOKEN if client_header == HEADER_NEWPASS else SYS_PASS_TOKEN
                        await websocket.close()
                        return

                    if client_auth_token != current_client.get("auth_token"):
                        await send_to_client(websocket, MSG_WRONG_SESSION)
                        await websocket.close()
                        return

                    if client_header == HEADER_NEWPASS:
                        current_client["password"] = hash_string(client_password)
                        await send_to_client(websocket, MSG_REGISTER)

                    elif client_header == HEADER_PASS:
                        if not await check_password(client_password, current_client["password"]):
                            await send_to_client(websocket, MSG_WRONG_PASSWORD)
                            await websocket.close()
                            return

                        await send_to_client(websocket, MSG_LOGIN, (current_client_pseudoColored))

                    current_client["connected"] = int(True)
                    current_client_isConnected = True

                    current_client["auth_token"] = ''
                    await redis_client.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=current_client)

                    last_messages = await get_last_messages(redis_client)
                    history_message = HISTORY_TOP_DESIGN + "\n" + "\n".join(last_messages) + "\n" + HISTORY_BOTTOM_DESIGN
                    await send_to_client(websocket, history_message)

                    await send_to_clients(redis_client, MSG_JOIN_CHAT, addr, clients_websocket, current_client_pseudoColored, exclude_self=False)
                    continue
                else:
                    await send_to_client(websocket, MSG_ERROR)
                    await websocket.close()
                    return

            if current_client_isConnected and current_client.get("auth_token") == '':
                await send_to_clients(redis_client, MSG_SEND_CHAT, current_client_pseudo, clients_websocket, current_client_pseudoColored, message)
            else:
                await send_to_client(websocket, MSG_PASSWORD_NOT_SET)
                await websocket.close()
                return

    except websockets.exceptions.ConnectionClosed:
        print(f"Connection closed from {addr}")
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f"Error : {e} (Type: {exc_type}, Line: {exc_tb.tb_lineno})")
    finally:
        if addr in clients_websocket:
            del clients_websocket[addr]

        if await redis_client.exists(REDIS_USERS_KEY + current_client_pseudo) == 1:
            current_client["connected"] = int(False)
            await redis_client.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=current_client)
            await send_to_clients(redis_client, MSG_LEAVE_CHAT, addr, clients_websocket, current_client_pseudoColored)

async def main():
    """
    Will start our websocket chat server
    """

    # Redis connection
    redis_client = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
    try:
        await redis_client.ping()
        print("Successful Redis connection")
    except Exception as e:
        print(f"Error, unable to connect to Redis : {e}")
        return

    # Store our websockets connections
    clients_websocket = {}

    async with websockets.serve(lambda ws: handle_client_msg(ws, redis_client, clients_websocket), "127.0.0.1", 8888):
        print("Server listen on ws://127.0.0.1:8888")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
