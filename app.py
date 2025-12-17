# -*- coding: utf-8 -*-
"""
배차 관리 시스템 (TMS) - 웹 버전
Streamlit을 활용한 거리/시간 계산기

실행 방법:
    streamlit run app.py
"""

import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from typing import Optional, Tuple, List, Dict

# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title="거리 계산기",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS 스타일링
# ============================================================
st.markdown("""
<style>
    /* 상단 여백 최소화 */
    .block-container {
        padding-top: 1rem !important;
    }
    
    /* 메인 컨테이너 */
    .main {
        padding: 0.5rem 2rem;
    }
    
    /* 헤더 스타일 - 높이 축소 */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0.8rem 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    
    .main-header p {
        margin: 0.3rem 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }
    
    /* 합계 카드 */
    .total-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
    }
    
    .total-card h2 {
        margin: 0 0 1rem 0;
        font-size: 1.5rem;
    }
    
    .total-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    
    /* 메트릭 스타일 */
    .metric-container {
        display: flex;
        justify-content: center;
        gap: 3rem;
        flex-wrap: wrap;
    }
    
    .metric-item {
        text-align: center;
    }
    
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
        margin-bottom: 0.25rem;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* 푸터 */
    .footer {
        text-align: center;
        padding: 2rem;
        color: #94a3b8;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# API 설정
# ============================================================
API_KEY = "cd01fa982c683377a6e68e1d3f92e4ed"
KAKAO_ADDRESS_API_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_DIRECTIONS_API_URL = "https://apis-navi.kakaomobility.com/v1/directions"


# ============================================================
# 유틸리티 함수
# ============================================================
def validate_address(address: str) -> Optional[Tuple[float, float, str]]:
    """
    주소 검증 (Geocoding)
    1차: 주소 검색 API 시도
    2차: 키워드 검색 API 시도
    """
    headers = {"Authorization": f"KakaoAK {API_KEY}"}
    
    # 1차: 주소 검색 시도
    try:
        response = requests.get(
            KAKAO_ADDRESS_API_URL, 
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


def _try_route(origin_x: float, origin_y: float, dest_x: float, dest_y: float) -> Optional[Tuple[int, int, int]]:
    """단일 경로 계산 시도 (내부 함수) - result_code도 함께 반환"""
    headers = {
        "Authorization": f"KakaoAK {API_KEY}",
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


def calculate_route(origin_x: float, origin_y: float, dest_x: float, dest_y: float) -> Optional[Tuple[int, int]]:
    """
    경로 계산 (Routing)
    105 에러(도로 접근 불가) 발생 시 주변 좌표로 자동 재시도
    """
    # 1차 시도: 원본 좌표
    result = _try_route(origin_x, origin_y, dest_x, dest_y)
    
    if result is None:
        return None
    
    distance, duration, result_code = result
    
    # 성공 시 바로 반환
    if result_code == 0 and distance > 0:
        return (distance, duration)
    
    # 105 에러(도로 접근 불가) 발생 시 주변 좌표로 재시도
    if result_code in [104, 105, 106]:  # 출발지/도착지 도로 접근 불가
        # 격자 탐색: 약 50~100m 범위로 좌표 조정
        # 위도 0.001도 ≈ 111m, 경도 0.001도 ≈ 88m (한국 기준)
        offsets = [
            (0.0005, 0), (-0.0005, 0),  # 동서
            (0, 0.0005), (0, -0.0005),  # 남북
            (0.0005, 0.0005), (-0.0005, 0.0005),  # 대각선
            (-0.0005, -0.0005), (0.0005, -0.0005),
            (0.001, 0), (-0.001, 0),  # 더 넓은 범위
            (0, 0.001), (0, -0.001),
        ]
        
        for dx, dy in offsets:
            # 출발지 조정 시도
            adj_result = _try_route(origin_x + dx, origin_y + dy, dest_x, dest_y)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                return (adj_result[0], adj_result[1])
            
            # 도착지 조정 시도
            adj_result = _try_route(origin_x, origin_y, dest_x + dx, dest_y + dy)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                return (adj_result[0], adj_result[1])
            
            # 양쪽 모두 조정 시도
            adj_result = _try_route(origin_x + dx, origin_y + dy, dest_x + dx, dest_y + dy)
            if adj_result and adj_result[2] == 0 and adj_result[0] > 0:
                return (adj_result[0], adj_result[1])
    
    return None


def format_duration(total_seconds: int) -> str:
    """초를 시간/분으로 변환"""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}시간 {minutes}분"
    else:
        return f"{minutes}분"


def format_distance(meters: int) -> str:
    """미터를 km로 변환"""
    km = round(meters / 1000, 1)
    return f"{km} km"


def meters_to_km(meters: int) -> float:
    """미터를 km로 변환 (숫자)"""
    return round(meters / 1000, 1)


def seconds_to_minutes(seconds: int) -> int:
    """초를 분으로 변환"""
    return round(seconds / 60)


def create_template_excel() -> bytes:
    """엑셀 양식 생성"""
    sample_data = {
        "배송호차": ["1호차", "1호차", "1호차", "2호차", "2호차"],
        "운행순번": [1, 2, 3, 1, 2],
        "거래처명": ["강남 물류센터", "판교 배송센터", "수원 창고", "인천 물류창고", "부천 배송센터"],
        "거래처주소": [
            "서울특별시 강남구 테헤란로 152",
            "경기도 성남시 분당구 판교역로 235",
            "경기도 수원시 영통구 광교중앙로 170",
            "인천광역시 연수구 센트럴로 194",
            "경기도 부천시 원미구 부일로 309"
        ]
    }
    df = pd.DataFrame(sample_data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='배송데이터')
    output.seek(0)
    return output.getvalue()


# ============================================================
# 세션 상태 초기화
# ============================================================
if 'customers' not in st.session_state:
    st.session_state.customers = []

if 'results' not in st.session_state:
    st.session_state.results = None

if 'summary' not in st.session_state:
    st.session_state.summary = None


# ============================================================
# 메인 UI
# ============================================================
# 헤더
st.markdown("""
<div class="main-header">
    <h1>거리 계산기</h1>
    <p>Kakao Mobility API를 활용한 배차 거리/시간 계산 시스템</p>
</div>
""", unsafe_allow_html=True)

# 사이드바 - 설정
with st.sidebar:
    # 메뉴 선택
    menu = st.radio(
        "메뉴",
        ["🚛 거리 계산", "📋 업데이트 내역"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    if menu == "🚛 거리 계산":
        st.markdown("### 📍 상차지 정보")
        origin_address = st.text_input(
            "상차지 주소",
            value="서울특별시 중구 세종대로 110",
            help="출발지 주소를 입력하세요."
        )
        
        # 상차지 주소 검증 버튼
        if st.button("🔍 상차지 주소 확인"):
            with st.spinner("검증 중..."):
                result = validate_address(origin_address)
                if result:
                    st.success(f"✅ {result[2]}")
                else:
                    st.error("❌ 주소를 찾을 수 없습니다.")
    else:
        origin_address = "서울특별시 중구 세종대로 110"  # 기본값

# 메뉴에 따른 화면 표시
if menu == "🚛 거리 계산":
    # 탭 구성
    tab1, tab2 = st.tabs(["📤 엑셀 업로드", "✏️ 직접 입력"])

    # ============================================================
    # 탭 1: 엑셀 업로드
    # ============================================================
    with tab1:
        col_upload1, col_upload2 = st.columns([1, 1])
    
    with col_upload1:
        st.markdown("### 📁 엑셀 파일 업로드")
        
        # 양식 다운로드
        st.download_button(
            label="📥 양식 다운로드 (Excel)",
            data=create_template_excel(),
            file_name="input_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        st.markdown("---")
        
        # 파일 업로드
        uploaded_file = st.file_uploader(
            "엑셀 파일을 업로드하세요",
            type=['xlsx', 'xls'],
            help="배송호차, 운행순번, 거래처명, 거래처주소 컬럼이 필요합니다."
        )
        
        if uploaded_file is not None:
            try:
                df_uploaded = pd.read_excel(uploaded_file, engine='openpyxl')
                
                # 필수 컬럼 확인
                required_columns = ['배송호차', '운행순번', '거래처명', '거래처주소']
                missing_columns = [col for col in required_columns if col not in df_uploaded.columns]
                
                if missing_columns:
                    st.error(f"❌ 필수 컬럼이 없습니다: {missing_columns}")
                else:
                    # 배송호차를 문자열로 변환
                    df_uploaded['배송호차'] = df_uploaded['배송호차'].astype(str)
                    st.session_state.customers = df_uploaded.to_dict('records')
                    st.success(f"✅ {len(df_uploaded)}건의 데이터를 로드했습니다.")
                    
                    # 데이터 미리보기
                    st.markdown("#### 📋 데이터 미리보기")
                    st.dataframe(df_uploaded, use_container_width=True, hide_index=True)
                    
            except Exception as e:
                st.error(f"❌ 파일 읽기 오류: {e}")
    
    with col_upload2:
        st.markdown("### 📊 계산 결과")
        
        # 경로 계산 버튼 (엑셀 업로드용)
        if st.button("🚀 경로 계산", key="calc_excel", use_container_width=True, type="primary"):
            if not origin_address:
                st.error("⚠️ 상차지 주소를 입력해주세요.")
            elif not st.session_state.customers:
                st.error("⚠️ 엑셀 파일을 업로드해주세요.")
            else:
                with st.spinner("🔄 경로 계산 중..."):
                    # 상차지 검증
                    origin_result = validate_address(origin_address)
                    
                    if not origin_result:
                        st.error(f"❌ 상차지 주소를 찾을 수 없습니다: {origin_address}")
                    else:
                        origin_x, origin_y, origin_name = origin_result
                        st.success(f"✅ 상차지 확인: {origin_name}")
                        
                        # 데이터프레임 생성 및 그룹화
                        df = pd.DataFrame(st.session_state.customers)
                        df['배송호차'] = df['배송호차'].astype(str)
                        
                        groups = df.groupby('배송호차')
                        
                        all_results = []
                        summary_results = []
                        
                        progress_bar = st.progress(0)
                        total_groups = len(groups)
                        
                        for group_idx, (group_name, group_df) in enumerate(groups):
                            progress_bar.progress((group_idx + 1) / total_groups)
                            
                            # 운행순번 정렬
                            group_df = group_df.sort_values('운행순번').reset_index(drop=True)
                            
                            current_x, current_y = origin_x, origin_y
                            current_name = "상차지"
                            
                            group_distance = 0
                            group_duration = 0
                            cumulative_distance = 0
                            cumulative_duration = 0
                            
                            for idx, row in group_df.iterrows():
                                sequence = int(row['운행순번'])
                                customer_name = row['거래처명']
                                customer_address = row['거래처주소']
                                
                                # 주소 검증
                                dest_result = validate_address(customer_address)
                                
                                if not dest_result:
                                    all_results.append({
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
                                    current_name = customer_name
                                    continue
                                
                                dest_x, dest_y, dest_formatted = dest_result
                                
                                # 경로 계산
                                route_result = calculate_route(current_x, current_y, dest_x, dest_y)
                                
                                if route_result:
                                    distance, duration = route_result
                                    group_distance += distance
                                    group_duration += duration
                                    cumulative_distance += distance
                                    cumulative_duration += duration
                                    
                                    all_results.append({
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
                                    all_results.append({
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
                                
                                current_x, current_y = dest_x, dest_y
                                current_name = customer_name
                            
                            # 호차별 요약
                            summary_results.append({
                                "배송호차": group_name,
                                "거래처수": len(group_df),
                                "총 운행거리(km)": meters_to_km(group_distance),
                                "총 운행시간": format_duration(group_duration)
                            })
                        
                        progress_bar.empty()
                        
                        # 결과 저장
                        st.session_state.results = all_results
                        st.session_state.summary = summary_results
        
        # 결과 표시
        if st.session_state.results and st.session_state.summary:
            # 요약 정보
            st.markdown("#### 📈 호차별 요약")
            df_summary = pd.DataFrame(st.session_state.summary)
            st.dataframe(df_summary, use_container_width=True, hide_index=True)
            
            # 총합 계산
            total_distance = sum([r.get('구간거리(km)', 0) for r in st.session_state.results if isinstance(r.get('구간거리(km)'), (int, float))])
            total_stops = len(st.session_state.results)
            
            st.markdown(f"""
            <div class="total-card">
                <h2>📊 전체 합계</h2>
                <div class="metric-container">
                    <div class="metric-item">
                        <div class="metric-label">🚛 총 운행 거리</div>
                        <div class="total-value">{round(total_distance, 1)} km</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">📍 총 배송처</div>
                        <div class="total-value">{total_stops}곳</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # 상세 결과
            st.markdown("#### 📋 상세 결과")
            df_results = pd.DataFrame(st.session_state.results)
            st.dataframe(df_results, use_container_width=True, hide_index=True)
            
            # 엑셀 다운로드
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_results.to_excel(writer, sheet_name='배송상세', index=False)
                df_summary.to_excel(writer, sheet_name='호차별요약', index=False)
            output.seek(0)
            
            st.download_button(
                label="📥 결과 다운로드 (Excel)",
                data=output.getvalue(),
                file_name="dispatch_result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )


# ============================================================
# 탭 2: 직접 입력
# ============================================================
with tab2:
    col_input1, col_input2 = st.columns([1, 1])
    
    with col_input1:
        st.markdown("### 📦 거래처 정보")
        
        # 기본 데이터
        if not st.session_state.customers:
            st.session_state.customers = [
                {"배송호차": "1호차", "운행순번": 1, "거래처명": "강남 물류센터", "거래처주소": "서울특별시 강남구 테헤란로 152"},
                {"배송호차": "1호차", "운행순번": 2, "거래처명": "판교 배송센터", "거래처주소": "경기도 성남시 분당구 판교역로 235"},
                {"배송호차": "1호차", "운행순번": 3, "거래처명": "수원 창고", "거래처주소": "경기도 수원시 영통구 광교중앙로 170"},
            ]
        
        df = pd.DataFrame(st.session_state.customers)
        
        edited_df = st.data_editor(
            df,
            column_config={
                "배송호차": st.column_config.TextColumn("배송호차", width="small"),
                "운행순번": st.column_config.NumberColumn("순번", min_value=1, max_value=100, width="small"),
                "거래처명": st.column_config.TextColumn("거래처명", width="medium"),
                "거래처주소": st.column_config.TextColumn("거래처주소", width="large"),
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
        )
        
        st.session_state.customers = edited_df.to_dict('records')
    
    with col_input2:
        st.markdown("### 📊 계산 결과")
        
        if st.button("🚀 경로 계산", key="calc_manual", use_container_width=True, type="primary"):
            if not origin_address:
                st.error("⚠️ 상차지 주소를 입력해주세요.")
            elif not st.session_state.customers:
                st.error("⚠️ 거래처 정보를 입력해주세요.")
            else:
                with st.spinner("🔄 경로 계산 중..."):
                    origin_result = validate_address(origin_address)
                    
                    if not origin_result:
                        st.error(f"❌ 상차지 주소를 찾을 수 없습니다: {origin_address}")
                    else:
                        origin_x, origin_y, origin_name = origin_result
                        st.success(f"✅ 상차지 확인: {origin_name}")
                        
                        df = pd.DataFrame(st.session_state.customers)
                        df['배송호차'] = df['배송호차'].astype(str)
                        
                        groups = df.groupby('배송호차')
                        
                        all_results = []
                        summary_results = []
                        
                        for group_name, group_df in groups:
                            group_df = group_df.sort_values('운행순번').reset_index(drop=True)
                            
                            current_x, current_y = origin_x, origin_y
                            current_name = "상차지"
                            cumulative_distance = 0
                            cumulative_duration = 0
                            
                            for idx, row in group_df.iterrows():
                                customer_name = row['거래처명']
                                customer_address = row['거래처주소']
                                
                                dest_result = validate_address(customer_address)
                                
                                if dest_result:
                                    dest_x, dest_y, _ = dest_result
                                    route_result = calculate_route(current_x, current_y, dest_x, dest_y)
                                    
                                    if route_result:
                                        distance, duration = route_result
                                        cumulative_distance += distance
                                        cumulative_duration += duration
                                        
                                        all_results.append({
                                            "배송호차": group_name,
                                            "구간": f"{current_name} → {customer_name}",
                                            "거리": format_distance(distance),
                                            "시간": format_duration(duration),
                                        })
                                    
                                    current_x, current_y = dest_x, dest_y
                                
                                current_name = customer_name
                            
                            summary_results.append({
                                "배송호차": group_name,
                                "총 거리": format_distance(cumulative_distance),
                                "총 시간": format_duration(cumulative_duration)
                            })
                        
                        if all_results:
                            st.markdown("#### 📋 계산 결과")
                            st.dataframe(pd.DataFrame(all_results), use_container_width=True, hide_index=True)
                            
                            st.markdown("#### 📈 호차별 요약")
                            st.dataframe(pd.DataFrame(summary_results), use_container_width=True, hide_index=True)


# ============================================================
# 탭 3: 업데이트 내역
# ============================================================
with tab3:
    st.markdown("### 📋 버전별 업데이트 내역")
    st.markdown("---")
    
    # 버전 정보
    versions = [
        {
            "version": "v1.3.0",
            "date": "2024-12-17",
            "changes": [
                "🔧 도로 접근 불가(105 에러) 시 주변 좌표 자동 보정 기능 추가",
                "🔧 SSL 인증서 검증 오류 해결 (기업 프록시 환경 지원)",
                "🔧 키워드 검색 API 추가로 주소 검증 성공률 향상"
            ]
        },
        {
            "version": "v1.2.0",
            "date": "2024-12-16",
            "changes": [
                "✨ 엑셀 업로드 기능 추가",
                "✨ 호차별 그룹 계산 지원",
                "✨ 결과 엑셀 다운로드 (배송상세/호차별요약 시트)"
            ]
        },
        {
            "version": "v1.1.0",
            "date": "2024-12-15",
            "changes": [
                "✨ 직접 입력 모드 추가",
                "✨ 구간별 거리/시간 계산",
                "✨ 누적 거리/시간 표시"
            ]
        },
        {
            "version": "v1.0.0",
            "date": "2024-12-14",
            "changes": [
                "🚀 최초 버전 출시",
                "✨ Kakao Mobility API 연동",
                "✨ 주소 검증 (Geocoding) 기능",
                "✨ 경로 계산 (Directions) 기능"
            ]
        }
    ]
    
    for v in versions:
        with st.expander(f"**{v['version']}** - {v['date']}", expanded=(v['version'] == 'v1.3.0')):
            for change in v['changes']:
                st.markdown(f"- {change}")


# 푸터
st.markdown("""
<div class="footer">
    <p>거리 계산기 v1.3.0 | Powered by Kakao Mobility API</p>
</div>
""", unsafe_allow_html=True)
