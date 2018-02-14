# -*- coding: utf-8 -*-

"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.
    
    @author: mkaay, RaNaN
"""

from time import sleep, time
from random import uniform
from traceback import print_exc
from threading import Lock

from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

class CaptchaManager():
    def __init__(self, core):
        self.lock = Lock()
        self.core = core
        self.tasks = [] #task store, for outgoing tasks only

        self.ids = 0 #only for internal purpose

    def newTask(self, img, format, file, result_type, initialize_driver=None):
        task = CaptchaTask(self.ids, self.core, img, format, file, result_type, initialize_driver)
        self.ids += 1
        return task

    def removeTask(self, task):
        self.lock.acquire()
        if task in self.tasks:
            self.tasks.remove(task)
        self.lock.release()

    def getTask(self):
        self.lock.acquire()
        for task in self.tasks:
            if task.status in ("waiting", "shared-user"):
                self.lock.release()
                return task
        self.lock.release()
        return None

    def getTaskByID(self, tid):
        self.lock.acquire()
        for task in self.tasks:
            if task.id == str(tid): #task ids are strings
                self.lock.release()
                return task
        self.lock.release()
        return None

    def handleCaptcha(self, task):
        cli = self.core.isClientConnected()

        if cli: #client connected -> should solve the captcha
            task.setWaiting(500) #wait 50 sec for response

        for plugin in self.core.hookManager.activePlugins():
            try:
                plugin.newCaptchaTask(task)
            except:
                if self.core.debug:
                    print_exc()
            
        if task.handler or cli: #the captcha was handled
            self.tasks.append(task)
            return True

        task.error = _("No Client connected for captcha decrypting")

        return False


class CaptchaTask():
    XPATH_IFRAME_CHECKBOX = "//div[@class='g-recaptcha']//iframe"
    XPATH_IFRAME_CAPTCHA = "//iframe[@title='recaptcha challenge']"

    def __init__(self, id, core, img, format, file, result_type='textual', initialize_driver=None):
        self.id = str(id)
        self.core = core
        self.captchaImg = img
        self.captchaFormat = format
        self.captchaFile = file
        self.captchaResultType = result_type
        self.handler = [] #the hook plugins that will take care of the solution
        self.result = None
        self.waitUntil = None
        self.error = None #error message
        self.driver = None # selenium driver for interaction
        self.initialize_driver = initialize_driver

        self.status = "init"
        self.data = {} #handler can store data here

    def start_interaction(self):
        if not self.isInteractive():
            self.core.log.error('CaptchaTask: task is not interactive')
            return False

        self.core.log.debug('CaptchaTask: start interactive')
        if not self.core.config["reCAPTCHA"]["uBlockOrigin"]:
            self.core.log.error('CaptchaTask: uBlockOrigin addon for firefox not found')
            return False
        binary = None
        if self.core.config["reCAPTCHA"]["firefox_binary"]:
            binary = FirefoxBinary(self.core.config["reCAPTCHA"]["firefox_binary"])

        firefox_options = webdriver.FirefoxOptions()
        firefox_options.add_argument('--headless')
        self.driver = webdriver.Firefox(executable_path=self.core.config["reCAPTCHA"]["geckodriver"], firefox_options=firefox_options, firefox_binary=binary)
        # install addon workaround, see https://github.com/SeleniumHQ/selenium/issues/4093
        self.driver.install_addon(self.core.config["reCAPTCHA"]["uBlockOrigin"])  # add uBlock Origin to block computational intensive scripts (ads, miners etc.)
        self.driver.get(self.captchaImg)
        if self.initialize_driver:
            self.initialize_driver(self.driver)

        WebDriverWait(self.driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

        self.driver.switch_to.frame(self.driver.find_element_by_xpath(self.XPATH_IFRAME_CHECKBOX))
        # *************  locate CheckBox  **************
        # CheckBox = WebDriverWait(self.driver, 10).until(
        #     EC.presence_of_element_located((By.ID, "recaptcha-anchor"))
        # )
        CheckBox = self.driver.find_element_by_id('recaptcha-anchor')
        # *************  click CheckBox  ***************
        sleep(uniform(0.5, 0.7))
        # making click on captcha CheckBox
        CheckBox.click()
        # ***************** back to main window **************************************
        self.driver.switch_to.default_content()
        sleep(uniform(1.0, 1.5))

        if self.is_interaction_complete():
            return self

        # ************ switch to the second iframe by tag name ******************
        self.driver.switch_to.frame(self.driver.find_element_by_xpath(self.XPATH_IFRAME_CAPTCHA)) # select iframe with captcha
        self.data = self.driver.page_source # save data
        self.driver.switch_to.default_content()  # switch back
        return self

    def interact(self, element, nth):
        nth = int(nth)
        self.driver.switch_to.frame(self.driver.find_element_by_xpath(self.XPATH_IFRAME_CAPTCHA))

        self.core.log.debug('CaptchaTask: ' + element)
        if element == 'recaptcha-verify-button':
            self.driver.find_element_by_id('recaptcha-verify-button').click()
            self.core.log.debug('CaptchaTask: click button')
        elif element in ['rc-image-tile-wrapper', 'rc-imageselect-checkbox']:
            selected_elements = self.driver.find_elements_by_class_name(element)
            if 0 <= nth < len(selected_elements):
                selected_elements[nth].click()
                self.core.log.debug('CaptchaTask: click')
            else:
                self.core.log.debug('CaptchaTask: no click :(')
                self.data = "<html><body><p>Something went wrong</p></body></html>"
                return

        sleep(uniform(1.0, 2.0))

        self.driver.switch_to.default_content()  # switch back
        if self.is_interaction_complete():
            self.data = "<html><body><p>Successful</p></body></html>"
            return True

        self.driver.switch_to.frame(self.driver.find_element_by_xpath(self.XPATH_IFRAME_CAPTCHA))
        self.data = self.driver.page_source  # save data
        self.driver.switch_to.default_content()  # switch back

    def reload(self):
        self.driver.switch_to.frame(self.driver.find_element_by_xpath(self.XPATH_IFRAME_CAPTCHA))
        self.data = self.driver.page_source  # save data
        self.driver.switch_to.default_content()  # switch back
        return self

    def is_interaction_complete(self):
        response = self.driver.find_element_by_id('g-recaptcha-response').get_attribute('value')
        if not response:
            self.core.log.debug('CaptchaTask: interaction not complete')
            return False

        self.setResult(response)
        self.core.log.debug('CaptchaTask: interaction complete')
        self.core.log.debug('CaptchaTask: response:' + response)
        self.driver.quit()
        return True

    def getCaptcha(self):
        return self.captchaImg, self.captchaFormat, self.captchaResultType

    def setResult(self, text):
        if self.isTextual():
            self.result = text
        elif self.isPositional():
            try:
                parts = text.split(',')
                self.result = (int(parts[0]), int(parts[1]))
            except:
                self.result = None
        elif self.isInteractive():
            self.result = text

    def getResult(self):
        try:
            res = self.result.encode("utf8", "replace")
        except:
            res = self.result

        return res

    def getStatus(self):
        return self.status

    def setWaiting(self, sec):
        """ let the captcha wait secs for the solution """
        self.waitUntil = max(time() + sec, self.waitUntil)
        self.status = "waiting"

    def isWaiting(self):
        if self.result or self.error or time() > self.waitUntil:
            return False

        return True

    def isTextual(self):
        """ returns if text is written on the captcha """
        return self.captchaResultType == 'textual'

    def isPositional(self):
        """ returns if user have to click a specific region on the captcha """
        return self.captchaResultType == 'positional'

    def isInteractive(self):
        """ returns if text is written on the captcha """
        return self.captchaResultType == 'selenium'

    def setWatingForUser(self, exclusive):
        if exclusive:
            self.status = "user"
        else:
            self.status = "shared-user"

    def timedOut(self):
        return time() > self.waitUntil

    def invalid(self):
        """ indicates the captcha was not correct """
        [x.captchaInvalid(self) for x in self.handler]

    def correct(self):
        [x.captchaCorrect(self) for x in self.handler]

    def __str__(self):
        return "<CaptchaTask '%s'>" % self.id
