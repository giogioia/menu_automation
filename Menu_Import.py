#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 04:21:44 2020

@author: giovanni.scognamiglio

@Object: Menu importer as part of the Menu Creation package
"""
import logging
import requests
from threading import Timer
import time
import requests
import threading
import pandas as pd
import json
import datetime
import sys
import os
import datetime
from get_new_token import  *
import multiprocessing
import math
import numpy as np

bot_name = 'Menu_Creator'

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
    print("Logger started")

'''Get new access token with the refresh token''' 
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
    headers = {'authorization' : access_token}
    logger.info('Access Token Refreshed')


'''Intro'''
set_path()
login_check()
logger_start()
refresh()
''''''

'''Set storeId'''
def set_storeid():
    global storeid, store_name
    nop = 0
    while True:
        storeid = input("\nInsert the Store ID of the menu to import:\n")
        params = {'query' : storeid}
        url = f'https://adminapi.glovoapp.com/admin/stores?limit=100&offset=0'
        r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
        if r.ok is False: 
            print("Store not on Admin. Please insert a valid Store Id")
            nop += 1
            if nop > 1: print("If error repeats, close the program and start again")
            continue
        store_name = r.json()['stores'][0]['name']
        print(f'\n{store_name} - {storeid} found in Admin')
        confirm_menu = input(f"Menu of {store_name} - {storeid} will be will be imported and stored into 'Menu_{store_name}.xlsx'\n\nContinue [yes]/[no]:\n").lower().strip()
        if confirm_menu in ["yes","y","ye","si"]: 
            logger.info(f"Importing menu of store {store_name} - {storeid}")
            break

def output_dir():
    global output_path
    output_path = os.path.join(dir, store_name)
    try: os.mkdir(output_path)
    except Exception: pass

def part_one():
    global df_addons, attrib_info
    #PART1:Add-Ons sheet (attrib + attrib groups)
    url = f'https://adminapi.glovoapp.com/admin/attribute_groups/search?storeId={storeid}&query='

    r = requests.get(url, headers = {'authorization' : access_token})
    df_addons = pd.DataFrame(columns = ["Add-On Name","Min Selection","Max Selection", "Multiple Selection", "Add-On ID","Attribute","Price", "Attribute ID", "Active"])
    attrib_info = r.json()
    for i in attrib_info:
        for n in i['attributeDetails']:
            df_addons.loc[0 if pd.isnull(df_addons.index.max()) else df_addons.index.max() + 1] = [i['name'],i['min'],i['max'],i['multipleSelection'],i['externalId'],n['name'],n['priceImpact'],n['externalId'],n['enabled']]
    
    df_addons.loc[df_addons.duplicated(subset = ["Add-On Name"]), ["Add-On Name","Min Selection","Max Selection",	"Multiple Selection","Add-On ID"]] = np.nan
    print('Created Add-Ons sheet')
    
def find_extId(n):
    for _ in attrib_info:
        if _['name'] == prod['attributeGroups'][n]['name']:
            return _['externalId']

def part_two():    
    global df_prods, prod
    #PART2: Products sheet
    #getting menu products name
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = {'authorization' : access_token})
    r.headers
    r
    collection_js = r.json()
    
    collectionId_list = [_['id'] for _ in (collection_js[0]['collections'])]    
    df_prods = pd.DataFrame(columns = ['Super Collection', 'Collection', 'Section', 'Product Name', 'Product Description',	'Product Price','Product ID', 'Question 1', 'Question 2', 'Question 3', 'Question 4','Question 5','Question 6','Question 7','Active (TRUE/FALSE)','Image Ref'])
    prod_order = 0
    for collection in collection_js[0]['collections']:
        collectionId = collection['id']
        url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
        r = requests.get(url, headers = {'authorization' : access_token})
        section_js = r.json()
        for section in r.json():
            for prod in section['products']:
                for _ in range(len(prod['attributeGroups'])-1,7):  
                    prod['attributeGroups'].append({'id': None, 'name': None})
                #df_prods.loc[0 if pd.isnull(df_prods.index.max()) else df_prods.index.max() + 1] = [np.nan,	 collection['name'], section['name'], prod['name'], prod['description'],prod['price'],prod['externalId'], find_extId(0), find_extId(1), find_extId(2),find_extId(3),find_extId(4),find_extId(5),find_extId(6),prod['enabled'],prod["image"]]                
                df_prods.loc[0 if pd.isnull(df_prods.index.max()) else df_prods.index.max() + 1] = [np.nan,	 collection['name'], section['name'], prod['name'], prod['description'],prod['price'],prod['externalId'], prod['attributeGroups'][0]['name'], prod['attributeGroups'][1]['name'], prod['attributeGroups'][2]['name'],prod['attributeGroups'][3]['name'],prod['attributeGroups'][4]['name'],prod['attributeGroups'][5]['name'],prod['attributeGroups'][6]['name'],prod['enabled'],prod["image"]]                

    df_prods.loc[df_prods.duplicated(subset = ['Super Collection','Collection']), ['Super Collection','Collection']] = np.nan
    print('Created Products sheet')
    
def save_to_excel():
    #saving to excel part 1 & part 2
    with pd.ExcelWriter(os.path.join(output_path,f'{store_name}_menu.xlsx')) as writer:
        df_prods.to_excel(writer, sheet_name = 'Products', index_label = 'Products Order')
        df_addons.to_excel(writer, sheet_name = 'Add-Ons', index = False)
    print(f"Succesfully saved to excel @{os.path.join(output_path,f'{store_name}_menu.xlsx')}")
def download_images():
    #downloading images
    x = 0
    try: os.mkdir(os.path.join(output_path,'Images'))
    except Exception: pass
    image_path = os.path.join(output_path,'Images')
    for nu in df_prods.index:
        _ = df_prods.at[nu,'Image Ref']
        x +=1
        if _ == None:
            continue
        elif os.path.isfile(os.path.join(image_path,f"({x})_{str(df_prods.at[nu,'Image Ref'])[9:]}.jpg")):
            print(f"Image ({x})_{str(df_prods.at[nu,'Image Ref'])[9:]}.jpg already exists")
            continue
        else: 
            url = f'http://res.cloudinary.com/glovoapp/image/upload/v1596612872/{_}.jpeg'
            r = requests.get(url)
            with open(os.path.join(image_path,f"({x})_{str(df_prods.at[nu,'Image Ref'])[9:]}.jpg"), 'wb') as f:
                f.write(r.content)
                print(f"Image {x} downloaded")
    
if __name__ == '__main__':
    t0 = datetime.datetime.now()
    set_storeid()
    output_dir()
    part_one()
    part_two()
    save_to_excel()
    download_images()
    t1 = datetime.datetime.now()
    print(f"Menu of {store_name} successfully imported to excel in {(t1-t0).seconds} seconds")
    
