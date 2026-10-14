"""Chat routing and tool continuation without production data or API requests."""
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import openai
import pytest

import chat_assistant as chat


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    monkeypatch.setattr(openai, 'OpenAI', Mock(return_value=client))
    monkeypatch.setattr(chat.Config, 'POLZA_AI_API_KEY', 'isolated-test-key')
    monkeypatch.setattr(chat.Config, 'POLZA_AI_MODEL', 'openai/gpt-6-astra-pro')
    return client


def completion(message, reason='stop'):
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=reason)])


def test_chat_uses_configured_model_and_preserves_history(client, monkeypatch):
    monkeypatch.setattr(chat.Config, 'POLZA_AI_MODEL', 'test/another-permitted-model')
    client.chat.completions.create.return_value = completion(
        SimpleNamespace(content='Готово', tool_calls=None))
    assert chat.ask('Проверка', [{'role': 'user', 'content': 'Предыдущий вопрос'}]) == {'answer': 'Готово'}
    params = client.chat.completions.create.call_args.kwargs
    assert params['model'] == 'test/another-permitted-model'
    assert params['tools'] == chat.TOOLS
    assert params['messages'][-2:] == [
        {'role': 'user', 'content': 'Предыдущий вопрос'},
        {'role': 'user', 'content': 'Проверка'},
    ]


def test_astra_tool_result_is_returned_to_same_model(client, monkeypatch):
    call = SimpleNamespace(id='call_test', function=SimpleNamespace(
        name='get_loans_balance', arguments='{"pf":"факт"}'))
    message = Mock(tool_calls=[call])
    message.model_dump.return_value = {'role': 'assistant', 'tool_calls': []}
    client.chat.completions.create.side_effect = [
        completion(message, 'tool_calls'),
        completion(SimpleNamespace(content='Тест завершён', tool_calls=None)),
    ]
    tool = Mock(return_value={'test_value': 123})
    monkeypatch.setattr(chat, '_call_tool', tool)
    assert chat.ask('Тестовый запрос') == {'answer': 'Тест завершён'}
    tool.assert_called_once_with('get_loans_balance', {'pf': 'факт'})
    requests = client.chat.completions.create.call_args_list
    assert len(requests) == 2
    assert all(c.kwargs['model'] == 'openai/gpt-6-astra-pro' for c in requests)
    assert requests[-1].kwargs['messages'][-1] == {
        'role': 'tool', 'tool_call_id': 'call_test', 'content': '{"test_value": 123}',
    }


def test_forbidden_model_reports_configuration_problem_without_retry(client):
    response = httpx.Response(403, request=httpx.Request('POST', 'https://polza.ai/api/v1/chat/completions'))
    client.chat.completions.create.side_effect = openai.PermissionDeniedError(
        'forbidden', response=response, body=None)
    result = chat.ask('Проверка')
    assert 'POLZA_AI_MODEL' in result['error']
    assert 'isolated-test-key' not in result['error']
    client.chat.completions.create.assert_called_once()


def test_no_key_never_calls_external_service(client, monkeypatch):
    monkeypatch.setattr(chat.Config, 'POLZA_AI_API_KEY', None)
    assert 'POLZA_AI_API_KEY' in chat.ask('Проверка')['error']
    openai.OpenAI.assert_not_called()
