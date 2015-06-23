# coding=utf-8
from pytg import Telegram
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
   filename="svcbot.log",
   filemode='a'
)
 
#stdout_logger = logging.getLogger('STDOUT')
#sl = StreamToLogger(stdout_logger, logging.INFO)
#sys.stdout = sl
 
#stderr_logger = logging.getLogger('STDERR')
#sl = StreamToLogger(stderr_logger, logging.ERROR)
#sys.stderr = sl

# Constants

GOO_GL_API_KEY = config.GOO_GL_API_KEY
ROOT_PATH = config.ROOT_PATH
DEVELOPEMENT_MODE = config.DEVELOPEMENT_MODE
TELEGRAM_DIR = config.TELEGRAM_DIR
TELEGRAM_CERT = config.TELEGRAM_CERT
SELF = config.SELF
VERSION = "ver 0.1.0 build 20150613"

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
		"Error occured while logging in LMS.", #2
		"User not found.", #3
		"Invalid School ID.", #4
		"You have not logged in yet, or you have already logged out.", #5
		"Invalid parameter.", #6
		"Login required.", #7
		"Error occurend while logging in AJINC.", #8
		"You don't play-play ah." #9 for calling on private methods
	]

	_services = ['LMSdaily', 'attendance']

	# 
	# Init & Helpers
	# 

	def __init__(self, msg, tid, group = False):

		# init
		self._db = sqlite3.connect(ROOT_PATH + 'database.db')
		self._c = self._db.cursor()
		# Debug info
		if (msg[:1] == "!"):
			return
		uid = self._get_uid(tid)

		if (msg[:7] == "/cancel"):
			self._clear_status(uid)
			self._send("Action has been cancelled. What else can I do for you?", uid)
			return
		if (not self._get_status(uid) == None):
			fn = getattr(self, self._get_status(uid))
			fn(msg, uid)
			return

		if (msg[:1] == '/'):
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
		self._send(msg, uid)

		if clear_status:
			self._clear_status(uid)
			pass

	def _clear_status(self, uid):
		self._c.execute("UPDATE users SET status = NULL, status_para = NULL WHERE id = ?", (uid, ))
		self._db.commit()
		pass

	def _send(self, msg, uid):
		global sender
		tid = self._get_tid(uid)
		msg = msg.splitlines()
		for i in range(int(len(msg) / 40)):
			batch = "["+str(i+1)+"/"+str(int(len(msg) / 40)+1)+"] \n"
			batch += "\n".join(msg[40*i:40*(i+1)-1])
			if DEVELOPEMENT_MODE:
				batch = "![ 1A23SvcBot ]\n" + batch
			sender.send_msg(tid, batch)
		if int(len(msg) / 40) > 0:
			batch = "["+str(int(len(msg) / 40)+1)+"/"+str(int(len(msg) / 40)+1)+"] \n"
		else:
			batch = ""
		batch += "\n".join(msg[40*int(len(msg) / 40):])
		if DEVELOPEMENT_MODE:
			batch = "![ 1A23SvcBot ]\n" + batch
		sender.send_msg(tid, batch)

	def _set_status(self, status, uid):
		print("yay")
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
		print('before', uid)
		self._c.execute("DELETE FROM LMS WHERE uid = ?", (uid, ))
		print ('between')
		self._db.commit()
		print ('end')		

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
		"""

		:rtype :
		"""
		return self._c.execute('SELECT username, password FROM AJINC WHERE uid = ?', (uid, )).fetchall()[0]
	def _shortern_url(self, url):
		return requests.post("https://www.googleapis.com/urlshortener/v1/url?key="+GOO_GL_API_KEY, data=json.dumps({"longUrl":url}), headers={"Content-type":"application/json"}).json()['id']

	def _get_LMSdaily_subscribers(self):
		result = self._c.execute('SELECT uid FROM config WHERE "key" == "LMSdaily" AND "value" = "1"').fetchall()
		return [a[0] for a in result]

	def _get_attendance_subscribers(self):
		result = self._c.execute('SELECT uid FROM config WHERE "key" == "attendance" AND "value" = "1"').fetchall()
		return [a[0] for a in result]
	# 
	# Commands
	# 

	def help (self, msg, uid):
		help_msg = r"""1A23 Service Bot

@SvcBot1a23 is currently in alpha test stage. You are welcomed to provide any suggestions. 

You can use this bot by sending the following commands.

/help - Show this help message. 
/h - Show a concise help message.
/loginLMS - Log into LMS.
/logoutLMS - Log out from LMS.
/loginAJINC - Log into AJINC.
/logoutAJINC - Log out from AJINC.
/LMSdaily - Check LMS updates.
/LMSdaily 10 - Check LMS updates in the recent 10 days. (Number of days must be between 1 and 30 inclusive.)
/attendance - Check attendance for today.
/attendance 8 31 - Check attendance on 8/31 (31st of August).
/cancel - Cancel the current action.
/about - About this bot.
/announcements - Check announcements from both LMS and AJINC.
/announcements (LMS|AJINC) number - Show detail of one announcement. e.g.: "/announcements LMS 3"
/sub <channel_name> - Subscribe to a channel. 
/unsub <channel_name> - Unsubscribe from a channel.

=== Not Available for now ===
/searchLMS keyword - Search resources in LMS.

For enquires and feedback, please contact @blueset .
"""
		self._send(help_msg, uid)

	def h (self, msg, uid):
		help_msg = "1A23 Service Bot\n\nSend the following messages to control this bot.\n\n/announcements - Check announcements"
		lmsL = self._is_AJINC_logged_in(uid)
		ajincL = self._is_AJINC_logged_in(uid)
		if lmsL:
			help_msg += "/LMSdaily - Check LMS updates.\n"
		else: 
			help_msg += "/loginLMS - Login LMS account. \n"
		if ajincL:
			help_msg += "/attendance - Check your attendance for today.\n" 
		else:
			help_msg += "/loginAJINC - Login AJINC account.\n"
		if lmsL or ajincL:
			help_msg += "/sub - Subscribe to a channel.\n"
		help_msg += "\nFor a more detailed help message, reply /help ."
		self._send(help_msg, uid)
		#self.help(msg, uid)

	def about (self, msg, uid):
		about_msg = r"""1A23 Service Bot (Version %s) brought to you by 1A23.com

@SvcBot1A23 is currently in alpha test stage. You are welcomed to provide any suggestions. 

For enquires and feedback, please contact @blueset .
"""

		self._send(about_msg % VERSION, uid)

	def loginLMS(self, msg, uid):
		if self._is_LMS_logged_in(uid):
			hint_msg = "You are already logged in, to log out, reply /logoutLMS ."
			self._send(hint_msg, uid)
			return

		self._set_status("_loginLMSun", uid)
		hint_msg = "Please tell me your LMS Username, or reply /cancel to quit."
		self._send(hint_msg, uid)

	def logoutLMS(self, msg, uid):
		if self._is_LMS_logged_in(uid):
			self._delete_LMS_account(uid)
			self._send("You've been successfully logged out from LMS.", uid)
		else:
			self._send_error(5, uid)

	def LMSdaily(self, msg, uid):
		if not self._is_LMS_logged_in(uid):
			self._send_error(7, uid, error_msg="Please login to LMS with /loginLMS .")
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

		self._send(msg, uid)

	def loginAJINC(self, msg, uid):
		if self._is_AJINC_logged_in(uid):
			hint_msg = "You are already logged in, to log out, reply /logoutAJINC ."
			self._send(hint_msg, uid)
			return

		self._set_status("_loginAJINCun", uid)
		hint_msg = "Please tell me your AJINC Username, or reply /cancel to quit."
		self._send(hint_msg, uid)

	def logoutAJINC(self, msg, uid):
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
			an = "Here are the list of announcements. \n\n"
			if not lms:
				an += "You havent logged into LMS. \n"
			else: 
				for key, item in enumerate(lmsA):
					an += "[ LMS %s ] %s\n" % (key, item.title)
			for key, item in enumerate(ajincA):
				an += "[ AJINC %s ] %s\n" % (key, item['title'])

			an += "\nReply /announcements (LMS|AJINC) id for detial."
			self._send(an, uid)
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
				self._send(an, uid)
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
				self._send(an, uid)
				return
			else:
				self._send_error(6, uid, "Source must be either LMS or AJINC.")
				return

	def sub(self, msg, uid):
		if msg == '':
			msg = """Subscribe to a service.
After subscribing to it, you can receive daily messages of that channel.

Currently available channels are:
"""
			msg = msg + "\n".join(self._services)
			self._send(msg, uid)
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
		self._send("You are now subscribed to %s." % msg, uid)


	def unsub(self, msg, uid):
		if not msg in self._services:
			error_msg = "%s is not an available service. \nYou can unsubscribe from the following:\n%s" % (msg, "\n".join(self._services))
			self._send_error(6, uid, error_msg = error_msg)
			return
		query = """INSERT OR REPLACE INTO config (id, uid, `key`, value) VALUES (
(SELECT id FROM config WHERE uid = ? AND `key` = ?),
?,
?,
0)"""
		self._c.execute(query, (uid, msg, uid, msg))
		self._send("You are now unsubscribe from %s." % msg, uid)

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
		for i in range(len(self._LMSschoolList)):
			hint_msg += str(i)+": "+self._LMSschoolList[i]+"\n"
		self._send(hint_msg, uid)

	def _loginLMSsc(self, msg, uid):
		try:
			school = self._LMSschoolList[int(msg)]
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
		self._send(hint_msg, uid)
		self._clear_status()

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

# Daemon stuff.

class MyDaemon(daemon):
	def run(self):
		tg = Telegram(
		    telegram=TELEGRAM_DIR,
		    pubkey_file=TELEGRAM_CERT)
		global sender
		receiver = tg.receiver
		sender = tg.sender
		receiver.start()
		receiver.message(main_loop())
		receiver.stop()
		tg.stopCLI()

@coroutine 
def main_loop():
	while True:
		msg = (yield) 
		if (msg.event == "message" and msg.receiver.cmd == SELF):
			SvcBot(msg.text, msg.sender.cmd)
		else: 
			dprint("Not a message:", msg.event)

if (__name__ == "__main__"):
	daemon = MyDaemon('/tmp/daemon-example.pid')
	if (len(sys.argv) == 2):
		if 'start' == sys.argv[1]:
			daemon.start()
		elif 'stop' == sys.argv[1]:
			daemon.stop()
		elif 'restart' == sys.argv[1]:
			daemon.restart()
		elif 'run' == sys.argv[1]:
			daemon.run()
		else:
			print ("Unknown command")
			sys.exit(2)
		sys.exit(0)
	else:
		print ("usage: %s start|stop|restart|run" % sys.argv[0])
		sys.exit(2)

			