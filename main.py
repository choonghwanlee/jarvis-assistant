import boto3
import json
import time
import random
import uuid
import string
import logging
import pprint
import sys
from botocore.exceptions import ClientError, NoCredentialsError


# Configure logging
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define constant for region
REGION_NAME = 'us-east-1'


def create_client():
    """Create and return a bedrock-agent-runtime client with error handling."""
    try:
        print("Creating Bedrock client...")
        client = boto3.client(service_name='bedrock-agent-runtime', region_name=REGION_NAME)
        print("Client created:", client)
        return client
    except NoCredentialsError:
        logger.error("No AWS credentials found. Please configure your AWS credentials.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to create Bedrock client: {str(e)}")
        sys.exit(1)


# Initialize the client globally 
try:
    bedrock_agent_runtime = create_client()
except Exception as e:
    logger.critical(f"Fatal error initializing Bedrock client: {str(e)}")
    sys.exit(1)


def invoke(inputText, sessionId, agentAliasId, agentId, enable_trace=False, memoryId=None, session_state=None, endSession=False):
    """
    Invoke the Bedrock agent with comprehensive error handling.
    
    Args:
        inputText (str): The text input for the agent
        sessionId (str): The unique session identifier
        agentAliasId (str): The agent alias ID
        agentId (str): The agent ID
        enable_trace (bool): Whether to enable tracing
        memoryId (str): Optional memory ID
        session_state (dict): Optional session state
        endSession (bool): Whether to end the session
    
    Returns:
        bool: True if successful, False if failed
    """
    if not session_state:
        session_state = {}
    
    # Validate inputs
    if not all([inputText, sessionId, agentAliasId, agentId]):
        logger.error("Required parameters missing: inputText, sessionId, agentAliasId, and agentId must be provided")
        return False
        
    try:
        # Create request parameters
        invoke_params = {
            "agentAliasId": agentAliasId,   
            "agentId": agentId,       
            "sessionId": sessionId,       
            "inputText": inputText,
            "endSession": endSession,  
            "enableTrace": enable_trace, 
            "sessionState": session_state
        }
        
        # Add optional memoryId if provided
        if memoryId:
            invoke_params["memoryId"] = memoryId
            
        # Make the API call
        response = bedrock_agent_runtime.invoke_agent(**invoke_params)
        
        # Log trace information if enabled
        if enable_trace:
            logger.info("Trace information:")
            logger.info(pprint.pformat(response))
        
        # Process the response stream
        event_stream = response.get("completion")
        if not event_stream:
            logger.error("No completion stream returned from Bedrock")
            return False
            
        # Process events in the stream
        for event in event_stream:
            if 'chunk' in event:
                chunk = event.get('chunk', {})
                if 'bytes' in chunk:
                    try:
                        text = chunk['bytes'].decode('utf-8')
                        print(f"JARVIS: {text}", end="", flush=True)
                    except UnicodeDecodeError as ude:
                        logger.error(f"Failed to decode response bytes: {ude}")
                else:
                    logger.warning("Received chunk without 'bytes' field")
            elif 'trace' in event:
                if enable_trace:
                    logger.info(f"Trace event: {json.dumps(event['trace'], indent=2)}")
            else:
                logger.warning(f"Unexpected event type: {event}")
        
        print()  # Add newline after all chunks
        return True
        
    except ClientError as ce:
        error_code = ce.response.get('Error', {}).get('Code', 'Unknown')
        error_message = ce.response.get('Error', {}).get('Message', 'Unknown error')
        
        if error_code == 'ThrottlingException':
            logger.warning(f"API throttling detected. Waiting before retry: {error_message}")
            time.sleep(2)  # Wait before potential retry
        elif error_code == 'ValidationException':
            logger.error(f"Validation error: {error_message}")
        elif error_code == 'AccessDeniedException':
            logger.error(f"Access denied: {error_message}. Check your IAM permissions.")
        elif error_code == 'ResourceNotFoundException':
            logger.error(f"Resource not found: {error_message}. Check your agent IDs.")
        else:
            logger.error(f"AWS API error: {error_code} - {error_message}")
        
        return False

    except Exception as e:
        logger.error(f"Unexpected error during agent invocation: {str(e)}")
        return False


def end_session(agentAliasId, sessionId, agentId, memoryId=None):
    """End the agent session with error handling."""
    try:
        logger.info(f"Ending session {sessionId}")
        success = invoke("Goodbye", sessionId, agentAliasId, agentId, memoryId=memoryId, endSession=True)
        if success:
            logger.info("Session ended successfully")
        else:
            logger.warning("Failed to properly end session")
    except Exception as e:
        logger.error(f"Error ending session: {str(e)}")


def chat_with_agent(agentAliasId, sessionId, agentId, memoryId=None, max_retries=3):
    """
    Main function to chat with the agent with retry logic.
    
    Args:
        agentAliasId (str): The agent alias ID
        sessionId (str): The unique session identifier
        agentId (str): The agent ID 
        memoryId (str): Optional memory ID
        max_retries (int): Maximum number of retries on transient errors
    """
    print("This is JARVIS, your personal assistant. Type 'exit' to end the conversation.")
    
    try:
        while True:
            try:
                user_input = input("You: ")
                
                if not user_input.strip():
                    print("Please enter some text. Type 'exit' to end the conversation.")
                    continue
                    
                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("Ending session...")
                    end_session(agentAliasId, sessionId, agentId, memoryId)
                    break
                                
                success = invoke(user_input, sessionId, agentAliasId, agentId, memoryId=memoryId)                
                if not success:
                    print("JARVIS: I'm sorry, I'm having trouble processing your request right now. Please try again later.")
                    
            except KeyboardInterrupt:
                confirm = input("\nDo you want to exit? (y/n): ")
                if confirm.lower() in ['y', 'yes']:
                    print("Ending session...")
                    end_session(agentAliasId, sessionId, agentId, memoryId)
                    break
            
    except Exception as e:
        logger.error(f"Fatal error in chat session: {str(e)}")
        print("\nAn unexpected error occurred. Please check the logs for details.")
        # Try to end the session gracefully
        try:
            end_session(agentAliasId, sessionId, agentId, memoryId)
        except:
            pass
        

if __name__ == '__main__':
    try:
        # Generate a unique session ID
        sessionId = str(uuid.uuid4())
        memoryId = "JARVIS-MEMORY-123"

        # Validate agent configuration
        agent_alias_id = 'S9KYCFSUF2'
        agent_id = 'LN835LDO1L'
        
        if not all([agent_alias_id, agent_id]):
            logger.error("Agent configuration is incomplete. Please check your agent IDs.")
            sys.exit(1)
        
        # Start the chat session
        logger.info(f"Starting new session {sessionId} with memory {memoryId}")
        chat_with_agent(agentAliasId=agent_alias_id, agentId=agent_id, sessionId=sessionId, memoryId=memoryId)
        
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}")
        sys.exit(1)
