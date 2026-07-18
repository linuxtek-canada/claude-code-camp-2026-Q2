#!/usr/bin/env python3
"""Persistent MUD connection for exploration"""
import socket
import time
import re
import sys

def clean(text):
    """Strip ANSI escape codes and control chars"""
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text

def mud_login_and_cmd(commands_to_send):
    """Login once, then send all commands on same connection"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect(('localhost', 4000))
    s.setblocking(False)
    
    # Wait for protocol detection and drain initial noise
    time.sleep(4)
    raw = b''
    try:
        while True:
            try:
                data = s.recv(4096)
                if data:
                    raw += data
                else:
                    break
            except BlockingIOError:
                break
    except:
        pass
    initial = clean(raw.decode('utf-8', errors='replace'))
    print("=== Initial connection ===")
    print(initial[:1500])
    
    # Send credentials
    time.sleep(0.5)
    s.send(b'dummy\r\n')
    time.sleep(1)
    s.send(b'helloworld\r\n')
    time.sleep(3)
    
    # Receive login response
    raw = b''
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            s.settimeout(0.5)
            data = s.recv(4096)
            if data:
                raw += data
            else:
                break
        except BlockingIOError:
            continue
        except:
            break
    login_resp = clean(raw.decode('utf-8', errors='replace'))
    print("\n=== Login response ===")
    print(login_resp[:1500])
    
    # Now send all commands
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
                if data:
                    raw += data
                else:
                    break
            except BlockingIOError:
                continue
            except:
                break
        
        output = clean(raw.decode('utf-8', errors='replace'))
        print(f"\n=== Command: {cmd} ===")
        print(output[:3000])
    
    s.close()
    return True

# Explore: look, then move south, look, go north, look, check shops
# score: check player stats and class
mud_login_and_cmd(['score', 'help warrior', 'help thief'])
