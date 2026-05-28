import socket
import uuid
import hashlib

def generate_host_id() -> str:
    """
    Deterministic host_id based on hostname + MAC address.
    Ensures it's unique per machine but stable across reboots.
    """
    hostname = socket.gethostname()
    mac = hex(uuid.getnode())[2:]
    raw = f"{hostname}-{mac}"
    return "HOST-" + hashlib.sha1(raw.encode()).hexdigest()[:12]