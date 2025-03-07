from unittest.mock import patch
from main import invoke, end_session 

# Test successful invoke
@patch('main.bedrock_agent_runtime')
def test_invoke_success(mock_runtime):
    mock_runtime.invoke_agent.return_value = {"completion": [{"chunk": {"bytes": b"Hello, world!"}}]}
    result = invoke("Hello", "session123", "alias123", "agent123")
    assert result is True
    mock_runtime.invoke_agent.assert_called_once()

# Test invoke failure due to missing params
def test_invoke_missing_params():
    result = invoke("", "session123", "alias123", "agent123")
    assert result is False

# Test invoke API error
@patch('main.bedrock_agent_runtime')
def test_invoke_api_error(mock_runtime):
    mock_runtime.invoke_agent.side_effect = Exception("API Error")
    result = invoke("Hello", "session123", "alias123", "agent123")
    assert result is False

# Test end session
@patch('main.invoke', return_value=True)
def test_end_session(mock_invoke):
    end_session("alias123", "session123", "agent123")
    mock_invoke.assert_called_once_with("Goodbye", "session123", "alias123", "agent123", memoryId=None, endSession=True)
