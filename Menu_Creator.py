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
from get_new_token import *
import multiprocessing
import numpy as np
from tqdm import tqdm
from requests_toolbelt.multipart.encoder import MultipartEncoder

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
'''Stage 0: Set target Admin store and input data'''
#set store where to create menu on Admin
def set_storeid():
    global storeid, input_path, store_name, store_cityCode, excel_name
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
        excel_name = f'{store_name}_{store_cityCode}.xlsx'
        time.sleep(0.3)
        print(f'\n{store_name} - {store_cityCode} ({storeid}) found in Admin')
        try:
            find_excel_file_path(excel_name)
        except NameError:
            time.sleep(0.5)
            print(f'\nDid not find {excel_name} in {dir}')
            plan_b()
            break
        else:
            time.sleep(0.5)
            print(f'\nFound {excel_name} in {dir}')
            aorb = input(f"\nUpdate menu of {store_name} - {store_cityCode} ({storeid}) with:\n[A] - Data inside '{excel_name}'\n[B] - Other excel file\nPress 'A' or 'B' then press ENTER:\n").lower().strip()
            if aorb in ["a","b"]: 
                if aorb == "a": 
                    input_path = find_excel_file_path(excel_name)
                    logger.info(f"Updating menu of store {store_name} - {store_cityCode} ({storeid}) with {excel_name}")
                    break
                if aorb == "b":
                    plan_b()
                    break

#custom function for set_storeid(): 
#user indicates the excel for data input
def plan_b():
    global input_path, excel_name
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
                logger.info(f"Updating menu of store {store_name} - {store_cityCode} ({storeid}) with {excel_name}")
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

#Import 'add-ons' sheet dataframe
def import_df_attrib(): 
    #import
    global data_attrib, group_list
    data_attrib = pd.read_excel(input_path, sheet_name = 'Add-Ons')
    data_attrib.dropna(how='all', inplace = True)
    #getting list of attribute groups
    group_list = data_attrib.loc[:,'Add-On Name'].dropna().tolist()
    #strip dataframe
    #data_attrib = data_attrib.apply(lambda x: x.strip() if isinstance(x, str) else x)   
    #cleaning price:
    for _ in data_attrib.index:
        data_attrib.at[_,'Price'] = str(data_attrib.at[_,'Price']).replace(',','.')
        try:
            data_attrib.at[_,'Price'] = float(data_attrib.at[_,'Price'])
        except ValueError:
            data_attrib.at[_,'Price'] = 0              
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
    global id_list, data_attrib
    #init multiprocess
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
        #print(phantom_list)
        id_list = list(phantom_list)
    #push fresh id_list to dataframe
    data_attrib.loc[:, 'Attrib_Id'] = id_list
        #fill empty Attrib_Id values
    for ind_wouf in data_attrib.loc[:, 'Attrib_Id'].index:
        wouf =  data_attrib.at[ind_wouf, 'Attrib_Id']
        skusku = data_attrib.at[ind_wouf, 'Attribute ID']
        if wouf == '' or pd.isna(wouf):
            findex2 = data_attrib.loc[data_attrib['Attribute ID']== skusku].index[0]
            data_attrib.at[ind_wouf, 'Attrib_Id'] =  data_attrib.at[findex2, 'Attrib_Id']
    print(data_attrib.loc[:, 'Attrib_Id'])
    
#custom function for stage1(): 
#check if duplicate attributes have been already created
def attrib_check(phantom_list,i):  
    #check if external id is duplicate
    sku = data_attrib['Attribute ID'][i]
    repetition_check = int(np.array(data_attrib.loc[data_attrib['Attribute ID'] == sku,'Attribute ID'].value_counts()))
    if repetition_check > 1:
        findex = data_attrib.loc[data_attrib['Attribute ID']==sku].index[0]
        if findex < i:
            try:
                #data_attrib.at[i, 'Attrib_Id'] =  data_attrib.at[findex, 'Id']
                phantom_list[i] =  phantom_list[findex]
            except Exception:
                phantom_list[i] = np.nan
            finally:
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
    #strip sections
    data_prod['Section'] = data_prod['Section'].str.strip()
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
            data_prod.loc[:,f'Add-On {_}']
            asociados_list.append(_)
        except Exception:
            break
    #replace all nan with ''
    data_prod = data_prod.fillna('')
        
########special functions for checking new pictures to upload with product creation########
#check for new image to upload
#walk in the image directory, get all image ref and cross check it with image ref column in excel.
#if new image, upload it on and get metadata
def check_for_new_images_in_df():
    global listOfImages
    print('\nChecking for new images to upload..')
    get_image_names()
    #uploading all new images with multiprocessing
    with multiprocessing.Manager() as manager:
        l_of_im = manager.list()
        processes = []
        for im in data_prod.index:
            l_of_im.append('')
        for im in data_prod.index:
            pro = multiprocessing.Process(target = upload_image, args = [im, l_of_im])
            pro.start()
            processes.append(pro)
        for process in processes:
            process.join()
        listOfImages = list(l_of_im)
    #saving new image ID to dataframe
    for im in data_prod.index:
        im_ref = data_prod.at[im,'Image Ref']
        if pd.isna(im_ref) is False:
            if pd.isna(data_prod.at[im,'Image ID']) or data_prod.at[im,'Image ID'] == '':
                if check_image_exists(im_ref):
                    data_prod.at[im,'Image ID'] = listOfImages[im]
    if len(listOfImages) == listOfImages.count(''):
        print('No new images to upload')
    else:
        print(f"Uploaded {int(len(listOfImages))-int(listOfImages.count(''))} new images")
        print(f'Saving new Image IDs to {input_path}')
        save_to_excel()
        
def get_image_names():
    global image_names, complete_names, im_dic
    #print('Scanning {os.path.relpath(os.path.join(os.path.dirname(input_path),"Images"))} folder')
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(input_path),"Images")):
        image_names = []
        complete_names = []
        for file in files:
            if file[-3:] == 'jpg' or file[-3:] == 'png':
                complete_names.append(file)
                image_names.append(file[:-4])
        im_dic = dict(zip(image_names, complete_names))

def check_image_exists(im_ref):
        if im_ref in image_names:
            return True
        else:
            return False                    

def upload_image(im, l_of_im):
    im_ref = data_prod.at[im,'Image Ref']
    if pd.isna(im_ref) is False:
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
                    #r.json()
                    #data_prod.at[im,'Image ID'] = r.json()['public_id']
                    l_of_im[im] = r.json()['public_id']
                    print(f'Image {im_ref} uploaded')

#saving df back to excel with updated image ID:
#only necessary if new image have been uploaded
def save_to_excel():
    #import existing df
    data_prod_lite = pd.read_excel(input_path, sheet_name = 'Products')
    data_prod_lite.dropna(how='all', inplace = True)
    data_attrib_lite = pd.read_excel(input_path, sheet_name = 'Add-Ons')
    data_attrib_lite.dropna(how='all', inplace = True)
    #modify the 'Image ID' column
    data_prod_lite.loc[:,'Image ID'] = data_prod.loc[:,'Image ID']
    #save it back to excel
    with pd.ExcelWriter(input_path) as writer:
        data_prod_lite.to_excel(writer, sheet_name = 'Products', index = False)
        writer.sheets['Products'].set_column('B:Z',20)
        writer.sheets['Products'].set_column('D:D',25)
        writer.sheets['Products'].set_column('E:E',70)
        writer.sheets['Products'].set_column('H:Z',20)
        data_attrib_lite.to_excel(writer, sheet_name = 'Add-Ons', index = False)
        writer.sheets['Add-Ons'].set_column('B:Z',15)
        writer.sheets['Add-Ons'].set_column('A:A',25)
        writer.sheets['Add-Ons'].set_column('F:F',50)    

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
        print('\nOrdering sections positions')
        for secId in tqdm(zombie_sectionId_list):
            position = zombie_sectionId_list.index(secId)
            url = f'https://adminapi.glovoapp.com/admin/collectionsections/{secId}/changeCollection'
            payload = {"position" : position, "collectionId" : collectionId}
            put_pos = requests.put(url, headers = {'authorization':access_token}, json = payload)
            if put_pos.ok is False: print(f'Section {secId} PROBLEM when moved to P {position}')
        print('Ordering sections positions completed')
        
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

def cleaned(value):
    if value == None or value == np.nan or value == '' or value == 'nan':
        return None
    else:
        return str(value)    

#Custom function for stage3():
#creates products
def prod_creation(q):               
    temp_attributeGroupNames = []
    #temp_attributeGroupExternalIds = []
    for asociado in asociados_list:
        if pd.isna(temp_df3_bis.loc[q,f'Add-On {asociado}']) is False and temp_df3_bis.loc[q,f'Add-On {asociado}'] != '':
            #temp_attributeGroupExternalIds.append(str(temp_df3_bis.loc[q,f'Add-On {asociado}']))
            temp_attributeGroupNames.append(str(temp_df3_bis.loc[q,f'Add-On {asociado}']))
    #making attrib group list to add to products
    if len(temp_attributeGroupNames) == 0: 
        temp_attributeGroupIds = []
    else:
        temp_attributeGroupIds = ['' for _ in range(len(temp_attributeGroupNames))]    
        for attrGroup in attrib_groups.json():
            #if yeezy['externalId'] in temp_attributeGroupExternalIds:
            if attrGroup['name'] in temp_attributeGroupNames:
                n = temp_attributeGroupNames.index(attrGroup['name'])
                #temp_attributeGroupIds.append(attrGroup['id'])
                temp_attributeGroupIds[n] = attrGroup['id']
            
    url = 'https://adminapi.glovoapp.com/admin/products'
    payload = {"name": cleaned(temp_df3_bis.at[q,'Product Name']),
               "description": cleaned(temp_df3_bis.at[q,'Product Description']),
               "imageServiceId": cleaned(temp_df3_bis.at[q,'Image ID']),
               "price": temp_df3_bis.at[q,'Product Price'],
               "topSellerCustomization": "AUTO",
               "externalId": cleaned(temp_df3_bis.at[q,'Product ID']),
               "enabled": bool(temp_df3_bis.at[q,'Active'].astype('bool')),
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
    
'''Bot framework'''
def start():
    set_storeid()
    t0 = datetime.datetime.now()
    del_menu()
    import_df_attrib()
    stage1()
    stage2()      
    import_df_prod()
    check_for_new_images_in_df()
    stage3()
    t1 = datetime.datetime.now()
    print(f"\nMenu of store id {store_name} - {store_cityCode} ({storeid}) successfully created from '{excel_name}' in {(t1-t0).seconds} seconds")

'''''''''''''''''''''''''''''End Bot'''''''''''''''''''''''''''''
'''launch'''    
if __name__ == '__main__':
    '''Initiation code'''
    set_path()
    login_check()
    logger_start()
    refresh()
    '''Bot code'''
    start()
