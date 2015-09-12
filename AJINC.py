from datetime import date, datetime

import os

import requests
from bs4 import BeautifulSoup


class AJINCAPILoginError(Exception):
    def __init__(self, error_message):
        self.error_message = error_message

    def __str__(self):
        return repr(self.error_message)


class AJINCAPI(object):
    __username = None
    __password = None
    __s = requests.Session()
    __payload = {}

    __response = None

    def __init__(self, username, password):
        self.__username = username
        self.__password = password
        r = self.__s.get("http://ajinc.wizlearn.com/ajinc")
        self._save_viewstate(r.text)
        sp = BeautifulSoup(r.text)
        inputs = sp.find_all('input')

        payload = {
            'Login1$UserName': username,
            'Login1$Password': password,
            'Login1$LoginButton': 'Log In',
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': '',
            'PasswordRecovery1$UserNameContainerID$UserName': '',
        }

        for item in inputs:
            if "value" in item.attrs and item['name'].startswith('__'):
                payload[item['name']] = item['value']

        login = self.__s.post('http://ajinc.wizlearn.com/AjInc/login.aspx', data=payload)
        self._save_viewstate(login.text)
        loginsp = BeautifulSoup(login.text).find("font", color="Red")
        if loginsp is not None:
            raise AJINCAPILoginError(loginsp.text)

    def _save_viewstate(self, text):
        sp = BeautifulSoup(text)
        inputs = sp.find_all('input')
        for item in inputs:
            if "value" in item.attrs and item['name'].startswith('__'):
                self.__payload[item['name']] = item['value']

    def check_attendance(self, months=date.today().month, day=date.today().day):
        attendance = self.__s.get('http://ajinc.wizlearn.com/ajinc/Student/Attendance/default.aspx')
        self._save_viewstate(attendance.text)
        at = BeautifulSoup(attendance.text)
        atsp = at.find(id='ctl00_ContentArea_tblAttendance')
        status = atsp.find_all('tr')[months].find_all('td')[day]['title']

        return status

    @staticmethod
    def check_announcements():
        html = requests.get("http://ajinc.wizlearn.com/ajinc").text
        filt = lambda t: t.has_attr("onclick") and t.name == "tr"
        titles = BeautifulSoup(html).find_all(filt)
        announcements = []
        announcement = {'title': '', 'author': '', 'time': None, 'content': '', 'attachments': []}
        attachment = {'name': '', 'link': ''}
        for title in titles:
            announcements.append(announcement.copy())
            announcements[-1]['title'] = title.find('b').text
            announcements[-1]['time'] = datetime.strptime(title.find_all('b')[1].text, "%A, %d-%b-%Y")
            announcements[-1]['content'] = os.linesep.join(
                [s for s in title.find_next_sibling().text.splitlines() if s])
            announcements[-1]['author'] = title.find_next_sibling().find_next_sibling().find('b').text[2:]
            atts = []
            for attr in title.find_next_sibling().find_next_sibling().find_all("a"):
                atts.append(attachment.copy())
                atts[-1]['name'] = attr.text
                atts[-1]['link'] = "http://ajinc.wizlearn.com" + attr.attrs['onclick'][59:-2]
            announcements[-1]['attachments'] = atts
        # pprint(announcements[-1])

        return announcements

    def get_timetable(self, tdate=date.today()):

        html = self.__s.get("http://ajinc.wizlearn.com/ajinc/Student/TimeTable/default.aspx")
        self._save_viewstate(html.text)
        import calendar
        last_day = calendar.monthrange(tdate.year, tdate.month)[1]
        payload = {
            '__EVENTTARGET': 'ctl00$ContentArea$btnGo',
            '__EVENTARGUMENT': 'btnGo',
            'ctl00_ContentArea_dpDate_picker_selecteddates': tdate.strftime("%Y.%-m.%-d.0.0.0"),
            'ctl00_ContentArea_dpDate_picker_visibledate': date.today().strftime("%Y.%-m.%-d"),
            'ctl00_ContentArea_dpDate_picker_picker': tdate.strftime("%a, %-d-%-b-%Y"),
            'ctl00_SchoolBuzzTopMenu_ContextData': '',
            'ctl00_ContentArea_dpDate_calendar_apparentvisibledate': date.today().strftime("%Y.%-m"),
            'ctl00_ContentArea_dpDate_calendar_selecteddates': tdate.strftime("%Y.%-m." + str(last_day)),
            'ctl00_ContentArea_dpDate_calendar_visibledate': date.today().strftime("%Y.%-m.%-d"),
        }
        payload.update(self.__payload)
        html = self.__s.post("http://ajinc.wizlearn.com/ajinc/Student/TimeTable/default.aspx", data=payload)
        self._save_viewstate(html.text)
        # html = self.__s.get("http://ajinc.wizlearn.com/ajinc/Student/TimeTable/default.aspx")

        soup = BeautifulSoup(html.text)
        trs = soup.find(id="ctl00_ContentArea_tblTimeSlots").find_all("tr")
        tbl = []
        day = []
        subject = {"name": [], "venue": [], "type": "", "span": 0}
        empty = {"name": [], "venue": [], "type": "empty", "span": 0}
        for tr in trs[1:]:
            trday = day.copy()
            for td in tr.find_all("td")[1:]:
                span = int(td.attrs['colspan'])
                if len(td.contents) == 0:  # empty day
                    if len(trday) == 0:
                        trday.append(empty.copy())
                        trday[-1]['span'] = span
                        pass
                    if trday[-1]['type'] == 'empty':
                        trday[-1]['span'] += span
                        pass
                    else:
                        trday.append(empty.copy())
                        trday[-1]['span'] = span
                        pass
                else:
                    name = []
                    venue = []
                    for i in range(int(len(td.contents) / 4)):
                        name.append(str(td.contents[i * 4]))
                        venue.append(str(td.contents[i * 4 + 2]))
                    trday.append(subject.copy())
                    trday[-1]['name'] = name
                    trday[-1]['venue'] = venue
                    trday[-1]['span'] = int(td.attrs['colspan'])
                    trday[-1]['type'] = td.attrs['title']
            tbl.append(trday.copy())
        return tbl

    def reset_session(self):
        self.__s.get("http://ajinc.wizlearn.com/ajinc/logout.aspx")
        self.__s.cookies.clear()
