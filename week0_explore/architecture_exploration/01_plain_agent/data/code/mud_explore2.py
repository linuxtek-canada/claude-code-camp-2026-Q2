#!/usr/bin/env python3
"""MUD exploration - find the bakery"""
import socket
import time
import re

def clean(text):
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text

def mud_login_and_cmd(commands_to_send):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect(('localhost', 4000))
    s.setblocking(False)
    
    # Protocol detection
    time.sleep(4)
    raw = b''
    try:
        while True:
            try:
                data = s.recv(4096)
                if data: raw += data
                else: break
            except BlockingIOError: break
    except: pass
    
    # Login
    time.sleep(0.5)
    s.send(b'dummy\r\n')
    time.sleep(1)
    s.send(b'helloworld\r\n')
    time.sleep(3)
    
    # Receive login
    raw = b''
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            s.settimeout(0.5)
            data = s.recv(4096)
            if data: raw += data
            else: break
        except BlockingIOError: continue
        except: break
    
    # Send commands
    for cmd in commands_to_send:
        time.sleep(0.5)
        s.send((cmd + '\r\n').encode('utf-8'))
        time.sleep(2)
        raw = b''
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                s.settimeout(0.5)
                data = s.recv(4096)
                if data: raw += data
                else: break
            except BlockingIOError: continue
            except: break
        output = clean(raw.decode('utf-8', errors='replace'))
        print(f"=== {cmd} ===")
        print(output[:3000])
    
    s.close()

# Explore east from Main Street, also check market and pet shop
mud_login_and_cmd([
    'south',           # Go to Main Street
    'east',            # Continue east on Main Street
    'look',
    'exits',
])
