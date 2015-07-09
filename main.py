# encoding=utf-8

"""1A23 Service Bot Telegram Bot API version"""
__author__ = "Eana Hufwe <iLove@1a23.com>"

from pytg.utils import coroutine
from pprint import pprint
from daemon import daemon
from AJINC import AJINCAPI
from LMSAPI import LMSAPI
import sqlite3
import sys
import json
import requests
import logging
import traceback
import config

# Constants

GOO_GL_API_KEY = config.GOO_GL_API_KEY
ROOT_PATH = config.ROOT_PATH
DEVELOPEMENT_MODE = config.DEVELOPEMENT_MODE
TELEGRAM_DIR = config.TELEGRAM_DIR
TELEGRAM_CERT = config.TELEGRAM_CERT
SELF = config.SELF
VERSION = "ver 1.0.5 build 20150709"
BOT_KEY = config.BOT_KEY

# Redirect STDOUT and STDERR to logger
class StreamToLogger(object):
	"""
	Fake file-like stream object that redirects writes to a logger instance.
	"""
	def __init__(self, logger, log_level=logging.INFO):
		self.logger = logger
		self.log_level = log_level
		self.linebuf = ''

	def write(self, buf):
		for line in buf.rstrip().splitlines():
			self.logger.log(self.log_level, line.rstrip())

	def flush(self):
		pass

logging.basicConfig(
   level=logging.DEBUG,
   format='[ %(asctime)s : %(levelname)s : %(name)s ] %(message)s',
   filename=ROOT_PATH+"svcbot.log",
   filemode='a'
)

#stdout_logger = logging.getLogger('STDOUT')
#sl = StreamToLogger(stdout_logger, logging.INFO)
#sys.stdout = sl

#stderr_logger = logging.getLogger('STDERR')
#sl = StreamToLogger(stderr_logger, logging.ERROR)
#sys.stderr = sl


def dprint(*arg):
	if DEVELOPEMENT_MODE:
		print (*arg)

class SvcBot:
	"""docstring for SvcBot"""
	_db = None
	_c = None
	_LMSschoolList = ['ANDERSON_JC']
	_error_list = [
		"Command not found. Please send /h to get the list of commands.", #0
		"Not a command. Please send /h to get the list of commands.", #1
		"Error occurred while logging in LMS.", #2
		"User not found.", #3
		"Invalid School ID.", #4
		"You have not logged in yet, or you have already logged out.", #5
		"Invalid parameter.", #6
		"Login required.", #7
		"Error occurred while logging in AJINC.", #8
		"You don't play-play ah." #9 for calling on private methods
	]

	_services = ['lmsdaily', 'attendance']

	#
	# Init & Helpers
	#

	def __init__(self, json_obj):

		# init
		self._db = sqlite3.connect(ROOT_PATH + 'database.db')
		self._c = self._db.cursor()
		try:
			msg = json_obj['message']['text']
			tid = json_obj['message']['from']['id']
		except:
			return

		# Debug info
		if (msg[:1] == "!"):
			return
		uid = self._get_uid(tid)

		if (msg[:7] == "/cancel"):
			self._clear_status(uid)
			self._send("Action has been cancelled. What else can I do for you?", uid, reply_markup={'hide_keyboard': True})
			return
		if (not self._get_status(uid) == None):
			fn = getattr(self, self._get_status(uid))
			fn(msg, uid)
			return

		if (msg[:1] == '/' and len(msg) > 1):
			para = msg[1:].split()
			if para[0][:1] == '_' and not DEVELOPEMENT_MODE:
				self._send_error(9, uid)
				return
			try:
				fn = getattr(self, para[0])
			except AttributeError as e:
				debug_msg = str(type(e)) + "\nArgs: " + str(e.args) + "\nErr: " + str(e) + "\n"
				self._send_error(1, uid, debug_info = debug_msg)
				return
			fn(" ".join(para[1:]), uid)
		else:
			if DEVELOPEMENT_MODE:
				pass
			else:
				self.help("",uid)

	def _get_uid(self, tid):
		result = self._c.execute('SELECT id FROM users WHERE tid = ?', (tid, )).fetchall()
		if (len(result) == 0):
			self._c.execute('INSERT INTO users (tid) VALUES (?)', (tid, ))
			self._db.commit()
			return self._c.lastrowid
		else:
			return result[0][0]

	def _get_tid(self, uid):
		result = self._c.execute('SELECT tid FROM users WHERE id = ?', (uid, )).fetchall()
		if (len(result) == 0):
			self._send_error(3, uid)
			return
		return result[0][0]

	def _send_error(self, error_id, uid, error_msg="", clear_status=True, debug_info=""):
		for line in traceback.format_stack():
			dprint (line.strip())
		msg = "Error %s: %s (%s)" % (error_id, self._error_list[error_id], error_msg)
		if DEVELOPEMENT_MODE:
			msg += "\n\nDebug info:\n" + debug_info;
		msg += "\n\nTo report any issue, please contact @blueset ."
		reply_markup = {'hide_keyboard': True}
		self._send(msg, uid, reply_markup=reply_markup)

		if clear_status:
			self._clear_status(uid)
			pass

	def _clear_status(self, uid):
		self._c.execute("UPDATE users SET status = NULL, status_para = NULL WHERE id = ?", (uid, ))
		self._db.commit()
		pass

	def _send(self, msg, uid, disable_web_page_preview=None, reply_to_message_id=None, reply_markup={'hide_keyboard': True}):
		tid = self._get_tid(uid)
		msg = msg.splitlines()
		payload = {'chat_id': tid, 'text': msg}
		if not disable_web_page_preview == None:
			payload['disable_web_page_preview'] = disable_web_page_preview
		if not reply_to_message_id == None:
			payload['reply_to_message_id'] = reply_to_message_id
		if not reply_markup == None:
			payload['reply_markup'] = json.dumps(reply_markup, separators=(',',':'))

		for i in range(int(len(msg) / 40)):
			batch = "["+str(i+1)+"/"+str(int(len(msg) / 40)+1)+"] \n"
			batch += "\n".join(msg[40*i:40*(i+1)-1])
			if DEVELOPEMENT_MODE:
				batch = "![ 1A23SvcBot ]\n" + batch
			payload['text'] = batch
			self._HTTP_req('sendMessage',payload)

		if int(len(msg) / 40) > 0:
			batch = "["+str(int(len(msg) / 40)+1)+"/"+str(int(len(msg) / 40)+1)+"] \n"
		else:
			batch = ""

		batch += "\n".join(msg[40*int(len(msg) / 40):])
		if DEVELOPEMENT_MODE:
			batch = "![ 1A23SvcBot ]\n" + batch
		payload['text'] = batch
		self._HTTP_req('sendMessage', payload)

	def _set_status(self, status, uid):
		dprint("Setting status for user", uid, "to", status)
		self._c.execute("UPDATE users SET status = ? WHERE id = ?", (status, uid, ))
		self._db.commit()

	def _get_status(self, uid):
		result = self._c.execute('SELECT status FROM users WHERE id = ?', (uid, )).fetchall()
		return result[0][0]

	def _get_status_para(self, key, uid):
		result = self._c.execute('SELECT status_para FROM users WHERE id = ?', (uid, )).fetchall()
		result = result[0][0]
		if result == None:
			return None
		dprint ("getting status para json str", result)
		paras = json.loads(result)
		return paras[key]

	def _set_status_para(self, key, val, uid):
		result = self._c.execute('SELECT status_para FROM users WHERE id = ?', (uid, )).fetchall()
		result = result[0][0]
		dprint ("getting status para json str", result)
		if result == None:
			json_str = json.dumps({key:val})
		else:
			paras = json.loads(result)
			paras[key]=val
			json_str = json.dumps(paras)

		self._c.execute("UPDATE users SET status_para = ? WHERE id = ?", (json_str, uid, ))
		self._db.commit()

	def _add_LMS_account(self, username, password, school, pid, uid):
		self._c.execute("INSERT INTO LMS (username, password, school, puid, uid) VALUES (?, ?, ?, ?, ?)", (username, password, school, pid, uid, ))
		self._db.commit()

	def _is_LMS_logged_in(self, uid):
		result = self._c.execute("SELECT * FROM LMS WHERE uid = ?", (uid, )).fetchall()
		if (len(result) > 0):
			return True
		else:
			return False

	def _delete_LMS_account(self, uid):
		self._c.execute("DELETE FROM LMS WHERE uid = ?", (uid, ))
		self._db.commit()

	def _get_LMS_puid_school(self, uid):
		return self._c.execute('SELECT puid, school FROM LMS WHERE uid = ?', (uid, )).fetchall()[0]

	def _is_AJINC_logged_in(self, uid):
		result = self._c.execute("SELECT * FROM AJINC WHERE uid = ?", (uid, )).fetchall()
		if (len(result) > 0):
			return True
		else:
			return False

	def _add_AJINC_account(self, username, password, uid):
		self._c.execute("INSERT INTO AJINC (username, password, uid) VALUES (?, ?, ?)", (username, password, uid, ))
		self._db.commit()

	def _delete_AJINC_account(self, uid):
		self._c.execute("DELETE FROM AJINC WHERE uid = ", (uid, ))
		self._db.commit()

	def _get_AJINC_un_pw(self, uid):
		return self._c.execute('SELECT username, password FROM AJINC WHERE uid = ?', (uid, )).fetchall()[0]

	def _shortern_url(self, url):
		#return requests.post("https://www.googleapis.com/urlshortener/v1/url?key="+GOO_GL_API_KEY, data=json.dumps({"longUrl":url}), headers={"Content-type":"application/json"}).json()['id']
		import urllib
		payload = {'action': 'shorturl', 'url': url, 'format': 'json'}
		return requests.post("http://tny.im/yourls-api.php?" + urllib.parse.urlencode(payload)).json()['shorturl']

	def _get_subscribers(self, channel_name):
		result = self._c.execute('SELECT uid FROM config WHERE "key" == ? AND "value" = "1"', (channel_name, )).fetchall()
		return [a[0] for a in result]

	def _HTTP_req(self, method, payload):
		req = requests.post('https://api.telegram.org/bot%s/%s' % (BOT_KEY, method), payload)
		import urllib
		return req.json

	#
	# Commands
	#

	def help (self, msg, uid):
		help_msg = r"""1A23 Service Bot

@Svc1A23Bot is currently in alpha test stage. You are welcomed to provide any suggestions.

You can use this bot by sending the following commands.

/help - Show this help message.
/h - Show a concise help message.
/loginlms - Log into LMS.
/logoutlms - Log out from LMS.
/loginajinc - Log into AJINC.
/logoutajinc - Log out from AJINC.
/lmsdaily - Check LMS updates.
/lmsdaily 10 - Check LMS updates in the recent 10 days. (Number of days must be between 1 and 30 inclusive.)
/attendance - Check attendance for today.
/attendance 8 31 - Check attendance on 8/31 (31st of August).
/cancel - Cancel the current action.
/about - About this bot.
/announcements - Check announcements from both LMS and AJINC.
/announcements (LMS|AJINC) number - Show detail of one announcement. e.g.: "/announcements LMS 3"
/sub <channel_name> - Subscribe to a channel.
/unsub <channel_name> - Unsubscribe from a channel.

For enquires and feedback, please contact @blueset .
"""
		self._send(help_msg, uid)

	def h (self, msg, uid):
		help_msg = "1A23 Service Bot\n\nSend the following messages to control this bot.\n\n/announcements - Check announcements\n"
		lmsL = self._is_AJINC_logged_in(uid)
		ajincL = self._is_AJINC_logged_in(uid)
		keyboard = [["/announcements","/help"],[]]
		if lmsL:
			help_msg += "/lmsdaily - Check LMS updates.\n"
			keyboard[1].append("/lmsdaily")
		else:
			help_msg += "/loginlms - Login LMS account. \n"
			keyboard[1].append("/loginlms")
		if ajincL:
			help_msg += "/attendance - Check your attendance for today.\n"
			keyboard[1].append("/attendance")
		else:
			help_msg += "/loginajinc - Login AJINC account.\n"
			keyboard[1].append("/loginajinc")
		if lmsL or ajincL:
			help_msg += "/sub - Subscribe to a channel.\n"
			keyboard[1].append("/sub")
		help_msg += "\nFor a more detailed help message, reply /help ."
		reply_markup = {'one_time_keyboard': True, "keyboard": keyboard}
		self._send(help_msg, uid, reply_markup=reply_markup)
		#self.help(msg, uid)

	def about (self, msg, uid):
		about_msg = r"""1A23 Service Bot (Version %s) brought to you by 1A23.com

@Svc1A23Bot is currently in alpha test stage. You are welcomed to provide any suggestions.

For enquires and feedback, please contact @blueset .
"""

		self._send(about_msg % VERSION, uid, disable_web_page_preview=True)

	def start(self, msg, uid):
		self.h(msg, uid)

	def loginlms(self, msg, uid):
		if self._is_LMS_logged_in(uid):
			hint_msg = "You are already logged in, to log out, reply /logoutlms ."
			self._send(hint_msg, uid)
			return

		self._set_status("_loginLMSun", uid)
		hint_msg = "Please tell me your LMS Username, or reply /cancel to quit."
		self._send(hint_msg, uid)

	def logoutlms(self, msg, uid):
		if self._is_LMS_logged_in(uid):
			self._delete_LMS_account(uid)
			self._send("You've been successfully logged out from LMS.", uid)
		else:
			self._send_error(5, uid)

	def lmsdaily(self, msg, uid):
		if not self._is_LMS_logged_in(uid):
			self._send_error(7, uid, error_msg="Please login to LMS with /loginlms .")
			return
		import datetime
		delta = datetime.timedelta(-1)
		if (not msg == ""):
			try:
				days = int(msg)
			except:
				self._send_error(6, uid, error_msg="%s is not number of days." % msg)
				return
			if days < 1 or days > 30:
				self._send_error(6, uid, error_msg="Number of days must be between 1 and 30 inclusive.")
				return
			delta = datetime.timedelta(0-days)

		hint_msg = "Connecting to LMS server. It may take a few seconds."
		self._send(hint_msg, uid)
		(puid, school) = self._get_LMS_puid_school(uid)

		l = LMSAPI.LMSAPI()
		dprint ("fetching from", puid, school)
		l.login_pid (puid, school)
		f = l.get_course_info()
		c = l.parse_course_info(f)
		r = l.find_resources_by_date(c, datetime.datetime.now()+delta, datetime.datetime.now())
		msg = "LMS Daily Update\n from " + str(datetime.datetime.now()+delta) + " \nto " + str(datetime.datetime.now()) + "\n\n"
		if len(r) == 0:
			msg += "There is no update."
		for res in r:
			res.url = self._shortern_url(res.url)
			msg += ("["+str(res.create_time)+"] " + str(res.title) +
					"\n - - From: " + res.course_name + "/" + res.section_name +
					"\n - - Download: " + res.url + "\n\n")

		self._send(msg, uid, disable_web_page_preview=True)

	def loginajinc(self, msg, uid):
		if self._is_AJINC_logged_in(uid):
			hint_msg = "You are already logged in, to log out, reply /logoutajinc ."
			self._send(hint_msg, uid)
			return

		self._set_status("_loginAJINCun", uid)
		hint_msg = "Please tell me your AJINC Username, or reply /cancel to quit."
		self._send(hint_msg, uid)

	def logoutajinc(self, msg, uid):
		if self._is_AJINC_logged_in(uid):
			self._delete_AJINC_account(uid)
			self._send("You are successfully logged out of AJINC.", uid)
		else:
			self._send_error(5, uid)

	def attendance(self, msg, uid):
		from datetime import datetime
		if not self._is_AJINC_logged_in(uid):
			self._send_error(7, uid, error_msg="Please login to AJINC with /loginALINC .")
			return
		(username, password) = self._get_AJINC_un_pw(uid)
		a = AJINCAPI(username, password)
		msg = msg.split(" ")
		if len(msg) < 2:
			adate = datetime.today()
			msg = [adate.month, adate.day]
		else:
			try:
				msg [0] = int(msg[0])
				msg [1] = int(msg[1])
				adate = datetime(year=datetime.today().year, month=msg[0], day=msg[1])
			except ValueError as e:
				self._send_error(6, uid, error_msg=str(e))
				return

		attendance = a.check_attendance(msg[0], msg[1])
		datestr = adate.strftime("%a, %d %b")
		result = "Your attendance is marked as \"%s\" on %s ." % (attendance, datestr)
		self._send(result, uid)

	def announcements(self, msg, uid):
		if msg == "":
			lms = self._is_LMS_logged_in(uid)
			if lms:
				(puid, school) = self._get_LMS_puid_school(uid)
				l = LMSAPI.LMSAPI()
				l.login_pid (puid, school)
				lmsxml = l.get_announcements()
				lmsA = l.parse_announcements(lmsxml)
			ajincA = AJINCAPI.check_announcements(None)

			keylist = []

			an = "Here are the list of announcements. \n\n"
			if not lms:
				an += "You havent logged into LMS. \n"
			else:
				for key, item in enumerate(lmsA):
					an += "[ LMS %s ] %s\n" % (key, item.title)
					keylist.append(["/ann LMS %s %s" % (key, item.title)])
			for key, item in enumerate(ajincA):
				an += "[ AJINC %s ] %s\n" % (key, item['title'])
				keylist.append(["/ann AJINC %s %s" % (key, item['title'])])
			an += "\nReply /announcements (LMS|AJINC) id for detial."
			reply_markup = {"keyboard": keylist, "one_time_keyboard": True}
			self._send(an, uid, reply_markup = reply_markup)
			return
		else:
			from datetime import datetime
			msg = msg.split()
			if len(msg) < 2:
				self._send_error(6, uid, "/announcements requires 2 parameters where only %s is given" % len(msg))
				return
			if not msg[1].isdecimal():
				self._send_error(6, uid, "2nd parameter of /announcements must be a number, where %s is given" % msg[1])
				return
			if msg[0] == "AJINC":
				ajincA = AJINCAPI.check_announcements(None)
				mid = int(msg[1])
				if mid >= len(ajincA):
					self._send_error(6, uid, "AJINC only have %s announcements, where number %s is asked." % (len(ajincA), mid))
					return
				an = "AJINC announcement number %s\n\n" % mid
				an += "Title: %s\n" % ajincA[mid]['title']
				an += "Time: %s\n" % ajincA[mid]['time'].strftime("%a, %d %b")
				an += "Author: %s\n" % ajincA[mid]['author']
				an += "==============\n%s" % ajincA[mid]['content']
				if len(ajincA[mid]['attachments']) > 0:
					an += "\n==============\nAttachments:\n"
				for att in ajincA[mid]['attachments']:
					an += "[ %s ] Link: %s \n" % (att['name'], self._shortern_url(att['link']))

				reply_markup = {'hide_keyboard': True}
				self._send(an, uid, reply_markup=reply_markup)
				return
			elif msg[0] == "LMS":
				lms = self._is_LMS_logged_in(uid)
				if not lms:
					self._send_error(7, uid)
				(puid, school) = self._get_LMS_puid_school(uid)
				l = LMSAPI.LMSAPI()
				l.login_pid (puid, school)
				lmsA = l.parse_announcements(l.get_announcements())
				mid = int(msg[1])
				if mid >= len(lmsA):
					self._send_error(6, uid, "LMS only have %s announcements, where number %s is asked." % (len(lmsA), mid))
					return
				an = "LMS announcement number %s\n\n" % mid
				an += "Title: %s\n" % lmsA[mid].title
				an += "Time: %s\n" % lmsA[mid].created_on.strftime("%a, %d %b")
				an += "Author: %s\n" % lmsA[mid].creator_name
				an += "==============\n%s" % lmsA[mid].message
				if len(lmsA[mid].attachments) > 0:
					an += "\n==============\nAttachments:\n"
				for att in lmsA[mid].attachments:
					an += "[ %s ] Link: %s \n" % (att.file_name, self._shortern_url(att.download_link))
				reply_markup = {'hide_keyboard': True}
				self._send(an, uid, reply_markup=reply_markup)
				return
			else:
				self._send_error(6, uid, "Source must be either LMS or AJINC.")
				return

	def ann(self, msg, uid):
		self.announcements(msg, uid)

	def sub(self, msg, uid):
		if msg == '':
			msg = """Subscribe to a service.
Receive daily message from channels.

Currently available channels are:
"""
			msg = msg + "\n".join(self._services)
			keylist = [["/sub "+svc] for svc in self._services]
			reply_markup = {'keyboard': keylist, 'one_time_keyboard': True}
			self._send(msg, uid, reply_markup=reply_markup)
			return
		if not msg in self._services:
			error_msg = "%s is not an available service. \nYou can subscribe to the following:\n%s" % (msg, "\n".join(self._services))
			self._send_error(6, uid, error_msg = error_msg)
			return
		query = """INSERT OR REPLACE INTO config (id, uid, `key`, value) VALUES (
(SELECT id FROM config WHERE uid = ? AND `key` = ?),
?,
?,
1)"""
		self._c.execute(query, (uid, msg, uid, msg))
		self._db.commit()
		reply_markup = {'hide_keyboard': True}
		self._send("You are now subscribed to %s." % msg, uid, reply_markup=reply_markup)


	def unsub(self, msg, uid):
		if not msg in self._services:
			error_msg = "You can unsubscribe from the following:\n%s" % ("\n".join(self._services))
			keylist = [["/unsub "+svc] for svc in self._services]
			reply_markup = {'keyboard': keylist, 'one_time_keyboard': True}
			self._send(msg, uid, reply_markup=reply_markup)
			return
		query = """INSERT OR REPLACE INTO config (id, uid, `key`, value) VALUES (
(SELECT id FROM config WHERE uid = ? AND `key` = ?),
?,
?,
0)"""
		self._c.execute(query, (uid, msg, uid, msg))
		self._db.commit()
		reply_markup = {'hide_keyboard': True}
		self._send("You are now unsubscribe from %s." % msg, uid, reply_markup=reply_markup)

	#
	# Status commands
	#

	def _loginLMSun(self, msg, uid):
		dprint("received username:", msg, "for user", uid)
		self._set_status("_loginLMSpw", uid)
		self._set_status_para("LMSun", msg, uid)
		hint_msg = "Please tell me your LMS password, or reply /cancel to quit."
		self._send(hint_msg, uid)

	def _loginLMSpw(self, msg, uid):
		self._set_status("_loginLMSsc", uid)
		self._set_status_para("LMSpw", msg, uid)
		hint_msg = "Please reply the number of your school, or reply /cancel to quit. \n We will add more schools along the way. \n\n"
		keylist = []
		for i in range(len(self._LMSschoolList)):
			keylist.append([str(i)+" "+self._LMSschoolList[i]])
			hint_msg += str(i)+" "+self._LMSschoolList[i]+"\n"
		reply_markup = {"keyboard": keylist, "one_time_keyboard": True}
		self._send(hint_msg, uid, reply_markup=reply_markup)

	def _loginLMSsc(self, msg, uid):
		try:
			msg = msg.split()
			school = self._LMSschoolList[int(msg[0])]
		except:
			self._send_error(4, uid)
			return
		username = self._get_status_para("LMSun", uid)
		password = self._get_status_para("LMSpw", uid)
		try:
			l = LMSAPI.LMSAPI()
			dprint("logging in", username, password, school)
			l.login(username, password, school)
		except LMSAPI.LMSAPILoginError as e:
			if (str(e) == 'ErrorCode 1:Index was outside the bounds of the array.'):
				e = "The communication to LMS has some problem for now. Please try again in 5 minutes. (Yea, I really mean it.) " + str(e)
			self._send_error(2, uid, error_msg=str(e))
			return
		hint_msg = "You have successfully logged in."
		self._add_LMS_account(username, password, school, l.pid, uid)
		reply_markup = {'hide_keyboard': True}
		self._send(hint_msg, uid, reply_markup=reply_markup)
		self._clear_status(uid)

	def _loginAJINCun(self, msg, uid):
		self._set_status("_loginAJINCpw", uid)
		self._set_status_para("AJINCun", msg, uid)
		hint_msg = "Please tell me your AJINC password, or reply /cancel to quit."
		self._send(hint_msg, uid)

	def _loginAJINCpw(self, msg, uid):
		username = self._get_status_para("AJINCun", uid)
		password = msg
		try:
			a = AJINCAPI(username, password)
		except AJINCAPILoginError as e:
			self._send_error(8, uid, error_msg = str(e))
			return
		hint_msg = "You have successfully logged in."
		self._add_AJINC_account(username, password, uid)
		self._send(hint_msg, uid)
		self._clear_status(uid)

	#
	# Easter eggs & Hidden features
	#

	def s(self, msg, uid):
		if msg == "":
			self._send("Sarcasm !!", uid)
