<p align="center">
  <img src="PMC_Logo.webp" width="120" height="120">
</p>

<h1 align="center">Mercdivers Contract Assistant (v1.0)</h1>

**The official tactical overlay for the "Mercdivers" PMC operational coordination.**

This tool is a lightweight, non-intrusive overlay designed to display real-time contracts/bounties, their objectives, rewards and deadlines directly over your **HELLDIVERS™ 2** interface. 

---

## Key Features
* **Real-time Synchronization:** Automatically fetches the latest mission data from the Mercdivers PMC Discord server, using discord bot and Gist.
* **Simple design with simple control:** Adjustable for any resolution and window position, requires two buttons to work.
* **Performance Optimized:** Comically lightweight (as possible with Python Executable) and zero perfomance impact.

---

## Installation & Usage

1.  **Download:** Go to the [Releases](https://github.com/Turianel/Mercdivers-Contract-Assistant/releases/tag/Release) section and download `MercTracker.exe`.
2.  **Launch:** Run **HELLDIVERS™ 2** first (Borderless Windowed mode recommended), then start the assistant.
3.  **Controls:**
    * `Numpad 0`: Show / Hide the overlay.
    * `Left Alt (Hold)`: Enables mouse interaction (click tabs, scroll through objectives).
    * `Tray Icon`: Right-click for manual refresh or exit.

---

## For those who want dive into code...

**Almost every line of code was written by a Viber coder using Gemini.** 
I'm not a programmer and I make no secret of it.
So if you look at the code, you'll see comments in Russian and possibly some questionable coding decisions. However, my design functions as intended, doesn't break, and is as secure as possible.

**About the bot...** 
This build is intended for my personal hosting and relies on data from the .env file. If you want to host your own bot, you'll have to either use SOCKS5 proxy or remove the it from the code entirely. i'll add example .env file

**About the comments within the code...** 
Yes, they're in Russian. Sorry about that. If you need these garbage comments, the translators will help without any problem.

---



## ⚖️ License & Terms of Use

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

> [!IMPORTANT]
> **By using or modifying this software, you agree to the following:**
> * **Attribution:** You must give appropriate credit to the original creator (**Turianel Black**).
> * **Non-Commercial:** You may **not** use this material for commercial purposes (selling the app, charging for access, etc.).
> * **ShareAlike:** If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original.

---

## 🛠️ Tech Stack
* **Language:** Python 3.x
* **Framework:** PyQt6 (GUI)
* **Integration:** Win32 API for global input and window management.
* **Data:** JSON-based transmission via GitHub Gist.
