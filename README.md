# PylaAI — Showdown Fork

This fork focuses on **Showdown** (trio). Other game modes still run off the upstream logic, but development effort and tuning here go into making Showdown play well end-to-end.

What the bot does in Showdown:

- **Analog joystick movement.** Brawlers are moved by a continuous angle, not WASD taps, so pathing and dodging are smoother than in the stock client-agnostic modes.
- **Follows teammates in trio** when there's no enemy to chase, with hysteresis so it doesn't ping-pong between two nearby teammates.
- **Passive roam** when alone and safe — slow rotation of standing still.
- **Poison fog avoidance.** Detects the fog and when a trusted fog mass enters the flee radius around the player, overrides movement to run the opposite way.
- **Wall-based unstuck detector + semicircle escape.** If surrounding walls stop moving while the bot is commanding movement, it's pressed against something — the bot retreats from the obstacle and then sweeps a semicircular arc around it. The arc side alternates between triggers.
- **Place-based trophy tracking.** Recognizes 1st/2nd/3rd/4th-place end screens and updates the trophy count accordingly.

---

PylaAI is currently the best external Brawl Stars bot.
This repository is intended for devs and it's recommended for others to use the official version from the discord.

**Warning :** This is the source-code, which is meant for developpers or people that know how to install python libraries and run python scripts --> The official build is linked in the discord, which is the source-code converted into an exe so you don't need additional knowledge to run the bot. (You will have to go through a linkvertise link)

How to run :
- One-click Windows setup:
  - Download or clone this repository.
  - Run `setup.exe` from the project folder.
  - The installer checks for Python 3.11 64-bit, installs Python 3.11.9 if needed, installs the bot dependencies, chooses GPU acceleration automatically when possible, and creates `Start PylaAI.bat`.
  - Start your emulator, open Brawl Stars, then run `Start PylaAI.bat`.

Manual setup :
- Install Python and Git. This project was tested with Python 3.11.
- Install an Android emulator with ADB support. MuMu Player, LDPlayer, BlueStacks, MEmu, and other ADB emulators may work.
- Clone this fork:
  `git clone https://github.com/paradies800/PylaAI-OP.git`
- Open the project folder:
  `cd PylaAI-OP`
- Install the required Python packages:
  `python setup.py install`
- Start your emulator and open Brawl Stars.
- Set the emulator resolution to 1920x1080 for best results.
- Run the bot:
  `python main.py`
- In the hub, choose the emulator you are using.
- Select your brawler setup, then press Start.

Brawl Stars API trophy autofill :
- Create an official Brawl Stars API token at https://developer.brawlstars.com/
- The token must allow your current public IP address.
- Open `cfg/brawl_stars_api.toml`.
- Fill in:
  `api_token = "YOUR_API_TOKEN"`
  `player_tag = "#YOURTAG"`
- When you click a brawler in the brawler selection window, the Current Trophies field is filled from the API automatically.
- If your public IP changes often, enable auto-refresh in `cfg/brawl_stars_api.toml`:
  `auto_refresh_token = true`
  `developer_email = "YOUR_DEVELOPER_EMAIL"`
  `developer_password = "YOUR_DEVELOPER_PASSWORD"`
- Auto-refresh logs in to the official developer portal, detects the current public IP, deletes old PylaAI-created keys, creates a fresh key for that IP, and saves it as `api_token`.
- Keep `delete_all_tokens = false` unless you really want every key on the developer account deleted.
- Do not share a filled `cfg/brawl_stars_api.toml`; the committed file should keep tokens, email, and password blank.

Push All 1k :
- Fill `cfg/brawl_stars_api.toml` first.
- Start your emulator, open Brawl Stars, and leave the game on the lobby screen.
- Run `python main.py`.
- In the brawler selection window, press `Push All 1k`.
- The bot will sort the in-game brawler menu by Least Trophies, select the lowest trophy brawler, and build a queue for all known brawlers under 1000 trophies.

Recovery features :
- If Brawl Stars closes or another app is in front, the bot can relaunch Brawl Stars.
- If the Brawl Stars Idle Disconnect / Reload dialog appears, the bot presses Reload.
- If the scrcpy video feed freezes, the bot restarts the scrcpy feed instead of repeatedly restarting Brawl Stars.

Notes :
- This is the "localhost" version which means everything API related isn't enabled (login, online stats tracking, auto brawler list updating, auto icon updating, auto wall model updating). 
You can make it "online" by changing the base api url in utils.py and recoding the app to answer to the different endpoints. Site's code might become opensource but currently isn't.
- You can get the .pt version of the ai vision model at https://github.com/AngelFireLA/BrawlStarsBotMaking
- This repository won't contain early access features before they are released to the public.
- Please respect the "no selling" license as respect for our work.

Devs : 
- Iyordanov
- AngelFire

# Run tests
Run `python -m unittest discover` to check if your changes have made any regressions. 

# If you want to contribute, don't hesitate to create an Issue, a Pull Request, or/and make a ticket on the Pyla discord server at :
https://discord.gg/xUusk3fw4A

Don't know what to do ? Check the To-Fix and Idea lists :
https://trello.com/b/SAz9J6AA/public-pyla-trello
