#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 04:21:44 2020

@author: giovanni.scognamiglio

@Object: Menu importer as part of the Menu Creation package
"""
import logging
import requests
import pandas as pd
import datetime
import sys
import os
from get_new_token import  *
import multiprocessing
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
    global storeid, store_name, store_cityCode, excelName
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
        store_cityCode = r.json()['stores'][0]['cityCode']
        excelName = f'{store_name}_{store_cityCode}.xlsx'
        print(f'\n{store_name} - {store_cityCode} ({storeid}) found in Admin')
        confirm_menu = input(f"Menu of {store_name} - {store_cityCode} ({storeid}) will be will be imported and stored into '{excelName}'\n\nContinue [yes]/[no]:\n").lower().strip()
        if confirm_menu in ["yes","y","ye","si"]: 
            logger.info(f"Importing menu of store {store_name} - {store_cityCode} ({storeid})")
            break

def create_output_dir():
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
    #clean duplicated values for readability
    df_addons.loc[df_addons.duplicated(subset = ["Add-On Name"]), ["Add-On Name","Min Selection","Max Selection",	"Multiple Selection","Add-On ID"]] = np.nan
    #print(f"\nCreated Add-Ons sheet in Excel file '{store_name}_{store_cityCode}.xlsx'")

def get_prod_externalId(phantom_dic, sbre):
    url = f'https://adminapi.glovoapp.com/admin/products/{sbre}'
    r_id = requests.get(url, headers = {'authorization':access_token})
    phantom_dic[sbre] = r_id.json()['externalId']

def id_dict_creation():
    global id_dict
    #step1: get the list of all product's id
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = {'authorization' : access_token})
    r.headers
    r
    collection_js = r.json()
    for collection in collection_js[0]['collections']:
        collectionId = collection['id']
        url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
        r = requests.get(url, headers = {'authorization' : access_token})
        section_js = r.json()
        id_dict_list = []
        for section in section_js:
            for prod in section['products']:
                id_dict_list.append(prod['id'])
    #step2: launch multiprocessing for calling all product's api and  get every single external id
    with multiprocessing.Manager() as manager:
        phantom_dic = manager.dict()
        processes = []
        for sbre in id_dict_list:
            pro = multiprocessing.Process(target = get_prod_externalId, args = (phantom_dic, sbre))
            pro.start()
            processes.append(pro)
        for process in processes:
            process.join()
        #print(phantom_dic)
        id_dict = dict(phantom_dic)

def part_two():    
    global df_prods, prod
    #PART2: Products sheet
    #getting menu products name
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = {'authorization' : access_token})
    r.headers
    r
    collection_js = r.json()
    #collectionId_list = [_['id'] for _ in (collection_js[0]['collections'])]    
    df_prods = pd.DataFrame(columns = ['Super Collection', 'Collection', 'Section', 'Product Name', 'Product Description',	'Product Price','Product ID', 'Question 1', 'Question 2', 'Question 3', 'Question 4','Question 5','Question 6','Question 7','Question 8','Question 9','Question 10','Question 11','Question 12','Question 13','Question 14','Question 15','Question 16','Active (TRUE/FALSE)','Image Ref'])
    for collection in collection_js[0]['collections']:
        collectionId = collection['id']
        url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
        r = requests.get(url, headers = {'authorization' : access_token})
        section_js = r.json()
        for section in section_js:
            for prod in section['products']:
                for _ in range(len(prod['attributeGroups'])-1,16):  
                    prod['attributeGroups'].append({'id': None, 'name': None})
                df_prods.loc[0 if pd.isnull(df_prods.index.max()) else df_prods.index.max() + 1] = [np.nan,	 collection['name'], section['name'], prod['name'], prod['description'],prod['price'],id_dict.get(prod['id']), prod['attributeGroups'][0]['name'], prod['attributeGroups'][1]['name'], prod['attributeGroups'][2]['name'],prod['attributeGroups'][3]['name'],prod['attributeGroups'][4]['name'],prod['attributeGroups'][5]['name'],prod['attributeGroups'][6]['name'],prod['attributeGroups'][7]['name'],prod['attributeGroups'][8]['name'],prod['attributeGroups'][9]['name'],prod['attributeGroups'][10]['name'],prod['attributeGroups'][11]['name'],prod['attributeGroups'][12]['name'],prod['attributeGroups'][13]['name'],prod['attributeGroups'][14]['name'],prod['attributeGroups'][15]['name'],prod['enabled'],prod["image"]]                
    #clean all duplicated values for  readability
    df_prods.loc[df_prods.duplicated(subset = ['Super Collection','Collection']), ['Super Collection','Collection']] = np.nan
    #Delete empty columns
    df_prods.dropna(axis = 1, how = 'all', inplace = True)
    #replace 'nan' desription with actual nan
    df_prods.loc[:,'Product Description'].replace('nan',np.nan, inplace = True)
    #print(f"\nCreated Products sheet in Excel file '{store_name}_{store_cityCode}.xlsx'")
    
def save_to_excel():
    #saving to excel part 1 & part 2
    with pd.ExcelWriter(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx')) as writer:
        df_prods.to_excel(writer, sheet_name = 'Products', index_label = 'Products Position')
        df_addons.to_excel(writer, sheet_name = 'Add-Ons', index = False)
    print(f"\nSuccesfully saved to excel @{os.path.relpath(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx'))}\n")

def download_images():
    global image_path, x
    #downloading images
    x = 0
    try: os.mkdir(os.path.join(output_path,'Images'))
    except Exception: pass
    image_path = os.path.join(output_path,'Images')
    processes = []
    for nu in df_prods.index:
        x +=1
        process =  multiprocessing.Process(target = fire_download, args = [nu,x])
        process.start()
        processes.append(process)
    for process_django in processes:
        process_django.join()
    print(f'\nImages folder of {store_name} updated')
        
def fire_download(nu,x):
    _ = df_prods.at[nu,'Image Ref']
    ProductName = str(df_prods.at[nu,'Product Name'])
    if any(s in ProductName for s in ('/',',','-')):
        for sy in ('/',',','-'):
            if sy in ProductName: 
                ProductName =  ProductName.replace(sy,'_')
    if _ == None:
        pass
    elif os.path.isfile(os.path.join(image_path,f"{ProductName}.jpg")):
        #print(f"Image {str(df_prods.at[nu,'Product Name'])}.jpg already exists")
        pass
    else:
        ProductName = str(df_prods.at[nu,'Product Name'])
        url = f'http://res.cloudinary.com/glovoapp/image/upload/v1596612872/{_}.jpeg'
        r = requests.get(url)
        if any(s in ProductName for s in ('/',',','-')):
            for sy in ('/',',','-'):
                if sy in ProductName: ProductName =  ProductName.replace(sy,'_')
        with open(os.path.join(image_path,f"{ProductName}.jpg"), 'wb') as f:
            f.write(r.content)
            print(f"Image {ProductName}.jpg downloaded")

if __name__ == '__main__':
    set_storeid()
    t0 = datetime.datetime.now()
    create_output_dir()
    part_one()
    id_dict_creation()
    part_two()
    save_to_excel()
    download_images()
    t1 = datetime.datetime.now()
    print(f"\n\nMenu of {store_name}-{store_cityCode} {(storeid)} successfully imported to Excel in {(t1-t0).seconds} seconds")
        
