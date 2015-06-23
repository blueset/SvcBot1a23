from pytg import Telegram
from pprint import pprint
import config
import main

tg = Telegram(telegram=config.TELEGRAM_DIR, pubkey_file=config.TELEGRAM_CERT)

global sender
sender = tg.sender

main.sender = sender

bot = main.SvcBot("!", 0)
Lsub = bot._get_LMSdaily_subscribers()
Asub = bot._get_attendance_subscribers()
pprint (Lsub)
pprint (Asub)

for uid in Lsub:
	bot.LMSdaily("", uid)

for uid in Asub:
	bot.attendance("", uid)