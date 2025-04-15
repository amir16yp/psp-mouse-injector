# PSP Mouse Injector

A mouse-to-gamepad injector for PPSSPP emulator, designed to enable native mouse aim in Medal of Honor: Heroes.

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/username/psp-mouse-injector/build.yml?branch=main)
![License](https://img.shields.io/github/license/username/psp-mouse-injector)

## Features

- Real-time mouse movement injection into PPSSPP emulator
- Automatic detection of different PPSSPP variants (SDL, Qt) (qt seems broken rn)
- Adjustable mouse sensitivity
- Option to invert mouse Y-axis
- Auto-detection of game memory layout

## Installation

### Prerequisites

- Python 3.6+
- PPSSPP emulator (SDL or Qt version)
- Linux operating system

### Option 1: Download pre-built binary

Download the latest release from the [Releases](https://github.com/username/psp-mouse-injector/releases) page.

### Option 2: Install from source

1. Clone the repository:
   ```bash
   git clone https://github.com/username/psp-mouse-injector.git
   cd psp-mouse-injector
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) For better cursor handling, install xdotool or unclutter:
   ```bash
   sudo apt install xdotool unclutter
   ```

## Usage

1. Start PPSSPP and load Medal of Honor: Heroes.

2. In a terminal, run the injector:
   ```bash
   python mohh1-mouse-injector.py
   ```

3. The injector will automatically detect the PPSSPP process, find the game's memory, and start injecting mouse movements.

4. To stop the injector, press `Ctrl+C` in the terminal.

## Configuration

You can modify the following parameters in the `main()` function:

- `sensitivity`: Adjust mouse sensitivity (default: 50.0)
- `invertpitch`: Invert Y-axis (default: False)
- `update_rate`: Update rate in seconds (default: 0.01)
- `ppsspp_process_names`: List of PPSSPP process names to search for

## How It Works

The injector:

1. Finds the PPSSPP process in memory
2. Locates the PSP game memory region (typically 32MB)
3. Finds the camera control data structures
4. Tracks mouse movements and injects them as camera angle changes
5. Updates the game's camera position in real-time

## Building from Source

To build a standalone executable:

```bash
pip install pyinstaller
pyinstaller --onefile --name psp-mouse-injector mohh1-mouse-injector.py
```

The executable will be created in the `dist` directory.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU GPLv2 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Got the offsets from a [https://github.com/MOW531/MouseInjectorDolphinDuck/](MouseInjectorDolphinDuck) fork, credits to him for finding them
