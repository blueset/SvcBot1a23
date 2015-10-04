import main

bot = main.SvcBot({'message': {'text': "!", "from": {"id": 0}}})
Lsub = bot._get_subscribers("lmsdaily")
Asub = bot._get_subscribers("attendance")
Tsub = bot._get_subscribers("timetable")

for uid in Lsub:
    bot.lmsdaily("", uid)

for uid in Asub:
    bot.attendance("", uid)

for uid in Tsub:
    bot.timetable("", uid)
