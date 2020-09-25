#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 29 11:59:30 2020
Last update on Fri Sep 4 10:28:53 2020

@author: giovanni.scognamiglio

Object: Creating a menu on Admin getting data from a file Excel
"""

#modules
import logging
import requests
import time
import pandas as pd
import datetime
import sys
import os
import os.path
import numpy as np
import string
import shutil
import json
import concurrent.futures
from tqdm import tqdm
from requests_toolbelt.multipart.encoder import MultipartEncoder
#from multiprocessing import Manager, Pool, Process, cpu_count
from get_new_token import *
from colorama import Fore, Style

bot_name = 'Menu Creator Bot'

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
    print('\n' + Fore.RED + Style.BRIGHT + bot_name + Style.RESET_ALL + '\n')
    
'''''''''''''''''''''''''''''End Init'''''''''''''''''''''''''''''

'''''''''''''''''''''''''''Beginning bot'''''''''''''''''''''''''''
'''Part 0: Set creation mode'''
#custom for stores_request(): get all cities for admin query related to AM's country
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
    global df_creator, mode
    while True:
        df_creator_copy = {}
        choice = input('Insert the Store ID where to create the menu:\n').strip()
        if ',' in choice: 
            choice = choice.split(',')
            l_choice = []
            for c in choice:
                try: l_choice.append(int(c))
                except Exception: pass
            if len(l_choice) == 0:
                print('No results found for "{choice}", please try again')
                continue
            else:
                mode = 'multiple'
                df_creator_copy = df_creator.loc[df_creator.loc[:,'id'].isin(l_choice)]
                if df_creator_copy.index.size < 1:
                    print('No results found for "{choice}", please try again')
                    continue
                print(df_creator_copy)
                print('\nThe bot will modify the above Store\'s menu:')
        elif choice.isdigit():
            mode = 'single'
            df_creator_copy = df_creator.loc[df_creator.loc[:,'id'] == int(choice)]
            print(df_creator_copy)
            print('\nThe bot will modify the above Store\'s menu:')
        elif choice.lower() == 'all':
            mode = 'all'
            df_creator_copy = df_creator.copy()
            print(df_creator_copy)
            print('\nThe bot will modify ALL the Store\'s menu:')
        else:
            print('Unable to process "{choice}", please try again')
            continue
        conferma = input('Continue? [yes]/[no]\t')
        if conferma in ['yes','ye','y','si']:
            df_creator = df_creator_copy.copy()
            break

#show a dataframe of all the stores (AM can then copy the ID of the city he is interested in and proceed with the creation)
def stores_request():
    global df_creator
    get_cities()
    #search stores on admin
    while True:
        partner = input('Insert a Store Name or Store ID to create:\n').strip()
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
                    df_creator = df_admin[['name','cityCode','id']]
                    df_creator = df_creator.rename({'cityCode':'city'}, axis = 1)
                    #df_creator.loc[:,'status'] = ['' for _ in range(len(df_creator.index))]
                    print(df_creator)
                    if q_input == 'id':
                        set_mode_id()
                    else:
                        set_mode_name()
                    break
        
'''Part 1: Set target Admin store and input data'''
#custom function for set_storeid(): find excel file in current working directory with os.walk
def find_excel_file_path(excel_name):
    #walk in cwd -> return excel path or raise error
    for root, dirs, files in os.walk(cwd):
        if excel_name in files:
            for file in files:
                if file == excel_name:
                    print(f'\n{excel_name} found in current working directory')
                    return os.path.join(root,file)
    else:
        #print('File not found in current working directory')
        raise NameError

#custom function for set_storeid(): user inserts the excel name for data input
def plan_b():
    global input_path, excel_name
    while True:
        time.sleep(0.5)
        excel_name = input("\nInsert the name of the Excel file to input(eg: 'Partner_MIL.xlsx'):\n").strip()
        if not 'xlsx' in excel_name: excel_name = f'{excel_name}.xlsx'
        try:
            excel_path = find_excel_file_path(excel_name)
        except NameError:
            time.sleep(0.5)
            print(f'\nCould not find {excel_name} in {cwd}\nPlease try again\n')
            continue
        else:
            time.sleep(0.5)
            confirm_path = input(f"\nMenu of {store_name} - {store_cityCode} ({storeid}) will be updated with data from '{os.path.relpath(excel_path)}'\nConfirm [yes]/[no]:\t")
            if confirm_path in ["yes","y","ye","si"]:
                logger.info(f"Updating menu of store {store_name} - {store_cityCode} ({storeid}) with {excel_name}")
                input_path = excel_path
                break
            else: 
                print('\nKey not recognized, please start again\n')
                continue

def df_to_repository():
    try: 
        os.mkdir(os.path.join(os.path.dirname(input_path),'Repository'))
    except FileExistsError: 
        pass
    finally:
        shutil.copy(input_path,os.path.join(os.path.dirname(input_path),'Repository',f'{datetime.datetime.now().strftime("%d_%m_%Y")}_{excel_name}'))

#let users set store where to create menu on Admin & verify if it exists on Admin
def set_storeid_unique(nassau):
    global storeid, input_path, store_name, store_cityCode, excel_name
    prova = 0
    while True:
        if prova != 0:
            storeid = input("\nInsert the Store ID where to create the menu:\n").strip()
        else: storeid = str(df_creator.at[nassau, 'id'])
        #check if store ID exists in Admin with request @ admin/stores?
        url = f'https://adminapi.glovoapp.com/admin/stores?limit=500&offset=0'
        params = {'query' : storeid}
        r = requests.get(url, headers = oauth, params = params)
        if r.ok is False: 
            print("\nStore not on Admin. Please insert a valid Store Id")
            prova += 1
            if prova > 1: print("If error repeats, consider closing the program and start again")
            continue
        try:
            store_name = (r.json()['stores'][0]['name']).strip()
        except IndexError:
            print("\nStore not on Admin. Please insert a valid Store Id")
            prova += 1
            if prova > 1: print("If error repeats, consider closing the program and start again")
            continue
        else:
            store_cityCode = r.json()['stores'][0]['cityCode']
            excel_name = f'{store_name}_{store_cityCode}.xlsx'
            #print(f'\n{store_name} - {store_cityCode} ({storeid}) found on Admin')
            #check if excel_name exists in cwd with find_excel_file_path()
            #if excel not in cwd -> user inserts manually the name of the file he wants to use as input file with planb()
            try:
                find_excel_file_path(excel_name)
            except NameError:
                time.sleep(0.5)
                print(f'\nDid not find {excel_name} in {cwd}')
                plan_b()
                break
            else:
                time.sleep(0.5)
                #print(f'\n{excel_name} found in {cwd}')
                #if excel_name found in cwd -> user can choose input file: confirm excel_name or enter other file name with planb()
                a_or_b = input(f"\nUpdate menu of {store_name} - {store_cityCode} ({storeid}) with:\n[A] - Data inside '{excel_name}'\n[B] - Other excel file\nPress 'A' or 'B' then press ENTER:\n").lower().strip()
                if a_or_b in ["a","b"]: 
                    if a_or_b == "a": 
                        input_path = find_excel_file_path(excel_name)
                        logger.info(f"Updating menu of store {store_name} - {store_cityCode} ({storeid}) with {excel_name}")
                        break
                    if a_or_b == "b":
                        plan_b()
                        break
                    
def set_storeid_all(nairobi):
    global storeid, input_path, store_name, store_cityCode, excel_name
    storeid = str(df_creator.at[nairobi, 'id'])
    #check if store ID exists in Admin with request @ admin/stores?
    url = f'https://adminapi.glovoapp.com/admin/stores?limit=500&offset=0'
    params = {'query' : storeid}
    r = requests.get(url, headers = oauth, params = params)
    if r.ok is False: 
        print("\nProblem with {storeid} -> Store not on Admin")
    else:
        try:
            store_name = (r.json()['stores'][0]['name']).strip()
        except IndexError:
            print("\nProblem with {storeid} -> Store not on Admin")
        else:
            store_cityCode = r.json()['stores'][0]['cityCode']
            excel_name = f'{store_name}_{store_cityCode}.xlsx'
            #print(f'\n{store_name} - {store_cityCode} ({storeid}) found on Admin')
            #check if excel_name exists in cwd with find_excel_file_path()
            #IF EXCEL NOT IN CWD -> PASS (IGNORE)
            try:
                input_path = find_excel_file_path(excel_name)
            except NameError:
                print(f'\nCAUTION: Did not find {excel_name} in {cwd}\nStore {storeid}-{store_cityCode} NOT updated.')
                df_creator.at[nairobi,'status'] = 'excel NOT found'

'''Part 2: main() part & all relative functions'''

#function1: delete existing menu
def del_menu():
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/menu'
    d = requests.delete(url, headers = oauth)
    if d.ok is True: print(f'Menu of store {storeid} deleted')
    else: print(d, d.contents)

#function2: create 'add-ons' sheet dataframe
def import_df_attrib(): 
    global data_attrib, group_list, data_attrib_saveback
    #import dataframe of 'Add-Ons' sheet
    data_attrib = pd.read_excel(input_path, sheet_name = 'Add-Ons')
    #clean empty rows
    data_attrib.dropna(how='all', inplace = True)
    #reset index after deleting empty rows
    data_attrib.reset_index(drop = True, inplace = True)
    #strip and capitalize dataframe columns 'Add-On Name' & 'Attribute'
    data_attrib.loc[:,'Add-On Name'] = data_attrib['Add-On Name'].str.strip()
    data_attrib.loc[:,'Attribute'] = data_attrib['Attribute'].str.strip()
    data_attrib.loc[:,'Attribute'] = data_attrib['Attribute'].str.capitalize()
    #cleaning column 'Price':
    for _ in data_attrib.index:
        data_attrib.at[_,'Price'] = str(data_attrib.at[_,'Price']).replace(',','.')
        try:
            data_attrib.at[_,'Price'] = float(data_attrib.at[_,'Price'])
        except ValueError:
            data_attrib.at[_,'Price'] = 0
    #cleaning column 'Active'
    data_attrib.loc[:,'Active'] = [False if _ == False else True for _ in data_attrib.loc[:,'Active']]
    #over-write column 'Attribute ID': allocate int starting at 1000
    #If two attribs have same name & price, insert same attrib id
    attrib_n_price_list = [f"{data_attrib.at[_,'Attribute']}&{data_attrib.at[_,'Price']}" for _ in range(len(data_attrib.index))]
    list_1000 = [_ for _ in range(1000,2000)]
    for n in data_attrib.index:
        attrib_n_price = attrib_n_price_list[n]
        rambo_index = attrib_n_price_list.index(attrib_n_price)
        if rambo_index == n:
            data_attrib.at[n,'Attribute ID'] = list_1000[n]
        else:
            data_attrib.at[n,'Attribute ID'] = data_attrib.at[rambo_index,'Attribute ID']
    #over-write column 'Add-On ID': allocate int to every Add-On ID starting at 0
    pimp = 0
    for _ in data_attrib.index:
        if pd.isna(data_attrib.at[_,'Add-On Name']) is False:
            data_attrib.at[_,'Add-On ID'] = pimp
            pimp += 1
    ###create new dataframe for save the above back to orignal excel###
    data_attrib_saveback = data_attrib.copy()
    ###end new df copy###
    #getting list of attribute groups
    group_list = data_attrib.loc[:,'Add-On Name'].dropna().tolist()
    #forward fill
    data_attrib.fillna(method = 'ffill', inplace = True)
    #create new column  'Attrib_real_Id' -> for attributes' real ID (necessary for building attribute groups)
    data_attrib.loc[:,'Attrib_real_Id'] = ['' for _ in range(len(data_attrib))]
    #create new column  'Attrib_group_real_Id' -> for attribute groups' real ID (necessary for building products groups)
    data_attrib.loc[:,'Attrib_group_real_Id'] = ['' for _ in range(len(data_attrib))]
    print('\nAdd-Ons sheet imported')

###Attribute creation -> functions 3,4,5###
#function3: attributes creation function
#custom for function5: 
def attrib_creation_function(shared_list,i):
    ##step 1: create the attribute
    #create attribute with requests @ admin/attributes and get response (attrib_real_id)
    url_post = 'https://adminapi.glovoapp.com/admin/attributes'
    payload = {'storeId' : storeid,
               'name' : data_attrib.at[i,'Attribute'],
               'priceImpact' : str(data_attrib.at[i,'Price']),
               'enabled' : bool(data_attrib.at[i,'Active'].astype('bool')),
               'selected' : False}
    p = requests.post(url_post, headers = oauth, json = payload)
    if p.ok is False:
        print(f"{i}: post{p} - {data_attrib.at[i,'Attribute']} NOT created")
        print(p.content)
    #data_attrib.at[i, 'Attrib_real_Id'] = p.json() -> (using list instead)
    #pushing response (attribute real id) to shared_list
    real_attrib_id = p.json()
    shared_list[i] = real_attrib_id
    ##step 2: get newly created attribute's details
    #get attrib details with request @ admin/attributes?storeId={storeid}
    url_get = f'https://adminapi.glovoapp.com/admin/attributes?storeId={storeid}'
    r = requests.get(url_get, headers = oauth)
    for response in r.json():
        if response['id'] == real_attrib_id: 
            attrib_details = response
            break
    ##step 3: change the external id the newly created attribute -> because we can't upload an attribute with custom external id...
    #change external id with the one in dataframe
    attrib_details['externalId'] = str(data_attrib.at[i,'Attribute ID'])
    #put request @ admin/attributes/{real_attrib_id} for pushing new external id to admin
    url_put = f"https://adminapi.glovoapp.com/admin/attributes/{real_attrib_id}"
    put = requests.put(url_put, headers = oauth, json = attrib_details)
    if put.ok:
        print(f"Created Attribute {i} with ext.id {str(data_attrib.at[i,'Attribute ID'])}")
    else:
        print(f"NOT created attribute {i}: {put}{put.content}")    

#function4: check if duplicate attributes have been already created
#custom for function5: 
def attrib_check(shared_list,i):  
    #check if external id is duplicate. If duplicate: give value of the previous one. Else create attrib.
    attri_ID = data_attrib['Attribute ID'][i]
    repetition_check = int(np.array(data_attrib.loc[data_attrib['Attribute ID'] == attri_ID,'Attribute ID'].value_counts()))
    if repetition_check > 1:
        findex = data_attrib.loc[data_attrib['Attribute ID']==attri_ID].index[0]
        if findex < i:
            try:
                #data_attrib.at[i, 'Attrib_real_Id'] =  data_attrib.at[findex, 'Id'] -> using list instead
                shared_list[i] = shared_list[findex]
            except Exception:
                shared_list[i] = None
            finally:
                print(f"Attribute {i} - external id already exist")
        else: attrib_creation_function(shared_list,i)
    else: attrib_creation_function(shared_list,i)

#fucntion5bis: use (max -1) number of cpu cores: every CPU in use increases speed by 1x
#custom for multiprocessing Pool ->  use all cpu cores - 1 to avoid freezing operating system
def cores():
    if cpu_count() <  2:
        return 1
    else:
        return (cpu_count() - 1)
        #return 8
#function5: attributes creation
#parse through all the attributes and trigger function attrib_check()
def attrib_creation():
    print('\nStage 1: Attributes creation')
    global data_attrib
    '''
    ###with linear code###
    shared_list = []
    for _ in data_attrib.index:
        shared_list.append('')
    for i in data_attrib.index:
        attrib_check(shared_list, i)
    temp_id_list = shared_list
    ###end linear code###
    
    ###with multiprocessing Pool###
    with Manager() as manager:
        shared_list = manager.list()
        pool = Pool(cores())
        for _ in data_attrib.index:
            shared_list.append("")
        for i in data_attrib.index:
            pool.apply_async(attrib_check, args = (shared_list, i))
        pool.close()
        pool.join()
        temp_id_list = list(shared_list)
    ###end multiprocessing Pool###
    '''
    ###with ThreadPoolExecutor###
    shared_list = ['' for _ in data_attrib.index]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for i in data_attrib.index:
            args = [shared_list, i]
            executor.submit(lambda p: attrib_check(*p), args)
    temp_id_list = shared_list
    ###end ThreadPoolExecutor###
    
    #push fresh temp_id_list to dataframe
    data_attrib.loc[:, 'Attrib_real_Id'] = temp_id_list
    #fill empty Attrib_real_Id values -> duplicate attrib id will have empty attrib_real_id so we fill their attrib_real_id with the same value of their duplicate
    for real_index in data_attrib.loc[:,'Attrib_real_Id'].index:
        real_id =  data_attrib.at[real_index,'Attrib_real_Id']
        real_attrib = data_attrib.at[real_index,'Attribute ID']
        if real_id == '' or pd.isna(real_id):
            real_findex = data_attrib.loc[data_attrib['Attribute ID']== real_attrib].index[0]
            data_attrib.at[real_index, 'Attrib_real_Id'] =  data_attrib.at[real_findex, 'Attrib_real_Id']
    if data_attrib.loc[:, 'Attrib_real_Id'].isna().any() is True:
        print('Houston, we have a problem')
        print(data_attrib.loc[:, 'Attrib_real_Id'])
        exit
    print(data_attrib.loc[:, 'Attrib_real_Id'])

###Attribute groups creation -> functions 6,7'''
#function6: attribute group creation function
#custom for function7
def attrib_group_creation_function(shared_list2, y, r_json, n):
        #set temporary dataframe filtering groups name
        temp_df = data_attrib.loc[data_attrib['Add-On ID']==y].reset_index(drop = True)
        temp_list = []
        for v in r_json:
            if v['id'] in temp_df.loc[:,'Attrib_real_Id'].tolist(): 
                temp_list.append(v)
                #print(f"{v} appended")
        #prepare payload
        url = 'https://adminapi.glovoapp.com/admin/attribute_groups'
        payload = {
             "name": temp_df.at[0,'Add-On Name'],
             "externalId": str(temp_df.at[0,'Add-On ID']),
             "min": str(temp_df.at[0,'Min Selection']),
             "max": str(temp_df.at[0,'Max Selection']),
             "collapsedByDefault": False,
             "multipleSelection": bool(temp_df.at[0,'Multiple Selection'].astype('bool')),
             "attributeDetails": temp_list,
             "isNew": True,
             "visible": True,
             "editMode": True,
             "storeId": storeid,
             "attributes": temp_df.loc[:,'Attrib_real_Id'].tolist()}
        #post request for attrib group creation
        p_group = requests.post(url, headers = oauth, json = payload)
        shared_list2[n] = p_group.json()
        #data_attrib.loc[data_attrib['Add-On ID']==y,'Attrib_group_real_Id'] = p_group.json() -> using list instead
        if p_group.ok:
            print(f"Added attribute group {int(y)} - {temp_df.at[0,'Add-On Name']}")
        else: 
            print(f"NOT added attribute group {int(y)} - {temp_df.at[0,'Add-On Name']} -> {p_group}-{p_group.content}")

#function7: attribute groups creation 
def attrib_group_creation():
    print('\nStage 2: Attribute groups creation')
    #get list of unique Add-On names
    group_num = list(dict.fromkeys(list(data_attrib.loc[:,'Add-On ID'])))
    #get attrib details
    url_get = f'https://adminapi.glovoapp.com/admin/attributes?storeId={storeid}'
    r = requests.get(url_get, headers = oauth)
    r_json = r.json()
    ##########Benginning Multithreading/Multiprocessing part
    '''
    ###with linear###
    shared_list2 = ['' for _ in range(len(group_num))]
    for y in group_num:
        n = group_num.index(y)
        attrib_group_creation_function(shared_list2, y, r_json, n)
    groupId_list = shared_list2
    ###end linear###
    ###with multiprocessing Pool###
    with Manager() as manager:
        shared_list2 = manager.list()
        pool = Pool(cores())
        for _ in group_num:
            shared_list2.append("")
        for y in group_num:
            n = group_num.index(y)
            pool.apply_async(attrib_group_creation_function, args = (shared_list2, y, r_json, n,))
        pool.close()
        pool.join()
        groupId_list = list(shared_list2)
    ###end multiprocessing Pool###
    '''
    ###with ThreadPoolExecutor###
    shared_list2 = ['' for _ in range(len(group_num))]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for y in group_num:
            n = group_num.index(y)
            args = [shared_list2, y, r_json, n] 
            executor.submit(lambda p: attrib_group_creation_function(*p),  args)
    groupId_list = shared_list2
    ###end ThreadPoolExecutor###
    ##########End Multithreading/Multiprocessing part
    #saving attributes group IDs to dataframe
    for n_group_num in range(len(group_num)):
        data_attrib.loc[data_attrib['Add-On ID']==group_num[n_group_num], 'Attrib_real_Id'] = groupId_list[n_group_num]

#function8: Import dataframe from 'Products' sheet 
def import_df_prod():
    global data_prod, asociados_list, data_prod_saveback
    #import dataframe of 'Products' sheet
    data_prod = pd.read_excel(input_path, sheet_name = 'Products', index_col=0)
    #clean empty rows
    data_prod.dropna(how = 'all', inplace = True)
    #reset index after deleting empty rows
    data_prod.reset_index(drop = True, inplace = True)
    #strip and capitalize dataframe columns 'Collection', 'Section', 'Product Name'
    for col_name in ['Collection', 'Section', 'Product Name']:
        data_prod.loc[:,col_name] = data_prod[col_name].str.strip()
        data_prod.loc[:,col_name] = data_prod[col_name].str.capitalize()
    #removing nan from column 'Product Description'  & 'Image ID' for clean upload
    data_prod.loc[:,'Product Description'].fillna('', inplace = True)
    data_prod.loc[:,'Image ID'].fillna('', inplace = True)
    #cleaning column 'Price':
    for _ in data_prod.index:
        data_prod.at[_,'Product Price'] = str(data_prod.at[_,'Product Price']).replace(',','.')
        try:
            data_prod.at[_,'Product Price'] = float(data_prod.at[_,'Product Price'])
        except ValueError:
            data_prod.at[_,'Product Price'] = 0  
    #cleaning column 'Active'
    data_prod.loc[:,'Active'] = [False if _ == False else True for _ in (data_prod.loc[:,'Active'])]
    #over-write column 'Product ID'
    for _ in data_prod.index:
        data_prod.at[_,'Product ID'] = _
    #get number of actual add-ons columns
    asociados_list = []
    for _ in range(1,16):
        try: 
            data_prod.loc[:,f'Add-On {_}']
            asociados_list.append(_)
        except Exception:
            break
    #strip add-ons columns
    for _ in asociados_list:
        if data_prod.loc[:,f'Add-On {_}'].isnull().all() is False:
            try: data_prod.loc[:,f'Add-On {_}'] = data_prod.loc[:,f'Add-On {_}'].str.strip()
            except Exception: pass
    ##create new dataframe for save the above back to orignal excel##
    data_prod_saveback = data_prod.copy()
    #forward fill
    data_prod.loc[:,'Collection'].fillna(method = 'ffill', inplace = True)
    #create column collectionId
    data_prod.loc[:,'CollectionId'] = ['' for _ in range(len(data_prod))]
    print('\nProducts sheet imported')
        
###Images upload -> functions 9,10,11,12###
#function9: get all image names in the Images folder and create dict with images name and images name with extension ->  needed for uploading
#custom for function12
def get_image_names():
    global image_names, complete_names, im_dic
    #print('Scanning {os.path.relpath(os.path.join(os.path.dirname(input_path),"Images"))} folder')
    image_names = []
    complete_names = []
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(input_path),"Images")):
        for file in files:
            if file[-3:] == 'jpg' or file[-3:] == 'png':
                complete_names.append(file)
                image_names.append(file[:-4])
        im_dic = dict(zip(image_names, complete_names))

#function10: check if Image Ref value is in Images folder as a real image
#custom for function11
def check_image_exists(im_ref):
        if im_ref in image_names:
            return True
        else:
            return False                    

#function11: pass or upload function -> upload images with no image ID that exists in Images folder
#custom for function12
def image_upload_function(im, l_of_im):
    im_ref = data_prod.at[im,'Image Ref']
    if pd.isna(im_ref) is False or im_ref != '':
        if pd.isna(data_prod.at[im,'Image ID']) or data_prod.at[im,'Image ID'] == '' :
            if check_image_exists(im_ref):
                im_name = im_dic.get(im_ref)
                im_path = os.path.join(os.path.dirname(input_path),'Images',im_name)
                url = 'https://api.cloudinary.com/v1_1/glovoapp/upload'
                mp_encoder = MultipartEncoder(
                    fields={'folder': 'Products',
                            'upload_preset': 'arj9awzq',
                            'source': 'uw',
                            'api_key': None,
                            'file': (os.path.relpath(im_path), open(os.path.relpath(im_path), 'rb'), 'text/plain')})
                header = {'Content-Type': mp_encoder.content_type}
                r = requests.post(url, data=mp_encoder, headers = header)
                if r.ok is False:
                    print('Houston, we have a problem')
                else:
                    #data_prod.at[im,'Image ID'] = r.json()['public_id']  -> using list instead
                    l_of_im[im] = r.json()['public_id']
                    print(f'Image {im_ref} uploaded')

#function12: check for new pictures to upload before product creation
#get all image refs in the images folder and cross check it with image ref column in excel. If new image: upload it on and get metadata
def images_upload():
    global listOfImages
    print('\nChecking for new images to upload..')
    get_image_names()
    #uploading new images
    ##########Benginning Multithreading/Multiprocessing part
    '''
    ###linear code###
    l_of_im = ['' for _ in range(len(data_prod.index))]
    for im in data_prod.index:
        image_upload_function(im, l_of_im)
    listOfImages = l_of_im
    ###end linear code###
    
    ###multiprocessing pool###
    with Manager() as manager:
        l_of_im = manager.list()
        pool = Pool(cores())
        for im in data_prod.index:
            l_of_im.append("")
        for im in data_prod.index:
            pool.apply_async(image_upload_function, args = (im, l_of_im,))
        pool.close()
        pool.join()
        listOfImages = list(l_of_im)
    ###end nultiprocessing pool###
    '''
    ###ThreadPoolExecutor###
    l_of_im = ['' for _ in range(len(data_prod.index))]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for im in data_prod.index:
            args = [im, l_of_im]
            executor.submit(lambda p: image_upload_function(*p), args)
    listOfImages = l_of_im
    ###end ThreadPoolExecutor###
    ##########End Multithreading/Multiprocessing
    #saving new image ID to dataframe
    for im in data_prod.index:
        im_ref = data_prod.at[im,'Image Ref']
        if pd.isna(im_ref) is False or im_ref != '':
            if pd.isna(data_prod.at[im,'Image ID']) or data_prod.at[im,'Image ID'] == '' :
                if check_image_exists(im_ref):
                    data_prod.at[im,'Image ID'] = f'https://res.cloudinary.com/glovoapp/f_auto,q_auto/{listOfImages[im]}'
    if len(listOfImages) == listOfImages.count(''):
        print('No new images to upload')
    else:
        print(f"Uploaded {int(len(listOfImages))-int(listOfImages.count(''))} new images")
        print(f'Saving new Image IDs to {input_path}')
        
#function13bis: create alaphabet dictionary
#custom for function9
def create_alphadic():
    global col_addons
    clean_addons_col = data_prod_saveback.columns[data_prod_saveback.columns.to_series().str.contains('Add-On')].to_list()
    number = []
    for _ in range(len(string.ascii_uppercase)):
        number.append(_)
    alphadic = dict(zip(number,string.ascii_uppercase))
    #for df_prods: 0 = B because of the index so we need to offset with +1
    col_addons = [alphadic.get(data_prod_saveback.columns.get_loc(_)+1) for _ in clean_addons_col]

#function13: saving df back to excel with updated image ID:
#cleaned data and new IDs are pushed back to original Excel
def saveback_df():
    #push new Image IDs values to saveback dataframe
    data_prod_saveback.loc[:,'Image ID'] = data_prod.loc[:,'Image ID'].copy()
    #clean column 'Multiple Selection': show data in in True/False bool type 
    data_attrib_saveback.loc[:,'Multiple Selection'].fillna('', inplace = True)
    for _ in data_attrib_saveback.index:
        if data_attrib_saveback.loc[_,'Multiple Selection'] != '':
            data_attrib_saveback.loc[_,'Multiple Selection'] = bool((data_attrib_saveback.loc[_,'Multiple Selection']))
    #create alphabet dictionary for matching columns to excel letter columns
    create_alphadic()
    #save both saveback dataframes to original Excel
    with pd.ExcelWriter(input_path) as writer:
        data_prod_saveback.to_excel(writer, sheet_name = 'Products', index_label = 'Index')
        writer.sheets['Products'].set_column('B:Z',20)
        writer.sheets['Products'].set_column('C:D',25)
        writer.sheets['Products'].set_column('E:E',70)
        writer.sheets['Products'].set_default_row(20)
        writer.sheets['Products'].freeze_panes(1, 0)
        try: writer.sheets['Products'].data_validation(f'{min(col_addons)}2:{max(col_addons)}1000',{"validate":"list","source":"='Add-Ons'!$A$2:$A$1000"})
        except ValueError: pass
        data_attrib_saveback.to_excel(writer, sheet_name = 'Add-Ons', index = False)
        writer.sheets['Add-Ons'].set_column('B:Z',15)
        writer.sheets['Add-Ons'].set_column('A:A',30)
        writer.sheets['Add-Ons'].set_column('F:F',50)
        writer.sheets['Add-Ons'].set_default_row(20)
        writer.sheets['Add-Ons'].freeze_panes(1, 0)
        writer.sheets['Add-Ons'].data_validation('A1:A500',{'validate':'custom','value':'=COUNTIF($A$1:$A$500,A1)=1'})
    print(f"\nClean 'Products' & 'Add-Ons' sheets saved back to original Excel {excel_name}")

###Product creation -> functions 14,15,16,18###
#function14: return cleaned value when required
#custom for function16
def cleaned(value):
    if value == '' or value == np.nan or value == None or value == 'nan':
        return None
    else:
        return str(value)    
    
#function14bis: convert link to usable image service id
def imageServiceId_name(image_link, image_ref):
    image_link = str(image_link)
    if image_ref == '' or image_ref == np.nan or image_ref == None or image_ref == 'nan':
        return None
    elif image_link == '' or image_link == np.nan or image_link == None or image_link == 'nan':
        return None
    else:
        #example: converts 'https://res.cloudinary.com/glovoapp/f_auto,q_auto/Products/tnondqzvqy2sthtzn6rj' into 'Products/tnondqzvqy2sthtzn6rj'
        return image_link[-(len(image_link)-image_link.rfind('/')+8):]

#function15bis: orders products after creating them as admin does not care of order of input
def order_product(product_Id, sectionId, q):
    order_url = f'https://adminapi.glovoapp.com/admin/products/{product_Id}/changeSection'
    payload = {"sectionId":sectionId, "position":q}
    order_put = requests.put(order_url, headers = oauth,json = payload)
    if order_put.ok is False:
        print(f'Ouch -> product not ordered: {order_put}-{order_put.content}')
        
#function15: creates products
#Custom function for product_creation():
def prod_creation_function(q, sectionId, temp_df3_bis):        
    #step1: prepare list with attrib group to include with product api creation request       
    #getting list of add-ons name from dataframe
    temp_attributeGroupNames = []
    for asociado in asociados_list:
        if pd.isna(temp_df3_bis.loc[q,f'Add-On {asociado}']) is False and temp_df3_bis.loc[q,f'Add-On {asociado}'] != '':
            temp_attributeGroupNames.append(str(temp_df3_bis.loc[q,f'Add-On {asociado}']))
    #parse over product's temp_attributeGroupNames and create new list with corresponding IDs from attrGroup_dict
    temp_attributeGroupIds = []
    if len(temp_attributeGroupNames) > 0: 
        for i in temp_attributeGroupNames:
            temp_attributeGroupIds.append(attrGroup_dict.get(i))
    #step2: create product with request @ admin/products
    url = 'https://adminapi.glovoapp.com/admin/products'
    payload = {"name": cleaned(temp_df3_bis.at[q,'Product Name']),
               "description": cleaned(temp_df3_bis.at[q,'Product Description']),
               "imageServiceId": imageServiceId_name(temp_df3_bis.at[q,'Image ID'], temp_df3_bis.at[q,'Image Ref']),
               "price": temp_df3_bis.at[q,'Product Price'],
               "topSellerCustomization": "AUTO",
               "externalId": cleaned(temp_df3_bis.at[q,'Product ID']),
               "enabled": bool(temp_df3_bis.at[q,'Active'].astype('bool')),
               "sectionId": sectionId,
               "attributeGroupIds": temp_attributeGroupIds,
               "prices": [],
               "productTags": []}
    post = requests.post(url, headers = oauth, json = payload)
    if post.ok is False:
        print(f"NOT inserted product {temp_df3_bis.at[q,'Product Name']}: {post}-{post.content}")
        exit
    else:
        print(f"Inserted product {temp_df3_bis.at[q,'Product Name']}")
        product_Id = post.json()
        order_product(product_Id, sectionId, q)
    
#function16: create sections
#Custom for function18
def section_creation(n, shared_sectionId_list, temp_df3, collectionId, section):      
    #create section-wise dataframe 
    temp_df3_bis = temp_df3.loc[temp_df3['Section']==section].reset_index(drop = True).copy()
    #create section with request @ admin/collectionsections
    url = 'https://adminapi.glovoapp.com/admin/collectionsections'
    payload = {"name":section,"collectionId": collectionId,"enabled": True}
    post = requests.post(url, headers = oauth, json = payload)
    if post.ok: print(f"Section {section} created")
    else: print(f"Section {section} post {post}-{post.content}")
    sectionId = post.json()
    shared_sectionId_list[n] = post.json()
    #once section is created: create products ([::-1] for order purposes)
    for q in temp_df3_bis.index:
        prod_creation_function(q, sectionId, temp_df3_bis)

#function18: create products 
def product_creation():
    global attrGroup_dict
    print('\nStage 3: Product creation')
    #get attribute groups info & create dict with attrib groups names and attrib groups IDs
    url = f'https://adminapi.glovoapp.com/admin/attribute_groups?storeId={storeid}'
    attrib_groups = requests.get(url, headers = oauth)
    attrGroup_NameList = [attrGroup['name'] for attrGroup in attrib_groups.json()]
    attrGroup_IdList = [attrGroup['id'] for attrGroup in attrib_groups.json()]
    attrGroup_dict = dict(zip(attrGroup_NameList,attrGroup_IdList))
    #Start with collections: get list of unique collection
    collection_list = list(dict.fromkeys(list(data_prod.loc[:,'Collection'].dropna())))
    #iterate over collection list
    for collection in collection_list:
        #position = collection_list.index(collection)
        temp_df3 = data_prod.loc[data_prod['Collection']==collection].reset_index(drop = True).copy()
        #create collection
        url = 'https://adminapi.glovoapp.com/admin/collections'
        payload = {"name": collection, "storeId": storeid}
        post = requests.post(url, headers = oauth, json = payload)
        data_prod.loc[data_prod['Collection']==collection,'CollectionId'] = post.json()
        collectionId = post.json()
        if post.ok: print(f"Created collection {collection}")
        else: print(f"NOT created collection {collection} -> {post}-{post.content}")
        #create sections
        section_list = list(dict.fromkeys(list(temp_df3.loc[:,'Section'].dropna())))
        ##########Beginning Multithreading/Multiprocessing
        '''
        ###using linear code###
        multipro = False
        shared_sectionId_list = ['' for _ in range(len(section_list))]
        for section in section_list:
            n = section_list.index(section)
            section_creation(n, shared_sectionId_list, temp_df3, collectionId, section)
        ###end linear code###
        
        ###using nultiprocessing pool###
        multipro = True
        with Manager() as manager:
            shared_sectionId_list = manager.list()
            pool = Pool(cores())
            for _ in range(len(section_list)):
                shared_sectionId_list.append('')
            for section in section_list:
                n = section_list.index(section)
                pool.apply_async(section_creation, args = (n, shared_sectionId_list, temp_df3, collectionId, section,))
            pool.close()
            pool.join()
            zombie_sectionId_list = list(shared_sectionId_list)
        ###end nultiprocessing pool###
        '''
        ###ThreadExecutorPool###
        multipro = True
        shared_sectionId_list = ['' for _ in range(len(section_list))]
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for section in section_list:
                n = section_list.index(section)
                args = [n, shared_sectionId_list, temp_df3, collectionId, section]
                executor.submit(lambda p: section_creation(*p), args)
        zombie_sectionId_list = shared_sectionId_list
        ###end ThreadExecutorPooll###
        ##########End Multithreading/Multiprocessing
        if multipro is True:
            #arrange section positions -> only needed if multiprocessing in use
            print('\nOrdering sections positions')
            for secId in tqdm(zombie_sectionId_list):
                position = zombie_sectionId_list.index(secId)
                url = f'https://adminapi.glovoapp.com/admin/collectionsections/{secId}/changeCollection'
                payload = {"position" : position, "collectionId" : collectionId}
                put_pos = requests.put(url, headers = oauth, json = payload)
                if put_pos.ok is False: print(f'Section {secId} PROBLEM when moved to P {position}')
            print('Ordering sections positions completed')
        
#function main(): create an entire from an Excel file
def main(niamey):
    df_to_repository()
    start = time.perf_counter()
    del_menu()
    import_df_attrib()
    attrib_creation()
    attrib_group_creation()      
    import_df_prod()
    images_upload()
    saveback_df()
    product_creation()
    finish = time.perf_counter()
    print(f"\nMenu of store id {store_name} - {store_cityCode} ({storeid}) successfully created from '{excel_name}' in {round(finish-start,2)} seconds")
    df_creator.loc[niamey,'status'] = 'Created'
    
'''''''''''''''''''''''''''''End Bot'''''''''''''''''''''''''''''
'''launch'''    
if __name__ == '__main__':
    '''Initiation code'''
    set_path()
    logger_start()
    login_check()
    refresh()
    print_bot_name()
    '''Bot code'''
    stores_request()
    if mode == 'all':
        for nairobi in df_creator.index:
            set_storeid_all(nairobi)
            main(nairobi)
    else:
        for nassau in df_creator.index:
            set_storeid_unique(nassau)
            main(nassau)
    print(df_creator)
    time.sleep(5)
        
        
