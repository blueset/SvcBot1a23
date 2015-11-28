# encoding=utf-8
import sqlite3
import json
import logging
import traceback

import requests
import config
from AJINC import AJINCAPI
from AJINC import AJINCAPILoginError
from LMSAPI import LMSAPI
"""1A23 Service Bot Telegram Bot API version"""
__author__ = "Eana Hufwe <iLove@1a23.com>"

# Constants

GOO_GL_API_KEY = config.GOO_GL_API_KEY
ROOT_PATH = config.ROOT_PATH
DEVELOPMENT_MODE = config.DEVELOPMENT_MODE
TELEGRAM_DIR = config.TELEGRAM_DIR
TELEGRAM_CERT = config.TELEGRAM_CERT
SELF = config.SELF
VERSION = "ver 1.3.5 build 20151128"
BOT_KEY = config.BOT_KEY
TEMP_PATH = config.TEMP_PATH


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
    filename=ROOT_PATH + "svcbot.log",
    filemode='a')

# stdout_logger = logging.getLogger('STDOUT')
# sl = StreamToLogger(stdout_logger, logging.INFO)
# sys.stdout = sl

# stderr_logger = logging.getLogger('STDERR')
# sl = StreamToLogger(stderr_logger, logging.ERROR)
# sys.stderr = sl


def dprint(*arg):
    if DEVELOPMENT_MODE:
        print(*arg)


class SvcBot:

    """SvcBot Object"""
    _db = None
    _c = None
    _LMSschoolList = ['ANDERSON_JC']
    _error_list = [
        "Command not found. Please send /h to get the list of commands.",  # 0
        "Not a command. Please send /h to get the list of commands.",  # 1
        "Error occurred while logging in LMS.",  # 2
        "User not found.",  # 3
        "Invalid School ID.",  # 4
        "You have not logged in yet, or you have already logged out.",  # 5
        "Invalid parameter.",  # 6
        "Login required.",  # 7
        "Error occurred while logging in AJINC.",  # 8
        "You don't play-play ah."  # 9 for calling on private methods
    ]

    _services = ['lmsdaily', 'attendance', 'jc2rev', 'timetable']

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

        uid = self._get_uid(tid)
        # Debug info
        msg = """Happy holiday!

Thank you for your support to 1A23 Service Bot. We are now looking for maintainers!
If you are, or you know any of your juniors, who are interested in programming and willing to contribute to this project, please do not hesitate to contact @blueset . Otherwise, you can directly check the source code at https://github.com/blueset/svcbot1a23 . We are waiting for you!
Meanwhile, @Svc1A23Bot is suspended until new maintainers are found.

We wish you a happy holiday and a happy new year!
Eana Hufwe < @blueset >
End of 2015
"""

        self._send(msg, uid)

    def _get_uid(self, tid):
        result = self._c.execute(
            'SELECT id FROM users WHERE tid = ?', (tid, )).fetchall()
        if len(result) == 0:
            self._c.execute('INSERT INTO users (tid) VALUES (?)', (tid, ))
            self._db.commit()
            return self._c.lastrowid
        else:
            return result[0][0]

    def _get_tid(self, uid):
        result = self._c.execute(
            'SELECT tid FROM users WHERE id = ?', (uid, )).fetchall()
        if len(result) == 0:
            self._send_error(3, uid)
            return
        return result[0][0]

    def _send_error(
            self,
            error_id,
            uid,
            error_msg="",
            clear_status=True,
            debug_info=""):
        for line in traceback.format_stack():
            dprint(line.strip())
        msg = "Error %s: %s (%s)" % (
            error_id, self._error_list[error_id], error_msg)
        if DEVELOPMENT_MODE:
            msg += "\n\nDebug info:\n" + debug_info
        msg += "\n\nTo report any issue, please contact @blueset ."
        reply_markup = {'hide_keyboard': True}
        self._send(msg, uid, reply_markup=reply_markup)

        if clear_status:
            self._clear_status(uid)
            pass

    def _clear_status(self, uid):
        self._c.execute(
            "UPDATE users SET status = NULL, status_para = NULL WHERE id = ?",
            (uid, ))
        self._db.commit()
        pass

    def _send(
            self,
            msg,
            uid,
            disable_web_page_preview=None,
            reply_to_message_id=None,
            reply_markup={'hide_keyboard': True},
            parse_mode=None):
        tid = self._get_tid(uid)
        msg = msg.splitlines()
        payload = {'chat_id': tid, 'text': msg}
        if disable_web_page_preview:
            payload['disable_web_page_preview'] = disable_web_page_preview
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            payload['reply_markup'] = json.dumps(
                reply_markup,
                separators=(',', ':'))
        if parse_mode:
            payload['parse_mode'] = parse_mode

        for i in range(int(len(msg) / 40)):
            batch = "[" + str(i + 1) + "/" + \
                str(int(len(msg) / 40) + 1) + "] \n"
            batch += "\n".join(msg[40 * i:40 * (i + 1) - 1])
            if DEVELOPMENT_MODE:
                batch = "![ 1A23SvcBot ]\n" + batch
            payload['text'] = batch
            self._HTTP_req('sendMessage', payload)

        if int(len(msg) / 40) > 0:
            batch = "[" + str(int(len(msg) / 40) + 1) + "/" + \
                str(int(len(msg) / 40) + 1) + "] \n"
        else:
            batch = ""

        batch += "\n".join(msg[40 * int(len(msg) / 40):])
        if DEVELOPMENT_MODE:
            batch = "![ 1A23SvcBot ]\n" + batch
        payload['text'] = batch
        self._HTTP_req('sendMessage', payload)

    def _set_status(self, status, uid):
        dprint("Setting status for user", uid, "to", status)
        self._c.execute(
            "UPDATE users SET status = ? WHERE id = ?", (status, uid, ))
        self._db.commit()

    def _get_status(self, uid):
        result = self._c.execute(
            'SELECT status FROM users WHERE id = ?', (uid, )).fetchall()
        return result[0][0]

    def _get_status_para(self, key, uid):
        result = self._c.execute(
            'SELECT status_para FROM users WHERE id = ?', (uid, )).fetchall()
        result = result[0][0]
        if result is None:
            return None
        dprint("getting status para json str", result)
        paras = json.loads(result)
        return paras[key]

    def _set_status_para(self, key, val, uid):
        result = self._c.execute(
            'SELECT status_para FROM users WHERE id = ?', (uid, )).fetchall()
        result = result[0][0]
        dprint("getting status para json str", result)
        if result is None:
            json_str = json.dumps({key: val})
        else:
            paras = json.loads(result)
            paras[key] = val
            json_str = json.dumps(paras)

        self._c.execute(
            "UPDATE users SET status_para = ? WHERE id = ?", (json_str, uid, ))
        self._db.commit()

    def _add_LMS_account(self, username, password, school, pid, uid):
        self._c.execute(
            "INSERT INTO LMS (username, password, school, puid, uid) VALUES (?, ?, ?, ?, ?)",
            (username, password, school, pid, uid, ))
        self._db.commit()

    def _is_LMS_logged_in(self, uid):
        result = self._c.execute(
            "SELECT * FROM LMS WHERE uid = ?", (uid, )).fetchall()
        if len(result) > 0:
            return True
        else:
            return False

    def _delete_LMS_account(self, uid):
        self._c.execute("DELETE FROM LMS WHERE uid = ?", (uid, ))
        self._db.commit()

    def _get_LMS_puid_school(self, uid):
        return self._c.execute(
            'SELECT puid, school FROM LMS WHERE uid = ?',
            (uid, )).fetchall()[0]

    def _is_AJINC_logged_in(self, uid):
        result = self._c.execute(
            "SELECT * FROM AJINC WHERE uid = ?", (uid, )).fetchall()
        if (len(result) > 0):
            return True
        else:
            return False

    def _add_AJINC_account(self, username, password, uid):
        self._c.execute(
            "INSERT INTO AJINC (username, password, uid) VALUES (?, ?, ?)", (
                username, password, uid, ))
        self._db.commit()

    def _delete_AJINC_account(self, uid):
        self._c.execute("DELETE FROM AJINC WHERE uid = ?", (uid, ))
        self._db.commit()

    def _get_AJINC_un_pw(self, uid):
        return self._c.execute(
            'SELECT username, password FROM AJINC WHERE uid = ?',
            (uid, )).fetchall()[0]

    def _shortern_url(self, url):
        return requests.post(
            "https://www.googleapis.com/urlshortener/v1/url?key=" +
            GOO_GL_API_KEY,
            data=json.dumps(
                {
                    "longUrl": url
                }),
            headers={
                "Content-type": "application/json"
            }).json()['id']
        # import urllib
        # payload = {'action': 'shorturl', 'url': url, 'format': 'json'}
        # return requests.post("http://tny.im/yourls-api.php?" +
        # urllib.parse.urlencode(payload)).json()['shorturl']

    def _get_subscribers(self, channel_name):
        result = self._c.execute(
            'SELECT uid FROM config WHERE "key" == ? AND "value" = "1"', (
                channel_name, )).fetchall()
        return [a[0] for a in result]

    @staticmethod
    def _HTTP_req(method, payload):
        req = requests.post(
            'https://api.telegram.org/bot%s/%s' % (BOT_KEY, method), payload)
        return req.json

    def _parse_timetable_string(self, tbl, now=False):
        empty = "⚪️"
        lesson = "🔵"
        result = ""
        import datetime
        t = datetime.datetime(1, 1, 1, 7, 15)
        period = datetime.timedelta(minutes=30)
        if tbl[-1]['type'] == 'empty':
            tbl = tbl[:-1]
        for lsn in tbl:
            lsn_type = empty if lsn['type'] == 'empty' else lesson
            lsn_name = "" if lsn['type'] == 'empty' else ' / '.join(list(
                set(self._parse_lesson_name(
                    lsn_raw_name)[1] for lsn_raw_name in
                    lsn['name']))) + " @ " + ' / '.join(lsn['venue'])
            for i in range(lsn['span']):
                t += period
                lsn_time = t.strftime("%H:%M")
                delta = t + period - datetime.datetime(
                    1, 1, 1, datetime.datetime.now().hour,
                    datetime.datetime.now().minute)
                if period > delta > datetime.timedelta(minutes=0):
                    lsn_type = '🔴'
                result += "%s %s %s\n" % (lsn_type, lsn_time, lsn_name)
        for i in range(2):
            t += period
            lsn_time = t.strftime("%H:%M")
            result += "%s %s %s\n" % (empty, lsn_time, '')
        return result

    @staticmethod
    def _parse_lesson_name(lesson):
        import re
        lsn_lst = config.LESSONS
        for key, val in lsn_lst.items():
            result = re.search(r'[^A-Za-z]%s[^A-Za-z]?' % key, lesson)
            if result:
                return val
        return [lesson, lesson]

    def _draw_timetable(self, tbl, time, username):
        import datetime
        WIDTH = 1240
        HEIGHT = 1753
        BANNER_FACTOR = 20
        FIRST_COLUMN_FACTOR = 8
        FONT_SIZE = 35
        LINE_SPACING = 0.2
        BANNER_SIZE = 30
        BANNER_SPACING = 10
        PADDING = [20, 20, 100, 20]  # L, R, T, B
        PADDING_DAY = [20, 20]
        PADDING_TIME = [10, 10]
        PADDING_LESSON_BOX = [8, 8, 8, 8]
        BANNER_TEXT = "Timetable on %s for %s" % (
            time.strftime("%-d %b, %Y"), username)
        BANNER_SUB = "Created with 1A23 Service Bot @Svc1A23Bot http://svcbot.1a23.com"
        WRAP_WIDTH = 12

        first_col_width = int(
            (WIDTH - PADDING[0] - PADDING[1]) / FIRST_COLUMN_FACTOR)
        banner_height = int((HEIGHT - PADDING[2] - PADDING[3]) / BANNER_FACTOR)
        cell_width = int(
            (WIDTH - PADDING[1] - PADDING[0] - first_col_width) / 5)

        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
        draw = ImageDraw.Draw(img)

        b_reg = ImageFont.truetype(
            ROOT_PATH + "Roboto-Regular.ttf", int(BANNER_SIZE * 0.8))
        b_bold = ImageFont.truetype(ROOT_PATH + "Roboto-Bold.ttf", BANNER_SIZE)

        draw.rectangle([0, 0, WIDTH, 90], fill=(87, 165, 240))
        draw.text([BANNER_SPACING, BANNER_SPACING],
                  BANNER_TEXT,
                  fill='white',
                  font=b_bold)
        draw.text([BANNER_SPACING, BANNER_SPACING * 2 + BANNER_SIZE],
                  BANNER_SUB,
                  fill='white',
                  font=b_reg)

        # L, R, T, B, Banner
        draw.line([PADDING[0], PADDING[2], PADDING[0], HEIGHT - PADDING[3]],
                  fill='black',
                  width=5)
        draw.line([WIDTH - PADDING[1], PADDING[2], WIDTH - PADDING[1],
                   HEIGHT - PADDING[3]],
                  fill='black',
                  width=5)
        draw.line([PADDING[0], PADDING[2], WIDTH - PADDING[1], PADDING[2]],
                  fill='black',
                  width=5)
        draw.line([PADDING[0], HEIGHT - PADDING[3], WIDTH - PADDING[1],
                   HEIGHT - PADDING[3]],
                  fill='black',
                  width=5)
        draw.line([PADDING[0], int(PADDING[2] + banner_height),
                   WIDTH - PADDING[1], int(PADDING[2] + banner_height)],
                  fill='black',
                  width=5)

        # First column and others
        draw.line([int(PADDING[0] + first_col_width), PADDING[2],
                   int(PADDING[0] + first_col_width), HEIGHT - PADDING[3]],
                  fill='black',
                  width=2)
        for i in range(5):
            y_val = int(PADDING[0] + first_col_width + cell_width * (i + 1))
            draw.line([y_val, PADDING[2], y_val, HEIGHT - PADDING[3]],
                      fill='black',
                      width=2)

        r_reg = ImageFont.truetype(ROOT_PATH + "Roboto-Regular.ttf", FONT_SIZE)
        r_venue = ImageFont.truetype(
            ROOT_PATH + "Roboto-Regular.ttf", int(FONT_SIZE * 0.8))
        r_bold = ImageFont.truetype(ROOT_PATH + "Roboto-Bold.ttf", FONT_SIZE)

        draw.text(
            [PADDING[0] + first_col_width + cell_width * 0 + PADDING_DAY[0],
             banner_height - FONT_SIZE + PADDING[2] - PADDING_DAY[1]],
            "Mon",
            fill="black",
            font=r_reg)
        draw.text(
            [PADDING[0] + first_col_width + cell_width * 1 + PADDING_DAY[0],
             banner_height - FONT_SIZE + PADDING[2] - PADDING_DAY[1]],
            "Tue",
            fill="black",
            font=r_reg)
        draw.text(
            [PADDING[0] + first_col_width + cell_width * 2 + PADDING_DAY[0],
             banner_height - FONT_SIZE + PADDING[2] - PADDING_DAY[1]],
            "Wed",
            fill="black",
            font=r_reg)
        draw.text(
            [PADDING[0] + first_col_width + cell_width * 3 + PADDING_DAY[0],
             banner_height - FONT_SIZE + PADDING[2] - PADDING_DAY[1]],
            "Thu",
            fill="black",
            font=r_reg)
        draw.text(
            [PADDING[0] + first_col_width + cell_width * 4 + PADDING_DAY[0],
             banner_height - FONT_SIZE + PADDING[2] - PADDING_DAY[1]],
            "Fri",
            fill="black",
            font=r_reg)

        max_spans = 0
        for d in tbl:
            d2 = d[:-1] if d[-1]['type'] == 'empty' else d
            span = 0
            for l in d2:
                span += l['span']
            max_spans = span if max_spans < span else max_spans

        max_spans = max_spans + 1 if max_spans < 13 else max_spans

        cell_height = int(
            (HEIGHT - PADDING[2] - PADDING[3] - banner_height) / max_spans)

        t = datetime.datetime(1, 1, 1, 7, 15)
        period = datetime.timedelta(minutes=30)

        for i in range(1, max_spans + 1):
            t += period
            if i < max_spans:
                draw.line([PADDING[0],
                           PADDING[2] + banner_height + cell_height * i,
                           WIDTH - PADDING[1],
                           PADDING[2] + banner_height + cell_height * i],
                          fill='black',
                          width=2)
            textw, texth = draw.textsize(t.strftime("%H:%M"), font=r_reg)
            draw.text([first_col_width - textw + PADDING_TIME[0],
                       banner_height + cell_height *
                       (i - 1) + texth + PADDING[2] - PADDING_TIME[1]],
                      t.strftime('%H:%M'),
                      fill='black',
                      font=r_reg)

        lsn_kinds = []

        for d in tbl:
            for l in d:
                l['name'] = ' / '.join(list(set(self._parse_lesson_name(
                    lsn_raw_name)[0] for lsn_raw_name in l['name'])))
                l['venue'] = ' / '.join(l['venue'])
                if not l['name'] == '':
                    lsn_kinds.append(l['name'])

        lsn_kinds = list(set(lsn_kinds))
        lsn_kinds = dict(zip(lsn_kinds, config.COLORS))

        for d, dval in enumerate(tbl):
            span = 0
            for l in tbl[d]:
                if l['type'] == 'empty':
                    span += l['span']
                    continue
                draw.rectangle([
                    PADDING[0] + first_col_width + d * cell_width +
                    PADDING_LESSON_BOX[0], PADDING[2] + banner_height +
                    cell_height * span + PADDING_LESSON_BOX[2],
                    PADDING[0] + first_col_width +
                    (d + 1) * cell_width - PADDING_LESSON_BOX[1],
                    PADDING[2] + banner_height + cell_height *
                    (span + l['span']) - PADDING_LESSON_BOX[3]
                ],
                               fill=lsn_kinds[l['name']])
                from textwrap import wrap
                draw.multiline_text(
                    [
                        PADDING[0] + first_col_width + d * cell_width +
                        PADDING_LESSON_BOX[0] * 2, PADDING[2] + banner_height +
                        cell_height * span + PADDING_LESSON_BOX[2] * 2
                    ],
                    "\n".join(
                        wrap(
                            l['name'],
                            width=WRAP_WIDTH)),
                    fill='white',
                    font=r_bold)
                draw.multiline_text(
                    [PADDING[0] + first_col_width + d * cell_width +
                     PADDING_LESSON_BOX[0] * 2,
                     PADDING[2] + banner_height + cell_height * span +
                     PADDING_LESSON_BOX[2] * 2 + int(FONT_SIZE *
                                                     (1 + LINE_SPACING))],
                    "\n".join(wrap(l['venue'],
                                   width=WRAP_WIDTH)),
                    fill='white',
                    font=r_venue)
                span += l['span']

        timestamp = int(datetime.datetime.now().timestamp())
        img.save(TEMP_PATH + 'TBL_%s.png' % timestamp, format="PNG")
        return TEMP_PATH + 'TBL_%s.png' % timestamp

    def _send_image(
            self,
            fname,
            uid,
            msg='',
            delete=False,
            disable_web_page_preview=None,
            reply_to_message_id=None,
            reply_markup={'hide_keyboard': True}):
        tid = self._get_tid(uid)
        payload = {'chat_id': tid, 'caption': msg}
        if disable_web_page_preview:
            payload['disable_web_page_preview'] = disable_web_page_preview
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            payload['reply_markup'] = json.dumps(
                reply_markup,
                separators=(',', ':'))

        method = 'sendPhoto'
        requests.post(
            'https://api.telegram.org/bot%s/%s' % (BOT_KEY, method),
            files={
                'photo': open(
                    fname, 'rb')
            },
            data=payload)
        if delete:
            import os
            os.remove(fname)

    @staticmethod
    def _escape_tg_markdown(s):
        import re
        s = re.sub(r"([_*])", r"\\\1", s)
        s = re.sub(r"\[(.*?)\]", r"\\[\1]", s)
        return s

    @staticmethod
    def _escape_tg_md_url(s):
        return s.replace(")", "%29")

    def _broadcast(self, msg, reply_markup={'hide_keyboard': True}):
        lms = self._c.execute('SELECT uid FROM LMS').fetchall()
        ajinc = self._c.execute('SELECT uid FROM AJINC').fetchall()
        suber = self._c.execute(
            'SELECT uid FROM config WHERE value = 1').fetchall()
        lms = [i[0] for i in lms]
        ajinc = [i[0] for i in ajinc]
        suber = [i[0] for i in suber]
        user_list = list(set(lms) | set(ajinc) | set(suber))

        for uid in user_list:
            self._send(msg, uid, reply_markup=reply_markup)

        return

    #
    # Commands
    #
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
            keylist.append([str(i) + " " + self._LMSschoolList[i]])
            hint_msg += str(i) + " " + self._LMSschoolList[i] + "\n"
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
            if str(e) == 'ErrorCode 1:Index was outside the bounds of the array.':
                e = "The communication to LMS has some problem for now. Please try again in 5 minutes. (Yea, I really mean it.) " + str(
                    e)
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
            AJINCAPI(username, password)
        except AJINCAPILoginError as e:
            self._send_error(8, uid, error_msg=str(e))
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

    def md(self, msg, uid):
        msg = "Send me the text you want me to markdown.\n Supporting only *bold*, _italic_, and [link](url)."
        self._set_status("_markdown_echo", uid)
        self._send(msg, uid)

    def _markdown_echo(self, msg, uid):
        self._clear_status(uid)
        self._send(msg, uid, parse_mode="Markdown")

    #
    # Special Events
    #

