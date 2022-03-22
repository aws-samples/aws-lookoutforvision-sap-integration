import json
import os 

class Config:
    def __init__(self):
        root_dir = os.path.dirname(os.path.dirname( __file__ ))
        configfile = open(root_dir + '/appConfig.json')
        appConfig = json.load(configfile)
        
        self.account = appConfig['env']['account']
        self.region  = appConfig['env']['region']
        self.stackname = appConfig['stackName']
        self.sapauth = appConfig['sapenv']['SAP_AUTH_SECRET']
        self.saphost  = appConfig['sapenv']['SAP_HOST_NAME']
        self.sapport  = appConfig['sapenv']['SAP_PORT']
        self.sapprotocol  = appConfig['sapenv']['SAP_PROTOCOL']
        self.ddbtable    = appConfig['ddbtablename']
        self.projectname = appConfig['lookoutvision']['projectname']
        self.modelversion = appConfig['lookoutvision']['modelversion']
        self.timeout = appConfig['lambdaTimeout']
        self.bucketname = appConfig['s3']['bucketname']
        self.vpc = appConfig['vpcId']
        self.equipment=appConfig['s3']['equipment']
        self.material=appConfig['s3']['material']
        self.plant=appConfig['s3']['plant']
        self.subnet=appConfig['subnet']


