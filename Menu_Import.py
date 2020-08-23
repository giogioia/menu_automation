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
import json

bot_name = 'Menu_Import'

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


'''''''''''''''''''''''''''''End Init'''''''''''''''''''''''''''''

'''''''''''''''''''''''''''Beginning bot'''''''''''''''''''''''''''

'''stage 1: start()''' 
#start() launches the bot according to the import mode set by set_import_mode()

#set_import_mode() sets the import mode based on user's input
#if user enters a Store ID: import_mode = 'single'  for downloading only a single menu
#if user enters a store name: import_mode = 'multiple' for downlaoding the menus of all the store IDs of the partner
def set_import_mode():
    global import_mode, partner
    partner = input('\nInsert a Store ID or a Store Name for beginning import\n')
    if partner.isdigit():
        import_mode = 'single'
    else:
        import_mode = 'multiple'

#stores_request() finds all the stores of a partner in a certain country
def stores_request():
    global df_admin, partner
    get_cities()
    #search stores on admin
    errore = 0
    while True:
        if errore == 1:
            partner = input('Insert the Store Name to import:\n')
        params = {'query' : partner}
        url = f'https://adminapi.glovoapp.com/admin/stores?{cities}limit=500&offset=0'
        r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
        if r.ok is False: 
            print('There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
            errore += 1
        else:
            list_raw = r.json()['stores']
            json_raw = json.dumps(list_raw)
            df_admin = pd.read_json(json_raw)
            df_admin = df_admin[df_admin['name'] == partner].reset_index(drop = True)
            print(df_admin[['name','cityCode','id']])
            #confi =  input('All the menu of the store IDs above will be converted to excel.\nContinue [yes]/[no]:\t').lower().strip()
            #if confi in ["yes","y","ye","si"]:
                #break
            break
                
#get_cities() makes a list of all cities of country
#necessary for avoiding download menu of other countries when partner is in multiple countries            
def get_cities():
    global cities
    while True:
        country = input('Insert your country code (eg. IT, ES, AR):\n').upper().strip()
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
        #print(i['code'])
        string.append(f"cities={i['code']}&")
    cities = ''.join(string)
    
'''Stage 2: main() '''
#main() is the process for downloading a single store ID menu and convert it to an excel file
def main(partner):
    if __name__ == '__main__':
        global empty
        empty = False
        check_storeid(partner)
        t0 = datetime.datetime.now()
        check_if_empty()
        if empty: 
            pass
        else:
            create_output_dir()
            part_one()
            id_dict_creation()
            part_two()
            save_to_excel()
            download_images()
            t1 = datetime.datetime.now()
            print(f"\n\nMenu of {store_name}-{store_cityCode} {(storeid)} successfully imported to Excel in {(t1-t0).seconds} seconds")

#check store ID 
def check_storeid(partner):
    global storeid, store_name, store_cityCode, excel_name
    ntrials = 0
    while True:
        if ntrials == 0:
            storeid = partner
        else: 
            storeid = input("\nInsert the Store ID of the menu to import:\n").strip()
        params = {'query' : storeid}
        url = f'https://adminapi.glovoapp.com/admin/stores?limit=100&offset=0'
        r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
        if r.ok is False: 
            print("Store not on Admin. Please insert a valid Store Id")
            ntrials += 1
            if ntrials > 1: print("If error repeats, consider closing the program and start again")
        else:
            try:
                store_name = r.json()['stores'][0]['name']
            except IndexError:
                print(f'Problem while searching {storeid} on Admin.\nPlease try again')
                ntrials += 1
            else:
                store_cityCode = r.json()['stores'][0]['cityCode']
                excel_name = f'{store_name}_{store_cityCode}.xlsx'
                print(f'\n{store_name} - {store_cityCode} ({storeid}) found in Admin')
                if import_mode == 'single':
                    confirm_menu = input(f"Menu of {store_name} - {store_cityCode} ({storeid}) will be imported and stored into '{excel_name}'\n\nContinue [yes]/[no]:\t").lower().strip()
                    if confirm_menu in ["yes","y","ye","si"]: 
                        logger.info(f"Importing menu of store {store_name} - {store_cityCode} ({storeid})")
                        break
                    else:
                        ntrials += 1
                else:
                    print(f"Menu of {store_name} - {store_cityCode} ({storeid}) will be will be imported and stored into '{excel_name}'\n")
                    break
     
def check_if_empty():
    global empty
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = {'authorization' : access_token})
    collection_js = r.json()
    if collection_js == []:
        print('Menu is empty. Nothing to import')
        empty = True

    
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
    if attrib_info == []:
        print('No Add-Ons to import')
        pass
    else: 
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
    df_prods = pd.DataFrame(columns = ['Super Collection', 'Collection', 'Section', 'Product Name', 'Product Description', 'Product Price','Product ID', 'Add-On 1', 'Add-On 2', 'Add-On 3', 'Add-On 4','Add-On 5','Add-On 6','Add-On 7','Add-On 8','Add-On 9','Add-On 10','Add-On 11','Add-On 12','Add-On 13','Add-On 14','Add-On 15','Add-On 16','Active', 'Image Ref','Image ID'])
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
                df_prods.loc[0 if pd.isnull(df_prods.index.max()) else df_prods.index.max() + 1] = [np.nan, collection['name'].strip(), section['name'].strip(), prod['name'].strip(), prod['description'].strip(), prod['price'], id_dict.get(prod['id']), prod['attributeGroups'][0]['name'], prod['attributeGroups'][1]['name'], prod['attributeGroups'][2]['name'],prod['attributeGroups'][3]['name'],prod['attributeGroups'][4]['name'],prod['attributeGroups'][5]['name'],prod['attributeGroups'][6]['name'], prod['attributeGroups'][7]['name'], prod['attributeGroups'][8]['name'], prod['attributeGroups'][9]['name'], prod['attributeGroups'][10]['name'], prod['attributeGroups'][11]['name'], prod['attributeGroups'][12]['name'], prod['attributeGroups'][13]['name'],prod['attributeGroups'][14]['name'],prod['attributeGroups'][15]['name'],prod['enabled'], image_name(prod['name'].strip()),prod["image"]]                
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
        writer.sheets['Products'].set_column('B:Z',20)
        writer.sheets['Products'].set_column('D:D',25)
        writer.sheets['Products'].set_column('E:E',70)
        writer.sheets['Products'].set_column('H:Z',20)
        df_addons.to_excel(writer, sheet_name = 'Add-Ons', index = False)
        writer.sheets['Add-Ons'].set_column('B:Z',15)
        writer.sheets['Add-Ons'].set_column('A:A',25)
        writer.sheets['Add-Ons'].set_column('F:F',50)
    print(f"\nSuccesfully saved to excel @{os.path.relpath(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx'))}\n")
    
def download_images():
    global image_path, x
    try: 
        df_prods.loc[:,'Image ID']
    except KeyError: 
        print('No pictures to download')
        pass
    else:
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
    _ = df_prods.at[nu,'Image ID']
    ProductName = str(df_prods.at[nu,'Product Name'])
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
        ProductName = image_name(ProductName)
        with open(os.path.join(image_path,f"{ProductName}.jpg"), 'wb') as f:
            f.write(r.content)
            #print(f"Image {ProductName}.jpg downloaded")

def image_name(ProductName):
    if any(s in ProductName for s in ("/","'")):
        for sy in ("/","'"):
            if sy in ProductName: 
                return ProductName.replace(sy,'_')
    else:
        return ProductName

'''''''''''''''''''''''''''''End Bot'''''''''''''''''''''''''''''

#if __name__ == '__main__':
#    start()        
    
#launches the bot according to the import mode set by set_import_mode()
if __name__ == '__main__':
    '''Init Procedural code'''
    set_path()
    login_check()
    logger_start()
    refresh()
    '''bot'''
    global partner
    set_import_mode()
    if import_mode == 'single':
        main(partner)
    elif import_mode == 'multiple':
        stores_request()
        conf = input('All the menu of the Store IDs above will be converted to excel\nContinue [yes]/[no]:\t').lower().strip()
        if conf in ["yes","y","ye","si"]:
            t0 = datetime.datetime.now()
            for partner in df_admin['id']:
                main(partner)
            t1 = datetime.datetime.now()
            print(f'All {store_name} Store IDs menu have been imported in {(t1-t0).seconds} seconds.')
        else:
            set_import_mode()
    else:
        print('Something went wrong')
        sys.exit(0)
