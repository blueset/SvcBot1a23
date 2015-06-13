import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
import base64
import json
import os
from pprint import pprint

class AJINCAPILoginError(Exception):
    def __init__ (self, error_message):
        self.error_message = error_message
    def __str__ (self):
        return repr(self.error_message)

class AJINCAPI(object):
	__username = None
	__password = None
	__s = requests.Session()

	__response = None

	def __init__(self, username, password):
		self.__username = username
		self.__password = password
		r = self.__s.get("http://ajinc.wizlearn.com/ajinc")
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
			if ("value" in item.attrs and item['name'].startswith('__')):
				payload[item['name']] = item['value']
		 
		login = self.__s.post('http://ajinc.wizlearn.com/AjInc/login.aspx', data=payload)
		loginsp = BeautifulSoup(login.text).find("font", color="Red")
		if not loginsp == None:
			raise AJINCAPILoginError(loginsp.text)
		

	def check_attendance(self, months=date.today().month, day=date.today().day):
		attendance = self.__s.get('http://ajinc.wizlearn.com/ajinc/Student/Attendance/default.aspx')
		 
		at = BeautifulSoup(attendance.text)
		atsp = at.find(id='ctl00_ContentArea_tblAttendance')
		status = atsp.find_all('tr')[months].find_all('td')[day]['title']

		return status

	def check_announcements(self):
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
			announcements[-1]['content'] = os.linesep.join([s for s in title.find_next_sibling().text.splitlines() if s])
			announcements[-1]['author'] = title.find_next_sibling().find_next_sibling().find('b').text[2:]
			atts = []
			for attr in title.find_next_sibling().find_next_sibling().find_all("a"):
				atts.append(attachment.copy())
				atts[-1]['name'] = attr.text
				atts[-1]['link'] = "http://ajinc.wizlearn.com" + attr.attrs['onclick'][59:-2]
			announcements[-1]['attachments'] = atts
			#pprint(announcements[-1])

		return announcements