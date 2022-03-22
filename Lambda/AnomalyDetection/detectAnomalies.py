import io
import os
import json
import traceback
import urllib.parse
import boto3
import copy
import botocore.response as br
import pyodata
import requests
from PIL import Image
import base64

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr

#clients
s3       = boto3.resource('s3')
smclient = boto3.client('secretsmanager')
lookoutvision_client = boto3.client('lookoutvision')
ddb = boto3.resource('dynamodb')

sapauth={}

#constants
DEFECT_SERVICE='/sap/opu/odata/sap/API_DEFECT_SRV'
DEFECT_SERVICE_PATH='/sap/opu/odata/sap/ZAPI_QUAL_NOTIFICATION_SRV'
ATTACHMENT_SERVICE='/sap/opu/odata/sap/API_CV_ATTACHMENT_SRV'

def handler(event,context):
# Incoming image
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'],\
         encoding='utf-8')

    try:
    # Read the image object    
        s3bucket = s3.Bucket(bucket)
        s3object = s3bucket.Object(key)

        response = s3object.get()
        imgcopy = s3object.get()

        imgbinary = imgcopy['Body'].read()        
        file_stream  = response['Body']

        image = Image.open(file_stream)
        image_type=Image.MIME[image.format]

        image_bytes = io.BytesIO()
        image.save(image_bytes, format=image.format)
        image_bytes = image_bytes.getvalue()

        print('calling lookout for vision to detect Anomolies..')
    
        detectDefect(os.environ.get('PROJECT_NAME'), 
                        image_bytes,
                        image_type,
                        os.environ.get('MODEL_VERSION'),
                        key,
                        imgbinary
                        
                        )
    except Exception as e:
        traceback.print_exc()
        return e


def detectDefect(project_name, image_bytes, image_type, model_version,key,imgbin):
    #analyze the image 
    response = lookoutvision_client.detect_anomalies(
        ProjectName=project_name,
        ContentType=image_type,  
        Body=image_bytes,
        ModelVersion=model_version,
                )
    print(key)
    result = str(response['DetectAnomalyResult']['IsAnomalous'])
    print('is Anomalous:'+result )
    
    if response['DetectAnomalyResult']['IsAnomalous'] == True:
         #createNotification(image_bytes,image_type,key)
         createDefect(image_bytes,image_type,key,imgbin)
    
def createDefect(image, image_type, key,imgbin):
    defectNotification =  getODataClient(DEFECT_SERVICE)
    equipment,plant,material,object = key.split('/')
    ddbConfigTable = ddb.Table(os.environ.get('DDB_CONFIG_TABLE'))

    response = ddbConfigTable.query(
        KeyConditionExpression=Key('notiftype').eq('06') & Key('equipment').eq(equipment),
        FilterExpression=Attr('plant').eq(plant) & Attr('material').eq(material)
    )

    configItem = response['Items']

    payload={
        "DefectCodeGroup": configItem[0]['DefectCodeGroup'],
        "DefectCode": configItem[0]['DefectCode'],
        "DefectCategory":  configItem[0]['notiftype'],
        "DefectCodeCatalog": configItem[0]['DefectCodeCatalog'],
        "DefectText": "Defect from lookout vision",
        "DefectClass":configItem[0]['DefectClass'],
        "Material": configItem[0]['material'],
        "Plant": configItem[0]['plant'],
    }

    create_request = defectNotification.entity_sets.A_Defect.create_entity()
    create_request.set(**payload)
    Defect = create_request.execute()

    print('SAP Defect number:'+Defect.DefectInternalID)

    attachResponse = createAttachment(object,Defect.DefectInternalID,image_type,imgbin)

def createAttachment(object,id,image_type,imgbin):
# Create Attachment
    attachmentClient = _getattachmentClient(ATTACHMENT_SERVICE,
    slug=object,
    defectid=id,
    type=image_type)

    attachmentEntity = attachmentClient['uri']+'/AttachmentContentSet'
    resp = attachmentClient['session'].post(attachmentEntity,data=imgbin)

    return(resp.text)

def _getattachmentClient(service,**kwargs):

    sap_host = os.environ.get('SAP_HOST_NAME')
    sap_port = os.environ.get('SAP_PORT')
    sap_proto = os.environ.get('SAP_PROTOCOL')
    
    serviceuri = sap_proto + '://' + sap_host + ':' + sap_port + service
    
    authresponse = smclient.get_secret_value(
            SecretId=os.environ.get('SAP_AUTH_SECRET')
        )

    sapauth = json.loads(authresponse['SecretString'])
    session = requests.Session()
    session.auth = (sapauth['user'],sapauth['password'])
    response = session.head(serviceuri, headers={'x-csrf-token': 'fetch'})
    token = response.headers.get('x-csrf-token', '')
    session.headers.update({'x-csrf-token': token})

   
    session.headers.update({'LinkedSAPObjectKey': kwargs.get('defectid')})
    session.headers.update({'BusinessObjectTypeName': 'QFGEN'})
    session.headers.update({'Content-Type': kwargs.get('type')})
    session.headers.update({'Slug': kwargs.get('slug')})

    return{ 'session': session, 'uri': serviceuri }


def createNotification(image, image_type,key):
    
    defectNotification =  getODataClient(DEFECT_SERVICE_PATH)
    
    equipment,plant,material,object = key.split('/')

    ddbConfigTable = ddb.Table(os.environ.get('DDB_CONFIG_TABLE'))

# Create notification type Q3( Iternal problem notification )
    # response = ddbConfigTable.getItem(Key={
    #                             'type': 'Q3',
    #                             'equipment': equipment,
    #                        })

    response = ddbConfigTable.query(
        KeyConditionExpression=Key('notiftype').eq('Q3') & Key('equipment').eq(equipment),
        FilterExpression=Attr('plant').eq(plant) & Attr('material').eq(material)
    )

    configItem = response['Items']

        #Secret Manager
    authresponse = smclient.get_secret_value(
        SecretId=os.environ.get('SAP_AUTH_SECRET')
    )

    sapauth = json.loads(authresponse['SecretString'])
    
# Create a notiification in SAP
    payload={
            "NotifType": configItem[0]['notiftype'],
            "ShortText": "Problem Notification - Cricuit Board",
            "CodeGroup": configItem[0]['codeGroup'],
            "Code": configItem[0]['code'],
            "MaterialPlant": plant,
            "Material": material,
            "AdditionalDeviceData": equipment,
            "Items": [
                {
                "ItemKey": "0001",
                "ItemSortNo": "0001",
                "Descript": "Defective Board",
                "DCodegrp": configItem[0]['DCodegrp'],
                "DCode": configItem[0]['DCode'],
                "DlCodegrp": configItem[0]['DlCodegrp'],
                "DlCode": configItem[0]['DlCode'],
                "ErrClass": configItem[0]['ErrClass'],
                "QuantIntItem": "1.00"
                }
            ],
            "Partners": [
                {
                "PartnRole": "AO",
                "Partner": sapauth['user'].upper()
                },
                {
                "PartnRole": "KU",
                "Partner": sapauth['user'].upper()
                }
            ],
            "Notes": [
                {
                "Objkey": "1",
                "TextLine": "Defect has been by lookout for vision during inspection"
                }
            ]
            }

    create_request = defectNotification.entity_sets.DefectNotification.create_entity()
    create_request.set(**payload)
    notification = create_request.execute()
    print('SAP Notification number:'+notification.Notification)




def getODataClient(service,**kwargs):
    try:
        sap_host = os.environ.get('SAP_HOST_NAME')
        sap_port = os.environ.get('SAP_PORT')
        sap_proto = os.environ.get('SAP_PROTOCOL')
        serviceuri = sap_proto + '://' + sap_host + ':' + sap_port + service
       
        print('service call:'+serviceuri)
       #Secret Manager
        authresponse = smclient.get_secret_value(
            SecretId=os.environ.get('SAP_AUTH_SECRET')
        )

        sapauth = json.loads(authresponse['SecretString'])
        
       #Set session headers - Auth,token etc
        session = requests.Session()
        session.auth = (sapauth['user'],sapauth['password'])
        response = session.head(serviceuri, headers={'x-csrf-token': 'fetch'})
        token = response.headers.get('x-csrf-token', '')
        session.headers.update({'x-csrf-token': token})

        if 'defectid' in kwargs:
            session.headers.update({'LinkedSAPObjectKey': kwargs.get('defectid')})
            session.headers.update({'BusinessObjectTypeName': 'QFGEN'})
            session.headers.update({'Content-Type': kwargs.get('type')})
            session.headers.update({'Slug': kwargs.get('slug')})
        
       
        oDataClient = pyodata.Client(serviceuri, session)
        
        return oDataClient

    except Exception as e:
          traceback.print_exc()
          return e


   




