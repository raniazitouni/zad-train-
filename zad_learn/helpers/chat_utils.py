import json
from typing import List, Dict, Any
from ..models import ChatMessage, ChatConversation


def get_chat_history(conversation_id: int, limit: int = 10, start: int = 0) -> List[Dict[str, Any]]:
    """
    Get chat history for a conversation.
    
    Args:
        conversation_id: The ID of the conversation
        limit: Maximum number of messages to return
        start: Offset for pagination
        
    Returns:
        List of message dictionaries
    """
    messages = ChatMessage.objects.filter(
        conversation_id=conversation_id,
        is_deleted=False
    ).order_by('-created_at')[start:start + limit]
    
    return [{
        'role': msg.sender,
        'text': msg.text,
        'image_url': msg.image_url,
        'image_description': msg.image_description,
        'created_at': msg.created_at.isoformat()
    } for msg in reversed(messages)]


def get_history_for_ai(conversation_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get formatted chat history for AI service.
    
    Args:
        conversation_id: The ID of the conversation
        limit: Maximum number of messages to return
        
    Returns:
        List of message dictionaries formatted for AI service
    """
    messages = ChatMessage.objects.filter(
        conversation_id=conversation_id,
        is_deleted=False
    ).order_by('-created_at')[:limit]
    
    return [{
        'role': msg.sender,
        'content': msg.text or '',
        'image_url': msg.image_url,
        'image_description': msg.image_description
    } for msg in reversed(messages)]


def split_s3_url(s3_url: str) -> str:
    """
    Extract the key from an S3 URL.
    
    Args:
        s3_url: Full S3 URL
        
    Returns:
        S3 key
    """
    if not s3_url:
        return None
    return s3_url.split('/')[-1]


def restructure_images(images: Dict[str, List[str]]) -> List[Dict[str, str]]:
    """
    Restructure image data from AI service response.
    
    Args:
        images: Dictionary containing image URLs and descriptions
        
    Returns:
        List of dictionaries with image data
    """
    if not images:
        return []
        
    restructured = []
    for i in range(len(images.get('images', []))):
        restructured.append({
            'image_url': images['images'][i],
            'description': images.get('descriptions', [''])[i],
            'utility': images.get('utilities', [''])[i]
        })
    return restructured 