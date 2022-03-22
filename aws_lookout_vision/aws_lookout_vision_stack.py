from aws_cdk import ( 
    core,
    aws_ec2 as ec2,
    aws_s3 as s3,
)
# import constructs
from LambdaLayer.LambdaLayers import LambdaLayers
from Lambda.Lambda import LambdaConstruct
from Roles.roles import rolesConstruct
from AppConfig.config import Config
from Dynamo.ddb import ddbConstruct
from CustomResource.custom import customResourceConstruct

# Requires docker
# from aws_cdk.aws_lambda_python import(
#     PythonLayerVersion
#     PythonFunction
# )
class AwsLookoutVisionStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
         
        #Configuration parameters for CDK from 'appConfig.json'
        appConfig = Config()
        
        #1.VPC
        vpc = ec2.Vpc.from_lookup(self,"VPC",vpc_id=appConfig.vpc)
         
        privateSubnets = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE)

        lamdbasubnet=[]

        for subnet in privateSubnets.subnets:
            if subnet.subnet_id==appConfig.subnet:
                lamdbasubnet.append(subnet)
 
        #2.Layers
        layers = LambdaLayers(self,'l4vlambdalayers')
        
        #3.Roles
        l4vrole = rolesConstruct(self, 'l4vrole')

        #4.DDB
        ddbConstruct(self, 'qmconfigddb',props={
             'config': appConfig,
             'ddbrole': l4vrole._lambdarole
         } )

        #5.S3 Bucket
        pocbucket = s3.Bucket(self,'l4vbucket',
        bucket_name=appConfig.bucketname,removal_policy=core.RemovalPolicy.DESTROY)

        #6. Create Custom Resources
        _folder = appConfig.equipment+'/'+appConfig.plant+'/'+appConfig.material

        customResourceConstruct(self, 'l4vfolders', props={
            'config': appConfig,
            'role': l4vrole._lambdarole,
            # 'boto3Layer': layers._boto3,
            'folder': _folder,
            'vpc': vpc,
            'subnet':lamdbasubnet,
        })

        #7.Lambda
        LambdaConstruct(self, 'poclambda', props={
            # 'pyodataLayer':layers._pyodataLayer,
            # 'boto3Layer': layers._boto3,
            # 'pillowLayer': layers._pillow,
            # 'requestsLayer': layers._requests,
            'lambdaLayer': layers._lambdalayer,
            'vpc': vpc,
            'subnet': lamdbasubnet,
            'config': appConfig,
            'lambdarole': l4vrole._lambdarole,
            'bucket': pocbucket,
            'prefix': _folder
            })


        #8.Lookout for vision
        