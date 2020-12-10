#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 04:21:44 2020

@author: giovanni.scognamiglio

@Object: Importing a menu of a Store ID and storing data in a file Excel
"""
import logging
import requests
import pandas as pd
import time
import sys
import os
from get_new_token import  *
import numpy as np
from tqdm import tqdm
import json
import string
#from multiprocessing import Manager, Pool, Process, cpu_count
from colorama import Fore, Style
import concurrent.futures

bot_name = 'Menu Import Bot'

'''Init functions'''
#Step 1: set path
def set_path():
    #step1: find launch origin (bundled exe. or local cwd)
    global cwd, login_path, input_path
    #if sys has attribute _MEIPASS then script launched by bundled exe.
    if getattr(sys, '_MEIPASS', False):
        cwd = os.path.dirname(sys.executable)
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
    print('\nStarting ' + Fore.MAGENTA + Style.BRIGHT + bot_name + Style.RESET_ALL + '\n')

'''''''''''''''''''''''''''''End Init'''''''''''''''''''''''''''''

'''''''''''''''''''''''''''Beginning bot'''''''''''''''''''''''''''
'''Part 0: Set import mode'''
#custom for stores_request(): get all cities for admin query related to AM's country
def get_cities():
    global cities
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

def check_query_input(partner):
    global q_input
    if partner.isdigit():
        q_input = 'id'
    else:
        q_input = 'name'

def set_mode_id():
    global mode
    mode = 'single'

def set_mode_name():
    global df_import, mode
    while True:
        df_import_copy = {}
        choice = input('Insert the Store ID of the menu to import:\n').strip()
        if ',' in choice: 
            choice = choice.split(',')
            l_choice = []
            for c in choice:
                try: l_choice.append(int(c))
                except Exception: pass
            if len(l_choice) == 0:
                print(f'No results found for "{choice}", please try again')
                continue
            else:
                mode = 'multiple'
                df_import_copy = df_import.loc[df_import.loc[:,'id'].isin(l_choice)]
                if df_import_copy.index.size < 1:
                    print(f'No results found for "{choice}", please try again')
                    continue
                print(df_import_copy)
                print('\nThe bot will import the above Store\'s menu')
        elif choice.isdigit():
            mode = 'mingle'
            df_import_copy = df_import.loc[df_import.loc[:,'id'] == int(choice)]
            print(df_import_copy)
            print('\nThe bot will import the above Store\'s menu')
        elif choice.lower() == 'all':
            mode = 'all'
            print(df_import_copy)
            print('\nThe bot will import ALL the Store\'s menu')
        else:
            print(f'Unable to process "{choice}", please try again')
            continue
        conferma = input('Continue? [yes]/[no]\t')
        if conferma in ['yes','ye','y','si']:
            df_import = df_import_copy.copy()
            break

#show a dataframe of all the stores (AM can then copy the ID of the city he is interested in and proceed with the creation)
def stores_request():
    global df_import
    get_cities()
    #search stores on admin
    while True:
        partner = input('Insert a Store Name or Store ID to import:\n').strip()
        check_query_input(partner)
        url = f'https://adminapi.glovoapp.com/admin/stores?{cities}limit=500&offset=0'
        parameters = {'query' : partner}
        r = requests.get(url, headers  = oauth, params = parameters)
        if r.ok is False:
            print(f'There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
        else:
            try:
                list_raw = r.json()['stores']
                df_admin_raw = pd.read_json(json.dumps(list_raw))
                df_admin_raw.loc[:,'name'] = df_admin_raw['name'].str.strip()
                df_admin = df_admin_raw.copy()
                if q_input == 'name':
                    df_admin = df_admin.loc[df_admin.loc[:,'name'] == partner].reset_index(drop = True)
            except KeyError:
               print(f'There was a problem while searching for store {partner} on Admin.\nPlease try again. (If problem persists, close bot and try again)')
            else:
                if df_admin.index.size < 1:
                    print(f'Could not find any results for store {partner} on Admin.\n'
                          f'Maybe you meant one of the following: \n{set(df_admin_raw["name"].to_list())}\n')
                else:
                    df_import = df_admin[['name','cityCode','id']]
                    df_import = df_import.rename({'cityCode':'city'}, axis = 1)
                    #df_import.loc[:,'status'] = ['' for _ in range(len(df_import.index))]
                    print(df_import)
                    if q_input == 'name':
                        set_mode_name()
                    break

'''Part 2: main() part & all relative functions'''
#main() -> series of functions for importing one store id into an Excel file

#function1: check store ID 
#receives a store ID (var 'partner') and checks if it's present on Admin (usefull if mode = 'single')
def check_storeid(lima):
    global storeid, store_name, store_cityCode, excel_name
    #by default var 'ntrials' = 0 and var 'storeid' = input var 'partner'
    ntrials = 0
    storeid = lima
    #if user makes mistake or smt goes wrong: var 'ntrials' +=1 and user can re-write var 'storeid'.
    while True:
        if ntrials > 0:
            storeid = input("\nInsert the Store ID of the menu to import:\n").strip()
        #requests @ admin/stores?
        url = f'https://adminapi.glovoapp.com/admin/stores?limit=100&offset=0'
        params = {'query' : storeid}
        r = requests.get(url, headers = oauth, params = params)
        if r.ok is False: 
            print('Store not on Admin. Please insert a valid Store Id\n(If error repeats, consider closing the program and start again)')
            ntrials += 1
        else:
            try:
                store_name = str(r.json()['stores'][0]['name']).strip()
            except IndexError:
                print(f'Problem while searching {storeid} on Admin.\nPlease try again')
                ntrials += 1
            else:
                store_cityCode = r.json()['stores'][0]['cityCode']
                excel_name = f'{store_name}_{store_cityCode}.xlsx'
                #print(f'\n{store_name} - {store_cityCode} ({storeid}) found in Admin')
                #ask for confirmation if mode = 'single'. Else no need of confirmation.
                if q_input == 'id':
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
    r = requests.get(url, headers = oauth)
    collection_js = r.json()
    if collection_js == []:
        print('Menu is empty. Nothing to import')
        empty = True

#function3: create output directory   
def create_output_dir():
    global output_path
    output_path = os.path.join(cwd, store_name)
    try: os.mkdir(output_path)
    except Exception: pass

#function4: create add-ons sheet (attribute groups & attributes)
def add_ons_import():
    global df_addons, attrib_info
    #get all attribute groups & attributes info of storeid 
    #requests @ admin/attribute_groups/search?storeId={storeid}&query= 
    url = f'https://adminapi.glovoapp.com/admin/attribute_groups/search?storeId={storeid}&query='
    r = requests.get(url, headers = oauth)
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
        ##clean dataframe
        #remove duplicated values for readability purposes
        df_addons.loc[df_addons.duplicated(subset = ["Add-On Name"]), ["Add-On Name","Min Selection","Max Selection","Multiple Selection","Add-On ID"]] = None
        #try format 'Add-On ID' & 'Attribute ID' columns as int
        df_addons.loc[:,'Add-On ID'] = pd.to_numeric(df_addons.loc[:,'Add-On ID'], downcast= "integer", errors= "ignore")
        df_addons.loc[:,'Attribute ID'] = pd.to_numeric(df_addons.loc[:,'Attribute ID'], downcast= "integer", errors= "ignore")
        #format price as float
        df_addons.loc[:,'Price'] = pd.to_numeric(df_addons.loc[:,'Price'], errors='coerce')
        #print(f"\nCreated Add-Ons sheet in Excel file '{store_name}_{store_cityCode}.xlsx'")
        
        
#function5: retrieve product's external ID
#custom for function6
def get_prod_externalId(shared_dic, productID):
    #get a prod external ID with requests @ admin/products/{productID}
    url = f'https://adminapi.glovoapp.com/admin/products/{productID}'
    r_id = requests.get(url, headers = oauth)
    shared_dic[productID] = r_id.json()['externalId']
    #print(shared_dic[productID],'=',r_id.json()['externalId'])
    
#fucntion6bis: use (max -1) number of cpu cores: every CPU in use increases speed by 1x
#custom for multiprocessing Pool ->  use all cpu cores - 1 to avoid freezing operating system
def cores():
    if cpu_count() <  2:
        return 1
    else:
        return (cpu_count() - 1)
        #return 8

#function6: create dictionary with products' iDs
#as products external IDs can  not be retreive from product list, we need to call each products' api and get external its external id
def id_dict_creation():
    global id_dict
    #step1: get the list of all product's id 
    #requests @ admin/stores/{storeid}/collections for getting collection json to parse
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = oauth)
    collection_js = r.json()
    print('Retrieving products external Ids')
    #parsing collection json
    id_dict_list = []
    for collection in (collection_js[0]['collections']):
        collectionId = collection['id']
        #requests @ admin/stores/{storeid}/collections/{collectionId}/sections for getting section json to parse
        url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
        r = requests.get(url, headers = oauth)
        section_js = r.json()
        #parsing section json to get prod info
        for section in section_js:
            for prod in section['products']:
                id_dict_list.append(prod['id'])
    #step2: parse 'id_dict_list' (all products' IDs) to call each product's api and get each external id
    ##########Benginning Multithreading/Multiprocessing part
    '''
    ###using linear procedure### -> slow but stable 
    start =  time.perf_counter()
    shared_dic = {}
    for productID in id_dict_list:
        get_prod_externalId(shared_dic, productID)
    id_dict = shared_dic
    finish =  time.perf_counter()
    ###end linear procedure###
    
    ###using multiprocessing Pool### -> fast and stable for high starting time on Windows
    start =  time.perf_counter()
    with Manager() as manager:
        shared_dic = manager.dict()
        pool = Pool(20)
        for productID in id_dict_list:
            pool.apply_async(get_prod_externalId, args = (shared_dic, productID,))
        pool.close()
        pool.join()
        id_dict = dict(shared_dic)
    finish =  time.perf_counter()
    ###end multiprocessing Pool###  
    
    ###using multiprocessing process### -> very fast, not so stable and very high starting time on Windows
    start =  time.perf_counter()
    with Manager() as manager:
        shared_dic = manager.dict()
        processes = []
        for productID in id_dict_list:
            pro = Process(target = get_prod_externalId, args = (shared_dic, productID))
            pro.start()
            processes.append(pro)
        for process in processes:
            process.join()
        #print(shared_dic)
        id_dict = dict(shared_dic)
    finish =  time.perf_counter()
    ###end multiprocessing process###
    
    ###using multithreading### -> crashes due to race condition: shared memory makes a mess (tried using Lock() but became too slow)
    lock = threading.Lock()
    start =  time.perf_counter()
    shared_dic = {}
    threads = []
    for productID in id_dict_list:
        pro = threading.Thread(target = get_prod_externalId, args = (shared_dic, productID, lock))
        pro.start()
        threads.append(pro)
    for thread in threads:
        thread.join()
    id_dict = dict(shared_dic)
    finish =  time.perf_counter()
    ###end multithreading###
    '''
    ###using multithreading concurrent futures### -> 
    import concurrent.futures
    shared_dic = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for productID in tqdm(id_dict_list):
            args = [shared_dic, productID]
            executor.submit(lambda p: get_prod_externalId(*p), args)
    id_dict = shared_dic
    ###end multiprocessing process###
    ##########End Multithreading/Multiprocessing part
    
#function7: return clean image name for 'Image Ref' column
#custom for function8
def image_name(ProductName, ImageID):
    #if ImageID == None or ImageID == np.nan or ImageID == '' or ImageID== 'nan':
        #return None --> not sure it's needed.. displaying image ref  even for non existing image might help when uploading new images
    if any(s in ProductName for s in ("/","'"," ")):
        for sy in ("/","'"," "):
            if sy in ProductName: 
                return ProductName.replace(sy,'_')
    else:
        return ProductName

#function7 bis: return link of image for 'Image ID' column
#custom for function8
def image_link(ImageID):
    if ImageID == None or ImageID == np.nan or ImageID == '' or ImageID == 'nan':
        return None
    else:
        return f'https://res.cloudinary.com/glovoapp/f_auto,q_auto/{ImageID}'
     
#super pic
def super_image_link(super_image_id):
    if super_image_id == None or super_image_id == np.nan or super_image_id == '' or super_image_id == 'nan':
        return None
    else:
        url = f'https://adminapi.glovoapp.com/admin/collection_groups/{super_image_id}' 
        r = requests.get(url, headers=oauth)
        return f"https://res.cloudinary.com/glovoapp/f_auto,q_auto/{r.json()['imageServiceId']}"

#function8: Create 'Products' sheet
def prod_import():    
    global df_prods, prod
    #step1: create columns for dataframe 'df_prods'
    df_prods = pd.DataFrame(columns = ['Super Collection', 'Super Collection ImageRef', 'Collection', 'Section', 'Product Name', 'Product Description', 'Product Price','Product ID', 'Add-On 1', 'Add-On 2', 'Add-On 3', 'Add-On 4','Add-On 5','Add-On 6','Add-On 7','Add-On 8','Add-On 9','Add-On 10','Add-On 11','Add-On 12','Add-On 13','Add-On 14','Add-On 15','Add-On 16','Active', 'Image Ref','Image ID'])
    print('Dowloading all products')
    #step2: get supercollections
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections'
    r = requests.get(url, headers = oauth)
    super_collections = r.json()
    for super_collection in super_collections:
        if super_collection["name"] != None:
            print(f'* Dowloading Super Collection {super_collection["name"]}')
        else: 
            print('* Dowloading all sections')
        collections = super_collection['collections']
        #top-down approach for getting all info structured: parsing collections > sections > products
        for collection in collections:
            collectionId = collection['id']
            url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/collections/{collectionId}/sections'
            r = requests.get(url, headers = oauth)
            sections = r.json()
            for section in sections:
                print(f'\t- Dowloading section {section["name"]}')
                for prod in (section['products']):
                    #add 'None' values to empty 'Add-On's columns in case the products has fewer than 16 add ons
                    for _ in range(len(prod['attributeGroups'])-1,16):  
                        prod['attributeGroups'].append({'id': None, 'name': None})
                    #fill in dataframe row by row
                    df_prods.loc[0 if pd.isnull(df_prods.index.max()) else df_prods.index.max() + 1] = [super_collection['name'], super_image_link(super_collection['id']), collection['name'].strip(), section['name'].strip(), prod['name'].strip(), prod['description'], prod['price'], id_dict.get(prod['id']), prod['attributeGroups'][0]['name'], prod['attributeGroups'][1]['name'], prod['attributeGroups'][2]['name'],prod['attributeGroups'][3]['name'],prod['attributeGroups'][4]['name'],prod['attributeGroups'][5]['name'],prod['attributeGroups'][6]['name'], prod['attributeGroups'][7]['name'], prod['attributeGroups'][8]['name'], prod['attributeGroups'][9]['name'], prod['attributeGroups'][10]['name'], prod['attributeGroups'][11]['name'], prod['attributeGroups'][12]['name'], prod['attributeGroups'][13]['name'],prod['attributeGroups'][14]['name'],prod['attributeGroups'][15]['name'],prod['enabled'], image_name(prod['name'].strip(), prod["image"]),image_link(prod["image"])]                
    ##clean dataframe
    #clean all duplicated values for readability in 'Super Collection' and 'Collection' columns
    df_prods.loc[df_prods.duplicated(subset = ['Super Collection']), ['Super Collection']] = None
    df_prods.loc[df_prods.duplicated(subset = ['Collection']), ['Collection']] = None
    df_prods.loc[df_prods.duplicated(subset = ['Super Collection ImageRef']), ['Super Collection ImageRef']] = None
    #try format 'Product ID' column as int
    df_prods.loc[:,'Product ID'] = pd.to_numeric(df_prods.loc[:,'Product ID'], downcast= "integer", errors= "ignore")
    #format Product Price column as float 
    df_prods.loc[:,'Product Price'] = pd.to_numeric(df_prods.loc[:,'Product Price'], errors= "coerce")
    #replace 'nan' desription with actual nan
    df_prods.loc[:,'Product Description'].replace('nan','', inplace = True)
    #Delete target empty columns
    AddOn_columns = df_prods.columns[df_prods.columns.to_series().str.contains('Add-On')].to_list()
    AddOn_columns.append('Super Collection')
    AddOn_columns.append('Super Collection ImageRef')
    for col in AddOn_columns[3:]: #starting at index 3 so to leave al least 3 add-ons columns in any situation
        if df_prods[col].isnull().all(): df_prods.drop(columns = col, inplace = True)
    #print(f"\nCreated Products sheet in Excel file '{store_name}_{store_cityCode}.xlsx'")
    list(df_prods)

#function9bis: create alaphabet dictionary
#custom for function9
def create_alphadic():
    global col_addons
    clean_addons_col = df_prods.columns[df_prods.columns.to_series().str.contains('Add-On')].to_list()
    number = []
    for _ in range(len(string.ascii_uppercase)):
        number.append(_)
    alphadic = dict(zip(number,string.ascii_uppercase))
    #for df_prods: 0 = B because of the index so we need to offset with +1
    col_addons = [alphadic.get(df_prods.columns.get_loc(_)+1) for _ in clean_addons_col]
    
#function9: save the created dataframe to excel
def save_to_excel():
    #create alphabet numeric dictionary to set data validation to Add-Ons columns
    create_alphadic()
    #saving to excel add-ons sheet and products sheet
    with pd.ExcelWriter(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx')) as writer:
        df_prods.to_excel(writer, sheet_name = 'Products', index_label = 'Index')
        writer.sheets['Products'].set_column('B:Z',20)
        writer.sheets['Products'].set_column('C:D',25)
        if 'Super Collection' in list(df_prods):
            writer.sheets['Products'].set_column('F:F',70)
        else:
            writer.sheets['Products'].set_column('E:E',70)
        writer.sheets['Products'].set_default_row(20)
        writer.sheets['Products'].freeze_panes(1, 0)
        try: writer.sheets['Products'].data_validation(f'{min(col_addons)}2:{max(col_addons)}5000',{"validate":"list","source":"='Add-Ons'!$A$2:$A$5000"})
        except ValueError: pass
        df_addons.to_excel(writer, sheet_name = 'Add-Ons', index = False)
        writer.sheets['Add-Ons'].set_column('B:Z',15)
        writer.sheets['Add-Ons'].set_column('A:A',30)
        writer.sheets['Add-Ons'].set_column('F:F',50)
        writer.sheets['Add-Ons'].set_default_row(20)
        writer.sheets['Add-Ons'].freeze_panes(1, 0)
        writer.sheets['Add-Ons'].data_validation('A1:A5000',{'validate':'custom','value':'=COUNTIF($A$1:$A$5000,A1)=1'})
    print(f"\nSuccesfully saved to excel @{os.path.relpath(os.path.join(output_path,f'{store_name}_{store_cityCode}.xlsx'))}\n")
    
#function10: download single image
#custom for function11
def image_download(nu,l):
    ImRef = df_prods.at[nu,'Image Ref']
    ImID = df_prods.at[nu,'Image ID']
    #pass if image reference is empty, Image ID is empty or image already present
    if ImRef == None or ImRef == np.nan or ImRef == '' or ImRef == 'nan':
        pass
    elif ImID == None or ImID == np.nan or ImID == '' or ImID == 'nan':
        pass
    elif os.path.isfile(os.path.join(image_path,f"{ImRef}.jpg")):
        #print(f"Image {str(df_prods.at[nu,'Product Name'])}.jpg already exists")
        pass
    else:
        l.append('ImRef')
        #download images with requests @ image/upload/ on cloudinary
        url = ImID
        r = requests.get(url)
        with open(os.path.join(image_path,f"{ImRef}.jpg"), 'wb') as f:
            f.write(r.content)
        print(f"Image {ImRef}.jpg downloaded")
        
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
        except FileExistsError: 
            pass
        finally:
            image_path = os.path.join(output_path,'Images')
            ##########Benginning Multithreading/Multiprocessing part
            '''
            ###with linear code###
            l = []
            for nu in tqdm(df_prods.index):
                image_download(nu,l)
            im_mod = l
            ###end linear code###
            
            ###with multiprocessing Pool###
            with Manager() as manager:
                l = manager.list()
                pool = Pool(cores())
                for nu in df_prods.index:
                    pool.apply_async(image_download, args = (nu,l,))
                pool.close()
                pool.join()
                im_mod = list(l)
            ###end multiprocessing Pool###   
            
            ###with multiprocessing### 
            with Manager() as manager: 
                l = manager.list()
                processes = []
                for nu in tqdm(df_prods.index):
                    process =  Process(target = image_download, args = [nu,l])
                    process.start()
                    processes.append(process)
                for process_django in processes:
                    process_django.join()
                im_mod = list(l)
            ###end multiprocessing###
            '''
            ###with multithreading concurrent futures### 
            l = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for nu in (df_prods.index):
                    args = [nu, l]
                    executor.submit(lambda p: image_download(*p), args)
            im_mod = l
            ###end  multithreading concurrent futures###
            ##########End Multithreading/Multiprocessing part
            if len(im_mod) == 0: print(f'\nNo new image to dowload')
            else: print(f'\nImages folder of {store_name} updated')
           

#function main(): dowload a single store ID menu and convert it to an excel file
def main(lima):
    global empty
    empty = False
    check_storeid(lima)
    check_if_empty()
    if empty: 
        pass
    else:
        start = time.perf_counter()
        create_output_dir()
        add_ons_import()
        id_dict_creation()
        prod_import()
        save_to_excel()
        check_images()
        finish = time.perf_counter()
        print(f"\n\nMenu of {store_name}-{store_cityCode} {(storeid)} successfully imported to Excel in {round(finish-start,2)} seconds\n")
        df_import.at[(df_import.loc[df_import.loc[:,'id'] == lima].index[0]),'status'] = 'Imported'

'''''''''''''''''''''''''''''End Bot'''''''''''''''''''''''''''''

'''''''''''''''''''''''''''''Launch'''''''''''''''''''''''''''''
if __name__ == '__main__':
    '''Init Procedural code'''
    set_path()
    logger_start()
    login_check()
    refresh()
    print_bot_name()
    '''Bot code'''
    stores_request()
    for lima in df_import['id']:
        main(lima)
    print(df_import)
    time.sleep(5)
