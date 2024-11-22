import asyncio
import websockets
import redis.asyncio as redis
import json
import random
import string
import sys, os
import hashlib

# Connexion Redis
clients = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
clients_websocket = {}

REDIS_USERS_KEY = "user:"

MSG_JOIN_CHAT = "Annonce : {} a rejoint la chatroom"
MSG_LEAVE_CHAT = "Annonce : {} a quitté la chatroom"
MSG_SEND_CHAT = "{} a dit : {}"
MSG_SEND_SELF_CHAT = "Vous avez dit : {}"
MSG_PSEUDO_UNAVAILABLE = "Le pseudo {} est déjà utilisé"
MSG_PSEUDO_UNAVAILABLE = "Le pseudo {} est déjà utilisé"

MSG_WRONG_PASSWORD = "Mauvais mot de passe"
MSG_PASSWORD_NOT_SET = "Veuillez définir un mot de passe"

MSG_WRONG_SESSION = "Erreur de session"
MSG_PLEASE_LOGIN = "Veuillez vous connecter"
MSG_WELCOME = "Vous êtes maintenant inscrit"
MSG_ERROR = "Une erreur a eu lieu"
MSG_ALREADY_CONNECTED = "Ce pseudo est déjà connecté"

HEADER_NEWPASS = "NEWPASS"
HEADER_PASS = "PASS"
HEADER_HELLO = "HELLO"

SYS_NEWPASS_TOKEN = HEADER_NEWPASS + "|{}"
SYS_PASS_TOKEN = HEADER_PASS + "|{}"


def generate_token():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def generate_random_rgb():
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def get_pseudo_colored(pseudo:str, rgb:tuple):
    return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{pseudo}\033[0m"

def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()

async def checkPassword(password, hash):
    return hashPassword(password) == hash

async def send_to_clients(message:str, addr:str, *args:tuple, exclude_self = True):
    global clients_websocket
    
    stringFormatted = message.format(*args)
    for other_key, other_ws in clients_websocket.items():
        if exclude_self and other_key == addr:
            continue
        await other_ws.send(stringFormatted)

async def send_to_client(ws, message:str, *args:tuple):
    stringFormatted = message.format(*args)
    await ws.send(stringFormatted)
        

async def handle_client_msg(websocket):
    """
    Gère les messages reçus d'un client via WebSocket.
    """
    addr = websocket.remote_address
    print(f"Nouvelle connexion de {addr}")

    try:
        # Enregistrer le websocket
        clients_websocket[addr] = websocket

        message = await websocket.recv()
        print(f"Message reçu de {addr} : {message}")

        current_client_pseudo = ''

        if f"{HEADER_HELLO}|" in message and len(message.split(f"{HEADER_HELLO}|")) > 1:
            print("super GIGA TEST")
            auth_token = generate_token()
            current_client_pseudo = message.split(f"{HEADER_HELLO}|")[1]
            current_client = {}

            user_exists = await clients.exists(REDIS_USERS_KEY + current_client_pseudo)
            # Si le compte utilisateur existe déjà
            if user_exists == 1:
                pseudo_account = await clients.hgetall(REDIS_USERS_KEY + current_client_pseudo)
                if bool(int(pseudo_account.get("connected", 0))) == False:
                    pseudo_account["auth_token"] = auth_token

                    await clients.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=pseudo_account)
                    await send_to_client(websocket, SYS_PASS_TOKEN, (pseudo_account["auth_token"]))
                else:
                    await send_to_client(websocket, MSG_ALREADY_CONNECTED, ())
            else:
                # Sauvegarder le pseudo
                current_client["pseudo"] = current_client_pseudo

                # Sauvegarder la couleur
                color = generate_random_rgb()
                current_client["color"] = json.dumps(color)

                # Sauvegarder le token d'auth
                current_client["auth_token"] = auth_token

                # Définir le nouveau compte comme non connecté
                current_client["connected"] = int(False)

                await clients.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=current_client)
                print(f"Utilisateur {current_client['pseudo']} sauvegardé !")

                await send_to_client(websocket, SYS_NEWPASS_TOKEN, (current_client["auth_token"]))


        current_client = await clients.hgetall(REDIS_USERS_KEY + current_client_pseudo)
        current_client_color = json.loads(current_client.get("color"))
        current_client_isConnected = bool(int(current_client.get("connected", 0)))
        current_client_authToken = current_client.get("auth_token")

        current_client_pseudoColored = get_pseudo_colored(current_client_pseudo, current_client_color)

        while True:
            message = await websocket.recv()
            if current_client_isConnected == False and (HEADER_NEWPASS in message or HEADER_PASS in message):
                # Récupération du mdp entré par l'user et du token de session
                message_data = message.split("|")
                if len(message_data) == 3: # NEWPASS/PASS | auth_token | client_password
                    client_header = message_data[0]
                    client_auth_token = message_data[1]
                    client_password = message_data[2]
                    
                    if len(client_password) == 0:
                        await send_to_client(websocket, MSG_PASSWORD_NOT_SET, ())
                        if client_header == HEADER_NEWPASS:
                            await send_to_client(websocket, SYS_NEWPASS_TOKEN, (client_auth_token))
                            continue

                        elif client_header == HEADER_PASS:
                            await send_to_client(websocket, SYS_PASS_TOKEN, (client_auth_token))
                            continue

                    elif client_auth_token != current_client_authToken:
                        await send_to_client(websocket, MSG_WRONG_SESSION, ())
                        continue

                    else:
                        # Si c'est une inscription
                        if client_header == HEADER_NEWPASS:
                            current_client["password"] = hashPassword(client_password)
                            await send_to_client(websocket, MSG_WELCOME, ())

                        # Si c'est une connexion
                        elif client_header == HEADER_PASS:
                            if not await checkPassword(client_password, current_client["password"]):
                                await send_to_client(websocket, MSG_WRONG_PASSWORD, ())
                                await send_to_client(websocket, SYS_PASS_TOKEN, (client_auth_token))
                                continue

                        current_client["connected"] = int(True)
                        current_client_isConnected = True

                        current_client["auth_token"] = ''
                        current_client_authToken = ''
                        await clients.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=current_client)

                        await send_to_clients(MSG_JOIN_CHAT, addr, (current_client_pseudoColored), exclude_self=False)
                        continue
                else:
                    await send_to_client(websocket, MSG_ERROR, ())
                    continue

            if current_client_isConnected == True and current_client_authToken == '':
                print(f"Message reçu de {current_client_pseudo} : {message}")
                await send_to_clients(MSG_SEND_CHAT, current_client_pseudo, *(current_client_pseudoColored, message))
            else:
                await send_to_client(websocket, MSG_PASSWORD_NOT_SET, ())

    except websockets.exceptions.ConnectionClosed:
        print(f"Connexion fermée par {addr}")
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f"Erreur : {e} (Type: {exc_type}, Ligne: {exc_tb.tb_lineno})")
    finally:
        if addr in clients_websocket:
            del clients_websocket[addr]

        if await clients.exists(REDIS_USERS_KEY + current_client_pseudo) == 1:
            current_client["connected"] = int(False)
            await clients.hset(REDIS_USERS_KEY + current_client_pseudo, mapping=current_client)
            await send_to_clients(MSG_LEAVE_CHAT, addr, (current_client_pseudoColored))



async def main():
    """
    Lancer le serveur WebSocket.
    """
    async with websockets.serve(handle_client_msg, "127.0.0.1", 8888):
        print("Serveur démarré sur ws://127.0.0.1:8888")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
