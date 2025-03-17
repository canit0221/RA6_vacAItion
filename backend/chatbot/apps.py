from django.apps import AppConfig
import threading
import os
from .RAG_minor_sep import setup_rag

# RAG 체인 인스턴스 및 상태 관리
_rag_instance = None
_rag_ready = threading.Event()
_initialization_lock = threading.Lock()


class ChatbotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chatbot"

    def ready(self):
        """서버 시작 시 RAG 체인 초기화"""
        # 자동 리로드 시 중복 초기화 방지
        if os.environ.get("RUN_MAIN") != "true":
            return

        global _rag_instance, _rag_ready

        def initialize_in_background():
            global _rag_instance, _rag_ready
            with _initialization_lock:
                if _rag_instance is not None:
                    return

                try:
                    print("\n=== 서버 시작: RAG 체인 초기화 시작 ===")
                    _rag_instance = setup_rag("")
                    _rag_ready.set()
                    print("=== RAG 체인 초기화 완료 ===\n")
                except Exception as e:
                    print(f"=== RAG 체인 초기화 실패: {e} ===\n")

        # 백그라운드 스레드에서 초기화 실행
        threading.Thread(target=initialize_in_background, daemon=True).start()


def get_rag_instance():
    """초기화된 RAG 체인 인스턴스 반환"""
    if not _rag_ready.is_set():
        print("RAG 체인이 아직 초기화되지 않았습니다.")
        return None
    return _rag_instance
