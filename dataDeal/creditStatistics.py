#coding:utf-8
import requests
import base64
import random

from bs4 import BeautifulSoup

import sys
default_encoding = 'utf-8'
if sys.getdefaultencoding() != default_encoding:
    reload(sys)
    sys.setdefaultencoding(default_encoding)

from models import Professions, Plan, Courses, MCCourses


# 在当前目录下创建可能的双专业个人信息
import os
DEBUG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DEBUG")

class CreditStatistics(object):
	def __init__(self, stuNum, stuPwd, captcha, cookies):
		self.stuNum = stuNum
		self.stuPwd = stuPwd
		self.captcha = captcha
		self.cookies = {
			cookies[:cookies.find("=")]: cookies[cookies.find("=") + 1:cookies.find(";")]
		}

		self.grade = None
		self.college = None
		self.profession = None
		self.professionId = None
		self.plan = None

		self.__init__changeProfession()

		self._finish = False
		self._success = False
		self._errorInfo = None

		self._start()

	def __init__changeProfession(self):
		'''
			初始化与更换专业需要重新初始化的变量
		'''
		self.latestSelectionResult = [] #最新选课结果
		self.repairedCourses = [] #已修课程
		self.failCourses = [] #挂科课程

		self.repairedPublicCourses = [] # 已修公共课程
		self.repairedProfessionCourses = [] # 已修学科专业核心课程
		self.repairedProfessionElective = [] # 已修学科选修课程
		self.repairedElective = [] # 已修（除学科专业）选修课程
		# self.repairedDoubleCourses = [] # 双学位/双专业 课程
		self.nonRepairedPublicCourses = [] #未修公共课程
		self.nonRepairedProfessionCourses = [] # 未修学科专业核心课程
		self.optionalCourses = [] # 可选修课程

	def _getLatestSelectionResult(self):
		'''
			获取最新选课结果
		'''
		url = "http://192.168.2.20/AXSXX/zxxkjg.aspx"
		response = requests.get(url, cookies=self.cookies)
		html = BeautifulSoup(response.content, "lxml")
		table = html.find(id="zxxkjgTable")
		trs = table.find_all("tr")[1:] # 除去第一个表头

		# 判断最新选课结果的成绩是否已出
		if len(self.repairedCourses) > 0:
			if self.repairedCourses[len(self.repairedCourses) - 1]["termNum"] == trs[0].find_all("td")[1].string:
					# 成绩已出的话就不添加最新选课结果
					return 
		for tr in trs:
			td = tr.find_all("td")
			data = {
				"termNum": td[1].string.strip(),
				"courseNum": td[2].string.strip()[:-2], # 从课程号中除去班级信息
				"courseType": td[4].string.strip(),
				"courseName": td[5].string.strip(),
				"credit": float(td[6].string.strip()),
				"creditType": "无"
			}
			self.latestSelectionResult.append(data)

	def _getRepairedCourses(self):
		'''
			获取已修课程，并分离出挂科科目
		'''
		url = "http://192.168.2.20/AXSXX/aCHENGJISTD.asp"
		response = requests.get(url, cookies=self.cookies)
		html = BeautifulSoup(response.content, "lxml")
		tables = html.find_all("table")
		for x in xrange(1, len(tables), 3):
			table = tables[x]
			trs = table.find_all("tr")[1:] #不要表头
			infoType = len(trs[0].find_all("td")) - 11# 2015年第一学期表头没有培养方案认定课程类别 标记infoType为0 含培养方案认定课程类别标记为1
			for tr in trs:
				td = tr.find_all("td")
				data = {
					"termNum": td[1].string.strip(),
					"courseNum": td[2].string.strip()[:-2], # 从课程号中除去班级信息
					"courseName": td[3].string.strip(),
					"courseType": td[4 + infoType].string.strip(),
					"credit": float(td[5 + infoType].string.strip()),
					"creditType": "无"
				}
				creditGet = float(td[6 + infoType].string)
				if creditGet == 0: # 取得学分为0 说明挂科
					self.failCourses.append(data)
				else :
					self.repairedCourses.append(data)

	@staticmethod
	def getCaptcha():
		'''
			获取验证码图片临时地址
			@return (string, string) (图片base64数据, cookies)
		'''
		codeUrl = "http://192.168.2.20/mycode/code.asp?id=!!!&random=" + str(random.random())
		response = requests.get(codeUrl)
		cookies = response.headers["Set-cookie"]
		return (base64.b64encode(response.content), cookies)

	def _login(self):
		'''
			登录学生信息查询系统
		'''
		url = "http://192.168.2.20/axsxx/AALICENSEstd.asp"
		params = {
			"USERID": self.stuNum,
			"PASSWORD": self.stuPwd,
			"GetCode": self.captcha,
			"SUBMIT": "确 定"
		}
		response = requests.post(url, data=params, cookies=self.cookies)
		# 登录成功返回 <script>top.location.href='../Amain.asp';</script>
		if response.content.find("top.location.href=") == -1:
			print "用户名或口令错误 in _login"
			raise Exception("用户名或口令错误")

	def _getBasicInfo(self):
		'''
			获取年级、学院、专业
			@return boolean 获取是否成功
		'''
		url = "http://192.168.2.20/AXSXX/xjxxcheck.aspx"
		params = {
			"stulogflag": True,
			"cetlogflag": True,
			"USERID": "",
			"PASSWORD": self.stuPwd,
			"GetCode": self.captcha,
			"userxhSTD": self.stuNum,
			"useridSTD":self.stuNum,
			"userpms": "S",
			"level": 0,
			"PMSFILEC": "/AXSXX/aipconstd.asp",
			"PMSFILEM": "AXSXX/xjxxcheck.asp",
			"StuXjxxcheck": 1
		}
		response = requests.post(url, data=params, cookies=self.cookies)
		html = BeautifulSoup(response.content, "lxml")
		# 判断招生高考信息是否为空判断是否登录成功
		if html.find(id="lblKsh").string == None:
			print "用户名或口令错误 in _getBasicInfo"
			raise Exception("用户名或口令错误")

		cookies = response.headers["Set-cookie"]
		self.cookies["ASP.NET_SessionId"] = cookies[cookies.find("=") + 1:cookies.find(";")]
		
		self.grade = int(html.find(id="lblNj").string.strip())
		self.college = html.find(id="lblXy").string.strip()
		
		profession = html.find(id="lblZxzy").string.strip()
		if profession.find("  ") != -1:
			# 双专业或双学位
			# 计算机与软件学院  数学与计算机科学实验班
			# 计算机科学与技术（数学与计算机科学实验班）
			# http://192.168.2.20/axsxx/sxwfx_zige.asp 双专业/双学位/辅修资格
			print "疑似双专业" + profession
			file(os.path.join(DEBUG_DIR, profession + "个人信息页.txt"), "wb").write(response.content)
			file(os.path.join(DEBUG_DIR, profession + "双修资格页.txt"), "wb").write(requests.get("http://192.168.2.20/axsxx/sxwfx_zige.asp", cookies=self.cookies).content)

			profession = profession.replace("  ", "（") + "）"
		self.profession = profession

	def _getProfessionId(self):
		'''
			通过已获取的信息查询数据库获得专业id
		'''
		query = Professions.objects.filter(grade=self.grade).filter(college=self.college)
		if len(query) == 0:
			raise Exception("查询不到专业id")
		profession = query.filter(profession=self.profession)
		if len(profession) == 0:
			self.profession = self.college
			profession = query[0]
		else :
			profession = profession[0]

		self.professionId = profession.id

	def _getPlan(self):
		query = Plan.objects.filter(professionId=self.professionId)
		if len(query) < 1:
			raise Exception("专业id不存在！")
		query = query[0]
		artsStream = query.artsStream if query.artsStream else 0.0
		scienceStream = query.scienceStream if query.scienceStream else 0.0
		self.plan = {
			"publicRequired": query.publicRequired,
			"professionalRequired": query.professionalRequired,
			"elective": query.elective,
			"professionalElective": query.professionalElective,
			"artsStream": artsStream,
			"scienceStream": scienceStream,
			"practice": query.practice
		}

	def _getCourses(self):
		'''
			通过专业id查询该专业的所有课程
		'''
		query = Courses.objects.filter(professionId=self.professionId)
		for course in query:
			courseType = course.courseType
			data = {
					"termNum": course.suggestion,
					"courseNum": course.courseNum,
					"courseName": course.courseName,
					"courseType": course.courseType,
					"credit": course.credit,
					"creditType": course.creditType
			}
			if courseType == "公共必修课":
				self.nonRepairedPublicCourses.append(data)
			elif courseType == "学科专业核心课":
				self.nonRepairedProfessionCourses.append(data)
			elif courseType == "学科专业选修课":
				self.optionalCourses.append(data)

	def _retakeCourses(self):
		'''
			从挂科课程列表中找出未重修的课程，添加到新的挂科列表
		'''
		failCourses = []
		for failCourse in self.failCourses:
			if not (failCourse in self.repairedCourses or failCourse in self.latestSelectionResult):
				# 挂科科目不在已修课程中，课程添加到挂科课程列表
				failCourses.append(failCourse)
		self.failCourses = failCourses

	def _matchAllCourses(self):
			self._matchCourses(self.latestSelectionResult) # 匹配最新选课结果
			self._matchCourses(self.repairedCourses) # 匹配已修课程

	def _matchCourses(self, courseList):
		for course in courseList:
			find = False
			if course["courseNum"][:2] == "MC": #判断是否为MOOC课程
				self._matchMCCourse(course)
			elif course["courseNum"][:5] == "53000": # 判断是否为体育课， 体育课前五位为53000
				self._matchPECourse(course)
			else :
				self._matchOtherCourse(course)

	def _matchMCCourse(self, course):
		'''
			MOOC课程匹配
			通过匹配课程名
		'''
		query = MCCourses.objects.filter(courseName=course["courseName"])
		if len(query) < 1:
			print "MOOC课程" + course["courseName"] + "未记录在数据库"
			# 不在的话...先放进选修列表中
			self.repairedElective.append(course)
			return
		query = query[0]
		course["creditType"] = query.creditType

		matchResult = CreditStatistics._inCourseInCourseList(course, self.nonRepairedPublicCourses, "courseName")
		if matchResult:# 判断是否在公共必修课程
			self.repairedPublicCourses.append(course)
			self.nonRepairedPublicCourses.remove(matchResult)
			return 
		matchResult = CreditStatistics._inCourseInCourseList(course, self.nonRepairedProfessionCourses, "courseName")
		if matchResult:# 判断是否在专业必修课程
			self.repairedProfessionCourses.append(course)
			self.nonRepairedProfessionCourses.remove(matchResult)
			return 
		matchResult = CreditStatistics._inCourseInCourseList(course, self.optionalCourses, "courseName")
		if matchResult: # 判断是否在专业选修课程
			self.repairedProfessionElective.append(course)
			self.optionalCourses.remove(matchResult)
			return
		# 都不在的话...放进选修列表中
		self.repairedElective.append(course)

	def _matchPECourse(self, course):
		'''
			体育课程匹配
		'''
		for publicCourse in self.nonRepairedPublicCourses:
			if publicCourse["courseNum"][:5] == "53000":
				self.repairedPublicCourses.append(course)
				self.nonRepairedPublicCourses.remove(publicCourse)

	def _matchOtherCourse(self, course):
		'''
			匹配除MOOC和体育课程以外的课
		'''
		matchResult = CreditStatistics._inCourseInCourseList(course, self.nonRepairedPublicCourses, "courseNum", "courseName")
		if matchResult:# 判断是否在公共必修课程
			self.repairedPublicCourses.append(course)
			self.nonRepairedPublicCourses.remove(matchResult)
			return 
		matchResult = CreditStatistics._inCourseInCourseList(course, self.nonRepairedProfessionCourses, "courseNum", "courseName")
		if matchResult:# 判断是否在专业必修课程
			course["creditType"] = matchResult["creditType"]
			self.repairedProfessionCourses.append(course)
			self.nonRepairedProfessionCourses.remove(matchResult)
			return 
		matchResult = CreditStatistics._inCourseInCourseList(course, self.optionalCourses, "courseNum", "courseName")
		if matchResult: # 判断是否在专业选修课程
			course["creditType"] = matchResult["creditType"]
			self.repairedProfessionElective.append(course)
			self.optionalCourses.remove(matchResult)
			return
		# 都不在的话m 判断课程类型
		if course["courseType"] == "选修":
			# 选修课则从全部课程中查找课程类型
			query = Courses.objects.filter(courseNum=course["courseNum"])
			if len(query) < 1:
				# 没查到的话...放入专业选修
				self.repairedProfessionElective.append(course)
			else:
				query = query[0]
				course["courseType"] == query.courseType
				self.repairedElective.append(course)
		elif course["courseType"] == "必修":
			query = Courses.objects.filter(courseNum=course["courseNum"])
			if self.college == self.profession: #如果必修课程在当前专业查不到且专业名等于学院名 则可能是类似计软国际班的专业
				for x in query:
					result = Professions.objects.filter(id=x.professionId).filter(grade=self.grade).filter(college=self.college)#学院、年级相同,认为是类似计软国际班的专业
					if len(result) > 0:#若年级符合,则认为专业需要更新.并重新进行课程查询
						self.__init__changeProfession()
						self.profession = result[0].profession
						self._start(x.professionId)
						raise Exception("更换专业")
			# 不在其他专业的话...课程类型选错的概率比较大...故将其放入选修课程中
			if len(query) > 0:
				course["creditType"] = query[0].creditType
			else :
				course["creditType"] = ("理" if self.plan["artsStream"] == 0.0 else "文")
			self.repairedElective.append(course)
	
	@staticmethod
	def _inCourseInCourseList(course, courseList, key, key2=None):
		'''
			通过key值
			判断course是否在courseList中
			在则返回courseList中符合的course
			否则返回None
		'''
		for icourse in courseList:
			if str(course[key]) == str(icourse[key]):
				return icourse
			if key2 and str(course[key2]) == str(icourse[key2]):
				return icourse
			# print str(course[key]), str(icourse[key])
		return None
	
	@property
	def finish(self):
		return self._finish

	@property
	def success(self):
		return self._success

	@property
	def errorInfo(self):
		return self._errorInfo

	def _start(self, professionId=None):
		try:
			if professionId == None:
				self._login()
				self._getBasicInfo()
			self._getRepairedCourses()
			self._getLatestSelectionResult()
			if professionId == None:
				self._getProfessionId()
			else:
				self.professionId = professionId
			self._getPlan()
			self._getCourses()
			self._retakeCourses()
			self._matchAllCourses()
		except Exception as e:
			if e.message != "更换专业":
				self._errorInfo = e.message
				self._success = False
				self._finish = True
				print self._errorInfo
			return
		
		self._success = True
		self._finish = True