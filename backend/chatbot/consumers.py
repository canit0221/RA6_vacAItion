import json
import asyncio
from dotenv import load_dotenv
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatSession, ChatMessage
import os
from accounts.models import User
import jwt
from django.conf import settings
from urllib.parse import parse_qs
import weakref
from .graph_chatbot import get_graph_instance, graph_ready
from django.apps import apps
from django.utils import timezone
from openai import OpenAI

# 전역 변수로 연결 관리
_active_connections = weakref.WeakSet()

load_dotenv()
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_name = None
        self.room_group_name = None
        self.user = None
        self.message_history = None
        self._active = False

    async def connect(self):
        try:
            if self._active:
                return

            # 토큰 인증 처리
            query_string = self.scope.get("query_string", b"").decode()
            query_params = parse_qs(query_string)

            # URL 파라미터에서 정보 추출 (더 두드러지게 로깅)
            date_param = query_params.get("date", [None])[0]
            schedule_id_param = query_params.get("schedule_id", [None])[
                0
            ]  # 일정 ID 추가

            print("\n=== WebSocket 연결 시작 ===")
            print(f"연결 URL 쿼리 문자열: {query_string}")

            # 일정 ID 처리 (우선적으로 처리)
            if schedule_id_param:
                try:
                    schedule_id = int(schedule_id_param)
                    print(f"✅ URL에서 일정 ID 파라미터 성공적으로 추출: {schedule_id}")
                    # 나중에 사용하기 위해 인스턴스 변수로 저장
                    self.schedule_id = schedule_id
                except ValueError:
                    print(
                        f"❌ 일정 ID 형식 오류: {schedule_id_param}은 유효한 정수가 아닙니다"
                    )
                except Exception as e:
                    print(f"❌ schedule_id 파라미터 처리 중 오류: {e}")
            else:
                print("❌ URL에 schedule_id 파라미터가 없습니다")

            if date_param:
                try:
                    # URL 인코딩 디코드 및 날짜 형식 검증
                    date_param = date_param.strip()
                    from datetime import datetime

                    try:
                        parsed_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                        print(
                            f"✅ URL에서 날짜 파라미터 성공적으로 추출: {date_param} (파싱됨: {parsed_date})"
                        )
                        # 나중에 사용하기 위해 인스턴스 변수로 저장
                        self.session_date = parsed_date
                    except ValueError:
                        print(
                            f"❌ 날짜 형식 오류: {date_param}은 올바른 날짜 형식(YYYY-MM-DD)이 아닙니다"
                        )
                except Exception as e:
                    print(f"❌ date 파라미터 처리 중 오류: {e}")
            else:
                print("❌ URL에 date 파라미터가 없습니다")

            # 토큰 추출 및 검증
            token = query_params.get("token", [None])[0]
            if not token:
                print("WebSocket 연결에 토큰이 없음")
                await self.close()
                return

            try:
                # Bearer 접두사 제거
                if token.startswith("Bearer "):
                    token = token[7:]

                # JWT 토큰 디코딩
                decoded_token = jwt.decode(
                    token, settings.SECRET_KEY, algorithms=["HS256"]
                )
                username = decoded_token.get("username")

                if not username:
                    print("토큰에 username이 없음")
                    print("토큰 내용:", decoded_token)
                    await self.close()
                    return

                self.user = await self.get_user_from_username(username)
                if not self.user:
                    print("유효하지 않은 사용자")
                    await self.close()
                    return

            except jwt.InvalidTokenError as e:
                print(f"토큰 검증 실패: {e}")
                await self.close()
                return
            except Exception as e:
                print(f"인증 처리 중 오류 발생: {e}")
                await self.close()
                return

            self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
            self.room_group_name = f"chat_{self.room_name}"

            # 세션 가져오기
            try:
                session = await self.get_or_create_session(self.room_name, date_param)

                # URL 파라미터 정보를 세션에 저장 (더 명확하게 로깅)
                if date_param or schedule_id_param:
                    # URL 파라미터를 업데이트 또는 초기화
                    url_params = {}
                    if hasattr(session, "url_params") and session.url_params:
                        if isinstance(session.url_params, dict):
                            url_params = session.url_params
                        elif isinstance(session.url_params, str):
                            try:
                                url_params = json.loads(session.url_params)
                            except:
                                url_params = {}

                    # date 파라미터 추가
                    if date_param:
                        url_params["date"] = date_param

                        # 세션의 date 필드 업데이트
                        try:
                            from datetime import datetime

                            session_date = datetime.strptime(
                                date_param, "%Y-%m-%d"
                            ).date()
                            session.date = session_date
                            print(
                                f"✅ 세션 {self.room_name}에 날짜 저장됨: {session_date}"
                            )
                        except Exception as e:
                            print(f"❌ 날짜 변환 중 오류: {e}")

                    # schedule_id 파라미터 추가
                    if schedule_id_param:
                        try:
                            schedule_id = int(schedule_id_param)
                            url_params["schedule_id"] = schedule_id
                            print(
                                f"✅ 세션 {self.room_name}에 일정 ID 저장됨: {schedule_id}"
                            )
                        except Exception as e:
                            print(f"❌ 일정 ID 저장 중 오류: {e}")

                    # URL 파라미터 저장
                    session.url_params = url_params
                    await database_sync_to_async(session.save)()
                    print(
                        f"✅ 세션 {self.room_name}에 URL 파라미터 저장 완료: {url_params}"
                    )
            except Exception as e:
                print(f"❌ 세션 정보 저장 중 오류: {e}")

            # 메세지 히스토리 로드
            self.message_history = await self.load_chat_history()

            # 채널 그룹에 추가
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)

            # WebSocket 연결 수락
            await self.accept()
            self._active = True
            _active_connections.add(self)
            print(
                f"✅ WebSocket 연결 성공: {self.user.username}, 세션: {self.room_name}"
            )
            print("=== WebSocket 연결 완료 ===\n")

        except Exception as e:
            print(f"❌ Connection error: {e}")
            if hasattr(self, "close"):
                await self.close(code=1011)
            raise

    async def disconnect(self, close_code):
        # 채널 그룹에서 제거
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
        self._active = False
        _active_connections.discard(self)

    # OpenAI API를 사용하여 메시지가 장소 질문/추천 관련인지 판별하는 함수
    async def is_place_related_message(self, message):
        """
        OpenAI의 gpt-4o-mini 모델을 사용하여 메시지가 장소 질문/추천 관련인지 판별
        """
        try:
            # OpenAI 클라이언트 초기화
            client = OpenAI(api_key=OPENAI_API_KEY)

            # 시스템 프롬프트와 사용자 메시지 설정
            system_prompt = """
            당신은 메시지 분류기입니다. 메시지가 일정 추천, 여행, 장소 추천, 맛집 추천, 카페 추천, 
            공연 추천, 전시 추천, 관광지, 여행 계획, 갈만한 곳, 휴가 장소, 방문할 곳, 관광, 여행지 등 
            장소 질문이나 일정추천에 관련된 내용인지 판별해주세요. 
            판별 결과는 'yes' 또는 'no'로만 답변하세요.
            """

            # API 호출
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0,
                max_tokens=100,
            )

            # 응답 분석
            result = response.choices[0].message.content.strip().lower()
            is_related = "yes" in result

            print(
                f"메시지 분류 결과: '{message}' -> {result} (장소 관련: {is_related})"
            )
            return is_related

        except Exception as e:
            print(f"메시지 분류 중 오류: {e}")
            # 오류 발생 시 기본적으로 처리 계속 진행 (True 반환)
            return True

    # 웹소켓에서 메세지 수신 - 메시지 판별 로직 추가
    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신"""
        print(f"받은 데이터: {text_data}")

        try:
            text_data_json = json.loads(text_data)
            print(f"파싱된 JSON: {text_data_json}")

            message = text_data_json.get("message", "")
            session_id = text_data_json.get("sessionId")

            print(
                f"추출된 메시지: '{message}', 세션 ID: {session_id or self.room_name}"
            )

            if not message.strip():
                print("빈 메시지 무시")
                return

            # 메시지가 장소 질문/추천 관련인지 판별
            is_place_related = await self.is_place_related_message(message)

            # 메시지 저장
            session, is_new = await self.save_message_and_get_response(
                message, session_id
            )
            print(f"메시지 저장 완료, 새 세션: {is_new}")

            # 클라이언트에게 메시지 수신 알림 (is_user 대신 is_bot=False 사용)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message,
                    "is_bot": False,  # 사용자 메시지는 is_bot=False
                    "session_id": str(session.id),
                },
            )

            # 장소 관련 메시지가 아닌 경우 안내 메시지 전송 후 종료
            if not is_place_related:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "message": "죄송합니다. 저는 장소 추천에만 특화되어 있습니다. 지역 및 장소에 대한 질문을 해주세요.",
                        "is_bot": True,
                        "session_id": str(session.id),
                    },
                )
                print("장소 관련 메시지가 아니므로 처리 종료")
                return

            # 백그라운드에서 AI 응답 처리 (장소 관련 메시지인 경우에만 실행)
            print("AI 응답 처리 시작")
            task = asyncio.create_task(
                self.process_message_in_background(message, session)
            )
            print(f"백그라운드 태스크 생성됨: {task}")

            # 태스크 예외 처리를 위한 콜백 추가
            def handle_task_exception(task):
                try:
                    exception = task.exception()
                    if exception:
                        print(f"백그라운드 태스크 예외 발생: {exception}")
                except asyncio.CancelledError:
                    print("백그라운드 태스크가 취소됨")
                except Exception as e:
                    print(f"백그라운드 태스크 예외 처리 중 오류: {e}")

            task.add_done_callback(handle_task_exception)
            print("백그라운드 태스크 예외 처리 콜백 추가됨")

        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
        except Exception as e:
            print(f"메시지 수신 중 오류: {e}")
            import traceback

            print(f"자세한 오류: {traceback.format_exc()}")

    async def process_message_in_background(self, message, session):
        """백그라운드에서 메시지 처리"""
        animation_task = None
        try:
            print("\n=== AI 응답 처리 시작 ===")
            # LangGraph 인스턴스 대기
            print(f"=== LangGraph 준비 상태: {graph_ready.is_set()} ===")
            wait_count = 0
            while not graph_ready.is_set():
                wait_count += 1
                if wait_count % 10 == 0:  # 10번마다 로그 출력 (약 1초마다)
                    print(f"=== LangGraph 대기 중... {wait_count/10}초 경과 ===")
                await asyncio.sleep(0.1)

            print("=== LangGraph 대기 완료, 인스턴스 가져오기 시도 ===")
            try:
                graph = get_graph_instance()
                print("=== LangGraph 인스턴스 가져옴 ===")
            except Exception as graph_init_error:
                print(f"=== LangGraph 인스턴스 가져오기 실패: {graph_init_error} ===")
                raise

            # 상태 업데이트 시작 - 애니메이션 효과를 위한 반복
            ellipsis_patterns = ["", ".", "..", "..."]
            animation_count = 0

            # 애니메이션 태스크 정의
            async def animate_ellipsis():
                nonlocal animation_count
                while True:
                    pattern = ellipsis_patterns[
                        animation_count % len(ellipsis_patterns)
                    ]
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "chat_message",
                            "message": f"맞춤 장소를 찾아보는 중입니다{pattern}",
                            "is_bot": True,
                            "is_streaming": True,
                            "session_id": str(session.id),
                        },
                    )
                    animation_count += 1
                    await asyncio.sleep(0.5)  # 0.5초마다 업데이트

            # 애니메이션 시작
            print("=== 애니메이션 태스크 시작 ===")
            animation_task = asyncio.create_task(animate_ellipsis())

            # 일정 정보 가져오기 - Calendar 모델에서만 조회
            schedule_place = None
            schedule_companion = None

            try:
                # 일정 ID가 있는 경우 먼저 ID로 조회 시도
                if hasattr(self, "schedule_id"):
                    try:
                        # calendar_app의 Schedule 모델 가져오기
                        Schedule = apps.get_model("calendar_app", "Schedule")

                        # ID로 일정 조회
                        user_schedule = await database_sync_to_async(
                            lambda: Schedule.objects.filter(
                                user=self.user, id=self.schedule_id
                            ).first()
                        )()

                        if user_schedule:
                            print(
                                f"✅ 일정 ID({self.schedule_id})로 일정 정보를 성공적으로 조회했습니다."
                            )

                            # 일정 데이터 추출
                            if (
                                hasattr(user_schedule, "location")
                                and user_schedule.location
                            ):
                                schedule_place = user_schedule.location
                                print(
                                    f"✅ 일정 ID에서 장소 정보 가져옴: '{schedule_place}'"
                                )

                            if (
                                hasattr(user_schedule, "companion")
                                and user_schedule.companion
                            ):
                                schedule_companion = user_schedule.companion
                                print(
                                    f"✅ 일정 ID에서 동행자 정보 가져옴: '{schedule_companion}'"
                                )

                            # 세션 날짜 업데이트
                            if hasattr(user_schedule, "date") and user_schedule.date:
                                self.session_date = user_schedule.date
                                print(
                                    f"✅ 일정 ID에서 날짜 정보 업데이트: {self.session_date}"
                                )
                        else:
                            print(
                                f"⚠️ ID {self.schedule_id}에 해당하는 일정을 찾을 수 없습니다."
                            )
                    except Exception as e:
                        print(f"❌ 일정 ID 기반 조회 중 오류 발생: {str(e)}")

                # 일정 ID로 조회에 실패한 경우 날짜로 시도
                if not schedule_place and not schedule_companion:
                    # 날짜 데이터 준비
                    session_date = None

                # 1. 세션 객체에서 date 필드 가져오기 (가장 우선순위)
                try:
                    if hasattr(session, "date") and session.date:
                        session_date = await database_sync_to_async(
                            lambda: session.date
                        )()
                        print(f"✅ 세션 객체에서 날짜 정보 가져옴: {session_date}")
                except Exception as e:
                    print(f"❌ 세션 date 필드 접근 중 오류: {e}")

                # 2. self.session_date에서 가져오기 (connect 메서드에서 설정된 값)
                if (
                    not session_date
                    and hasattr(self, "session_date")
                    and self.session_date
                ):
                    session_date = self.session_date
                    print(f"✅ self.session_date에서 날짜 정보 가져옴: {session_date}")

                # 3. URL 파라미터에서 날짜 확인
                if not session_date:
                    try:
                        session_url_params = await database_sync_to_async(
                            lambda: (
                                session.url_params
                                if hasattr(session, "url_params") and session.url_params
                                else {}
                            )
                        )()

                        if (
                            isinstance(session_url_params, dict)
                            and "date" in session_url_params
                        ):
                            from datetime import datetime

                            date_str = session_url_params.get("date")
                            try:
                                session_date = datetime.strptime(
                                    date_str, "%Y-%m-%d"
                                ).date()
                                print(
                                    f"✅ URL 파라미터에서 날짜 정보 가져옴: {session_date}"
                                )
                            except Exception as e:
                                print(f"❌ URL 날짜 변환 실패: {e}")
                    except Exception as e:
                        print(f"❌ URL 파라미터 추출 중 오류: {e}")

                # 4. 날짜 정보가 없으면 현재 날짜 사용 (마지막 방법)
                if not session_date:
                    session_date = timezone.now().date()
                    print(
                        f"⚠️ 날짜 정보를 찾을 수 없어 현재 날짜를 사용합니다: {session_date}"
                    )

                # 세션 객체에 날짜 저장 (없는 경우에만)
                if not hasattr(session, "date") or not session.date:
                    try:
                        session.date = session_date
                        await database_sync_to_async(session.save)()
                        print(f"✅ 세션 객체에 날짜 {session_date} 저장 완료")
                    except Exception as e:
                        print(f"❌ 세션에 날짜 저장 중 오류: {e}")

                # 일정 정보 조회 준비
                print(
                    f"📅 일정 조회 - 날짜: {session_date}, 사용자: {self.user.username}"
                )

                # calendar_app의 Schedule 모델 가져오기
                try:
                    Schedule = apps.get_model("calendar_app", "Schedule")

                    # 지정된 날짜의 일정 조회
                    user_schedule = await database_sync_to_async(
                        lambda: Schedule.objects.filter(
                            user=self.user, date=session_date
                        ).first()
                    )()

                    if user_schedule:
                        # 일정 정보 추출
                        if (
                            hasattr(user_schedule, "location")
                            and user_schedule.location
                        ):
                            schedule_place = user_schedule.location
                            print(f"✅ 일정에서 장소 정보 가져옴: '{schedule_place}'")

                        if (
                            hasattr(user_schedule, "companion")
                            and user_schedule.companion
                        ):
                            schedule_companion = user_schedule.companion
                            print(
                                f"✅ 일정에서 동행자 정보 가져옴: '{schedule_companion}'"
                            )

                        print(
                            f"✅ 사용자 {self.user.username}의 {session_date} 일정 정보를 성공적으로 가져왔습니다."
                        )
                    else:
                        print(
                            f"⚠️ 사용자 {self.user.username}의 {session_date} 일정이 없습니다."
                        )
                except Exception as e:
                    print(f"❌ Schedule 모델 조회 중 오류: {e}")
            except Exception as e:
                print(f"❌ 일정 정보 조회 중 오류 발생: {str(e)}")

            # LangGraph 실행 (비동기 호출)
            print("=== LangGraph 비동기 호출 시작 ===")
            try:
                # 세션 ID를 전달
                session_id = session.id
                print(f"=== 세션 ID: {session_id} (타입: {type(session_id)}) ===")

                # 전달하는 state 객체 생성
                state = {"question": message, "session_id": session_id}

                # 일정 정보가 있으면 추가
                if schedule_place:
                    state["schedule_place"] = schedule_place
                    state["place"] = (
                        schedule_place  # 호환성을 위해 두 가지 키 모두 설정
                    )
                    print(f"✅ 그래프에 일정 장소 정보 전달: '{schedule_place}'")

                if schedule_companion:
                    state["companion"] = schedule_companion
                    state["with_who"] = (
                        schedule_companion  # 호환성을 위해 두 가지 키 모두 설정
                    )
                    print(f"✅ 그래프에 동행자 정보 전달: '{schedule_companion}'")

                print(f"📋 그래프에 전달하는 상태 객체: {state}")

                result = await graph.ainvoke(state)

                if "answer" in result:
                    content = result["answer"]
                    print(f"=== 응답 받음: 길이 {len(content)} ===")
                    print(f"=== 응답 미리보기: {content[:100]}... ===")
                    final_response = content
                else:
                    print(
                        f"=== 응답에 'answer' 키가 없음, 가능한 키: {list(result.keys())} ==="
                    )
                    final_response = ""
            except Exception as graph_error:
                print(f"❌ LangGraph 처리 중 오류: {graph_error} ===")
                final_response = f"죄송합니다, 응답을 생성하는 중에 오류가 발생했습니다: {str(graph_error)}"

            # 응답이 비어있으면 기본 응답 설정
            if not final_response or final_response.strip() == "":
                final_response = "죄송합니다, 요청하신 정보를 찾을 수 없습니다. 다른 질문을 해주시겠어요?"
                print("⚠️ 응답이 비어있어 기본 응답으로 대체합니다 ===")
            else:
                print(f"=== 최종 응답 길이: {len(final_response)} ===")
                print(f"=== 최종 응답 미리보기: {final_response[:100]}... ===")

            # 데이터베이스에 응답 저장
            print("=== 응답 데이터베이스에 저장 ===")
            await self.save_bot_response(session, final_response)

            # 최종 메시지 전송
            print("=== 최종 응답 전송 시작 ===")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": final_response,
                    "is_bot": True,
                    "is_streaming": False,
                    "session_id": str(session.id),
                },
            )
            print("✅ 최종 응답 전송 완료 ===")

        except Exception as e:
            error_message = f"오류가 발생했습니다: {str(e)}"
            print(f"=== AI 응답 생성 중 오류: {e} ===")
            import traceback

            print(f"=== 자세한 오류: {traceback.format_exc()} ===")

            # 오류 메시지 전송
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": error_message,
                    "is_bot": True,
                    "is_error": True,
                    "session_id": str(session.id),
                },
            )
        finally:
            # 애니메이션 태스크가 존재하면 취소
            if animation_task and not animation_task.done():
                print("=== 애니메이션 태스크 취소 ===")
                animation_task.cancel()
                try:
                    await animation_task
                    print("=== 애니메이션 태스크 취소 완료 ===")
                except asyncio.CancelledError:
                    print("=== 애니메이션 태스크 취소됨 ===")
                    pass

    async def chat_message(self, event):
        """채팅 메시지를 클라이언트에게 전송"""
        try:
            is_bot = event.get("is_bot", False)
            is_streaming = event.get("is_streaming", False)

            # 스트리밍이 아닌 경우에만 로그 출력
            if not is_streaming:
                message_preview = event.get("message", "")[:50]
                print(
                    f"=== 클라이언트로 메시지 전송: 타입={'봇' if is_bot else '사용자'}, 스트리밍={is_streaming}, 내용={message_preview}... ==="
                )

            # 메시지 전송
            await self.send(text_data=json.dumps(event))

            # 스트리밍이 아닌 경우에만 로그 출력
            if not is_streaming:
                print(f"=== 메시지 전송 완료: 길이={len(event.get('message', ''))} ===")

        except Exception as e:
            print(f"=== 메시지 전송 중 오류: {e} ===")
            try:
                # 오류 발생 시 간단한 오류 메시지 전송 시도
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "chat_message",
                            "message": f"메시지 전송 중 오류가 발생했습니다: {str(e)}",
                            "is_bot": True,
                            "is_error": True,
                            "session_id": event.get("session_id", "unknown"),
                        }
                    )
                )
            except Exception as e2:
                print(f"=== 오류 메시지 전송 시도 중 2차 오류: {e2} ===")

    @database_sync_to_async
    def load_chat_history(self):
        # 현재 세션의 모든 메시지를 시간순으로 가져옴
        try:
            # room_name 대신 id 필드 사용 (room_name은 URL에서 가져온 세션 ID)
            session = ChatSession.objects.filter(id=self.room_name).first()
            if session:
                messages = ChatMessage.objects.filter(session=session).order_by(
                    "created_at"
                )
                return [
                    {
                        "content": msg.content,
                        "is_user": not msg.is_bot,
                        "timestamp": msg.created_at.isoformat(),
                    }
                    for msg in messages
                ]
            return []
        except Exception as e:
            print(f"채팅 히스토리 로드 중 오류: {e}")
            return []

    @database_sync_to_async
    def save_message_and_get_response(self, message, session_id):
        # 사용자 메시지 저장
        try:
            # session_id가 있으면 해당 세션을 사용하고, 없으면 self.room_name(URL의 세션 ID)을 사용
            session_id_to_use = session_id if session_id else self.room_name

            # room_name 필드 제거하고 id로 세션 찾기
            try:
                session = ChatSession.objects.get(id=session_id_to_use)
                created = False
            except ChatSession.DoesNotExist:
                # 세션이 없으면 새로 생성
                session = ChatSession.objects.create(
                    user=self.user, title=f"새 채팅 {self.user.username}"
                )
                created = True

            ChatMessage.objects.create(session=session, content=message, is_bot=False)
            return session, created
        except Exception as e:
            print(f"메시지 저장 중 오류: {e}")
            # 오류 발생 시 기본적으로 새 세션 생성
            session = ChatSession.objects.create(
                user=self.user, title=f"오류 복구 채팅 {self.user.username}"
            )
            ChatMessage.objects.create(session=session, content=message, is_bot=False)
            return session, True

    @database_sync_to_async
    def save_bot_response(self, session, response):
        ChatMessage.objects.create(session=session, content=response, is_bot=True)

    @database_sync_to_async
    def get_user_from_username(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_or_create_session(self, session_id, date_param=None):
        """세션 ID로 세션을 가져오거나 생성하고 날짜 정보를 설정"""
        from .models import ChatSession

        try:
            # 먼저 ID로 조회
            session = ChatSession.objects.filter(id=session_id).first()

            # 세션을 찾은 경우 날짜 정보 업데이트
            if session and date_param:
                try:
                    from datetime import datetime

                    session_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                    session.date = session_date
                    session.save()
                    print(
                        f"✅ 기존 세션 {session_id}의 날짜를 {session_date}로 업데이트"
                    )
                except Exception as e:
                    print(f"❌ 기존 세션 날짜 업데이트 중 오류: {e}")
                return session

            elif session:
                print(f"✅ 기존 세션 {session_id}를 찾음 (날짜 파라미터 없음)")
                return session

            # ID가 문자열인 경우 세션 ID로 조회 (이전 버전 호환)
            session = ChatSession.objects.filter(session_id=session_id).first()
            if session:
                # 세션을 찾은 경우 날짜 정보 업데이트
                if date_param:
                    try:
                        from datetime import datetime

                        session_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                        session.date = session_date
                        session.save()
                        print(
                            f"✅ session_id로 찾은 세션 {session_id}의 날짜를 {session_date}로 업데이트"
                        )
                    except Exception as e:
                        print(f"❌ session_id로 찾은 세션 날짜 업데이트 중 오류: {e}")
                return session

            # 존재하지 않으면 새로 생성 (날짜 정보 포함)
            new_session_data = {
                "id": session_id,
                "user": self.user,
                "title": f"새 채팅 {self.user.username}",
            }

            # 날짜 파라미터가 있으면 추가
            if date_param:
                try:
                    from datetime import datetime

                    session_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                    new_session_data["date"] = session_date
                    print(f"✅ 새 세션 {session_id}에 날짜 {session_date} 설정")
                except Exception as e:
                    print(f"❌ 새 세션 날짜 설정 중 오류: {e}")

            new_session = ChatSession.objects.create(**new_session_data)
            print(f"✅ 새 세션 생성됨: {session_id}")
            return new_session
        except Exception as e:
            print(f"❌ 세션 가져오기/생성 중 오류: {e}")
            # 오류 발생 시 기본 세션 생성
            default_session = ChatSession.objects.create(
                user=self.user, title=f"오류 복구 채팅 {self.user.username}"
            )
            # 날짜 파라미터가 있으면 기본 세션에도 설정
            if date_param:
                try:
                    from datetime import datetime

                    session_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                    default_session.date = session_date
                    default_session.save()
                    print(f"✅ 오류 복구 세션에 날짜 {session_date} 설정")
                except Exception as e:
                    print(f"❌ 오류 복구 세션 날짜 설정 중 오류: {e}")

            return default_session

    async def process_message(self, user_message, session_id):
        """
        사용자 메시지 처리 및 AI 응답 생성
        """
        try:
            # 사용자 메시지 저장 및 응답 처리 준비
            print(f"추출된 메시지: '{user_message}', 세션 ID: {session_id}")
            session, created = await self.save_message_and_get_response(
                user_message, session_id
            )
            print(f"메시지 저장 완료, 새 세션: {created}")

            # AI 응답 생성
            print("AI 응답 처리 시작")

            # 그래프 인스턴스 가져오기
            print("\n=== AI 응답 처리 시작 ===")
            graph = await get_graph_instance()
            print("=== LangGraph 인스턴스 가져옴 ===")

            print("=== LangGraph 비동기 호출 시작 ===")
            print(f"=== 세션 ID: {session.id} (타입: {type(session.id)}) ===")

            # 사용자 메시지를 그래프에 전달
            state = {"question": user_message, "session_id": session.id}

            # URL에서 추출한 일정 정보 추가
            if hasattr(self, "location") and self.location:
                state["schedule_place"] = self.location
                state["place"] = self.location  # 호환성을 위해 두 가지 키 모두 사용

            if hasattr(self, "companion") and self.companion:
                state["companion"] = self.companion
                state["with_who"] = self.companion  # 호환성을 위해 두 가지 키 모두 사용

            # 메시지 처리를 위한 이벤트 전송
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": user_message,
                    "is_bot": False,
                    "is_streaming": False,
                    "session_id": session.id,
                },
            )
            print(
                f"=== 클라이언트로 메시지 전송: 타입=사용자, 스트리밍=False, 내용={user_message[:50] if len(user_message) > 50 else user_message}... ==="
            )
            print(f"=== 메시지 전송 완료: 길이={len(user_message)} ===")

            # 그래프 비동기 실행
            result = await graph.ainvoke(state)

            # 결과에서 응답 추출
            response = await self.get_response_from_graph_result(result)

            # 응답 메시지 저장
            await self.save_bot_response(session, response)

            # 응답 메시지를 클라이언트에게 전송
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": response,
                    "is_bot": True,
                    "is_streaming": False,
                    "session_id": session.id,
                },
            )

            print(f"=== 응답 받음: 길이 {len(response)} ===")
            print(f"=== 응답 미리보기: \n{response[:150]}... ===")

            return response
        except Exception as e:
            error_response = f"죄송합니다. 오류가 발생했습니다: {str(e)}"
            print(f"메시지 처리 중 오류 발생: {str(e)}")

            # 오류 메시지를 클라이언트에게 전송
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": error_response,
                    "is_bot": True,
                    "is_error": True,
                    "is_streaming": False,
                    "session_id": session_id,
                },
            )
            return error_response
