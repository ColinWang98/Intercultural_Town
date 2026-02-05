# -*- coding: utf-8 -*-
"""pytest tests for Main.py API endpoints.

Tests cover:
- GET /personas
- POST /conversations
- GET /conversations
- GET /conversations/{id}
- GET /conversations/{id}/messages
- POST /conversations/{id}/messages
- Message filtering (_strip_thinking)
- Message length limits
- Conversation isolation
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_generate_initial():
    """Mock _generate_group_initial_messages to avoid hitting Ollama."""
    with patch('Main._generate_group_initial_messages', new_callable=AsyncMock) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_run_chat():
    """Mock _run_chat_round to avoid hitting Ollama."""
    with patch('Main._run_chat_round', new_callable=AsyncMock) as mock:
        mock.return_value = "[芬兰学生讨论组] Moi!"
        yield mock


class TestGetPersonas:
    """Tests for GET /personas endpoint."""

    def test_get_personas_returns_list(self, client):
        """GET /personas returns a list of personas."""
        response = client.get("/personas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the finnish_discussion_root
        assert len(data) >= 1

    def test_get_personas_structure(self, client):
        """Each persona has id and name fields."""
        response = client.get("/personas")
        data = response.json()
        for persona in data:
            assert "id" in persona
            assert "name" in persona
            assert isinstance(persona["id"], str)
            assert isinstance(persona["name"], str)


class TestCreateConversation:
    """Tests for POST /conversations endpoint."""

    def test_create_conversation_success(self, client, mock_generate_initial):
        """POST /conversations creates a new conversation."""
        response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "persona_ids" in data
        assert "messages" in data
        assert "created_at" in data
        assert data["persona_ids"] == ["finnish_discussion_root"]

    def test_create_conversation_invalid_persona(self, client, mock_generate_initial):
        """POST /conversations with invalid persona returns 400."""
        response = client.post(
            "/conversations",
            json={"persona_ids": ["nonexistent_persona"]}
        )
        assert response.status_code == 400

    def test_create_conversation_empty_persona_ids(self, client, mock_generate_initial):
        """POST /conversations with empty persona_ids uses default."""
        response = client.post(
            "/conversations",
            json={"persona_ids": []}
        )
        # Empty defaults to DEFAULT_PERSONA (finnish_discussion_root)
        assert response.status_code == 200


class TestCreateConversationFinnishDiscussionOpeningDialogue:
    """Tests for automatic opening dialogue when creating Finnish discussion conversation."""

    def test_finnish_discussion_triggers_opening_dialogue(self, client, mock_generate_initial):
        """Creating conversation with Finnish discussion team triggers opening dialogue."""
        mock_generate_initial.return_value = [
            {"role": "model", "name": "芬兰学生讨论组", "content": "Mikko: Moi!\nAino: Hei!"},
        ]

        response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        # Should have opening messages from mock
        assert len(data["messages"]) == 1


class TestSendMessage:
    """Tests for POST /conversations/{id}/messages endpoint."""

    def test_send_message_to_nonexistent_conversation(self, client):
        """POST message to nonexistent conversation returns 404."""
        response = client.post(
            "/conversations/nonexistent-id/messages",
            json={"content": "Hello"}
        )
        assert response.status_code == 404

    def test_send_message_success(self, client, mock_generate_initial, mock_run_chat):
        """POST message to valid conversation returns new messages."""
        # First create a conversation
        create_response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Send a message
        response = client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "Hello"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "reply" in data

    def test_send_empty_message(self, client, mock_generate_initial, mock_run_chat):
        """POST empty message content should be handled."""
        # First create a conversation
        create_response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": ""}
        )
        # Empty content should either be rejected (422) or handled gracefully
        assert response.status_code in [200, 400, 422]


class TestMessageFilteringThinkingTags:
    """Tests for _strip_thinking function that filters model thinking tags."""

    def test_strip_thinking_removes_think_tags(self):
        """_strip_thinking removes <think>...</think> blocks."""
        from Main import _strip_thinking
        
        text = "Hello <think>I need to respond nicely</think> World"
        result = _strip_thinking(text)
        assert "<think>" not in result
        assert "</think>" not in result
        assert "I need to respond nicely" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strip_thinking_case_insensitive(self):
        """_strip_thinking handles case variations."""
        from Main import _strip_thinking
        
        text = "Hello <THINK>reasoning here</THINK> World"
        result = _strip_thinking(text)
        assert "reasoning here" not in result

    def test_strip_thinking_unclosed_tag(self):
        """_strip_thinking handles unclosed <think> tags."""
        from Main import _strip_thinking
        
        text = "Hello <think>some unclosed thinking"
        result = _strip_thinking(text)
        assert "<think>" not in result
        # Unclosed tag should truncate from that point
        assert "Hello" in result.strip()

    def test_strip_thinking_chinese_prefixes(self):
        """_strip_thinking removes Chinese thinking prefixes."""
        from Main import _strip_thinking
        
        text = "思考：我需要处理这个\n实际回复内容"
        result = _strip_thinking(text)
        assert "思考：" not in result
        assert "实际回复内容" in result

    def test_strip_thinking_preserves_normal_text(self):
        """_strip_thinking preserves text without thinking patterns."""
        from Main import _strip_thinking
        
        text = "This is a normal response without any thinking tags."
        result = _strip_thinking(text)
        assert result == text


class TestMessageLengthLimit:
    """Tests for MAX_REPLY_LENGTH truncation."""

    def test_get_reply_truncates_long_messages(self):
        """_get_reply_from_events truncates messages over MAX_REPLY_LENGTH."""
        from Main import _get_reply_from_events, MAX_REPLY_LENGTH
        
        # Create a mock event with very long text
        long_text = "A" * (MAX_REPLY_LENGTH + 500)
        
        # Create mock event structure
        mock_part = MagicMock()
        mock_part.text = long_text
        
        mock_content = MagicMock()
        mock_content.role = "model"
        mock_content.parts = [mock_part]
        
        mock_event = MagicMock()
        mock_event.content = mock_content
        
        result = _get_reply_from_events([mock_event])
        
        # Should be truncated to MAX_REPLY_LENGTH + ellipsis
        assert result is not None
        assert len(result) <= MAX_REPLY_LENGTH + 1  # +1 for ellipsis character
        assert result.endswith("…")

    def test_get_reply_preserves_short_messages(self):
        """_get_reply_from_events preserves messages under MAX_REPLY_LENGTH."""
        from Main import _get_reply_from_events, MAX_REPLY_LENGTH
        
        short_text = "This is a short message."
        
        mock_part = MagicMock()
        mock_part.text = short_text
        
        mock_content = MagicMock()
        mock_content.role = "model"
        mock_content.parts = [mock_part]
        
        mock_event = MagicMock()
        mock_event.content = mock_content
        
        result = _get_reply_from_events([mock_event])
        
        assert result is not None
        assert result == short_text
        assert not result.endswith("…")


class TestConversationIsolation:
    """Tests for conversation isolation - messages don't leak between conversations."""

    def test_conversations_are_isolated(self, client, mock_generate_initial, mock_run_chat):
        """Messages in one conversation don't appear in another."""
        # Create two conversations
        conv1_response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        conv1_id = conv1_response.json()["id"]

        conv2_response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        conv2_id = conv2_response.json()["id"]

        # Send message to conv1
        client.post(
            f"/conversations/{conv1_id}/messages",
            json={"content": "Message for conversation 1"}
        )

        # Get conv2 messages - should be empty or only have initial messages
        conv2_detail = client.get(f"/conversations/{conv2_id}")
        conv2_messages = conv2_detail.json()["messages"]

        # conv2 should NOT contain message sent to conv1
        for msg in conv2_messages:
            assert "Message for conversation 1" not in msg.get("content", "")

    def test_get_conversation_returns_correct_data(self, client, mock_generate_initial):
        """GET /conversations/{id} returns correct conversation."""
        # Create a conversation
        create_response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        conv_id = create_response.json()["id"]

        # Get conversation
        get_response = client.get(f"/conversations/{conv_id}")
        assert get_response.status_code == 200
        data = get_response.json()

        assert data["id"] == conv_id
        assert data["persona_ids"] == ["finnish_discussion_root"]

    def test_get_nonexistent_conversation(self, client):
        """GET /conversations/{id} for nonexistent conversation returns 404."""
        response = client.get("/conversations/nonexistent-id-12345")
        assert response.status_code == 404


class TestGetConversationMessages:
    """Tests for GET /conversations/{id}/messages endpoint."""

    def test_get_messages_with_pagination(self, client, mock_generate_initial):
        """GET /conversations/{id}/messages supports limit and offset."""
        # Create a conversation
        create_response = client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )
        conv_id = create_response.json()["id"]

        # Get messages with pagination params
        response = client.get(f"/conversations/{conv_id}/messages?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        # Response is a dict with "messages" and "total"
        assert "messages" in data
        assert "total" in data
        assert isinstance(data["messages"], list)

    def test_get_messages_nonexistent_conversation(self, client):
        """GET /conversations/{id}/messages for nonexistent conversation returns 404."""
        response = client.get("/conversations/nonexistent-id/messages")
        assert response.status_code == 404


class TestGetConversationsList:
    """Tests for GET /conversations endpoint."""

    def test_get_conversations_list(self, client, mock_generate_initial):
        """GET /conversations returns list of conversation summaries."""
        # Create a conversation first
        client.post(
            "/conversations",
            json={"persona_ids": ["finnish_discussion_root"]}
        )

        response = client.get("/conversations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Each item should have summary fields
        if len(data) > 0:
            item = data[0]
            assert "id" in item
            assert "persona_ids" in item
            assert "created_at" in item
            assert "message_count" in item


class TestRootEndpoint:
    """Tests for GET / root endpoint."""

    def test_root_returns_api_info(self, client):
        """GET / returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
