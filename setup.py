import boto3
import json
import time, random 
import uuid, string
import logging
from botocore.exceptions import ClientError, WaiterError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_policy(iam_client, account_id, policy_name, policy_document):
    """Create an IAM policy with error handling"""
    try:
        # Check if policy already exists to avoid duplicates
        try:
            existing_policy = iam_client.get_policy(PolicyArn=f"arn:aws:iam::{account_id}:policy/{policy_name}")
            logger.info(f"Policy {policy_name} already exists, using existing policy")
            return {"Policy": {"Arn": existing_policy['Policy']['Arn']}}
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                # Policy doesn't exist, create it
                logger.info(f"Creating policy: {policy_name}")
                policy = iam_client.create_policy(
                    PolicyName=policy_name,
                    PolicyDocument=policy_document
                )
                logger.info(f"Successfully created policy: {policy_name}")
                return policy
            else:
                raise
    except ClientError as e:
        logger.error(f"Failed to create policy {policy_name}: {e}")
        raise

def create_role(iam_client, role_name, assume_role_policy_document):
    """Create an IAM role with error handling"""
    try:
        # Check if role already exists
        try:
            existing_role = iam_client.get_role(RoleName=role_name)
            logger.info(f"Role {role_name} already exists, using existing role")
            return {"Role": existing_role['Role']}
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                # Role doesn't exist, create it
                logger.info(f"Creating role: {role_name}")
                role = iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=assume_role_policy_document
                )
                logger.info(f"Successfully created role: {role_name}")
                # Wait for IAM role to propagate
                logger.info(f"Waiting for role {role_name} to propagate...")
                time.sleep(10)
                return role
            else:
                raise
    except ClientError as e:
        logger.error(f"Failed to create role {role_name}: {e}")
        raise

def attach_policy_to_role(iam_client, role_name, policy_arn):
    """Attach a policy to a role with error handling"""
    try:
        # Check if policy is already attached
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in attached_policies['AttachedPolicies']:
            if policy['PolicyArn'] == policy_arn:
                logger.info(f"Policy {policy_arn} is already attached to role {role_name}")
                return
        
        # Attach the policy
        logger.info(f"Attaching policy {policy_arn} to role {role_name}")
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
        logger.info(f"Successfully attached policy to role {role_name}")
    except ClientError as e:
        logger.error(f"Failed to attach policy to role {role_name}: {e}")
        raise

def create_agent(bedrock_agent_client, agent_name, role_arn, description, instruction, foundation_model):
    """Create a Bedrock agent with error handling"""
    try:
        # Check if agent already exists
        try:
            agents = bedrock_agent_client.list_agents()
            for agent in agents.get('agentSummaries', []):
                if agent['agentName'] == agent_name:
                    logger.info(f"Agent {agent_name} already exists, using existing agent")
                    return {"agent": {"agentId": agent['agentId']}}
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise
        
        # Create new agent
        logger.info(f"Creating agent: {agent_name}")
        response = bedrock_agent_client.create_agent(
            agentName=agent_name,
            agentResourceRoleArn=role_arn,
            description=description,
            idleSessionTTLInSeconds=1800,
            foundationModel=foundation_model,
            instruction=instruction,
            memoryConfiguration={
                "enabledMemoryTypes": ["SESSION_SUMMARY"],
                "storageDays": 30
            }
        )
        logger.info(f"Successfully created agent: {agent_name}")
        
        # Wait for agent creation to complete
        logger.info(f"Waiting for agent {agent_name} to be ready...")
        time.sleep(30)
        return response
    except ClientError as e:
        logger.error(f"Failed to create agent {agent_name}: {e}")
        raise

def prepare_agent(bedrock_agent_client, agent_id):
    """Prepare a Bedrock agent with error handling"""
    try:
        logger.info(f"Preparing agent: {agent_id}")
        response = bedrock_agent_client.prepare_agent(agentId=agent_id)
        
        # Wait for agent preparation to complete
        logger.info(f"Waiting for agent {agent_id} to finish preparation...")
        time.sleep(30)
        
        # Check agent status
        agent_status = bedrock_agent_client.get_agent(agentId=agent_id)
        status = agent_status.get('agent', {}).get('status')
        
        if status != 'PREPARED':
            logger.warning(f"Agent preparation status: {status}. This may not be 'PREPARED' yet.")
        else:
            logger.info(f"Agent successfully prepared with status: {status}")
        
    except ClientError as e:
        logger.error(f"Failed to prepare agent {agent_id}: {e}")
        raise

def create_agent_alias(bedrock_agent_client, agent_id, alias_name):
    """Create an agent alias with error handling"""
    try:
        # Check if alias already exists
        try:
            aliases = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
            for alias in aliases.get('agentAliasSummaries', []):
                if alias['agentAliasName'] == alias_name:
                    logger.info(f"Alias {alias_name} already exists, using existing alias")
                    return {"agentAlias": {"agentAliasId": alias['agentAliasId']}}
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise
        
        # Create new alias
        logger.info(f"Creating agent alias: {alias_name}")
        response = bedrock_agent_client.create_agent_alias(
            agentAliasName=alias_name,
            agentId=agent_id
        )
        logger.info(f"Successfully created agent alias: {alias_name}")
        
        # Wait for alias creation to complete
        logger.info(f"Waiting for agent alias {alias_name} to be ready...")
        time.sleep(10)
        return response
    except ClientError as e:
        logger.error(f"Failed to create agent alias {alias_name}: {e}")
        raise

def main():
    try:
        # Initialize AWS clients
        iam = boto3.client('iam')
        sts_client = boto3.client('sts')
        bedrock_agent_client = boto3.client('bedrock-agent')

        session = boto3.session.Session()
        region_name = session.region_name
        try:
            account_id = sts_client.get_caller_identity()["Account"]
        except ClientError as e:
            logger.error(f"Failed to get AWS account ID: {e}")
            logger.error("Please check your AWS credentials and permissions")
            return

        # Configuration
        agentName = 'jarvis-agent'
        description = "Agent that helps users manage schedules and tasks"
        instruction = """You are a helpful chatbot, JARVIS, answering questions users might have about their schedule and tasks. 

        Your primary goals include: 

        1. Collect relevant information about user schedule and tasks such as when it is (due), how long it'll take, location (if applicable), additional context, etc. 
        2. Answer relevant questions such as what tomorrow's plans are, what they should work on right now, when a specific meeting is, etc. 

        Remember, you do not have the tool to add meetings or tasks to an external calendar, but you can keep track of them in memory and provide a summary upon request. 

        You also do not have the ability to provide guidance or support on any subject other than the user's schedule and tasks. """

        suffix = f"{region_name}-{account_id}"
        foundationModel = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
        agent_bedrock_allow_policy_name = f"{agentName}-ba-{suffix}"
        agent_role_name = f'AmazonBedrockExecutionRoleForAgents_{agentName}'
        agent_alias_name = 'test'

        # Create IAM policy
        bedrock_agent_bedrock_allow_policy_statement = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AmazonBedrockAgentBedrockFoundationModelPolicyProd",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream"
                    ],
                    "Resource": [
                        f"arn:aws:bedrock:{region_name}::foundation-model/{foundationModel}"
                    ]
                }
            ]
        }
        bedrock_policy_json = json.dumps(bedrock_agent_bedrock_allow_policy_statement)
        
        # Create IAM Role assume policy
        assume_role_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AmazonBedrockAgentBedrockFoundationModelPolicyProd",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": account_id
                        },
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock:{region_name}:{account_id}:agent/*"
                        }
                    }
                }
            ]
        }
        assume_role_policy_document_json = json.dumps(assume_role_policy_document)

        # Execute the setup workflow with error handling
        agent_bedrock_policy = create_policy(iam, account_id, agent_bedrock_allow_policy_name, bedrock_policy_json)
        agent_role = create_role(iam, agent_role_name, assume_role_policy_document_json)
        attach_policy_to_role(iam, agent_role_name, agent_bedrock_policy['Policy']['Arn'])
        
        agent_response = create_agent(
            bedrock_agent_client,
            agentName,
            agent_role['Role']['Arn'],
            description,
            instruction,
            foundationModel
        )
        
        agent_id = agent_response['agent']['agentId']
        logger.info(f"Agent ID: {agent_id}")
        
        prepare_agent(bedrock_agent_client, agent_id)
        alias_response = create_agent_alias(bedrock_agent_client, agent_id, agent_alias_name)
        
        agentAliasId = alias_response['agentAlias']['agentAliasId']
        logger.info(f"Agent Alias ID: {agentAliasId}")
        
        logger.info("Setup completed successfully")
        
        # Return the important IDs for reference
        return {
            "agent_id": agent_id,
            "agent_alias_id": agentAliasId,
            "role_arn": agent_role['Role']['Arn'],
            "policy_arn": agent_bedrock_policy['Policy']['Arn']
        }
        
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        result = main()
        print("Setup completed successfully with the following resources:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Setup failed: {e}")
