#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 29 11:59:30 2020
Last update on Wed Aug 19 12:06:58 2020

@author: giovanni.scognamiglio

Object: menu creator with picture upload
"""

bot_name = 'Menu_Creator'

#modules
import logging
import requests
import time
import pandas as pd
import datetime
import sys
import os
import os.path
from get_new_token import  *
import multiprocessing
import numpy as np

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

'''''''''''''''''''''''''''Beginning bot'''''''''''''''''''''''''''
                
'''Stage 0: Set target Admin store and input data'''
#set store where to create menu on Admin
def set_storeid():
    global storeid, input_path, store_name, store_cityCode, excelName
    nop = 0
    while True:
        storeid = input("\nInsert the Store ID where to create the menu:\n")
        params = {'query' : storeid}
        url = f'https://adminapi.glovoapp.com/admin/stores?limit=500&offset=0'
        r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
        if r.ok is False: 
            print("\nStore not on Admin. Please insert a valid Store Id")
            nop += 1
            if nop > 1: print("If error repeats, close the program and start again")
            continue
        store_name = r.json()['stores'][0]['name']
        store_cityCode = r.json()['stores'][0]['cityCode']
        excelName = f'{store_name}_{store_cityCode}.xlsx'
        time.sleep(0.3)
        print(f'\n{store_name} - {store_cityCode} ({storeid}) found in Admin')
        try:
            find_excel_file_path(excelName)
        except NameError:
            time.sleep(0.5)
            print(f'\nDid not find {excelName} in {dir}')
            plan_b()
            break
        else:
            time.sleep(0.5)
            print(f'\nFound {excelName} in {dir}')
            aorb = input(f"\nUpdate menu of {store_name} - {store_cityCode} ({storeid}) with:\n[A] - Data inside '{excelName}'\n[B] - Other excel file\nPress 'A' or 'B' then press ENTER:\n").lower().strip()
            if aorb in ["a","b"]: 
                if aorb == "a": 
                    input_path = find_excel_file_path(excelName)
                    logger.info(f"Updating menu of store {store_name} - {store_cityCode} ({storeid}) with {excelName}")
                    break
                if aorb == "b":
                    plan_b()
                    break

#custom function for set_storeid(): 
#user indicates the excel for data input
def plan_b():
    global input_path
    while True:
        time.sleep(0.5)
        excel_name = input("\nInsert the name of the Excel file to input(eg: 'Partner_MIL.xlsx'):\n")
        if not 'xlsx' in excel_name: excel_name = f'{excel_name}.xlsx'
        try:
            excel_path = find_excel_file_path(excel_name)
        except NameError:
            time.sleep(0.5)
            print(f'\nCould not find {excel_name} in {dir}\nPlease try again\n')
            continue
        else:
            time.sleep(0.5)
            confirm_path = input(f"\nMenu of {store_name} - {store_cityCode} ({storeid}) will be updated with data in '{os.path.relpath(excel_path)}'\nConfirm [yes]/[no]:\n")
            if confirm_path in ["yes","y","ye","si"]:
                logger.info(f"Updating menu of store {store_name} - {store_cityCode} ({storeid}) with {excelName}")
                input_path = excel_path
                break
            else: 
                print('\nKey not recognized, please start again\n')
                continue

#custom function for set_storeid(): 
#find excel file in current working directory with os.walk
def find_excel_file_path(excel_name):
    for root, dirs, files in os.walk(dir):
        if excel_name in files:
            for file in files:
                if file == excel_name:
                    print(f'\n{excel_name} found in current working directory')
                    return os.path.join(root,file)
    else:
        #print('File not found in current working directory')
        raise NameError

'''Stage1: Create attributes'''            
#delete existing menu
def del_menu():
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/menu'
    d = requests.delete(url, headers = {'authorization' : access_token})
    if d.ok is True: print(f'Menu of store {storeid} deleted')
    else: print(d, d.contents)

#Import add-ons sheet dataframe
def import_df_attrib(): 
    #import
    global data_attrib, group_list
    data_attrib = pd.read_excel(input_path, sheet_name = 'Add-Ons')
    data_attrib.dropna(how='all', inplace = True)
    #getting list of attribute groups
    group_list = data_attrib.loc[:,'Add-On Name'].dropna().tolist()
    #cleaning precios:
    for _ in data_attrib['Price'].index:
        if isinstance(data_attrib.at[_,'Price'],int) is False: data_attrib.at[_,'Price'] = 0    
    #reset index & do forward fill
    data_attrib.reset_index(drop = True, inplace = True)
    data_attrib.fillna(method = 'ffill', inplace = True)
    #create new column  'Attrib_Id'
    data_attrib.loc[:, 'Attrib_Id'] = ['' for _ in range(len(data_attrib))]
    #create new column  'Attrib_group_Id'
    data_attrib.loc[:, 'Attrib_group_Id'] = ['' for _ in range(len(data_attrib))]
    print('\nAttributes imported')

#stage1 function: 
#launch attribute creation with multiprocessing
def stage1():
    print('\nStage 1: Attributes creation')
    global id_list
    with multiprocessing.Manager() as manager:
        phantom_list = manager.list()
        for _ in data_attrib.index:
            phantom_list.append("")
        processes = []
        for i in data_attrib.index:
            #launch multiprocessing
            pro = multiprocessing.Process(target = attrib_check, args = (phantom_list, i))
            pro.start()
            processes.append(pro)
        for process in processes:
            process.join()
        print(phantom_list)
        id_list = [yup for yup in phantom_list]
    data_attrib.loc[:, 'Attrib_Id'] = id_list

#custom function for stage1(): 
#check if duplicate attributes have been already created
def attrib_check(phantom_list,i):  
    #check if external id is duplicate
    sku = data_attrib['Attribute ID'][i]
    repetition_check = int(np.array(data_attrib.loc[data_attrib['Attribute ID'] == sku,'Attribute ID'].value_counts()))
    if repetition_check > 1:
        findex = data_attrib.loc[data_attrib['Attribute ID']==sku].index[0]
        if findex < i:
            #data_attrib.at[i, 'Attrib_Id'] =  data_attrib.at[findex, 'Id']
            phantom_list[i] =  phantom_list[findex]
            print(f"{i} - external id already exist")
        else: attrib_creation(phantom_list,i)
    else: attrib_creation(phantom_list,i)
    
#custom function for stage1(): 
#attributes creation function
def attrib_creation(phantom_list,i):
    #create attribute
    url_post = 'https://adminapi.glovoapp.com/admin/attributes'
    payload = {
            'storeId' : storeid,
            'name' : data_attrib.at[i,'Attribute'],
            'priceImpact' : str(data_attrib.at[i,'Price']),
            'enabled' : bool(data_attrib.at[i,'Active'].astype('bool')),
            'selected' : False}
    p = requests.post(url_post, headers = {'authorization' : access_token}, json = payload)
    if p.ok is False:
        print(f"{i}: post{p} - {data_attrib.at[i,'Attribute']} NOT created")
        print(p.content)
    #data_attrib.at[i, 'Attrib_Id'] = p.json()
    phantom_list[i] = p.json()
    #get attrib details
    url_get = f'https://adminapi.glovoapp.com/admin/attributes?storeId={storeid}'
    r = requests.get(url_get, headers = {'authorization' : access_token})
    for j in r.json():
        if j['id'] != p.json(): 
            continue
        attrib_details = j
        if j['id'] != p.json():
            print(f"{i}: PROBLEM -> id check - {j['id']} = {p.json()}")
            exit
    #change external id
    attrib_details['externalId'] = str(data_attrib.at[i,'Attribute ID'])
    #put request
    url_put = f"https://adminapi.glovoapp.com/admin/attributes/{p.json()}"
    put = requests.put(url_put, headers = {'authorization' : access_token}, json = attrib_details)
    if put.ok:
        print(f"Created Attribute {i} with ext.id {str(data_attrib.at[i,'Attribute ID'])}")
    else:
        print(f"NOT created attribute {i}: {put}{put.content}")    

'''Stage2: Creating Attribute groups'''
#stage 2 funtion:
#launch attribute groups creation with multiprocessing
def stage2():
    print('\nStage 2: Attribute groups creation')
    #get unique group names
    group_num = list(dict.fromkeys(list(data_attrib.loc[:,'Add-On ID'])))
    #get attrib details
    url_get = f'https://adminapi.glovoapp.com/admin/attributes?storeId={storeid}'
    r = requests.get(url_get, headers = {'authorization' : access_token})
    json_details = r.json()
    with multiprocessing.Manager() as manager:
        phantomy = manager.list()
        for _ in group_num:
            phantomy.append("")
        processes = []
        for y in group_num:
            n = group_num.index(y)
            #launch multiprocessing
            proZ = multiprocessing.Process(target = attribGroup_creation, args = (phantomy, y, json_details, n))
            proZ.start()
            processes.append(proZ)
        for process in processes:
            process.join()
        print(phantomy)
        groupId_list = [yap for yap in phantomy]
    for numnum in range(len(group_num)):
        data_attrib.loc[data_attrib['Add-On ID']==group_num[numnum], 'Attrib_Id'] = groupId_list[numnum]

#custom function for stage2():
#attribute group creation function
def attribGroup_creation(phantomy, y, json_details, n):
        #set temporary dataframe filtering groups name
        temp_df = data_attrib.loc[data_attrib['Add-On ID']==y].reset_index(drop = True)
        temp_list = []
        for v in json_details:
            if v['id'] in temp_df.loc[:,'Attrib_Id'].tolist(): 
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
             "attributes": temp_df.loc[:,'Attrib_Id'].tolist()}
        #post request for attrib group creation
        p_group = requests.post(url, headers = {'authorization' : access_token}, json = payload)
        phantomy[n] = p_group.json()
        #data_attrib.loc[data_attrib['Add-On ID']==y,'Attrib_group_Id'] = p_group.json()
        if p_group.ok:
            print(f"Added attribute group {y} - {temp_df.at[0,'Add-On Name']}")
        else: 
            print(f"NOT added attribute group {y} - {temp_df.at[0,'Add-On Name']} -> {p_group}-{p_group.content}")

'''Stage3: Products creation'''
#Import data from Products Sheet dataframe
def import_df_prod():
    global data_prod, asociados_list
    data_prod =  pd.read_excel(input_path, sheet_name = 'Products')
    data_prod.dropna(how='all', inplace = True)
    #cleaning precios:
    for _ in data_prod['Product Price'].index:
        if isinstance(data_prod.at[_,'Product Price'],float) is False: data_prod.at[_,'Product Price'] = 0    
    #reset index & forward fill
    data_prod.reset_index(drop = True, inplace = True)
    data_prod.loc[:,'Collection'].fillna(method = 'ffill', inplace = True)
    #create column collectionId
    data_prod.loc[:,'CollectionId'] = ['' for _ in range(len(data_prod))]
    #attributes groups column cleaner
    asociados_list = []
    for _ in range(1,16):
        try: 
            data_prod.loc[:,f'Question {_}']
            asociados_list.append(_)
        except Exception:
            break

#Stage 3 function:
#Creates products with multiprocessing
def stage3():
    global attrib_groups
    print('\nStage 3: Product creation')
    #get attribute groups info
    url = f'https://adminapi.glovoapp.com/admin/attribute_groups?storeId={storeid}'
    attrib_groups = requests.get(url, headers = {'authorization' : access_token})
    #Start with collections: get list of unique collection
    collection_list = list(dict.fromkeys(list(data_prod.loc[:,'Collection'].dropna())))
    #iterate over collection list
    for collection in collection_list:
        #position = collection_list.index(collection)
        temp_df3 = data_prod.loc[data_prod['Collection']==collection].reset_index(drop = True)
        #create collection
        url = 'https://adminapi.glovoapp.com/admin/collections'
        payload = {"name": collection, "storeId": storeid}
        post = requests.post(url, headers = {'authorization' : access_token}, json = payload)
        data_prod.loc[data_prod['Collection']==collection,'CollectionId'] = post.json()
        collectionId = post.json()
        if post.ok: print(f"Created collection {collection}")
        else: print(f"NOT created collection {collection} -> {post}-{post.content}")
        #create sections
        section_list = list(dict.fromkeys(list(temp_df3.loc[:,'Section'].dropna())))
        processes2 = []
        with multiprocessing.Manager() as manager:
            temp_sectionId_list = manager.list()
            for _ in range(len(section_list)):
                temp_sectionId_list.append('')
            for section in section_list:
                n = section_list.index(section)
                pro2 = multiprocessing.Process(target = section_creation, args = [n, temp_sectionId_list, temp_df3, collectionId, section])
                pro2.start()
                processes2.append(pro2)
            for process2 in processes2:
               process2.join()
            print(temp_sectionId_list)
            zombie_sectionId_list = list(temp_sectionId_list)
        #arrange section positions
        for secId in zombie_sectionId_list:
            position = zombie_sectionId_list.index(secId)
            url = f'https://adminapi.glovoapp.com/admin/collectionsections/{secId}/changeCollection'
            payload = {"position" : position, "collectionId" : collectionId}
            put_pos = requests.put(url, headers = {'authorization':access_token}, json = payload)
            if put_pos.ok is False: print(f'Section {secId} PROBLEM when moved to P {position}')
        print('Sections re-ordered')
        
#Custom function for stage3():
#creates sections
def section_creation(n, temp_sectionId_list, temp_df3, collectionId, section):      
    global temp_df3_bis, sectionId
    temp_df3_bis = temp_df3.loc[temp_df3['Section']==section].reset_index(drop = True)
    url = 'https://adminapi.glovoapp.com/admin/collectionsections'
    payload = {"name":section,"collectionId": collectionId,"enabled": True}
    post = requests.post(url, headers = {'authorization' : access_token}, json = payload)
    if post.ok: print(f"Section {section} created")
    else: print(f"Section {section} post {post}-{post.content}")
    sectionId = post.json()
    temp_sectionId_list[n] = post.json()
    #create products
    for q in temp_df3_bis.index[::-1]:
        prod_creation(q)

#Custom function for stage3():
#creates products
def prod_creation(q):               
    temp_attributeGroupIds = []
    #temp_attributeGroupExternalIds = []
    temp_attributeGroupNames = []
    for asociado in asociados_list:
        if pd.isna(temp_df3_bis.loc[q,f'Question {asociado}']) is False:
            #temp_attributeGroupExternalIds.append(str(temp_df3_bis.loc[q,f'Question {asociado}']))
            temp_attributeGroupNames.append(str(temp_df3_bis.loc[q,f'Question {asociado}']))
    for yeezy in attrib_groups.json():
        #if yeezy['externalId'] in temp_attributeGroupExternalIds:
        if yeezy['name'] in temp_attributeGroupNames:
            temp_attributeGroupIds.append(yeezy['id'])
    url = 'https://adminapi.glovoapp.com/admin/products'
    payload = {"name": str(temp_df3_bis.at[q,'Product Name']),
               "description": str(temp_df3_bis.at[q,'Product Description']),
               "imageServiceId": str(temp_df3_bis.at[q,'Image Ref']),
               "price": temp_df3_bis.at[q,'Product Price'],
               "topSellerCustomization": "AUTO",
               "externalId": str(temp_df3_bis.at[q,'Product ID']),
               "enabled": bool(temp_df3_bis.at[q,'Active (TRUE/FALSE)'].astype('bool')),
               "sectionId": sectionId,
               "attributeGroupIds": temp_attributeGroupIds,
               "prices": [],
               "productTags": []}
    post = requests.post(url, headers = {'authorization' : access_token}, json = payload)
    if post.ok:
        print(f"Inserted product {temp_df3_bis.at[q,'Product Name']}")
    else:
        print(f"NOT inserted product {temp_df3_bis.at[q,'Product Name']}: {post}-{post.content}")
        sys.exit(0)

'''main_bot'''    
if __name__ == '__main__':
    t0 = datetime.datetime.now()
    set_storeid()
    del_menu()
    import_df_attrib()
    stage1()
    stage2()      
    import_df_prod()
    stage3()
    t1 = datetime.datetime.now()
    print(f"\nMenu of store id {store_name} - {store_cityCode} ({storeid}) successfully created from '{excelName}' in {(t1-t0).seconds} seconds")

    