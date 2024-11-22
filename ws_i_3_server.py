import asyncio
import websockets

CLIENTS = {}

async def handle_client_msg(websocket):
    """
    Used to handle data received from client
    """
    global CLIENTS

    addr = websocket.remote_address
    print(f"New connection from {addr[0]}:{addr[1]}")

    try:
        message = await websocket.recv()
        print(f"Message received from {addr[0]}:{addr[1]} : {message!r}")

        if addr not in CLIENTS:
            CLIENTS[addr] = {"websocket": websocket}
            if 'Hello|' in message:
                pseudo = message.split("Hello|")[1]
                CLIENTS[addr]["pseudo"] = pseudo

                for client_addr, client_data in CLIENTS.items():
                    if client_addr != addr:
                        client_data["websocket"].send(f"Annonce : {pseudo} a rejoint la chatroom".encode())
        else:
            pseudo = CLIENTS[addr]["pseudo"]

        while True:
            message = await websocket.recv()
            print(f"Message received from {addr[0]}:{addr[1]} : {message!r}")

            for client_addr, client_data in CLIENTS.items():
                if client_addr != addr:
                    await client_data["websocket"].send(f"{pseudo} a dit : {message}".encode())
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection with {addr[0]}:{addr[1]} closed with error: {e}")
    finally:
        if addr in CLIENTS:
            del CLIENTS[addr]

async def main():
    """
    Main function to start the WebSocket server
    """
    server = await websockets.serve(handle_client_msg, '127.0.0.1', 8888)
    print("Server started on ws://127.0.0.1:8888")

    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
