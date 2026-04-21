# pylaai-op-xxz

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

**Warning :** This is a source-code fork. It now includes a one-click Windows setup helper, but the official build and support are still linked in the Pyla Discord.

## Installation / How to run

For normal users, you only need `setup.exe`.

1. Download or clone this repository.
2. Open the project folder.
3. Run `setup.exe`.
4. Wait until setup finishes. It will:
   - install Python 3.11.9 if Python 3.11 64-bit is missing
   - install all required Python packages
   - install the best available ONNX Runtime option for your PC, including GPU acceleration when possible
5. Start your Android emulator.
6. Open Brawl Stars in the emulator.
7. Set the emulator resolution to `1920x1080` for best results.
8. Double-click `Run pylaai-op-xxz.bat` or run `python main.py`.
9. In the hub, choose your emulator, select your brawler setup, then press Start.

Manual developer setup:
- Install Python 3.11 and Git.
- Run `python setup.py install`.
- Run `python main.py`.

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

Performance troubleshooting :
- Run `python tools/performance_check.py`.
- If it says `CPUExecutionProvider`, run `setup.exe` again or set `cfg/general_config.toml` `cpu_or_gpu = "directml"`.
- On laptops with two GPUs, set Windows Graphics settings for `python.exe` and the emulator to High performance.
- If DirectML is active but still very slow, try `directml_device_id = "1"` in `cfg/general_config.toml`, then restart the bot.
- Turn off Windows Efficiency mode for the emulator if Task Manager shows it. Efficiency mode can cap emulator frame delivery and make the bot look stuck at 2-5 IPS.
- Keep some free RAM. If memory is above about 85%, close Discord/browser/other games before running the bot.

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
