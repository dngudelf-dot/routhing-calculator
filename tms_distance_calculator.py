# -*- coding: utf-8 -*-
"""
간단한 배차 관리 시스템 (TMS) - 거리 및 시간 계산 스크립트

이 스크립트는 Kakao Mobility API를 활용하여 주소를 검증하고,
입력된 순서대로 경로를 계산하여 운행 거리와 시간을 산출합니다.

[API 키 발급 방법]
1. Kakao Developers (https://developers.kakao.com/) 접속
2. 로그인 후 '내 애플리케이션' 클릭
3. '애플리케이션 추가하기' 버튼 클릭 후 앱 생성
4. 생성된 앱의 'REST API 키'를 복사하여 아래 REST_API_KEY 변수에 입력
5. '플랫폼' 메뉴에서 웹 플랫폼 등록 (도메인: http://localhost)
6. 'Kakao 모빌리티' API 활성화 필요 (유료)

[필요 라이브러리]
pip install requests
"""

import requests
from typing import Optional, Tuple, List, Dict

# ============================================================
# 🔑 여기에 Kakao REST API 키를 입력하세요
# ============================================================
REST_API_KEY = "cd01fa982c683377a6e68e1d3f92e4ed"

# ============================================================
# API 엔드포인트
# ============================================================
KAKAO_LOCAL_API_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_DIRECTIONS_API_URL = "https://apis-navi.kakaomobility.com/v1/directions"


def validate_address(address: str) -> Optional[Tuple[float, float, str]]:
    """
    주소 검증 (Geocoding)
    
    입력받은 주소(문자열)를 위도/경도 좌표로 변환합니다.
    1차: 주소 검색 API 시도
    2차: 키워드 검색 API 시도
    
    Args:
        address: 검증할 주소 문자열
        
    Returns:
        (경도, 위도, 도로명주소) 튜플 또는 None (검증 실패 시)
    """
    headers = {
        "Authorization": f"KakaoAK {REST_API_KEY}"
    }
    
    # 1차: 주소 검색 시도
    try:
        response = requests.get(
            KAKAO_LOCAL_API_URL, 
            headers=headers, 
            params={"query": address}, 
            timeout=10,
            verify=False
        )
        response.raise_for_status()
        
        data = response.json()
        documents = data.get("documents", [])
        
        if documents:
            result = documents[0]
            x = float(result.get("x"))
            y = float(result.get("y"))
            road_address = result.get("road_address")
            if road_address:
                formatted_address = road_address.get("address_name", address)
            else:
                formatted_address = result.get("address_name", address)
            return (x, y, formatted_address)
    except Exception:
        pass
    
    # 2차: 키워드 검색 시도
    try:
        response = requests.get(
            KAKAO_KEYWORD_API_URL, 
            headers=headers, 
            params={"query": address}, 
            timeout=10,
            verify=False
        )
        response.raise_for_status()
        
        data = response.json()
        documents = data.get("documents", [])
        
        if documents:
            result = documents[0]
            x = float(result.get("x"))
            y = float(result.get("y"))
            place_name = result.get("place_name", "")
            road_address = result.get("road_address_name", "")
            formatted_address = road_address if road_address else result.get("address_name", address)
            return (x, y, formatted_address)
    except Exception:
        pass
    
    print(f"  ❌ 주소 검색 결과 없음: '{address}'")
    return None


def _try_route(origin_x: float, origin_y: float, dest_x: float, dest_y: float) -> Optional[Tuple[int, int, int]]:
    """단일 경로 계산 시도 (내부 함수) - result_code도 함께 반환"""
    headers = {
        "Authorization": f"KakaoAK {REST_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {
        "origin": f"{origin_x},{origin_y}",
        "destination": f"{dest_x},{dest_y}",
        "priority": "RECOMMEND"
    }
    
    try:
        response = requests.get(KAKAO_DIRECTIONS_API_URL, headers=headers, params=params, timeout=15, verify=False)
        response.raise_for_status()
        
        data = response.json()
        routes = data.get("routes", [])
        
        if not routes:
            return None
        
        route = routes[0]
        result_code = route.get("result_code", 0)
        
        if result_code != 0:
            return (0, 0, result_code)  # 에러 코드 반환
        
        summary = route.get("summary", {})
        distance = summary.get("distance", 0)
        duration = summary.get("duration", 0)
        
        return (distance, duration, 0)  # 성공
        
    except Exception:
        return None


def calculate_route(
    origin_x: float, origin_y: float,
    dest_x: float, dest_y: float
) -> Optional[Tuple[int, int]]:
    """
    경로 계산 (Routing)
    105 에러(도로 접근 불가) 발생 시 주변 좌표로 자동 재시도
    
    Args:
        origin_x: 출발지 경도
        origin_y: 출발지 위도
        dest_x: 도착지 경도
        dest_y: 도착지 위도
        
    Returns:
        (거리(미터), 소요시간(초)) 튜플 또는 None (계산 실패 시)
    """
    # 1차 시도: 원본 좌표
    result = _try_route(origin_x, origin_y, dest_x, dest_y)
    
    if result is None:
        print("  ❌ 경로를 찾을 수 없습니다.")
        return None
    
    distance, duration, result_code = result
    
    # 성공 시 바로 반환
    if result_code == 0 and distance > 0:
        return (distance, duration)
    
    # 104~106 에러(도로 접근 불가) 발생 시 주변 좌표로 재시도
    if result_code in [104, 105, 106]:
        print(f"  ⚠️ 도로 접근 불가 (코드 {result_code}) - 주변 좌표로 재시도 중...")
        offsets = [
            (0.0005, 0), (-0.0005, 0),
            (0, 0.0005), (0, -0.0005),
            (0.0005, 0.0005), (-0.0005, 0.0005),
            (-0.0005, -0.0005), (0.0005, -0.0005),
            (0.001, 0), (-0.001, 0),
            (0, 0.001), (0, -0.001),
        ]
        
        for dx, dy in offsets:
            adj_result = _try_route(origin_x + dx, origin_y + dy, dest_x, dest_y)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                print(f"     ✅ 보정된 좌표로 성공!")
                return (adj_result[0], adj_result[1])
            
            adj_result = _try_route(origin_x, origin_y, dest_x + dx, dest_y + dy)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                print(f"     ✅ 보정된 좌표로 성공!")
                return (adj_result[0], adj_result[1])
            
            adj_result = _try_route(origin_x + dx, origin_y + dy, dest_x + dx, dest_y + dy)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                print(f"     ✅ 보정된 좌표로 성공!")
                return (adj_result[0], adj_result[1])
        
        print(f"  ❌ 주변 좌표로도 경로를 찾을 수 없습니다.")
    
    return None


def format_duration(total_seconds: int) -> str:
    """
    초 단위 시간을 '시간 분' 형식으로 변환합니다.
    0시간일 경우 분만 표시합니다.
    
    Args:
        total_seconds: 총 소요 시간 (초)
        
    Returns:
        형식화된 시간 문자열
    """
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}시간 {minutes}분"
    else:
        return f"{minutes}분"


def format_distance(meters: int) -> str:
    """
    미터 단위 거리를 km로 변환합니다.
    소수점 첫째 자리까지 반올림합니다.
    
    Args:
        meters: 거리 (미터)
        
    Returns:
        형식화된 거리 문자열 (km)
    """
    km = round(meters / 1000, 1)
    return f"{km} km"


def get_user_input_address(prompt: str) -> Tuple[float, float, str]:
    """
    사용자로부터 주소를 입력받고 유효성을 검증합니다.
    유효하지 않으면 재입력을 요구합니다.
    
    Args:
        prompt: 사용자에게 보여줄 입력 프롬프트
        
    Returns:
        (경도, 위도, 검증된 주소) 튜플
    """
    while True:
        address = input(prompt).strip()
        
        if not address:
            print("  ⚠️  주소를 입력해주세요.\n")
            continue
        
        print(f"  🔍 주소 검증 중: '{address}'")
        result = validate_address(address)
        
        if result:
            x, y, formatted_address = result
            print(f"  ✅ 검증 완료: {formatted_address}")
            print(f"     좌표: ({y}, {x})\n")
            return (x, y, formatted_address)
        else:
            print("  ⚠️  유효하지 않은 주소입니다. 다시 입력해주세요.\n")


def main():
    """
    메인 함수: 배차 관리 시스템 실행
    """
    print("=" * 60)
    print("🚛 간단한 배차 관리 시스템 (TMS) - 거리/시간 계산기")
    print("=" * 60)
    print()
    
    # API 키 확인
    if REST_API_KEY == "YOUR_KAKAO_REST_API_KEY":
        print("❌ 오류: REST_API_KEY를 설정해주세요.")
        print("   코드 상단의 REST_API_KEY 변수에 Kakao REST API 키를 입력하세요.")
        return
    
    # --------------------------------------------------------
    # Step 1: 상차지(출발지) 주소 입력 및 검증
    # --------------------------------------------------------
    print("📍 [Step 1] 상차지(출발지) 주소 입력")
    print("-" * 40)
    origin_x, origin_y, origin_name = get_user_input_address("상차지 주소를 입력하세요: ")
    
    # --------------------------------------------------------
    # Step 2: 거래처 데이터 정의 (예시 데이터)
    # --------------------------------------------------------
    print("📦 [Step 2] 거래처 데이터 로드")
    print("-" * 40)
    
    # 테스트용 예시 데이터 (3개 이상의 거래처)
    # 실제 사용 시 이 데이터를 수정하거나 외부에서 입력받도록 변경
    customers: List[Dict] = [
        {
            "거래처명": "강남 물류센터",
            "거래처주소": "서울특별시 강남구 테헤란로 152",
            "운행순번": 1
        },
        {
            "거래처명": "판교 배송센터",
            "거래처주소": "경기도 성남시 분당구 판교역로 235",
            "운행순번": 2
        },
        {
            "거래처명": "수원 창고",
            "거래처주소": "경기도 수원시 영통구 광교중앙로 170",
            "운행순번": 3
        },
        {
            "거래처명": "용인 물류단지",
            "거래처주소": "경기도 용인시 기흥구 동백중앙로 191",
            "운행순번": 4
        }
    ]
    
    print(f"  📋 총 {len(customers)}개 거래처 데이터 로드 완료\n")
    
    # 거래처 주소 검증
    print("📍 [Step 2-1] 거래처 주소 검증")
    print("-" * 40)
    
    validated_customers = []
    for customer in customers:
        name = customer["거래처명"]
        address = customer["거래처주소"]
        sequence = customer["운행순번"]
        
        print(f"  🔍 [{sequence}] {name}: '{address}'")
        result = validate_address(address)
        
        if result:
            x, y, formatted_address = result
            validated_customers.append({
                "거래처명": name,
                "거래처주소": formatted_address,
                "운행순번": sequence,
                "경도": x,
                "위도": y
            })
            print(f"     ✅ 검증 완료\n")
        else:
            print(f"     ❌ 검증 실패 - 해당 거래처 건너뜀\n")
    
    if not validated_customers:
        print("❌ 유효한 거래처가 없습니다. 프로그램을 종료합니다.")
        return
    
    # --------------------------------------------------------
    # Step 3: 운행 순번에 따라 거래처 정렬
    # --------------------------------------------------------
    print("🔢 [Step 3] 운행 순번 정렬")
    print("-" * 40)
    validated_customers.sort(key=lambda x: x["운행순번"])
    print("  ✅ 운행 순번에 따라 정렬 완료")
    print("  📋 배송 순서:")
    for idx, customer in enumerate(validated_customers, 1):
        print(f"     {idx}. {customer['거래처명']}")
    print()
    
    # --------------------------------------------------------
    # Step 4: 구간별 경로 계산
    # --------------------------------------------------------
    print("🛣️  [Step 4] 구간별 경로 계산")
    print("-" * 40)
    
    route_results = []
    total_distance = 0  # 총 거리 (미터)
    total_duration = 0  # 총 시간 (초)
    
    # 현재 위치 (시작: 상차지)
    current_x, current_y = origin_x, origin_y
    current_name = origin_name.split()[-1] if len(origin_name.split()) > 2 else origin_name  # 간략한 이름
    
    for customer in validated_customers:
        dest_name = customer["거래처명"]
        dest_x = customer["경도"]
        dest_y = customer["위도"]
        
        print(f"  🔄 계산 중: {current_name} → {dest_name}")
        
        result = calculate_route(current_x, current_y, dest_x, dest_y)
        
        if result:
            distance, duration = result
            total_distance += distance
            total_duration += duration
            
            route_results.append({
                "출발지": current_name,
                "도착지": dest_name,
                "거리": distance,
                "시간": duration
            })
            print(f"     ✅ 완료 (거리: {format_distance(distance)}, 시간: {format_duration(duration)})\n")
        else:
            print(f"     ❌ 경로 계산 실패\n")
            route_results.append({
                "출발지": current_name,
                "도착지": dest_name,
                "거리": 0,
                "시간": 0,
                "오류": True
            })
        
        # 다음 구간을 위해 현재 위치 업데이트
        current_x, current_y = dest_x, dest_y
        current_name = dest_name
    
    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------
    print()
    print("=" * 60)
    print("📊 운행 결과 보고서")
    print("=" * 60)
    print()
    
    # 구간별 상세 정보
    print("📍 구간별 상세 정보")
    print("-" * 40)
    
    for idx, route in enumerate(route_results, 1):
        origin = route["출발지"]
        destination = route["도착지"]
        
        if route.get("오류"):
            print(f"  [{idx}구간] {origin} → {destination}")
            print(f"      ⚠️  경로 계산 실패")
        else:
            distance_str = format_distance(route["거리"])
            duration_str = format_duration(route["시간"])
            
            print(f"  [{idx}구간] {origin} → {destination}")
            print(f"      📏 이동 거리: {distance_str}")
            print(f"      ⏱️  이동 시간: {duration_str}")
        print()
    
    # 최종 합계
    print("-" * 40)
    print("📈 최종 합계")
    print("-" * 40)
    print(f"  🚛 총 운행 거리: {format_distance(total_distance)}")
    print(f"  ⏱️  총 운행 시간: {format_duration(total_duration)}")
    print()
    print("=" * 60)
    print("✅ 계산 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
