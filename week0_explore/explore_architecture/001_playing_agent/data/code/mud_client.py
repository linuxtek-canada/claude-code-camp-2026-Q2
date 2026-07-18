#!/usr/bin/env python3
"""Persistent MUD connection for exploration"""
import socket
import time
import re

def clean(text):
    """Strip ANSI escape codes and control chars"""
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text

class MUDClient:
    def __init__(self):
        self.s = None
        self.buffer = ''
    
    def connect(self, username, password):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(10)
        self.s.connect(('localhost', 4000))
        self.s.setblocking(False)
        
        # Wait for protocol detection and drain initial noise
        time.sleep(4)
        raw = b''
        try:
            while True:
                try:
                    data = self.s.recv(4096)
                    if data:
                        raw += data
                    else:
                        break
                except BlockingIOError:
                    break
        except:
            pass
        self.buffer += raw.decode('utf-8', errors='replace')
        
        # Send credentials
        time.sleep(0.5)
        self._send(username)
        time.sleep(1)
        self._send(password)
        time.sleep(3)
        raw = b''
        try:
            while True:
                try:
                    data = self.s.recv(4096)
                    if data:
                        raw += data
                    else:
                        break
                except BlockingIOError:
                    break
        except:
            pass
        self.buffer += raw.decode('utf-8', errors='replace')
        print("=== Connected! ===")
    
    def _send(self, cmd):
        time.sleep(0.3)
        self.s.send((cmd + '\r\n').encode('utf-8'))
    
    def _recv(self, timeout=2):
        raw = b''
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.s.settimeout(0.5)
                data = self.s.recv(4096)
                if data:
                    raw += data
                else:
                    break
            except BlockingIOError:
                continue
            except:
                break
        text = raw.decode('utf-8', errors='replace')
        self.buffer += text
        return text
    
    def cmd(self, command, wait=2):
        """Send a command and wait for response"""
        self._send(command)
        return clean(self._recv(wait))
    
    def run(self, commands):
        """Run a list of commands"""
        results = []
        for cmd in commands:
            if isinstance(cmd, tuple):
                result = self.cmd(cmd[0], cmd[1])
            else:
                result = self.cmd(cmd)
            results.append((cmd, result))
            print(f"\n=== {cmd} ===")
            print(result[:3000])
        return results

# Create client and connect
mud = MUDClient()
mud.connect('dummy', 'helloworld')

# Explore
commands = [
    'look',
    'exits',
    'south',
    'look',
    'exits',
    'north',
    'look',
    'help shops',
]

mud.run(commands)
