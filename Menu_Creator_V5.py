'''
Created on Wed Jul 29 11:59:30 2020

Last update on Mon Aug 10 15:24:20 2020

@author: giovanni.scognamiglio

Object: menu creator with picture upload
'''

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

bot_name = 'Menu_Creator'

'''Init Functions'''
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
    print("logger started")

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


'''Init Procedural code'''
set_path()
login_check()
logger_start()
refresh()

'''End Init'''

#pd.set_option('display.max_rows', None)
#pd.reset_option('display.max_rows')
'''set store'''
#set store
def set_storeid():
    global storeid, input_path
    nop = 0
    while True:
        storeid = input("\nInsert the Store ID where to create the menu:\n")
        params = {'query' : storeid}
        url = f'https://adminapi.glovoapp.com/admin/stores?limit=500&offset=0'
        r = requests.get(url, headers  = {'authorization' : access_token}, params = params)
        if r.ok is False: 
            print("Store not on Admin. Please insert a valid Store Id")
            nop += 1
            if nop > 1: print("If error repeats, close the program and start again")
            continue
        store_name = r.json()['stores'][0]['name']
        print(f'\n{store_name} - {storeid} found in Admin')
        confirm_menu = input(f"Menu of {store_name} - {storeid} will be updated using the data inside '{store_name}/{store_name}_menu.xlsx'\n\nContinue [yes]/[no]:\n").lower().strip()
        if confirm_menu in ["yes","y","ye","si"]: 
            logger.info(f"Updating menu of store {store_name} - {storeid}")
            break
    input_path = os.path.join(dir,f'Roadhouse/Roadhouse_menu.xlsx')

'''dataframe'''
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

'''Stage1: Create attributes'''            
#delete existing menu
def del_menu():
    url = f'https://adminapi.glovoapp.com/admin/stores/{storeid}/menu'
    d = requests.delete(url, headers = {'authorization' : access_token})
    if d.ok is True: print(f'Menu of store {storeid} deleted')
    else: print(d, d.contents)

''''''        
            
def attrib_check(l,i):  
    #check if external id is duplicate
    sku = int(data_attrib['Attribute ID'][i])
    if data_attrib['Attribute ID'].value_counts()[sku] > 1:
        findex = data_attrib.loc[data_attrib['Attribute ID']==sku].index[0]
        if findex < i:
            #data_attrib.at[i, 'Attrib_Id'] =  data_attrib.at[findex, 'Id']
            l[i] =  l[findex]
            print(f"{i} - external id already exist")
        else: attrib_creation(l,i)
    else: attrib_creation(l,i)
    
def attrib_creation(l,i):
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
    l[i] = p.json()
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
    attrib_details['externalId'] = str(int(data_attrib.at[i,'Attribute ID']))
    #put request
    url_put = f"https://adminapi.glovoapp.com/admin/attributes/{p.json()}"
    put = requests.put(url_put, headers = {'authorization' : access_token}, json = attrib_details)
    if put.ok:
        print(f"Created Attribute {i} with ext.id {str(int(data_attrib.at[i,'Attribute ID']))}")
    else:
        print(f"NOT created attribute {i}: {put}{put.content}")    
    
def stage1():
    print('\nStage 1: Attributes creation')
    global id_list 
    with multiprocessing.Manager() as manager:
        l = manager.list()
        for _ in data_attrib.index:
            l.append("")
        processes = []
        for i in data_attrib.index:
            #launch multiprocessing
            pro = multiprocessing.Process(target = attrib_check, args = (l, i))
            pro.start()
            processes.append(pro)
        for process in processes:
            process.join()
        print(l)
        id_list = [yup for yup in l]
    data_attrib.loc[:, 'Attrib_Id'] = id_list
 
#data_attrib.to_excel('attrib2.xlsx')
'''End of stage1'''


'''Stage2: Creating Attribute groups'''
def stage2():
    print('\nStage 2: Attribute groups creation')
    #get unique group names
    group_num = list(dict.fromkeys(list(data_attrib.loc[:,'Add-On ID'])))
  
    #get attrib details
    url_get = f'https://adminapi.glovoapp.com/admin/attributes?storeId={storeid}'
    r = requests.get(url_get, headers = {'authorization' : access_token})
    json_details = r.json()

    for y in group_num:
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
             "externalId": int(temp_df.at[0,'Add-On ID']),
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
        data_attrib.loc[data_attrib['Add-On ID']==y,'Attrib_group_Id'] = p_group.json()
        if p_group.ok:
            print(f"Added attribute group {int(y)} - {temp_df.at[0,'Add-On Name']}")
        else: 
            print(f"NOT added attribute group {int(y)} - {temp_df.at[0,'Add-On Name']} -> {p_group}-{p_group.content}")
  
'''Stage3: Create products'''
def import_df_prod():
    global data_prod
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

def stage3():
    global r_group, temp_df3_bis, sectionId
    print('\nStage 3: Product creation')
    #get attribute groups info
    url = f'https://adminapi.glovoapp.com/admin/attribute_groups?storeId={storeid}'
    r_group = requests.get(url, headers = {'authorization' : access_token})
    #Start with collections:  get list of unique collection
    collection_list = list(dict.fromkeys(list(data_prod.loc[:,'Collection'].dropna())))
    #iterate over collection list
    for collection in collection_list:
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
        for section in section_list:
            temp_df3_bis = temp_df3.loc[temp_df3['Section']==section].reset_index(drop = True)
            url = 'https://adminapi.glovoapp.com/admin/collectionsections'
            payload = {"name":section,"collectionId": collectionId,"enabled": True}
            post = requests.post(url, headers = {'authorization' : access_token}, json = payload)
            if post.ok: print(f"Section {section} created")
            else: print(f"Section {section} post {post}-{post.content}")
            sectionId = post.json()
            #create products
            processes2 = []
            for q in temp_df3_bis.index:
                pro2 = multiprocessing.Process(target = prod_creation, args = [q])
                pro2.start()
                processes2.append(pro2)
            for process2 in processes2:
                process2.join()
                
                
def prod_creation(q):               
    temp_attributeGroupIds = []
    temp_attributeGroupExternalIds = []
    for asociado in range(1,8):
        if pd.isna(temp_df3_bis.loc[q,f'Question {asociado}']) is False:
            temp_attributeGroupExternalIds.append(str(int(temp_df3_bis.loc[q,f'Question {asociado}'])))
    for yeezy in r_group.json():
        if yeezy['externalId'] in temp_attributeGroupExternalIds:
            temp_attributeGroupIds.append(yeezy['id'])
    url = 'https://adminapi.glovoapp.com/admin/products'
    payload = {"name": str(temp_df3_bis.at[q,'Product Name']),
               "description": str(temp_df3_bis.at[q,'Product Description']),
               "imageServiceId": str(temp_df3_bis.at[q,'Image Ref']),
               "price": temp_df3_bis.at[q,'Product Price'],
               "topSellerCustomization": "AUTO",
               "externalId": int(temp_df3_bis.at[q,'Product ID']),
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

'''main'''    
if __name__ == '__main__':
    t0 = datetime.datetime.now()
    set_storeid()
    import_df_attrib()
    del_menu()
    stage1()
    stage2()      
    import_df_prod()
    stage3()
    t1 = datetime.datetime.now()
    print(f'\nMenu of store id {storeid} is created.\nTime elapsed: {(t1-t0).seconds} seconds')

    
    





