#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  6 23:11:19 2020

@author: giovanni.scognamiglio

Object: Exporting a menu of a Store ID to a list of others Store IDs
"""
import logging
import requests
import time
import pandas as pd
import json
import datetime
import sys
import os
from get_new_token import *
from colorama import Fore, Style

bot_name = 'Menu Export Bot'

'''Init functions'''
#Step 1: set path
def set_path():
    #step1: find launch origin (bundled exe. or local cwd)
    global cwd, login_path, input_path
    #if sys has attribute _MEIPASS then script launched by bundled exe.
    if getattr(sys, '_MEIPASS', False):
        cwd = os.path.dirname(os.path.dirname(sys._MEIPASS))
    #else: script is launched locally
    else:
        cwd = os.getcwd()
    #step 2: defining paths
    #print(f'Working directory is {cwd}')
    login_path = os.path.join(cwd,'my_personal_token.json')

#Step 2: enable Logger
def logger_start():
    #log config
    logging.basicConfig(filename = os.path.join(cwd,"my_log.log"), 
                        level =  logging.INFO,
                        format = "%(levelname)s %(asctime)s %(message)s",
                        datefmt = '%m/%d/%Y %H:%M:%S',
                        filemode = "a")
    #log start
    global logger
    logger = logging.getLogger()
    logger.info(f"Starting log for {bot_name}")
    #print("Logger started")

#custom for Step 3: read credentials json
def read_json():
    global glovo_email, refresh_token, country
    with open(login_path) as read_file:
        content = json.load(read_file)
    glovo_email = content['glovo_email']
    refresh_token = content['refresh_token']
    country = content['country']
        
#Step 3: check login credentials
def login_check():
    #Check/get login data: check if file 'my personal token' exists and read it to get login data.
    global glovo_email, refresh_token
    #print("Checking login data")
    if os.path.isfile(login_path):
        try:
            read_json()
        except Exception:
            get_token()
        else:
            welcome_name = glovo_email[:glovo_email.find("@")].replace("."," ").title()
            print(f"\nWelcome back {welcome_name}")
    #if file does not exist: lauch file creation
    else:
        get_token()

#Step 4: get fresh api access token
def refresh():
    global oauth
    read_json()
    #step 2: make request at oauth/refresh
    oauth_data = {'refreshToken' : refresh_token, 'grantType' : 'refresh_token'}
    oauth_request = requests.post('https://adminapi.glovoapp.com/oauth/refresh', json = oauth_data)
    #print(oauth_request.ok)
    if oauth_request.ok:
        access_token = oauth_request.json()['accessToken']
        oauth = {'authorization' : access_token}
        #print("Token refreshed")
        logger.info('Access Token Refreshed')
    else:
        print(f"Token NOT refreshed -> {oauth_request.content}")
        logger.info(f'Access Token NOT Refreshed -> {oauth_request.content}')
        
def print_bot_name():
    print('\nStarting ' + Fore.RED + Style.BRIGHT + bot_name + Style.RESET_ALL + '\n')
    time.sleep(1)
'''''''''''''''''''''''''''''End Init'''''''''''''''''''''''''''''

'''''''''''''''''''''''''''Beginning bot'''''''''''''''''''''''''''
'''Custom Functions'''
#drop stores from dataframe
def drop_store(store2drop):
    global django_index, df_admin
    try: 
        django_index = df_admin[df_admin['id'] == store2drop].index[0]
    except IndexError:
        print(f'\nStore {store2drop} not in list')
    else:
        df_admin = df_admin.drop(django_index).reset_index(drop = True)
        print(f'\n{store2drop} removed from target stores')

''''''
#get all cities for admin query related to AM's country
def get_cities():
    global  cities
    while True:
        #country = input('Insert your country code (eg. IT, ES, AR):\n').upper().strip() -> already in json credentials
        url = 'https://adminapi.glovoapp.com/admin/cities'
        r = requests.get(url, headers = oauth)
        df_cities = pd.read_json(json.dumps(r.json()))
        try:
            json_list_country = df_cities.loc[df_cities['code']==country,['cities']].values.item()
        except ValueError:
            print('Country not found, please insert a valid country code')
            continue
        else: break
    #parse json 
    string = []
    for i in json_list_country:
        #print(i['code'])
        string.append(f"cities={i['code']}&")
    cities = ''.join(string)
    
def stores_request():
    global partner, df_admin
    #search stores on admin
    while True:
        partner = input('Insert the Store Name of the menu to export:\n')
        url = f'https://adminapi.glovoapp.com/admin/stores?{cities}limit=500&offset=0'
        parameters = {'query' : partner}
        r = requests.get(url, headers  = oauth, params = parameters)
        if r.ok is False:
            print(f'There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
        else:
            try:
                list_raw = r.json()['stores']
                df_admin_raw = pd.read_json(json.dumps(list_raw))
                df_admin_raw['name'] = df_admin_raw['name'].str.strip()
                df_admin = df_admin_raw[df_admin_raw['name'] == partner].reset_index(drop = True)
            except KeyError:
               print(f'There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
            else:
                if df_admin.index.size < 1:
                    print(f'Could not find any results for store {partner} on Admin.\nMake sure spelling is correct. (If problem persists, close bot and try again)')
                else:
                    print(df_admin[['name','cityCode','id']])
                    break
                
''''''   
def import_details():
    global store_to_export
    #main    
    store_to_export = int(input('Insert the Store ID of the menu to export:\n'))
    drop_store(store_to_export)
    print(df_admin[['name','cityCode','id']])
    print(f'\n{partner} {store_to_export} will be exported to the stores above\n')
    while True:
        exclude =  input('Insert any Store ID you would like to exclude? [If multiple values: separate them by comma. Leave blank if no Store ID to exclude]\n')
        if len(exclude) > 0: 
            if "," in exclude: 
                exclude = exclude.split(",")
                for s in exclude: 
                    try: drop_store(int(s))
                    except Exception: pass
            else: 
                try: drop_store(int(exclude))
                except Exception: print('No Store ID will be excluded')
        else:
            print('No Store ID will be excluded')
        time.sleep(1)
        print(df_admin[['name','cityCode','id']])
        print(f'\n{partner} {store_to_export} will be imported to the stores above')
        confirm = input('Continue? [yes/no]\n')
        if confirm in ['yes','ye','y','si']: break
        else: continue

def menu_requests():
    t0 = datetime.datetime.now()
    for j in df_admin.index:
        i = df_admin['id'][j]
        url_menu = f'https://adminapi.glovoapp.com/admin/stores/{i}/menu'
        url_import = f'https://adminapi.glovoapp.com/admin/stores/{i}/import_menu'
        data = {'storeIdToBeImported': store_to_export}
        d = requests.delete(url_menu, headers = oauth)
        if d.ok is True:
            print(f'menu {i} - deleted (d.ok is {d.ok})')
            logging.info(f'Menu {i} - deleted (d.ok = {d.ok})')
        else:
            print(f'CAUTION: Store {i} - d.ok = {d.ok}')
            logging.error(f'CAUTION: Store {i} - d.ok = {d.ok} - {d}')
            break
        time.sleep(0.1)
        p = requests.post(url_import, headers = oauth, json = data)
        if p.ok is True:
            print(f'Menu {i} - posted (p.ok is {p.ok})')
            logging.info(f'Menu {i} - posted (p.ok is {p.ok})')
        else:
            print(f'CAUTION: Menu {i} - p.ok = {p.ok}')
            logging.error(f'CAUTION: Menu {i} - p.ok = {p.ok} - {p}')
            break
    t1 = datetime.datetime.now()
    print(f'\nDone!\nSuccessfully exported {partner}-{store_to_export} to {len(df_admin.index)} stores in {(t1-t0).seconds} seconds')

'''Procedural code'''
if __name__ == '__main__':
    set_path()
    logger_start()
    login_check()
    refresh()
    get_cities()
    stores_request()
    import_details()
    menu_requests()
