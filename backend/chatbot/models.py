from django.db import models
from vacation.settings import AUTH_USER_MODEL  # AUTH USER MODEL 불러오기
from django.contrib.auth.models import User
from django.conf import settings  # settings import 추가
import re
import json
import os

# Create your models here.
class Chat(models.Model):
    user = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE
    )  # 채팅 참여자, 비회원 또한 채팅 참여 가능
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    session_id = models.CharField(max_length=100, null=True, blank=True)  # null 허용
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # 세션별로 추천된 장소들을 저장하는 필드 추가
    recommended_places = models.TextField(default='[]', blank=True)  # JSON 형식으로 저장

    def __str__(self):
        return f"{self.user.username}'s chat - {self.title}"
    
    def get_recommended_places(self):
        """추천된 장소들을 리스트로 반환"""
        try:
            return json.loads(self.recommended_places)
        except:
            return []
            
    def add_recommended_place(self, place_name):
        """새로운 장소를 추천 목록에 추가"""
        places = self.get_recommended_places()
        if place_name not in places:
            places.append(place_name)
            self.recommended_places = json.dumps(places)
            self.save()
        return places


class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession, related_name="messages", on_delete=models.CASCADE
    )
    content = models.TextField()
    is_bot = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{'Bot' if self.is_bot else 'User'}: {self.content[:50]}..."
    
    @staticmethod
    def extract_places_from_message(message_content):
        """채팅 메시지에서 장소명 추출하는 함수"""
        # 장소 추출 패턴
        places = []
        
        # 1. <b>장소명</b> 패턴 추출
        b_pattern = r'<b>(.*?)</b>'
        b_matches = re.findall(b_pattern, message_content)
        for match in b_matches:
            # 숫자와 점으로 시작하는 경우 제거 (예: "1. ")
            clean_match = re.sub(r'^\d+\.\s*', '', match)
            if clean_match and len(clean_match) > 1:  # 최소 2글자 이상
                places.append(clean_match)
        
        # 2. 위치: 또는 주소: 뒤에 나오는 텍스트 추출
        location_patterns = [
            r'위치:\s*(.*?)(?=\n|$)',
            r'주소:\s*(.*?)(?=\n|$)',
            r'📍\s*위치:\s*(.*?)(?=\n|$)',
            r'📍\s*주소:\s*(.*?)(?=\n|$)'
        ]
        
        for pattern in location_patterns:
            location_matches = re.findall(pattern, message_content)
            for match in location_matches:
                clean_match = match.strip()
                if clean_match and len(clean_match) > 5:  # 주소는 보통 길어서 5자 이상으로 필터링
                    # 주소에서 장소명 추출 (첫 번째 공백이나 쉼표까지)
                    place_from_addr = clean_match.split(' ')[0].split(',')[0]
                    if place_from_addr and len(place_from_addr) > 1:
                        places.append(place_from_addr)
        
        # 3. 특정 패턴으로 잡히지 않는 장소를 위한 추가 처리
        # 숫자. 으로 시작하는 라인에서 장소명 추출
        numbered_pattern = r'\d+\.\s*(.*?)(?=\n|$)'
        numbered_matches = re.findall(numbered_pattern, message_content)
        for match in numbered_matches:
            clean_match = match.strip()
            if clean_match and len(clean_match) > 1 and '<' not in clean_match:
                places.append(clean_match)
        
        return list(set(places))  # 중복 제거

    @classmethod
    def get_recommended_places_for_session(cls, session_id):
        """특정 세션의 모든 메시지에서 장소명 추출"""
        messages = cls.objects.filter(session_id=session_id, is_bot=True).order_by('created_at')
        all_places = []
        
        for message in messages:
            places = cls.extract_places_from_message(message.content)
            all_places.extend(places)
        
        return list(set(all_places))  # 중복 제거


# 원본 문서 모델
class NaverBlog(models.Model):
    line_number = models.IntegerField(primary_key=True)  # 원본 문서 라인 번호
    page_content = models.TextField()
    url = models.TextField()


class NaverBlogFaiss(models.Model):  # 청크로 인해 달라진 id 맞춰줌
    faiss_index = models.IntegerField(primary_key=True)  # 벡터 인덱스
    line_number = models.ForeignKey(NaverBlog, on_delete=models.CASCADE)


class Event(models.Model):
    faiss_index = models.IntegerField(
        primary_key=True
    )  # 벡터 인덱스 = 원본 문서 라인 번호
    tag = models.TextField()
    title = models.TextField()
    time = models.TextField()
    location = models.TextField()
    address = models.TextField()
    address_detail = models.TextField()
    content = models.TextField()
    atmosphere = models.TextField()
    companions = models.TextField()