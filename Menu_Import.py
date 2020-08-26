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
    #step1: find launch origin (bundled exe. or local dir)
    global dir, login_path, input_path
    #if sys has attribute _MEIPASS then script launched by bundled exe.
    if getattr(sys, '_MEIPASS', False):
        dir = os.path.dirname(os.path.dirname(sys._MEIPASS))
    #else: script is launched locally
    else:
        dir = os.getcwd()
    #step 2: defining paths
    print(f'Working directory is {dir}')
    login_path = os.path.join(dir,'my_personal_token.py')

#check login credentials for api calls
def login_check():
    #Check/get login data: check if file 'my personal token exists' and read it to get login data.
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
    #if file does not exists: lauch file creation
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

#get api fresh access token
def refresh():
    print(f"Token refreshed")
    #step 1: execute 'my personal token' file to get login variables (future version: use pickle module to save data and load data)
    exec(open(login_path).read())
    global refresh_token, access_token, expirance
    #step 2: make request at /oauth/refresh
    data = {'refreshToken' : refresh_token, 'grantType' : 'refresh_token'}
    r = requests.post('https://adminapi.glovoapp.com/oauth/refresh', json = data)
    print(r.ok)
    access_token = r.json()['accessToken']
    #refresh_token = r.json()['refreshToken']
    #expirance = r.json()['expiresIn']
    logger.info('Access Token Refreshed')


'''''''''''''''''''''''''''''End Init'''''''''''''''''''''''''''''

'''''''''''''''''''''''''''Beginning bot'''''''''''''''''''''''''''
'''Part 1: Set mode'''
#set_import_mode() sets the import mode based on user's input
#if user enters a Store ID -> import_mode = 'single'  for downloading only a single menu
#if user enters a store name -> import_mode = 'multiple' for downlaoding the menus of all the store IDs of the partner
def set_import_mode():
    global import_mode, partner
    partner = input('\nInsert a Store ID or a Store Name for beginning import\n')
    if partner.isdigit():
        import_mode = 'single'
    else:
        import_mode = 'multiple'

'''functions for mode = "multiple"'''
#get_cities() makes a list of all cities of a country
#necessary for avoiding download menu of other countries when partner is in multiple countries            
def get_cities():
    global cities
    while True:
        country = input('Insert your country code (eg. IT, ES, AR):\n').upper().strip()
        #making api requests at /admin/cities
        url = 'https://adminapi.glovoapp.com/admin/cities'
        r = requests.get(url, headers = {'authorization' : access_token})
        #converting json response to panda dataframe
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

#admin_stores_request() finds all the stores of a partner in a certain country
def admin_stores_request():
    global df_admin, partner
    get_cities()
    #by default: var 'errore' = 0 and var 'partner' = the one inserted in the beginning.
    errore = 0
    #if user makes mistake or smt goes wrong: var errore +=1 and user can re-write var partner.
    while True:
        if errore > 0:
            partner = input('Insert the Store Name to import:\n')
        #request @ /admin/stores?
        url = f'https://adminapi.glovoapp.com/admin/stores?{cities}limit=500&offset=0'
        params = {'query' : partner}
        r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
        if r.ok is False:
            print(f'There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
            errore += 1
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
                confirm = input('All the menu of the Store IDs above will be converted to excel\nContinue [yes]/[no]:\t').lower().strip()
                if confirm in ["yes","y","ye","si"]:
                    errore += 1
                
'''Part 2: main() part & all relative functions'''
#main() -> series of functions for importing one store id into an Excel file

#function1: check store ID 
#receives a store ID (var 'partner') and checks if it's present on Admin (usefull if mode = 'single')
def check_storeid(partner):
    global storeid, store_name, store_cityCode, excel_name
    #by default var 'ntrials' = 0 and var 'storeid' = input var 'partner'
    ntrials = 0
    storeid = partner
    #if user makes mistake or smt goes wrong: var 'ntrials' +=1 and user can re-write var 'storeid'.
    while True:
        if ntrials > 0:
            storeid = input("\nInsert the Store ID of the menu to import:\n").strip()
        #requests @ admin/stores?
        url = f'https://adminapi.glovoapp.com/admin/stores?limit=100&offset=0'
        params = {'query' : storeid}
        r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
        if r.ok is False: 
            print('Store not on Admin. Please insert a valid Store Id\n(If error repeats, consider closing the program and start again)')
            ntrials += 1
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
                #ask for confirmation if mode = 'single'. Else no need of confirmation.
                if import_mode == 'single':
                    confirm_check_storeid = input(f"Menu of {store_name} - {store_cityCode} ({storeid}) will be imported and stored into '{excel_name}'\n\nContinue [yes]/[no]:\t").lower().strip()
                    if confirm_check_storeid in ["yes","y","ye","si"]: 
                        logger.info(f"Importing menu of store {store_name} - {store_cityCode} ({storeid})")
                        break
                    else:
                        ntrials += 1
                else:
                    print(f"Menu of {store_name} - {store_cityCode} ({storeid}) will be will be imported and stored into '{excel_name}'\n")
                    break
#function2: check if menu is empty
#Returns 'True' if a menu has no collection to import
def check_if_empty():
    global empty
    #requests @ admin/stores/{storeid}/collections
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = {'authorization' : access_token})
    collection_js = r.json()
    if collection_js == []:
        print('Menu is empty. Nothing to import')
        empty = True

#function3: create output directory   
def create_output_dir():
    global output_path
    output_path = os.path.join(dir, store_name)
    try: os.mkdir(output_path)
    except Exception: pass

#function4: create add-ons sheet (attribute groups & attributes)
def add_ons_import():
    global df_addons, attrib_info
    #get all attribute groups & attributes info of storeid 
    #requests @ admin/attribute_groups/search?storeId={storeid}&query= 
    url = f'https://adminapi.glovoapp.com/admin/attribute_groups/search?storeId={storeid}&query='
    r = requests.get(url, headers = {'authorization' : access_token})
    attrib_info = r.json()
    #dataframe 'df_addons' creation
    df_addons = pd.DataFrame(columns = ["Add-On Name","Min Selection","Max Selection", "Multiple Selection", "Add-On ID","Attribute","Price", "Attribute ID", "Active"])
    #pass if menu has no attribute groups, else parse 'attrib_info' json and fill in the dataframe row by row
    if attrib_info == []:
        print('No Add-Ons to import')
        pass
    else: 
        print('Creating "Add-Ons" sheet')
        for i in tqdm(attrib_info):
            for n in i['attributeDetails']:
                df_addons.loc[0 if pd.isnull(df_addons.index.max()) else df_addons.index.max() + 1] = [i['name'],i['min'],i['max'],i['multipleSelection'],i['externalId'],n['name'],n['priceImpact'],n['externalId'],n['enabled']]
        #clean duplicated values for readability
        df_addons.loc[df_addons.duplicated(subset = ["Add-On Name"]), ["Add-On Name","Min Selection","Max Selection","Multiple Selection","Add-On ID"]] = None
        #print(f"\nCreated Add-Ons sheet in Excel file '{store_name}_{store_cityCode}.xlsx'")

#function5: retrieve product's external ID
#custom for function6
def get_prod_externalId(shared_dic, productID):
    #get a prod external ID with requests @ admin/products/{productID}
    url = f'https://adminapi.glovoapp.com/admin/products/{productID}'
    r_id = requests.get(url, headers = {'authorization':access_token})
    shared_dic[productID] = r_id.json()['externalId']

#function6: create dictionary with products' iDs
#as products external IDs can  not be retreive from product list, we need to call each products' api and get external its external id
def id_dict_creation():
    global id_dict
    #step1: get the list of all product's id 
    #requests @ admin/stores/{storeid}/collections for getting collection json to parse
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = {'authorization' : access_token})
    collection_js = r.json()
    print('Retrieving attributes external Ids')
    #parsing collection json
    for collection in (collection_js[0]['collections']):
        collectionId = collection['id']
        #requests @ admin/stores/{storeid}/collections/{collectionId}/sections for getting section json to parse
        url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
        r = requests.get(url, headers = {'authorization' : access_token})
        section_js = r.json()
        id_dict_list = []
        #parsing section json to get prod info
        for section in section_js:
            for prod in section['products']:
                id_dict_list.append(prod['id'])
    #step2: parse 'id_dict_list' (all products' IDs) to call each product's api and get each external id
    #using linear procedure
    shared_dic = {}
    for productID in tqdm(id_dict_list):
        get_prod_externalId(shared_dic, productID)
    id_dict = shared_dic
    
    '''
    #using multiprocessing
    with multiprocessing.Manager() as manager:
        shared_dic = manager.dict()
        processes = []
        for productID in tqdm(id_dict_list):
            pro = multiprocessing.Process(target = get_prod_externalId, args = (shared_dic, productID))
            pro.start()
            processes.append(pro)
        for process in processes:
            process.join()
        #print(shared_dic)
        id_dict = dict(shared_dic)
    '''
#function7: return clean image name for 'Image Ref' column
#custom for function8
def image_name(ProductName, ImageID):
    if ImageID == None or ImageID == np.nan or ImageID == '' or ImageID== 'nan':
        return None
    if any(s in ProductName for s in ("/","'")):
        for sy in ("/","'"):
            if sy in ProductName: 
                return ProductName.replace(sy,'_')
    else:
        return ProductName

#function8: Create 'Products' sheet
def prod_import():    
    global df_prods, prod
    #step1: import collections
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = {'authorization' : access_token})
    collections = r.json()[0]['collections']
    #collectionId_list = [_['id'] for _ in (collection_js[0]['collections'])]  
    #step2: create columns for dataframe 'df_prods'
    df_prods = pd.DataFrame(columns = ['Super Collection', 'Collection', 'Section', 'Product Name', 'Product Description', 'Product Price','Product ID', 'Add-On 1', 'Add-On 2', 'Add-On 3', 'Add-On 4','Add-On 5','Add-On 6','Add-On 7','Add-On 8','Add-On 9','Add-On 10','Add-On 11','Add-On 12','Add-On 13','Add-On 14','Add-On 15','Add-On 16','Active', 'Image Ref','Image ID'])
    #top-down approach for getting all info structured: parsing collections > sections > products
    print('Creating "Products" sheet')
    for collection in tqdm(collections):
        collectionId = collection['id']
        url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
        r = requests.get(url, headers = {'authorization' : access_token})
        sections = r.json()
        for section in sections:
            for prod in section['products']:
                #add 'None' values to empty 'Add-On's columns in case the products has fewer than 16 add ons
                for _ in range(len(prod['attributeGroups'])-1,16):  
                    prod['attributeGroups'].append({'id': None, 'name': None})
                #fill in dataframe row by row
                df_prods.loc[0 if pd.isnull(df_prods.index.max()) else df_prods.index.max() + 1] = [None, collection['name'].strip(), section['name'].strip(), prod['name'].strip(), prod['description'], prod['price'], id_dict.get(prod['id']), prod['attributeGroups'][0]['name'], prod['attributeGroups'][1]['name'], prod['attributeGroups'][2]['name'],prod['attributeGroups'][3]['name'],prod['attributeGroups'][4]['name'],prod['attributeGroups'][5]['name'],prod['attributeGroups'][6]['name'], prod['attributeGroups'][7]['name'], prod['attributeGroups'][8]['name'], prod['attributeGroups'][9]['name'], prod['attributeGroups'][10]['name'], prod['attributeGroups'][11]['name'], prod['attributeGroups'][12]['name'], prod['attributeGroups'][13]['name'],prod['attributeGroups'][14]['name'],prod['attributeGroups'][15]['name'],prod['enabled'], image_name(prod['name'].strip(), prod["image"]),prod["image"]]                
    #clean all duplicated values for  readability in certain columns
    df_prods.loc[df_prods.duplicated(subset = ['Super Collection','Collection']), ['Super Collection','Collection']] = np.nan
    #Delete empty columns
    df_prods.dropna(axis = 1, how = 'all', inplace = True)
    #replace 'nan' desription with actual nan
    df_prods.loc[:,'Product Description'].replace('nan',None, inplace = True)
    #print(f"\nCreated Products sheet in Excel file '{store_name}_{store_cityCode}.xlsx'")
    
#function9: save the created dataframe to excel
def save_to_excel():
    #saving to excel add-ons sheet and products sheet
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
    
#function10: download single image
#custom for function11
def image_download(nu,l):
    ImRef = df_prods.at[nu,'Image Ref']
    indexRef = df_prods.at[nu,'Image ID']
    #pass if image reference is empy or image already present
    if ImRef == None or ImRef == np.nan or ImRef == '' or ImRef == 'nan':
        pass
    elif os.path.isfile(os.path.join(image_path,f"{ImRef}.jpg")):
        #print(f"Image {str(df_prods.at[nu,'Product Name'])}.jpg already exists")
        pass
    else:
        l.append('ImRef')
        #download images with requests @ image/upload/ on cloudinary
        url = f'http://res.cloudinary.com/glovoapp/image/upload/v1596612872/{indexRef}.jpeg'
        r = requests.get(url)
        with open(os.path.join(image_path,f"{ImRef}.jpg"), 'wb') as f:
            f.write(r.content)
            #print(f"Image {ProductName}.jpg downloaded")

#function11: images checker
def check_images():
    global image_path
    #get 'Image ID' column in dataframe
    try: 
        df_prods.loc[:,'Image ID']
    except KeyError: 
        print('No pictures to download')
        pass
    else:
        #look for images to download
        print('Looking for images to download')
        try: 
            os.mkdir(os.path.join(output_path,'Images'))
        except Exception: 
            pass
        else:
            image_path = os.path.join(output_path,'Images')
            #using linear code
            for nu in tqdm(df_prods.index):
                image_download(nu,l)
            im_mod = l
            if len(im_mod) == 0: print(f'\nNo new image to dowload')
            else: print(f'\nImages folder of {store_name} updated')
        
        '''
        #using multiprocessing -> accelarates process by 5x (crashes on Windows)
        with multiprocessing.Manager() as manager: 
            l = manager.list()
            processes = []
            for nu in tqdm(df_prods.index):
                process =  multiprocessing.Process(target = image_download, args = [nu,l])
                process.start()
                processes.append(process)
            for process_django in processes:
                process_django.join()
            im_mod = list(l)
        if len(im_mod) == 0: print(f'\nNo new image to dowload')
        else: print(f'\nImages folder of {store_name} updated')
        '''           
#main() is the process for downloading a single store ID menu and convert it to an excel file
def main(partner):
    global empty
    empty = False
    check_storeid(partner)
    check_if_empty()
    if empty: 
        pass
    else:
        t0 = datetime.datetime.now()
        create_output_dir()
        add_ons_import()
        id_dict_creation()
        prod_import()
        save_to_excel()
        check_images()
        t1 = datetime.datetime.now()
        print(f"\n\nMenu of {store_name}-{store_cityCode} {(storeid)} successfully imported to Excel in {(t1-t0).seconds} seconds")

'''''''''''''''''''''''''''''End Bot'''''''''''''''''''''''''''''

'''''''''''''''''''''''''''''Launch'''''''''''''''''''''''''''''
if __name__ == '__main__':
    '''Init Procedural code'''
    set_path()
    login_check()
    logger_start()
    refresh()
    '''Bot code'''
    set_import_mode()
    if import_mode == 'single':
        main(partner)
    elif import_mode == 'multiple':
        admin_stores_request()
        for partner in df_admin['id']:
            main(partner)
            print(f'All {store_name} Store IDs menu have been imported.')
    else:
        print('Something went wrong')
        sys.exit(0)


