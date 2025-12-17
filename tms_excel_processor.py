# -*- coding: utf-8 -*-
"""
배차 관리 시스템 (TMS) - 엑셀 기반 버전

이 스크립트는 엑셀 파일을 입력받아 배송호차별로 경로를 계산하고
결과를 엑셀 파일로 출력합니다.

[필수 라이브러리 설치]
pip install pandas openpyxl requests

[사용 방법]
1. 스크립트 실행: python tms_excel_processor.py
2. 옵션 선택:
   - 1번: 양식 다운로드 (input_template.xlsx)
   - 2번: 데이터 업로드 및 배차 시작
3. 상차지 주소 입력
4. 엑셀 파일 경로 입력
5. 결과 확인: dispatch_result.xlsx

[API 키 발급 방법]
1. Kakao Developers (https://developers.kakao.com/) 접속
2. 로그인 후 '내 애플리케이션' 클릭
3. 앱 생성 후 REST API 키 복사
4. ⚠️ Directions API 사용 시 Kakao 모빌리티 서비스 활성화 필요 (유료)
"""

import os
import requests
import pandas as pd
from typing import Optional, Tuple, List, Dict
from datetime import datetime

# ============================================================
# 🔑 Kakao REST API 키
# ============================================================
REST_API_KEY = "cd01fa982c683377a6e68e1d3f92e4ed"

# ============================================================
# API 엔드포인트
# ============================================================
KAKAO_LOCAL_API_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_DIRECTIONS_API_URL = "https://apis-navi.kakaomobility.com/v1/directions"


# ============================================================
# 1. 주소 검증 함수 (Geocoding)
# ============================================================
def validate_address(address: str) -> Optional[Tuple[float, float, str]]:
    """
    주소를 위도/경도 좌표로 변환합니다.
    1차: 주소 검색 API 시도
    2차: 키워드 검색 API 시도
    
    Args:
        address: 검증할 주소 문자열
        
    Returns:
        (경도, 위도, 도로명주소) 튜플 또는 None
    """
    headers = {"Authorization": f"KakaoAK {REST_API_KEY}"}
    
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
    
    return None


# ============================================================
# 2. 경로 계산 함수 (Routing)
# ============================================================
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
        response = requests.get(
            KAKAO_DIRECTIONS_API_URL, 
            headers=headers, 
            params=params, 
            timeout=15,
            verify=False
        )
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
    두 좌표 간 경로를 계산합니다.
    105 에러(도로 접근 불가) 발생 시 주변 좌표로 자동 재시도
    
    Args:
        origin_x, origin_y: 출발지 좌표 (경도, 위도)
        dest_x, dest_y: 도착지 좌표 (경도, 위도)
        
    Returns:
        (거리(미터), 소요시간(초)) 튜플 또는 None
    """
    # 1차 시도: 원본 좌표
    result = _try_route(origin_x, origin_y, dest_x, dest_y)
    
    if result is None:
        return None
    
    distance, duration, result_code = result
    
    # 성공 시 바로 반환
    if result_code == 0 and distance > 0:
        return (distance, duration)
    
    # 104~106 에러(도로 접근 불가) 발생 시 주변 좌표로 재시도
    if result_code in [104, 105, 106]:
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
                return (adj_result[0], adj_result[1])
            
            adj_result = _try_route(origin_x, origin_y, dest_x + dx, dest_y + dy)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                return (adj_result[0], adj_result[1])
            
            adj_result = _try_route(origin_x + dx, origin_y + dy, dest_x + dx, dest_y + dy)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                return (adj_result[0], adj_result[1])
    
    return None


# ============================================================
# 3. 단위 변환 함수
# ============================================================
def meters_to_km(meters: int) -> float:
    """미터를 km로 변환 (소수점 첫째 자리)"""
    return round(meters / 1000, 1)


def seconds_to_minutes(seconds: int) -> int:
    """초를 분으로 변환"""
    return round(seconds / 60)


def format_duration(total_seconds: int) -> str:
    """초를 '0시간 0분' 형식으로 변환"""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}시간 {minutes}분"
    else:
        return f"{minutes}분"


# ============================================================
# 4. 엑셀 양식 생성 함수
# ============================================================
def create_template(output_path: str = "input_template.xlsx") -> str:
    """
    입력용 엑셀 양식을 생성합니다.
    
    Args:
        output_path: 저장할 파일 경로
        
    Returns:
        생성된 파일 경로
    """
    # 샘플 데이터 포함
    sample_data = {
        "배송호차": ["1호차", "1호차", "1호차", "2호차", "2호차", "3호차", "3호차", "3호차"],
        "운행순번": [1, 2, 3, 1, 2, 1, 2, 3],
        "거래처명": [
            "강남 물류센터", "판교 배송센터", "수원 창고",
            "인천 물류창고", "부천 배송센터",
            "일산 물류센터", "파주 배송센터", "김포 창고"
        ],
        "거래처주소": [
            "서울특별시 강남구 테헤란로 152",
            "경기도 성남시 분당구 판교역로 235",
            "경기도 수원시 영통구 광교중앙로 170",
            "인천광역시 연수구 센트럴로 194",
            "경기도 부천시 원미구 부일로 309",
            "경기도 고양시 일산동구 중앙로 1261",
            "경기도 파주시 금릉역로 87",
            "경기도 김포시 양촌읍 김포대로 1243"
        ]
    }
    
    df = pd.DataFrame(sample_data)
    df.to_excel(output_path, index=False, engine='openpyxl')
    
    return output_path


# ============================================================
# 5. 배송호차 그룹 처리 함수
# ============================================================
def process_group(
    group_name: str, 
    group_df: pd.DataFrame, 
    origin_coords: Tuple[float, float, str]
) -> List[Dict]:
    """
    특정 배송호차 그룹의 경로를 계산합니다.
    
    Args:
        group_name: 배송호차명
        group_df: 해당 호차의 데이터프레임
        origin_coords: 상차지 좌표 (경도, 위도, 주소)
        
    Returns:
        계산 결과 리스트
    """
    results = []
    
    # 운행순번으로 정렬
    group_df = group_df.sort_values('운행순번').reset_index(drop=True)
    
    # 현재 위치 (시작: 상차지)
    current_x, current_y = origin_coords[0], origin_coords[1]
    current_name = "상차지"
    
    # 누적 거리/시간
    cumulative_distance = 0
    cumulative_duration = 0
    
    print(f"\n  📦 [{group_name}] 처리 중... (총 {len(group_df)}개 거래처)")
    
    for idx, row in group_df.iterrows():
        sequence = int(row['운행순번'])
        customer_name = row['거래처명']
        customer_address = row['거래처주소']
        
        # 도착지 주소 검증
        dest_result = validate_address(customer_address)
        
        if not dest_result:
            # 주소 검증 실패
            print(f"     ⚠️  [{sequence}] {customer_name}: 주소 확인 필요")
            results.append({
                "배송호차": group_name,
                "운행순번": sequence,
                "출발지": current_name,
                "도착지": customer_name,
                "구간거리(km)": "-",
                "구간소요시간(분)": "-",
                "누적거리(km)": meters_to_km(cumulative_distance),
                "누적시간": format_duration(cumulative_duration),
                "비고": "주소 확인 필요"
            })
            # 경로 계산 실패해도 다음 거래처 진행을 위해 주소 그대로 유지
            current_name = customer_name
            continue
        
        dest_x, dest_y, dest_formatted = dest_result
        
        # 경로 계산
        route_result = calculate_route(current_x, current_y, dest_x, dest_y)
        
        if route_result:
            distance, duration = route_result
            cumulative_distance += distance
            cumulative_duration += duration
            
            print(f"     ✅ [{sequence}] {customer_name}: {meters_to_km(distance)}km, {seconds_to_minutes(duration)}분")
            
            results.append({
                "배송호차": group_name,
                "운행순번": sequence,
                "출발지": current_name,
                "도착지": customer_name,
                "구간거리(km)": meters_to_km(distance),
                "구간소요시간(분)": seconds_to_minutes(duration),
                "누적거리(km)": meters_to_km(cumulative_distance),
                "누적시간": format_duration(cumulative_duration),
                "비고": ""
            })
        else:
            # 경로 계산 실패
            print(f"     ⚠️  [{sequence}] {customer_name}: 경로 계산 실패")
            results.append({
                "배송호차": group_name,
                "운행순번": sequence,
                "출발지": current_name,
                "도착지": customer_name,
                "구간거리(km)": "-",
                "구간소요시간(분)": "-",
                "누적거리(km)": meters_to_km(cumulative_distance),
                "누적시간": format_duration(cumulative_duration),
                "비고": "경로 계산 실패"
            })
        
        # 다음 구간을 위해 현재 위치 업데이트
        current_x, current_y = dest_x, dest_y
        current_name = customer_name
    
    return results, cumulative_distance, cumulative_duration


# ============================================================
# 6. 결과 엑셀 저장 함수
# ============================================================
def save_to_excel(
    results: List[Dict], 
    summary: List[Dict],
    output_path: str = "dispatch_result.xlsx"
) -> str:
    """
    계산 결과를 엑셀 파일로 저장합니다.
    
    Args:
        results: 구간별 계산 결과 리스트
        summary: 호차별 요약 정보 리스트
        output_path: 저장할 파일 경로
        
    Returns:
        저장된 파일 경로
    """
    # 결과 데이터프레임 생성
    df_results = pd.DataFrame(results)
    df_summary = pd.DataFrame(summary)
    
    # 엑셀 파일 저장 (여러 시트)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_results.to_excel(writer, sheet_name='배송상세', index=False)
        df_summary.to_excel(writer, sheet_name='호차별요약', index=False)
    
    return output_path


# ============================================================
# 7. 사용자 입력 함수
# ============================================================
def get_origin_address() -> Tuple[float, float, str]:
    """
    상차지 주소를 입력받고 검증합니다.
    
    Returns:
        (경도, 위도, 주소) 튜플
    """
    while True:
        address = input("\n📍 상차지(출발지) 주소를 입력하세요: ").strip()
        
        if not address:
            print("  ⚠️  주소를 입력해주세요.")
            continue
        
        print(f"  🔍 주소 검증 중...")
        result = validate_address(address)
        
        if result:
            x, y, formatted = result
            print(f"  ✅ 상차지 확인: {formatted}")
            return (x, y, formatted)
        else:
            print("  ❌ 유효하지 않은 주소입니다. 다시 입력해주세요.")


def get_excel_path() -> str:
    """
    엑셀 파일 경로를 입력받습니다.
    
    Returns:
        엑셀 파일 경로
    """
    while True:
        path = input("\n📁 엑셀 파일 경로를 입력하세요: ").strip()
        
        # 따옴표 제거
        path = path.strip('"').strip("'")
        
        if not path:
            print("  ⚠️  파일 경로를 입력해주세요.")
            continue
        
        if not os.path.exists(path):
            print(f"  ❌ 파일을 찾을 수 없습니다: {path}")
            continue
        
        if not path.lower().endswith(('.xlsx', '.xls')):
            print("  ❌ 엑셀 파일(.xlsx 또는 .xls)만 지원됩니다.")
            continue
        
        return path


# ============================================================
# 8. 메인 함수
# ============================================================
def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚛 배차 관리 시스템 (TMS) - 엑셀 기반 버전")
    print("=" * 60)
    
    # 메뉴 선택
    print("\n📋 메뉴를 선택하세요:")
    print("  [1] 양식 다운로드 (input_template.xlsx)")
    print("  [2] 데이터 업로드 및 배차 시작")
    print("  [0] 종료")
    
    while True:
        choice = input("\n선택: ").strip()
        
        if choice == "0":
            print("\n프로그램을 종료합니다. 👋")
            return
        
        elif choice == "1":
            # 양식 다운로드
            output = create_template()
            print(f"\n✅ 양식 파일이 생성되었습니다: {output}")
            print("   양식을 작성한 후 [2]번을 선택하여 배차를 시작하세요.")
        
        elif choice == "2":
            # 데이터 업로드 및 처리
            
            # 상차지 주소 입력
            origin_coords = get_origin_address()
            
            # 엑셀 파일 경로 입력
            excel_path = get_excel_path()
            
            print(f"\n📊 엑셀 파일 로딩 중...")
            
            try:
                # 엑셀 데이터 로드
                df = pd.read_excel(excel_path, engine='openpyxl')
                
                # 필수 컬럼 확인
                required_columns = ['배송호차', '운행순번', '거래처명', '거래처주소']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    print(f"  ❌ 필수 컬럼이 없습니다: {missing_columns}")
                    continue
                
                # 배송호차를 문자열로 변환
                df['배송호차'] = df['배송호차'].astype(str)
                
                print(f"  ✅ 데이터 로드 완료: {len(df)}건")
                
                # 배송호차별 그룹화
                groups = df.groupby('배송호차')
                print(f"  📦 배송호차 수: {len(groups)}개")
                
                # 전체 결과 저장
                all_results = []
                summary_results = []
                
                print("\n" + "=" * 60)
                print("🚀 경로 계산 시작")
                print("=" * 60)
                
                for group_name, group_df in groups:
                    # 그룹 처리
                    results, total_distance, total_duration = process_group(
                        group_name, 
                        group_df, 
                        origin_coords
                    )
                    all_results.extend(results)
                    
                    # 요약 정보 추가
                    summary_results.append({
                        "배송호차": group_name,
                        "거래처수": len(group_df),
                        "총 운행거리(km)": meters_to_km(total_distance),
                        "총 운행시간": format_duration(total_duration)
                    })
                
                # 결과 저장
                print("\n" + "=" * 60)
                print("💾 결과 저장 중...")
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"dispatch_result_{timestamp}.xlsx"
                save_to_excel(all_results, summary_results, output_path)
                
                print(f"  ✅ 결과 파일 저장 완료: {output_path}")
                
                # 요약 출력
                print("\n" + "=" * 60)
                print("📊 호차별 운행 요약")
                print("=" * 60)
                
                total_km = 0
                total_sec = 0
                
                for summary in summary_results:
                    print(f"  🚛 [{summary['배송호차']}]")
                    print(f"      거래처수: {summary['거래처수']}개")
                    print(f"      총 거리: {summary['총 운행거리(km)']}km")
                    print(f"      총 시간: {summary['총 운행시간']}")
                    total_km += summary['총 운행거리(km)']
                
                print("\n  " + "-" * 40)
                print(f"  📈 전체 합계")
                print(f"      총 거래처수: {len(df)}개")
                print(f"      총 운행거리: {round(total_km, 1)}km")
                
                print("\n" + "=" * 60)
                print("✅ 모든 처리가 완료되었습니다!")
                print("=" * 60)
                
            except Exception as e:
                print(f"  ❌ 오류 발생: {e}")
                continue
        
        else:
            print("  ⚠️  올바른 메뉴를 선택해주세요.")


if __name__ == "__main__":
    main()
