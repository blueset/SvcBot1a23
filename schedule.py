from pprint import pprint
import config
import main

bot = main.SvcBot({'message':{'text':"!","from":{"id":0}}})
Lsub = bot._get_subscribers("lmsdaily")
Asub = bot._get_subscribers("attendance")

for uid in Lsub:
	bot.LMSdaily("", uid)

for uid in Asub:
	bot.attendance("", uid)