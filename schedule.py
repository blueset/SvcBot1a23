from pprint import pprint
import config
import main

bot = main.SvcBot({'message':{'text':"!","from":{"id":0}}})
Lsub = bot._get_LMSdaily_subscribers()
Asub = bot._get_attendance_subscribers()

for uid in Lsub:
	bot.LMSdaily("", uid)

for uid in Asub:
	bot.attendance("", uid)