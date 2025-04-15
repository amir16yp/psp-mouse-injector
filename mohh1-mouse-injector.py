#!/usr/bin/env python3
import os
import re
import struct
import subprocess
import mmap
import time
import threading
import signal
import sys
from typing import Optional, Union, Tuple, List
from datetime import datetime
import math

# Import libraries for mouse tracking
import pyautogui
from pynput.mouse import Controller as MouseController, Listener

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def hexdump(data: bytes, address: int = 0) -> str:
    """Create a hexdump of the data."""
    result = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        result.append(f"{address + i:08x}  {hex_str:<48}  {ascii_str}")
    return '\n'.join(result)

TAU = 6.2831853  # 0x40C90FDB

# PSP game memory addresses (offsets from game_memory_base)
MOHH1_CAMBASE_PTR = 0xD8361C
MOHH1_CAMY = 0x188
MOHH1_CAMX = 0x1A4
MOHH1_FOV = 0x1E8

class MouseTracker:
    def __init__(self):
        self.mouse = MouseController()
        self.prev_x = 0
        self.prev_y = 0
        self.delta_x = 0
        self.delta_y = 0
        self.is_tracking = False
        self.tracking_thread = None
        self.mouse_listener = None
        self.lock = threading.Lock()
        # Center the mouse when starting
        self.screen_width, self.screen_height = pyautogui.size()
        self.center_x = self.screen_width // 2
        self.center_y = self.screen_height // 2
        self.cursor_hidden = False
        
    def hide_cursor(self):
        """Try to hide the cursor using platform-specific methods."""
        # Only attempt on Linux
        if sys.platform.startswith('linux'):
            try:
                # Use xdotool to hide cursor
                subprocess.run(["xdotool", "mousemove_relative", "--sync", "--", "0", "0"], 
                               stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                self.cursor_hidden = True
                print("Cursor hidden")
            except (subprocess.SubprocessError, FileNotFoundError):
                print("Could not hide cursor. Install xdotool for better experience.")
        
    def show_cursor(self):
        """Show the cursor if it was hidden."""
        if self.cursor_hidden and sys.platform.startswith('linux'):
            try:
                # Use xdotool to show cursor
                subprocess.run(["xdotool", "mousemove_relative", "--sync", "--", "0", "0"], 
                               stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                self.cursor_hidden = False
                print("Cursor visible again")
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        
    def on_move(self, x, y):
        """Callback for mouse movement."""
        with self.lock:
            # Calculate relative movement from the previous position
            self.delta_x += x - self.prev_x
            self.delta_y += y - self.prev_y
            self.prev_x = x
            self.prev_y = y

    def start_tracking(self):
        """Start tracking mouse movements using a listener."""
        if self.is_tracking:
            return
            
        self.is_tracking = True
        
        # Try to hide the cursor
        self.hide_cursor()
        
        # Initialize position
        self.prev_x, self.prev_y = self.mouse.position
        
        # Start mouse listener
        self.mouse_listener = Listener(on_move=self.on_move)
        self.mouse_listener.start()
        
        print("Mouse tracking started. Move your mouse to control the game camera.")
        
    def stop_tracking(self):
        """Stop tracking mouse movements."""
        self.is_tracking = False
        
        # Show the cursor again
        self.show_cursor()
        
        # Stop the mouse listener
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        
    def get_and_reset_deltas(self):
        """Get the current movement deltas and reset them."""
        with self.lock:
            dx, dy = self.delta_x, self.delta_y
            self.delta_x = 0
            self.delta_y = 0
        return dx, dy

class ProcessMemory:
    def __init__(self, process_names: List[str]):
        self.process_names = process_names
        self.process_name = None  # The actual detected process name
        self.pid = self._find_pid()
        self.mem_file = None
        self.maps_file = None
        self.game_memory_base = None  # Base address for game memory
        if self.pid:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb+")
            self.maps_file = open(f"/proc/{self.pid}/maps", "r")
    
    def _find_pid(self) -> Optional[int]:
        """Find the process ID of any of the given process names."""
        for process_name in self.process_names:
            try:
                output = subprocess.check_output(["pgrep", "-f", process_name])
                pid = int(output.decode().strip())
                self.process_name = process_name
                print(f"Found PPSSPP process '{process_name}' with PID: {pid}")
                return pid
            except subprocess.CalledProcessError:
                continue
                
        print(f"No PPSSPP process found. Tried: {', '.join(self.process_names)}")
        return None
    
    def read_memory(self, address: int, size: int) -> bytes:
        """Read memory at the given address."""
        if not self.mem_file:
            raise RuntimeError("Process not found or memory file not opened")
        
        self.mem_file.seek(address)
        return self.mem_file.read(size)
    
    def write_memory(self, address: int, data: bytes) -> None:
        """Write data to memory at the given address."""
        if not self.mem_file:
            raise RuntimeError("Process not found or memory file not opened")
        
        self.mem_file.seek(address)
        self.mem_file.write(data)
    
    def read_int(self, address: int, size: int = 4) -> int:
        """Read an integer from memory."""
        data = self.read_memory(address, size)
        return int.from_bytes(data, byteorder='little')
    
    def write_int(self, address: int, value: int, size: int = 4) -> None:
        """Write an integer to memory."""
        data = value.to_bytes(size, byteorder='little')
        self.write_memory(address, data)
    
    def dump_memory_region(self, start: int, size: int, filename: str) -> None:
        """Dump a memory region to a file in binary format."""
        try:
            data = self.read_memory(start, size)
            with open(filename, 'wb') as f:  # Open in binary write mode
                f.write(data)  # Write the raw binary data
            print(f"Dumped memory to {filename}")
        except Exception as e:
            print(f"Error dumping memory: {e}")
    
    def find_game_memory(self) -> Optional[int]:
        """Scan memory regions to find the game memory offset."""
        if not self.maps_file:
            return None
            
        # PSP game memory is typically around 32MB
        TARGET_SIZE = 32 * 1024 * 1024  # 32MB in bytes
        SIZE_TOLERANCE = 0.1  # 10% tolerance for size matching
        MIN_SIZE = 1 * 1024 * 1024  # Minimum size of 1MB
        
        # Read memory maps
        maps_content = self.maps_file.read()
        self.maps_file.seek(0)
        
        regions = []
        print("Scanning memory regions...")
        
        # First pass: collect all relevant regions
        for line in self.maps_file:
            parts = line.split()
            if len(parts) < 6:
                continue
                
            # Parse memory range
            addr_range = parts[0].split('-')
            if len(addr_range) != 2:
                continue
                
            start_addr = int(addr_range[0], 16)
            end_addr = int(addr_range[1], 16)
            region_size = end_addr - start_addr
            
            # Store region info for debugging
            regions.append({
                'start': start_addr,
                'size': region_size,
                'perms': parts[1],
                'path': parts[-1] if len(parts) > 5 else ''
            })
        
        # Second pass: look for game memory
        for i, region in enumerate(regions):
            if region['size'] >= MIN_SIZE:  # Read-write, private, and at least 1MB
                # Check if region size is close to 32MB
                size_diff = abs(region['size'] - TARGET_SIZE) / TARGET_SIZE
                if size_diff <= SIZE_TOLERANCE:
                    print(f"\nFound potential game memory region (close to 32MB):")
                    print(f"Address: 0x{region['start']:08X} Size: {format_size(region['size'])} ({hex(region['size'])})")
                    
                    # Verify this is actually game memory by checking for non-zero content
                    try:
                        # Read first few bytes to verify
                        test_data = self.read_memory(region['start'], 4)
                        if any(test_data):  # If any bytes are non-zero
                            print(f"Found non-zero content at: 0x{region['start']:08X}")
                            print(f"First 4 bytes: {test_data.hex()}")
                            
                            # Additional verification: check for PSP memory signature
                            if test_data[0] != 0 and test_data[1] != 0:
                                print("Found potential PSP memory signature")
                                self.game_memory_base = region['start']
                                return region['start']
                    except Exception as e:
                        print(f"Error reading memory: {e}")
                        continue
        
        print("\nNo suitable game memory region found.")
        return None
    
    def close(self):
        """Close the memory files."""
        if self.mem_file:
            self.mem_file.close()
            self.mem_file = None
        if self.maps_file:
            self.maps_file.close()
            self.maps_file = None

    # PSP memory read/write functions that use the game memory base
    def read_uint32(self, address: int) -> int:
        """Read a 32-bit unsigned integer from game memory (address is offset from game_memory_base)."""
        if not self.game_memory_base:
            print("Error: Game memory base not established. Call find_game_memory() first.")
            return 0
        return self.read_int(self.game_memory_base + address, size=4)

    def read_uint16(self, address: int) -> int:
        """Read a 16-bit unsigned integer from game memory."""
        if not self.game_memory_base:
            print("Error: Game memory base not established. Call find_game_memory() first.")
            return 0
        data = self.read_memory(self.game_memory_base + address, size=2)
        return int.from_bytes(data, byteorder='little')

    def read_float(self, address: int) -> float:
        """Read a float from game memory."""
        if not self.game_memory_base:
            print("Error: Game memory base not established. Call find_game_memory() first.")
            return 0.0
        data = self.read_memory(self.game_memory_base + address, size=4)
        return struct.unpack('f', data)[0]

    def write_uint16(self, address: int, value: int) -> None:
        """Write a 16-bit unsigned integer to game memory."""
        if not self.game_memory_base:
            print("Error: Game memory base not established. Call find_game_memory() first.")
            return
        data = value.to_bytes(2, byteorder='little')
        self.write_memory(self.game_memory_base + address, data)

    def write_float(self, address: int, value: float) -> None:
        """Write a float to game memory."""
        if not self.game_memory_base:
            print("Error: Game memory base not established. Call find_game_memory() first.")
            return
        data = struct.pack('f', value)
        self.write_memory(self.game_memory_base + address, data)

    def read_pointer(self, address: int) -> int:
        """Read a pointer from game memory and adjust it."""
        if not self.game_memory_base:
            print("Error: Game memory base not established. Call find_game_memory() first.")
            return 0
        # Equivalent to PSP_MEM_ReadPointer in C code
        val = self.read_uint32(address)
        if val:
            return val - 0x8000000  # Adjust pointer value as in C code
        return 0

    def psp_mohh1_status(self) -> bool:
        # check if ULUS-1014 is anywhere in the process memory
        for i in range(0, 0x10000000, 0x1000):
            if self.read_memory(i, 8) == b'ULUS-1014':
                return True
        return False
        
    def psp_mohh1_inject(self, xmouse: float, ymouse: float, sensitivity: float, invertpitch: bool) -> None:
        """Calculate mouse look and inject into the current game."""
        if not self.game_memory_base:
            print("Error: Game memory base not established. Call find_game_memory() first.")
            return
        
        # Read the camera base pointer
        cam_base = self.read_pointer(MOHH1_CAMBASE_PTR)
        if not cam_base:
            return

        # Read current FOV and adjust if necessary
        fov = self.read_float(cam_base + MOHH1_FOV)
        # if fov == 30:
        #     self.write_float(cam_base + MOHH1_FOV, 42.0)

        # If mouse is not moving, don't do anything
        if xmouse == 0 and ymouse == 0:  
            return

        # Read current camera angles
        cam_x = self.read_float(cam_base + MOHH1_CAMX)
        cam_y = self.read_float(cam_base + MOHH1_CAMY)

        # Calculate new camera angles based on mouse movement
        look_sensitivity = sensitivity / 20.0
        scale = 20000.0

        cam_x -= (xmouse * look_sensitivity / scale * fov)
        cam_y -= (ymouse * look_sensitivity / scale * fov) if not invertpitch else (-ymouse * look_sensitivity / scale * fov)

        # Adjust camera angles to stay within bounds
        # Equivalent to the while loops in C code for X axis
        while cam_x > TAU / 2:
            cam_x -= TAU
        while cam_x < -TAU / 2:
            cam_x += TAU
            
        # Clamp Y axis
        cam_y = max(min(cam_y, 1.483529806), -1.483529806)

        # Write the new camera angles
        self.write_float(cam_base + MOHH1_CAMX, cam_x)
        self.write_float(cam_base + MOHH1_CAMY, cam_y)

def signal_handler(sig, frame):
    """Handle Ctrl+C to stop the script gracefully."""
    print("Stopping mouse injector...")
    global running
    running = False
    sys.exit(0)

def main():
    # Register signal handler for graceful exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Configure script parameters
    sensitivity = 50.0
    invertpitch = False
    # List of PPSSPP process names to try
    ppsspp_process_names = ["PPSSPPSDL", "PPSSPPQt", "ppsspp"]
    update_rate = 0.01  # 100 Hz update rate
    
    # Start mouse tracker
    mouse_tracker = MouseTracker()
    
    # Connect to PPSSPP process
    process = ProcessMemory(ppsspp_process_names)
    
    if not process.pid:
        print(f"No PPSSPP process found. Make sure PPSSPP is running.")
        return
    
    try:
        # Find the game memory offset
        game_memory_offset = process.find_game_memory()
        if not game_memory_offset:
            print("\nCould not find game memory. Make sure a game is loaded in PPSSPP.")
            return
            
        print(f"\nFound game memory at offset: 0x{game_memory_offset:08X}")
        print("Starting mouse tracker...")
        
        # Start tracking mouse movements
        mouse_tracker.start_tracking()
        
        # Main loop - continuously inject mouse movement
        global running
        running = True
        print("Mouse injector running! Press Ctrl+C to exit.")
        
        while running:
            try:
                # Get mouse movement deltas
                dx, dy = mouse_tracker.get_and_reset_deltas()
                
                # Only inject if there's actual movement
                if dx != 0 or dy != 0:
                    # Inject mouse movement into game
                    process.psp_mohh1_inject(dx, dy, sensitivity, invertpitch)
                
                # Small sleep to prevent high CPU usage
                time.sleep(update_rate)
                
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(1)  # Wait a bit before retrying
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        mouse_tracker.stop_tracking()
        process.close()
        print("Mouse injector stopped.")

if __name__ == "__main__":
    main()
