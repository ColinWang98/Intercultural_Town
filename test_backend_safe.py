# -*- coding: utf-8 -*-
"""
直接测试后端功能 - 安全输出版本
"""

import os
import sys
import asyncio

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi.testclient import TestClient

# 导入后端
from Main import app, CONVERSATIONS, CONVERSATION_STATES

client = TestClient(app)


def safe_print(text):
    """安全打印，避免编码错误"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 如果打印失败，使用 repr 显示
        print(repr(text)[:200])


def test_get_personas():
    """测试获取 persona 列表"""
    safe_print("\n[TEST] Get Persona List")
    response = client.get("/personas")
    safe_print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        safe_print(f"  Count: {len(data)}")
        for p in data:
            safe_print(f"    - {p['id']}: {p['name']}")
        return True
    else:
        safe_print(f"  Error: {response.text}")
        return False


def test_create_conversation():
    """测试创建会话"""
    safe_print("\n[TEST] Create Conversation (with event context)")
    
    payload = {
        "persona_ids": ["mikko", "aino"],
        "player_name": "Player",
        "dynamic_personas": [
            {
                "id": "mikko",
                "name": "Mikko",
                "gender": "Male",
                "nationality": "Finnish",
                "personality": "外向、热情",
                "personality_type": "Extrovert",
                "interests": "派对、音乐",
                "speaking_style": "直接、热情",
                "likes": ["派对", "音乐"],
                "dislikes": ["安静"],
                "current_state": "准备派对",
                "location_hint": "宿舍",
                "event_title": "学生宿舍派对",
                "event_description": "周末在宿舍举办的派对",
                "event_topics": ["食物准备", "饮料选择"],
                "required_topics": ["饮食限制"]
            },
            {
                "id": "aino",
                "name": "Aino",
                "gender": "Female",
                "nationality": "Finnish",
                "personality": "细心、有条理",
                "personality_type": "Introvert",
                "interests": "策划活动",
                "speaking_style": "温和",
                "likes": ["计划"],
                "dislikes": ["坚果"],
                "current_state": "讨论派对准备",
                "location_hint": "宿舍"
            }
        ]
    }
    
    response = client.post("/conversations", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        conv_id = data['id']
        safe_print(f"  Status: 200 OK")
        safe_print(f"  Conversation ID: {conv_id}")
        safe_print(f"  Persona IDs: {data['persona_ids']}")
        safe_print(f"  Messages count: {len(data['messages'])}")
        
        if data['messages']:
            safe_print(f"  Opening messages generated: YES")
        
        return conv_id
    else:
        safe_print(f"  Error: {response.status_code}")
        safe_print(f"  Response: {response.text[:200]}")
        return None


def test_send_messages(conv_id):
    """测试发送消息"""
    safe_print("\n[TEST] Send Messages")
    
    messages = [
        "你们好！派对准备得怎么样了？",
        "需要准备什么食物吗？",
        "有人有饮食限制吗？"
    ]
    
    for i, msg in enumerate(messages, 1):
        safe_print(f"\n  [Round {i}] Sending message...")
        
        payload = {
            "content": msg,
            "player_name": "Player"
        }
        
        response = client.post(
            f"/conversations/{conv_id}/messages",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            reply_len = len(data['reply']) if data['reply'] else 0
            safe_print(f"    Status: 200 OK")
            safe_print(f"    Reply length: {reply_len} chars")
            safe_print(f"    New messages: {len(data['messages'])}")
        else:
            safe_print(f"    Error: {response.status_code}")
            return False
    
    return True


def test_get_conversation(conv_id):
    """测试获取会话详情"""
    safe_print("\n[TEST] Get Conversation Detail")
    
    response = client.get(f"/conversations/{conv_id}")
    safe_print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        safe_print(f"  ID: {data['id'][:16]}...")
        safe_print(f"  Personas: {data['persona_ids']}")
        safe_print(f"  Total messages: {len(data['messages'])}")
        return True
    else:
        return False


def test_get_summary(conv_id):
    """测试获取总结"""
    safe_print("\n[TEST] Get Conversation Summary")
    
    response = client.get(f"/conversations/{conv_id}/summary")
    safe_print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        safe_print(f"  Messages count: {data['messages_count']}")
        safe_print(f"  Phase: {data['phase']}")
        summary_len = len(data['summary']) if data['summary'] else 0
        safe_print(f"  Summary length: {summary_len} chars")
        return True
    else:
        return False


def main():
    safe_print("=" * 60)
    safe_print("Backend API Test - Godot Simulation")
    safe_print("=" * 60)
    
    results = []
    
    # Test 1: Get personas
    results.append(("Get Personas", test_get_personas()))
    
    # Test 2: Create conversation
    conv_id = test_create_conversation()
    results.append(("Create Conversation", conv_id is not None))
    
    if conv_id:
        # Test 3: Send messages
        results.append(("Send Messages", test_send_messages(conv_id)))
        
        # Test 4: Get conversation
        results.append(("Get Conversation", test_get_conversation(conv_id)))
        
        # Test 5: Get summary
        results.append(("Get Summary", test_get_summary(conv_id)))
    
    # Report
    safe_print("\n" + "=" * 60)
    safe_print("Test Report")
    safe_print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        safe_print(f"  [{status}] {name}")
    
    safe_print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        safe_print("\n[SUCCESS] All tests passed! Backend is working correctly.")
    else:
        safe_print(f"\n[WARNING] {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
