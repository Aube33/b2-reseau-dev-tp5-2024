import asyncio
import aioconsole
import websockets

# Global lock to synchronize user input
input_lock = asyncio.Lock()

async def receive_one_response(websocket):
    try:
        data = await websocket.recv()
        if "PASS|" in data or "NEWPASS|" in data:
            auth_data = data.split("|")  # PASS/NEWPASS | auth_token
            if len(auth_data) == 2:
                header = auth_data[0]
                token = auth_data[1]

                input_prompt = "New password > "
                if header == "PASS":
                    input_prompt = "Enter password > "

                input_password = await input_data(input_prompt)

                input_password = f"{header}|{token}|{input_password}"
                await send_data(websocket, input_password)
                return

        print("#", data)
    except websockets.ConnectionClosed:
        print("Annonce : Le serveur est hors ligne")
        return

async def receive_responses(websocket):
    while True:
        await receive_one_response(websocket)

async def input_data(prompt="> "):
    message = ""
    async with input_lock:
        while message == "":
            message = await aioconsole.ainput(prompt)
        return message
        

async def send_data(websocket, message):
    await websocket.send(message)

async def send_data_loop(websocket):
    while True:
        message = await input_data()
        await send_data(websocket, message)

async def main():
    pseudo = input("Pseudo: ")

    uri = "ws://127.0.0.1:8888"
    async with websockets.connect(uri) as websocket:
        await websocket.send(f"HELLO|{pseudo}")
        await receive_one_response(websocket)

        tasks = [
            asyncio.create_task(receive_responses(websocket)),
            asyncio.create_task(send_data_loop(websocket))
        ]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
