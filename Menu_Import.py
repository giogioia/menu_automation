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
from tqdm import tqdm

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
        storeid = input("\nInsert the Store ID of the menu to import:\n").strip()
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
    print('Creating "Add-Ons" sheet')
    for i in tqdm(attrib_info):
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
    print('Retrieving attributes external Ids')
    for collection in (collection_js[0]['collections']):
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
        for sbre in tqdm(id_dict_list):
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
    df_prods = pd.DataFrame(columns = ['Super Collection', 'Collection', 'Section', 'Product Name', 'Product Description',	'Product Price','Product ID', 'Add-On 1', 'Add-On 2', 'Add-On 3', 'Add-On 4','Add-On 5','Add-On 6','Add-On 7','Add-On 8','Add-On 9','Add-On 10','Add-On 11','Add-On 12','Add-On 13','Add-On 14','Add-On 15','Add-On 16','Active','Image Ref'])
    print('Creating "Products" sheet')
    for collection in tqdm(collection_js[0]['collections']):
        collectionId = collection['id']
        url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
        r = requests.get(url, headers = {'authorization' : access_token})
        section_js = r.json()
        for section in section_js:
            for prod in section['products']:
                for _ in range(len(prod['attributeGroups'])-1,16):  
                    prod['attributeGroups'].append({'id': None, 'name': None})
                df_prods.loc[0 if pd.isnull(df_prods.index.max()) else df_prods.index.max() + 1] = [np.nan,	 collection['name'].strip(), section['name'].strip(), prod['name'].strip(), prod['description'].strip(), prod['price'], id_dict.get(prod['id']), prod['attributeGroups'][0]['name'], prod['attributeGroups'][1]['name'], prod['attributeGroups'][2]['name'],prod['attributeGroups'][3]['name'],prod['attributeGroups'][4]['name'],prod['attributeGroups'][5]['name'],prod['attributeGroups'][6]['name'], prod['attributeGroups'][7]['name'], prod['attributeGroups'][8]['name'], prod['attributeGroups'][9]['name'], prod['attributeGroups'][10]['name'], prod['attributeGroups'][11]['name'], prod['attributeGroups'][12]['name'], prod['attributeGroups'][13]['name'],prod['attributeGroups'][14]['name'],prod['attributeGroups'][15]['name'],prod['enabled'],prod["image"]]                
    #clean all duplicated values for  readability
    df_prods.loc[df_prods.duplicated(subset = ['Super Collection','Collection']), ['Super Collection','Collection']] = np.nan
    #Delete empty columns
    df_prods.dropna(axis = 1, how = 'all', inplace = True)
    #replace 'nan' desription with actual nan
    df_prods.loc[:,'Product Description'].replace('nan',np.nan, inplace = True)
    #print(f"\nCreated Products sheet in Excel file '{store_name}_{store_cityCode}.xlsx'")
    
def save_to_excel():
    #saving to excel part 1 & part 2
    '''
    dfs = {'Products': [df_prods, True, 'Index'], 'Add-Ons': [df_addons, False, None]}
    writer = pd.ExcelWriter((os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx')), engine='xlsxwriter') 
    for sheetname, dfinfo in dfs.items():
        dfinfo[0].to_excel(writer, sheet_name = sheetname, index = dfinfo[1], index_label = dfinfo[2])
        worksheet = writer.sheets[sheetname]
        for idx, col in enumerate(dfinfo[0]):  # loop through all columns
            series = dfinfo[0][col]
            max_len = max((series.astype(str).map(len).max(), len(str(series.name)))) 
            worksheet.set_column(idx, idx, max_len)
    writer.save()
    print(f"\nSuccesfully saved to excel @{os.path.relpath(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx'))}\n")
    '''
    with pd.ExcelWriter(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx')) as writer:
        df_prods.to_excel(writer, sheet_name = 'Products', index_label = 'Index')
        writer.sheets['Products'].set_column('B:Z',15)
        writer.sheets['Products'].set_column('D:D',20)
        writer.sheets['Products'].set_column('E:E',70)
        writer.sheets['Products'].set_column('M:M',27)
        df_addons.to_excel(writer, sheet_name = 'Add-Ons', index = False)
        writer.sheets['Add-Ons'].set_column('B:Z',15)
        writer.sheets['Add-Ons'].set_column('A:A',25)
        writer.sheets['Add-Ons'].set_column('F:F',50)
    print(f"\nSuccesfully saved to excel @{os.path.relpath(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx'))}\n")
    
def download_images():
    global image_path, x
    #downloading images
    x = 0
    try: os.mkdir(os.path.join(output_path,'Images'))
    except Exception: pass
    image_path = os.path.join(output_path,'Images')
    processes = []
    with multiprocessing.Manager() as manager: 
        l = manager.list()
        print('Downloading images')
        for nu in tqdm(df_prods.index):
            x +=1
            process =  multiprocessing.Process(target = fire_download, args = [nu,x,l])
            process.start()
            processes.append(process)
        for process_django in processes:
            process_django.join()
        im_mod = list(l)
    if len(im_mod) == 0: print(f'\nNo new image to dowload')
    else: print(f'\nImages folder of {store_name} updated')
        
def fire_download(nu,x,l):
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
        l.append('_')
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
        
