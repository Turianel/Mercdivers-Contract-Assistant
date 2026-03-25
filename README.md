# 🛰️ Mercdivers Contract Assistant (v1.0)

**The official tactical overlay for the "Mercdivers" PMC operational coordination.**

This tool is a lightweight, non-intrusive overlay designed to display real-time contracts, mission objectives, and rewards (Bounties) directly over your **HELLDIVERS™ 2** interface. 

---

## Key Features
* **Real-time Synchronization:** Automatically fetches the latest mission data from the Mercdivers PMC Discord server.
* **Simple design with simple control:** Adjustable for any resolution and window position, requires two buttons to work.
* **Performance Optimized:** Comically lightweight (as possible with Python Executable) and zero perfomance impact.

---

## Installation & Usage

1.  **Download:** Go to the [Releases](Later) section and download `MercTracker.exe`.
2.  **Launch:** Run **HELLDIVERS™ 2** first (Borderless Windowed mode recommended), then start the assistant.
3.  **Controls:**
    * `Numpad 0`: Show / Hide the overlay.
    * `Left Alt (Hold)`: Enables mouse interaction (click tabs, scroll through objectives).
    * `Tray Icon`: Right-click for manual refresh or exit.

---

## ⚖️ License & Terms of Use

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

> [!IMPORTANT]
> **By using or modifying this software, you agree to the following:**
> * **Attribution:** You must give appropriate credit to the original creator (**Turianel Black**).
> * **Non-Commercial:** You may **not** use this material for commercial purposes (selling the app, charging for access, etc.).
> * **ShareAlike:** If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original.

[![CC BY-NC-SA](https://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-nc-sa.png)](http://creativecommons.org/licenses/by-nc-sa/4.0/)

---

## 🛠️ Tech Stack
* **Language:** Python 3.x
* **Framework:** PyQt6 (GUI)
* **Integration:** Win32 API for global input and window management.
* **Data:** JSON-based transmission via GitHub Gist.
