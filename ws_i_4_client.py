import sys
import time
import re
import asyncio
import aioconsole
import websockets

input_lock = asyncio.Lock()

def color_format_string(string:str):
    """
    Transform minecraft color code in string to ANSI color
    """
    def hex_to_rgb(hex_code):
        """
        Transform minecraft color code to RGB (&#FFFFF -> (255,255,255))
        """
        hex_code = hex_code.replace("&#", "", 1)
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return r, g, b

    def replace_color(match):
        """
        Replace hexa color to ANSI color
        """
        hex_code = match.group(0)
        rgb = hex_to_rgb(hex_code)
        return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"

    def replace_minecraft_format(match):
        """
        Replace minecraft color code (&a, &b, &l, etc.) to ANSI color
        """
        color_map = {
            '&0': '30',  # Black
            '&1': '34',  # Blue
            '&2': '32',  # Green
            '&3': '36',  # Cyan
            '&4': '31',  # Red
            '&5': '35',  # Magenta
            '&6': '33',  # Yellow
            '&7': '37',  # Light gray
            '&8': '90',  # Gray
            '&9': '94',  # Light blue
            '&a': '92',  # Light green
            '&b': '96',  # Light cyan
            '&c': '91',  # Light red
            '&d': '95',  # Light magenta
            '&e': '93',  # Light yellow
            '&f': '97',  # White
            '&l': '1',   # Bold
            '&m': '9',   # Strikethrough
            '&n': '4',   # Underline
            '&o': '3',   # Italic
            '&r': '0'    # Reset
        }

        code = match.group(0)
        if code in color_map:
            return f"\033[{color_map[code]}m"
        return code


    str_output = re.sub(r"&#[A-Fa-f0-9]{6}", replace_color, string)
    str_output = re.sub(r"&[0-9a-fk-or]", replace_minecraft_format, str_output)
    return str_output + "\033[0m"

async def force_cancel(task, max_tries=10):
    """
    Force cancel asyncio task
    """
    tries = 0
    while not task.done():
        if tries >= max_tries:
            raise RuntimeError(f'Failed to cancel task {task} after {max_tries} attempts.')
        task.cancel()
        tries += 1
        await asyncio.sleep(1)

def print_title():
    """
    Print chat title in Ascii art
    """
    ascii_art = """
 ██████╗██╗  ██╗ █████╗ ████████╗
██╔════╝██║  ██║██╔══██╗╚══██╔══╝
██║     ███████║███████║   ██║   
██║     ██╔══██║██╔══██║   ██║   
╚██████╗██║  ██║██║  ██║   ██║   
 ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   
    """

    print("#"*len(ascii_art.split("\n")[1]))
    for line in ascii_art.split("\n"):
        print(line)
        time.sleep(0.07)

async def receive_one_response(websocket):
    """
    Receive and display one request from server
    """
    try:
        data = await websocket.recv()

        if "PASS|" in data or "NEWPASS|" in data:
            auth_data = data.split("|")  # PASS/NEWPASS | auth_token
            if len(auth_data) == 2:
                header = auth_data[0]
                token = auth_data[1]

                input_prompt = "Create password: "
                if header == "PASS":
                    input_prompt = "Enter password: "

                input_password = await input_data(input_prompt)

                input_password = f"{header}|{token}|{input_password}"
                await send_data(websocket, input_password)
                return

        data_colored = color_format_string(data)
        print(data_colored)
    except websockets.ConnectionClosed as e:
        raise e

async def receive_responses(websocket):
    """
    Receive in loop server data
    """
    try:
        while True:
            await receive_one_response(websocket)
    except (ConnectionError, websockets.ConnectionClosed) as e:
        raise e

async def input_data(prompt=""):
    """
    Get user input asynchronously
    """
    message = ""
    async with input_lock:
        while message == "":
            message = await aioconsole.ainput(prompt)
        return message

async def send_data(websocket, message):
    """
    Send data to server asynchronously
    """
    await websocket.send(message)

async def send_data_loop(websocket):
    """
    Ask in loop user input asynchronously
    """
    while True:
        message = await input_data()
        await send_data(websocket, message)

async def main():
    """
    Connection to websocket server and launch interface
    """

    print_title()
    pseudo = input("Username: ")

    uri = "ws://127.0.0.1:8888"
    tasks = []
    try:
        async with websockets.connect(uri) as websocket:
            # First request to login or register
            await websocket.send(f"HELLO|{pseudo}")
            await receive_one_response(websocket)
            print("")

            tasks = [
                asyncio.create_task(receive_responses(websocket)),
                asyncio.create_task(send_data_loop(websocket))
            ]
            await asyncio.gather(*tasks)
    except (websockets.ConnectionClosed, ConnectionError) as e:
        print(f"Error: {e}. Exiting the program.")
        for task in tasks:
            await force_cancel(task)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
