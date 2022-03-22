from aws_cdk import(
    core,
    aws_iam as iam
)

class rolesConstruct(core.Construct):
    def __init__(self, scope: core.Construct, id:str) -> None:
        super().__init__(scope, id)
        
        self._lambdarole = iam.Role(self,'l4vsuperrole',
        assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'))

        self._lambdarole.add_managed_policy(iam.ManagedPolicy.\
            from_managed_policy_arn(self,
            'LambdaInVPC',
            'arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole' ))

        self._lambdarole.add_managed_policy(iam.ManagedPolicy.\
            from_aws_managed_policy_name('AdministratorAccess'))



