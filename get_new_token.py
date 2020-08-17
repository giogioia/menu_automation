#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 19 13:53:48 2020

@author: giovanni.scognamiglio
"""
                                                                                                                                                        
bot_name  = "get_new_token"

#stuff to import
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import sys
from webdriver_manager.chrome import ChromeDriverManager
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import json
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import requests
import logging
from getpass import getpass
#import logging

'''OATH2'''


'''Part 1: Access google account with selenium and get network requests'''
'''Working directory and paths'''
def set_path():
    global dir, login_path
    #if sys has attribute _MEIPASS then script launched by bundled exe.
    if getattr(sys, '_MEIPASS', False):
        dir = os.path.dirname(os.path.dirname(sys._MEIPASS))
    else:
        dir = os.getcwd()
    #defining paths
    login_path = os.path.join(dir,"my_personal_token.py")

'''Logger'''
#single logger, continously updating
def logger_start():
    #log config
    logging.basicConfig(filename = "my_log.log", 
                    level =  logging.INFO,
                    format = "%(levelname)s %(asctime)s %(message)s",
                    datefmt = '%m/%d/%Y %H:%M:%S',
                    filemode = "a")
    #log start
    global logger
    logger = logging.getLogger()
    logger.info(f"Starting log for {bot_name}")
    print("logger started")

'''Initiations functions'''
def first_login():
    while True:
        print(f"\n\nHello and welcome to the {bot_name}."
              "\nFor starting, you'll have to log in to Admin:")
        global glovo_email
        glovo_email = input("Insert your glovo email:\n")
        global password
        password = getpass("Insert your password: (PW will not be displayed. Type it and press ENTER)\n")
        print(f"\nemail = {glovo_email}\npassword = {len(password)*'*'}\n")
        confirm = input("Confirm data? [yes]/[no]\n").lower().strip()
        if confirm in ["yes","y","ye","si"]:
            welcome_name = glovo_email[:glovo_email.find("@")].replace("."," ").title()
            print(f"\n\nWelcome {welcome_name}!")
            logger.info(f'Started by {welcome_name}')
            break
        else: continue
    print('First login completed')

def first_login_check():
    #Check/get login data
    print("Checking login data")
    if os.path.isfile(login_path):
        with open(login_path) as f:
            content = f.read()
        if all(s in content for s in ("glovo_email", "password", "refresh_token")):
            exec(open(login_path).read())
            welcome_name = glovo_email[:glovo_email.find("@")].replace("."," ").title()
            print(f"\n\nWelcome back {welcome_name}!")
            logger.info(f'Started by {welcome_name}')
            confirm = input("Do you need a new token? [yes]/[no]\n").lower().strip()
            if confirm in ["yes","y","ye","si"]: pass
            else: sys.exit(0)
        else: first_login()
    else:
        first_login()

def launch_Chrome():
    print("Launching Chrome")
    global browser, wait
    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
    browser = webdriver.Chrome(desired_capabilities = caps, executable_path=ChromeDriverManager().install())
    browser.implicitly_wait(4)
    wait = WebDriverWait(browser, 13)
    initiate_google_login()
    
def initiate_google_login():
    browser.get('https://accounts.google.com/')
    print("\nAccessing your Google/Glovo account")
    wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
    g_username=browser.find_element_by_id("identifierId")
    g_username.send_keys(glovo_email,Keys.RETURN)
    time.sleep(0.5)
    wait.until(EC.presence_of_element_located((By.NAME, "password")))
    g_password=browser.find_element_by_name("password")
    g_password.send_keys(password,Keys.RETURN)
    print("Signed in!")
    browser.get("https://beta-admin.glovoapp.com/content")
    time.sleep(2)
    logger.info('Logged with Google')

'''Get google token from network log'''
def get_g_token():  
    global google_token, browser_log
    browser_log = browser.get_log('performance')
    for i in browser_log:
        try:
            google_token = json.loads(json.loads(i['message'])['message']['params']['request']['postData'])['googleToken']
        except Exception:
            continue
        else:
            logger.info(f'Got Google Token: {google_token}')
            browser.close()
     
        
'''Part2: Post google token to admin to get access key'''
'''Send post request to admin api to receive access and refresh token'''
def post_g_token():
    global refresh_token
    #define payload
    data = {'googleToken': google_token, 'grantType': "google"}
    #POST request
    p = requests.post('https://adminapi.glovoapp.com/oauth/operator_token', json = data)
    logger.info('Posted Google Token at https://adminapi.glovoapp.com/oauth/operator_token')
    logger.info(f'Response is {p.ok}')
    p.content
    refresh_token = p.json()['refreshToken']
    logger.info(f'Received Refresh Token: {refresh_token}')

def save_token():
    with open(login_path,"w") as w:
        w.write("global glovo_email, password, refresh_token, google_token")
        w.write(f"\nglovo_email = '{glovo_email}'\npassword = '{password}'\nrefresh_token = '{refresh_token}'\ngoogle_token = '{google_token}'")
    print(f'\n\nCongrats! Your Refresh Token is {refresh_token}.\n\nThe token has been saved to {login_path} file.\nIf the token stops working, execute the {bot_name} file again.')
    logger.info(f'Refresh Token saved in {login_path}')

'''procedural code'''
def get_token():
    #1:Set path
    set_path()
    #Start logger
    logger_start()
    #Check login data
    first_login_check()
    #Launching browser
    launch_Chrome()
    #Get google token  
    get_g_token()
    #Post google token
    post_g_token()
    #Save token
    save_token()
