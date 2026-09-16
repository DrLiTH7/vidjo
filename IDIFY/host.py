import sys
import json
import struct
import subprocess
import os

import logging

logging.basicConfig(filename=os.path.join(os.path.dirname(__file__), 'host.log'), level=logging.DEBUG, format='%(asctime)s - %(message)s')

def get_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        logging.info("get_message: 0 bytes read, exiting")
        sys.exit(0)
    message_length = struct.unpack('@I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    logging.info(f"Received message: {message}")
    return json.loads(message)

def send_message(message):
    logging.info(f"Sending message: {message}")
    encoded_content = json.dumps(message).encode('utf-8')
    encoded_length = struct.pack('@I', len(encoded_content))
    sys.stdout.buffer.write(encoded_length)
    sys.stdout.buffer.write(encoded_content)
    sys.stdout.buffer.flush()

def main():
    logging.info("host.py started")
    while True:
        try:
            msg = get_message()
            command = msg.get("command")
            
            if command == "start":
                server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
                logging.info(f"Starting server: {server_path}")
                
                creationflags = 0
                if os.name == 'nt':
                    CREATE_NO_WINDOW = 0x08000000
                    DETACHED_PROCESS = 0x00000008
                    CREATE_NEW_PROCESS_GROUP = 0x00000200
                    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
                    creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
                    
                crash_log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_crash.log"), "w")
                
                exe_path = sys.executable
                if os.name == 'nt':
                    pythonw = exe_path.replace("python.exe", "pythonw.exe")
                    if os.path.exists(pythonw):
                        exe_path = pythonw
                
                env = os.environ.copy()
                scripts_dir = os.path.dirname(exe_path)
                if scripts_dir and scripts_dir not in env.get("PATH", ""):
                    env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")

                subprocess.Popen(
                    [exe_path, server_path],
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=crash_log,
                    stdin=subprocess.DEVNULL,
                    env=env
                )
                
                logging.info("Server started successfully")
                send_message({"status": "started"})
            elif command == "ping":
                send_message({"status": "pong"})
            else:
                logging.warning(f"Unknown command: {command}")
                send_message({"status": "unknown command"})
        except Exception as e:
            logging.error(f"Error: {e}")
            send_message({"status": "error", "message": str(e)})

if __name__ == "__main__":
    main()
