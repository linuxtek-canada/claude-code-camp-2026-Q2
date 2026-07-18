#!/usr/bin/env python3
import socket
import time
import sys

def connect_and_login(username, password, actions=None):
    """Connect to MUD and send commands with proper timing"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect(('localhost', 4000))
    s.setblocking(False)
    
    buffer = b''
    
    def recv_all():
        nonlocal buffer
        try:
            while True:
                try:
                    data = s.recv(4096)
                    if data:
                        buffer += data
                    else:
                        break
                except BlockingIOError:
                    break
        except:
            pass
        return buffer.decode('utf-8', errors='replace')
    
    def send_cmd(cmd):
        time.sleep(0.5)
        cmd_bytes = (cmd + '\r\n').encode('utf-8')
        try:
            s.send(cmd_bytes)
        except:
            pass
    
    # Initial receive - get protocol detection
    time.sleep(3)
    output = recv_all()
    if output:
        print("=== Initial connection ===")
        print(output)
    
    # Send username
    send_cmd(username)
    time.sleep(2)
    output = recv_all()
    if output:
        print("=== After username ===")
        print(output)
    
    # Send password
    send_cmd(password)
    time.sleep(2)
    output = recv_all()
    if output:
        print("=== After password ===")
        print(output)
    
    # Execute additional actions if provided
    if actions:
        for action in actions:
            send_cmd(action)
            time.sleep(1)
            output = recv_all()
            if output:
                print(f"=== After '{action}' ===")
                print(output)
    
    s.close()

# Try with a valid name
connect_and_login("dummy", "helloworld", ["1"])
