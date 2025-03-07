# jarvis-assistant

A prototype JARVIS-like personal assistant using Amazon Bedrock + memory/session context

To build our conversational AI assistant, we leverage Bedrock Agents via their boto3 Python SDK.

Specifically, we configure a AWS Bedrock Agent with Anthropic's **Sonnet 3.5 model** as the foundational model and add **long-term memory** to the agent. This allows us to retain information from conversations between sessions.

`setup.py` contains the code to configure, create, and prepare a AWS Bedrock Agent. It creates the relevant policy and role, defines the agent's system prompt and description, then prepares an agent with the desired foundational model, long-term memory, and IAM configurations. To run, run `python setup.py` in your command line. Make sure you have boto3 and AWS configured!

This yields information like agent ID, alias ID, Role/Policy ARN which are important when we actually run the agent in runtime.

`main.py` contains the main code for running the agent. Users can send queries to the JARVIS personal assistant via user input in the command line. Upon pressing enter, we invoke our previously prepared Agent with the the user input and print the response for the user.

To run the agent, run `python main.py` after running the agent setup.

Users can continuously converse with the agent; if they want to exit, they can enter 'exit' or escape with control-C anytime.

Comprehensive error handling was added throughout both of the above files to gracefully handle edge cases or potential errors that arise.

Unit tests have also been added to ensure high coverage and functional code. These test for different agent invocation behaviors, namely missing parameters, API errors, ending session, and successfully generating a response.
