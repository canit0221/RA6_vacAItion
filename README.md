![Image](https://github.com/user-attachments/assets/61796c5f-40bf-4aba-b315-8c697b8f1ea1)
# 🦾 AI가 찾아주는 완벽한 휴일 - **vacAItion**

---

## 📖 프로젝트 소개
**vacAItion**은 사용자의 대화와 일정을 기반으로 날씨, 취향, 지역 정보를 반영해 최적의 휴일 활동을 추천하는 대화형 AI 서비스입니다.

데이트, 친구 모임, 가족 나들이 등 다양한 상황에 맞춘 맞춤형 추천을 제공하며, 최신 전시회, 공연, 축제 정보를 주기적으로 반영합니다.

### 🔗 서비스 접속: https://ra6vacaition.vercel.app/
### 🔗 시연 영상: https://www.youtube.com/watch?v=06y_Mj5P1eY
---

## 🚩 기획 의도 및 배경

기존 서비스는 주로 장소 정보 제공과 예약 기능에 중점을 두고 있으며, 실제 맞춤형 추천은 부족합니다. **vacAItion**은 사용자의 일정, 날씨, 동행자 및 개인 취향을 분석해 AI 기반의 맞춤형 장소 추천과 일정 관리를 통합 제공합니다.

---

## 🎯 주요 목표
- 맞춤형 장소 추천과 일정 관리를 하나의 플랫폼에서 제공
- 날씨, 동행자, 선호도를 분석한 맞춤형 추천으로 사용자 경험 강화
- 챗봇을 통해 숨겨진 명소와 로컬 맛집 발견
- 간단한 대화로도 간편하게 접근 가능한 서비스 제공

---

## 👥 팀원 소개 및 역할

| 이름 | 직책 | 역할 |
|------|------|------|
| 김민서 | 팀장 | 채팅 구현, 데이터 임베딩, 데이터 수집, RAG, 웹 API |
| 김용수 | 부팀장 | 데이터 수집, RAG, DB 구축, AWS 배포, 백엔드 |
| 김민정 | 팀원 | 백엔드, 프론트엔드, AWS 배포, 데이터 수집, 웹 API |
| 이고운 | 팀원 | 백엔드, 프론트엔드, AWS 배포, 데이터 수집, 웹 API |

---

## 🔧 주요 기능

### 일정 관리
- AI 기반으로 날짜별 계획 자동 생성 및 최적화
- 추천 장소를 원클릭으로 일정에 추가

### 맞춤형 장소 추천
- 챗봇 인터페이스를 통한 직관적인 장소 추천
- 실시간 날씨와 사용자 취향을 고려한 개인화 추천

### AI 어시스턴스
- 자연어 처리를 통한 직관적 대화
- 키워드 인식으로 숨겨진 명소와 로컬 맛집 추천
- 사용자 방문 이력 및 선호도 학습을 통한 정확도 향상

---

## 🛠️ 기술 스택
- **Backend**: Python, Django, DRF, Django Channels, Redis, JWT
- **Frontend**: HTML, CSS, Vanilla JS
- **Database**: PostgreSQL, FAISS
- **AI 서비스**: OpenAI API(o3-mini), LangChain, LangGraph
- **Deploy**: AWS EC2, Docker, Nginx, Daphne (ASGI)
- **협업 도구**: Figma, Slack, Zep, Notion

---

## 서비스 아키텍처
![Image](https://github.com/user-attachments/assets/7ebe1ac5-7514-4b39-a66b-f96915eae83c)

---

## 🗂️ 프로젝트 구조
- [와이어프레임](https://www.notion.so/SA-1a7a0d2750d08064bef1c024be7e48ec?pvs=4#1c1a0d2750d080afbc5cd064953f8d76)
- [API 명세서](https://www.notion.so/SA-1a7a0d2750d08064bef1c024be7e48ec?pvs=4#1a7a0d2750d0800db5aafdd4b413a12e)
- [ERD](https://www.notion.so/SA-1a7a0d2750d08064bef1c024be7e48ec?pvs=4#1a7a0d2750d080c58e62c523a7c45fe0)

---

## 📆 프로젝트 일정
- 데이터 수집, 전처리: 3/4 ~ 3/7
- MVP 기능 개발: 3/4 ~ 3/12
- 중간 발표: 3/14
- 피드백 기반, MVP 개선: 3/15 ~ 3/23
- 배포: 3/21 ~ 3/24
- 배포 테스트 및 디버깅: 3/24 ~ 3/27
- 유저 테스트: 3/27 ~ 3/29
- 최종 발표 및 배포: 3/31

---

## 🤔 기술적 의사결정
- WebSocket 선택 (실시간 채팅 구현)
- NAVER 지역 검색 API 사용 (국내 장소 데이터 최적화)
- Vanilla JS 채택 (빠른 프로토타입 개발)
- LangGraph 적용 (복잡한 대화 흐름 관리)
- o3-mini 모델 선택 (정확도와 속도의 균형)
- Docker 컨테이너 사용 (일관된 개발 환경)
- SQLite → PostgreSQL 전환 (대규모 데이터 관리)
- 하이브리드 검색 시스템 구축 (정확도 향상)
- 세션 ID 기반 개인화 추천 관리
- 대화 필터링 에이전트로 서비스 관련 대화만 응답

---

## 💻 설치 및 실행 방법
1. 저장소 Clone하기
```bash
git clone https://github.com/Kkimminseo/RA6_vacAItion.git
```

2. 환경 변수 설정<br>
* `.env` 파일을 생성하여 환경 변수 설정
```bash
DJANGO_SECRET_KEY = your_django_secret_key
OPENAI_API_KEY = your_openai_key
NAVER_CLIENT_ID = your_client_id
NAVER_CLIENT_SECRET = your_secret_key
GOOGLE_CLIENT_ID = your_client_id
GOOGLE_CLIENT_SECRET = your_secret_key


# Database settings
DB_ENGINE=django.db.backends.postgresql
DB_NAME=yourdb_name
DB_USER=yourdb_user
DB_PASSWORD=yourdb_password
DB_HOST=localhost
DB_PORT=5432
POSTGRES_USER=yourdb_user
POSTGRES_PASSWORD=yourdb_password
POSTGRES_DB=yourdb_name


# SMTP 이메일 설정
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@emaill.address
EMAIL_HOST_PASSWORD=yourpassword
DEFAULT_FROM_EMAIL=your@emaill.address
```
3. 벡터스토어 저장<br>
* /backend/data/db/vectorstore 와 /backend/data/eventdb/vectorstore 디렉토리에 `index.faiss`, `index.pkl` 파일 저장
```bash
.
├── backend
│   ├── data
│   │   ├── db
│   │   │   └── vectorstore -index.faiss,index.pkl
│   │   ├── event_db
│   │   │   └── vectorstore -index.faiss,index.pkl
```

5. 프로젝트 디렉토리로 이동
```bash
cd backend
```

5. 의존성 설치 및 서버 실행(Docker 기반)
```bash
docker-compose up -d --build
```

6. PostgreSQL에 db 임포트<br>
  * chatbot_event, chatbot_naverblog, chatbot_naverblog 테이블에 csv 임포트

8. 서비스 실행 및 접속
- `http://localhost:8000` 접속

---

## 🚨 트러블슈팅
- [상세 내용은 여기를 클릭하세요.](https://www.notion.so/1b4a0d2750d0807e8532f081a546be61?pvs=21)

---

📌 지속적으로 서비스 기능을 개선하고 있습니다. 더 좋은 휴일을 위해 vacAItion과 함께 하세요!
