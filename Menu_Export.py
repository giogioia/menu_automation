#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  6 23:11:19 2020

@author: giovanni.scognamiglio
"""
import logging
import requests
from threading import Timer
import time
import requests
import threading
import time
import pandas as pd
import json
import datetime
import  sys
import os
import datetime
from get_new_token import  *

bot_name = 'Menu_Exporter'

'''Init Functions'''
#set path
def set_path():
    global dir, login_path, input_path
    #if sys has attribute _MEIPASS then script launched by bundled exe.
    if getattr(sys, '_MEIPASS', False):
        dir = os.path.dirname(os.path.dirname(sys._MEIPASS))
    else:
        dir = os.getcwd()
    #defining paths
    print(f'Working directory is {dir}')
    login_path = os.path.join(dir,'my_personal_token.py')

#check login credentials for api calls
def login_check():
    #Check/get login data
    global glovo_email, password, refresh_token
    print("Checking login data")
    if os.path.isfile(login_path):
        with open(login_path) as f:
            content = f.read()
        if all(s in content for s in ("glovo_email", "password", "refresh_token")):
            exec(open(login_path).read())
            welcome_name = glovo_email[:glovo_email.find("@")].replace("."," ").title()
            print(f"\n\nWelcome back {welcome_name}!")
        else: get_token()
    else:
        get_token()

#enable Logger
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

#get api access token
def refresh():
    print(f"Token refreshed")
    exec(open(login_path).read())
    global refresh_token, access_token, expirance
    data = {'refreshToken' : refresh_token, 'grantType' : 'refresh_token'}
    r = requests.post('https://adminapi.glovoapp.com/oauth/refresh', json = data)
    print(r.ok)
    access_token = r.json()['accessToken']
    refresh_token = r.json()['refreshToken']
    expirance = r.json()['expiresIn']
    logger.info('Access Token Refreshed')


'''Init Procedural code'''
set_path()
login_check()
logger_start()
refresh()

'''''''''''''''''''''''''''''End Init'''''''''''''''''''''''''''''

'''Custome Functions'''
#drop stores from dataframe
def drop_store(store2drop):
    global django_index, df_admin
    try: 
        django_index = df_admin[df_admin['id'] == store2drop].index[0]
    except IndexError:
        print('\nStore not in list')
    else:
        df_admin = df_admin.drop(django_index).reset_index(drop = True)
        print(f'\n{store2drop} removed from target stores')

''''''
#get all cities for admin query related to AM's country
def get_cities():
    global  cities
    while True:
        country = input('Insert your country code (eg. IT, ES, AR):\n')
        url = 'https://adminapi.glovoapp.com/admin/cities'
        r = requests.get(url, headers = {'authorization' : access_token})
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
        print(i['code'])
        string.append(f"cities={i['code']}&")
    cities = ''.join(string)
    
def stores_request():
    global partner, df_admin
    #search stores on admin
    partner = input('Insert the Store Name to import:\n')
    url = f'https://adminapi.glovoapp.com/admin/stores?{cities}limit=500&offset=0'
    params = {'query' : partner}
    r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
    if r.ok is False:
        print(f'There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
    else:
        try:
            list_raw = r.json()['stores']
            df_admin = pd.read_json(json.dumps(list_raw))
            df_admin['name'] = df_admin['name'].str.strip()
            df_admin = df_admin[df_admin['name'] == partner].reset_index(drop = True)
        except KeyError:
           print(f'There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
           errore += 1
        else:
            print(df_admin[['name','cityCode','id']])
                
''''''   
def import_details():
    global store_to_import
    #main    
    store_to_import = int(input('Insert the Store ID of the store to import:\n'))
    drop_store(store_to_import)
    print(f'\n{partner} {store_to_import} will be imported to the following stores\n')
    print(df_admin[['name','cityCode','id']])
    while True:
        exclude =  input('Insert any Store ID you would like to exclude? [If multiple values: separate them by comma. Leave blank if no store to exclude]\n')
        if len(exclude) > 0: 
            if "," in exclude: 
                exclude = exclude.split(",")
                for s in exclude: drop_store(int(s))
            else: drop_store(int(exclude))
        else:
            print('No Store ID will be excluded')
        time.sleep(0.5)
        print(f'\n{partner} {store_to_import} will be imported to the following stores')
        print(df_admin[['name','cityCode','id']])
        confirm = input('Confirm? [yes/no]\n')
        if confirm in ['yes','ye','y','si']: break
        else: continue

def menu_requests():
    t0 = datetime.datetime.now()
    for j in df_admin.index:
        i = df_admin['id'][j]
        url_menu = f'https://adminapi.glovoapp.com/admin/stores/{i}/menu'
        url_import = f'https://adminapi.glovoapp.com/admin/stores/{i}/import_menu'
        headers  = {'authorization' : access_token}
        data = {'storeIdToBeImported': store_to_import}
        d = requests.delete(url_menu, headers = headers)
        if d.ok is True:
            print(f'menu {i} - deleted (d.ok is {d.ok})')
            logging.info(f'Menu {i} - deleted (d.ok = {d.ok})')
        else:
            print(f'CAUTION: Store {i} - d.ok = {d.ok}')
            logging.error(f'CAUTION: Store {i} - d.ok = {d.ok} - {d}')
            break
        time.sleep(0.1)
        p = requests.post(url_import, headers = headers, json = data)
        if p.ok is True:
            print(f'Menu {i} - posted (p.ok is {p.ok})')
            logging.info(f'Menu {i} - posted (p.ok is {p.ok})')
        else:
            print(f'CAUTION: Menu {i} - p.ok = {p.ok}')
            logging.error(f'CAUTION: Menu {i} - p.ok = {p.ok} - {p}')
            break
    t1 = datetime.datetime.now()
    print(f'\nDone!\nSuccessfully exported {partner}-{store_to_import} to {len(df_admin.index)} stores in {(t1-t0).seconds} seconds')

'''Procedural code'''
if __name__ == '__main__':
    get_cities()
    stores_request()
    import_details()
    menu_requests()
