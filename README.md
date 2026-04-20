# PylaAI

PylaAI is currently the best external Brawl Stars bot.
This repository is intended for devs and it's recommended for others to use the official version from the discord.

**Warning :** This is the source-code, which is meant for developpers or people that know how to install python libraries and run python scripts --> The official build is linked in the discord, which is the source-code converted into an exe so you don't need additional knowledge to run the bot. (You will have to go through a linkvertise link)

How to run :
- Install Python and Git. This project was tested with Python 3.11.
- Install an Android emulator. MuMu Player is supported by this fork; LDPlayer, BlueStacks, MEmu, and other ADB emulators may also work.
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
- In the hub, choose your emulator. For MuMu Player, select `MuMu`.
- Select your brawler setup, then press Start.

Brawl Stars API trophy autofill :
- Create an official Brawl Stars API token at https://developer.brawlstars.com/
- The token must allow your current public IP address.
- Open `cfg/brawl_stars_api.toml`.
- Fill in:
  `api_token = "YOUR_API_TOKEN"`
  `player_tag = "#YOURTAG"`
- When you click a brawler in the brawler selection window, the Current Trophies field is filled from the API automatically.

Push All 1k :
- Fill `cfg/brawl_stars_api.toml` first.
- Start MuMu/Brawl Stars and leave the game on the lobby screen.
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
