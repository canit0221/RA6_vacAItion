import os
import sys
from datetime import datetime

# Django 프로젝트 설정을 로드하기 위한 환경 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vacation.settings")

# django.setup() 제거 - Django 앱이 이미 초기화된 상태에서 호출되도록 함

def get_schedule_info(date_str):
    """
    주어진 날짜의 일정 정보(장소, 동행)를 가져옵니다.
    
    Args:
        date_str: 'YYYY-MM-DD' 형식의 날짜 문자열
    
    Returns:
        tuple: (위치, 동행) 또는 일정이 없으면 (None, None)
    """
    try:
        # Django가 초기화된 상태에서 모델 import
        from calendar_app.models import Schedule
        
        # 문자열을 날짜 객체로 변환
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 해당 날짜의 일정 조회
        schedules = Schedule.objects.filter(date=date_obj)
        
        if schedules.exists():
            # 해당 날짜의 모든 일정 출력
            print(f"'{date_str}' 날짜의 일정 정보:")
            for idx, schedule in enumerate(schedules, 1):
                print(f"일정 {idx}:")
                print(f"  - 장소: {schedule.location}")
                print(f"  - 동행: {schedule.companion}")
                if schedule.memo:
                    print(f"  - 메모: {schedule.memo}")
                print()
                
            # 첫 번째 일정의 장소와 동행 반환
            return schedules[0].location, schedules[0].companion
        else:
            print(f"'{date_str}' 날짜의 일정이 없습니다.")
            return None, None
            
    except Exception as e:
        print(f"오류 발생: {e}")
        return None, None

def get_schedule_by_id(schedule_id):
    """
    주어진 ID의 일정 정보(장소, 동행)를 가져옵니다.
    
    Args:
        schedule_id: 일정 ID
    
    Returns:
        tuple: (위치, 동행) 또는 일정이 없으면 (None, None)
    """
    try:
        # Django가 초기화된 상태에서 모델 import
        from calendar_app.models import Schedule
        
        # ID로 일정 조회
        try:
            schedule = Schedule.objects.get(id=schedule_id)
            
            print(f"ID '{schedule_id}'의 일정 정보:")
            print(f"  - 날짜: {schedule.date}")
            print(f"  - 장소: {schedule.location}")
            print(f"  - 동행: {schedule.companion}")
            if schedule.memo:
                print(f"  - 메모: {schedule.memo}")
            
            # 일정의 장소와 동행 반환
            return schedule.location, schedule.companion
            
        except Schedule.DoesNotExist:
            print(f"ID '{schedule_id}'의 일정이 없습니다.")
            return None, None
            
    except Exception as e:
        print(f"오류 발생: {e}")
        return None, None

if __name__ == "__main__":
    # 직접 실행할 때는 Django 초기화 필요
    import django
    django.setup()
    
    # 2025-03-27 날짜의 일정 정보 가져오기
    target_date = "2025-03-27"
    location, companion = get_schedule_info(target_date)
    
    if location and companion:
        print(f"\n요약 - {target_date}의 일정:")
        print(f"장소: {location}")
        print(f"동행: {companion}") 