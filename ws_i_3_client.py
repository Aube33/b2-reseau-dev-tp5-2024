import asyncio
import aioconsole
import websockets

async def receive_responses(websocket):
    """
    Used to receive server responses asynchronously over WebSocket.
    """
    while True:
        try:
            data = await websocket.recv()
            print("#", data.decode())
        except websockets.ConnectionClosed:
            print("Annonce : Le serveur est hors ligne")
            return

async def send_data(websocket):
    """
    Used to send data to server asynchronously over WebSocket.
    """
    while True:
        message = await aioconsole.ainput("> ")
        await websocket.send(message)

async def main():
    """
    Main function to have async WebSocket connection.
    """
    pseudo = input("Pseudo: ")

    uri = "ws://127.0.0.1:8888"
    async with websockets.connect(uri) as websocket:
        await websocket.send(f"Hello|{pseudo}")

        tasks = [
            receive_responses(websocket),
            send_data(websocket)
        ]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
