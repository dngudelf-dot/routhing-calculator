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
import urllib3
from io import BytesIO
from typing import Optional, Tuple

# SSL 경고 메시지 숨김
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    .block-container { padding-top: 1rem !important; }
    .main { padding: 0.5rem 2rem; }
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0.8rem 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p { margin: 0.3rem 0 0; opacity: 0.9; font-size: 0.95rem; }
    .total-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px; padding: 2rem; color: white; text-align: center;
    }
    .total-card h2 { margin: 0 0 1rem 0; font-size: 1.5rem; }
    .total-value { font-size: 2rem; font-weight: 700; margin: 0.5rem 0; }
    .metric-container { display: flex; justify-content: center; gap: 3rem; flex-wrap: wrap; }
    .metric-item { text-align: center; }
    .metric-label { font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.25rem; }
    .footer { text-align: center; padding: 2rem; color: #94a3b8; font-size: 0.9rem; }
    
    /* 사이드바 타이틀 통일 */
    .sidebar .stMarkdown h3 { font-size: 1.1rem !important; font-weight: 600 !important; }
    .sidebar .stTextInput label { font-size: 0.9rem !important; }
    
    /* 메인 영역 타이틀 통일 */
    .stTabs [data-baseweb="tab-list"] button { font-size: 1rem !important; }
    .stMarkdown h3 { font-size: 1.2rem !important; font-weight: 600 !important; margin-bottom: 0.5rem !important; }
    .stMarkdown h4 { font-size: 1.05rem !important; font-weight: 600 !important; margin-bottom: 0.5rem !important; }
    
    /* 본문 텍스트 크기 */
    .stMarkdown p, .stMarkdown li { font-size: 0.9rem !important; }
    .stDataFrame { font-size: 0.85rem !important; }
    
    /* 데이터프레임 비고 컬럼 스크롤 개선 */
    .stDataFrame [data-testid="stDataFrameResizable"] { max-width: 100%; }
    .stDataFrame td { white-space: pre-wrap !important; word-wrap: break-word !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# API 설정
# ============================================================
API_KEY = "cd01fa982c683377a6e68e1d3f92e4ed"
KAKAO_ADDRESS_API_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_DIRECTIONS_API_URL = "https://apis-navi.kakaomobility.com/v1/directions"

# HTTP 세션 (연결 재사용으로 속도 향상)
_session = requests.Session()
_session.headers.update({"Authorization": f"KakaoAK {API_KEY}"})
_session.verify = False


# ============================================================
# 유틸리티 함수
# ============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def validate_address(address: str) -> Optional[Tuple[float, float, str]]:
    """주소 검증 (Geocoding) - 캐싱 적용"""
    # 1차: 주소 검색
    try:
        response = _session.get(KAKAO_ADDRESS_API_URL, params={"query": address}, timeout=5)
        response.raise_for_status()
        documents = response.json().get("documents", [])
        if documents:
            result = documents[0]
            x, y = float(result.get("x")), float(result.get("y"))
            road = result.get("road_address")
            addr = road.get("address_name", address) if road else result.get("address_name", address)
            return (x, y, addr)
    except:
        pass
    
    # 2차: 키워드 검색
    try:
        response = _session.get(KAKAO_KEYWORD_API_URL, params={"query": address}, timeout=5)
        response.raise_for_status()
        documents = response.json().get("documents", [])
        if documents:
            result = documents[0]
            x, y = float(result.get("x")), float(result.get("y"))
            addr = result.get("road_address_name") or result.get("address_name", address)
            return (x, y, addr)
    except:
        pass
    
    return None


def _try_route(ox, oy, dx, dy):
    """단일 경로 계산 시도"""
    params = {"origin": f"{ox},{oy}", "destination": f"{dx},{dy}", "priority": "RECOMMEND"}
    try:
        response = _session.get(KAKAO_DIRECTIONS_API_URL, params=params, timeout=10)
        response.raise_for_status()
        routes = response.json().get("routes", [])
        if not routes:
            return None
        route = routes[0]
        code = route.get("result_code", 0)
        if code != 0:
            return (0, 0, code)
        summary = route.get("summary", {})
        return (summary.get("distance", 0), summary.get("duration", 0), 0)
    except:
        return None


import math

def _haversine_distance(lon1, lat1, lon2, lat2):
    """두 좌표 간의 직선 거리 계산 (미터)"""
    R = 6371000  # 지구 반지름 (미터)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_route(ox, oy, dx, dy):
    """경로 계산 - 105 에러 시 주변 좌표로 재시도 (최적화)"""
    # 동일/근접 좌표 체크 (100m 이내면 동일 위치로 간주)
    straight_dist = _haversine_distance(ox, oy, dx, dy)
    if straight_dist < 100:
        return (0, 0)
    
    result = _try_route(ox, oy, dx, dy)
    if result is None:
        return None
    dist, dur, code = result
    if code == 0 and dist > 0:
        return (dist, dur)
    
    if code in [104, 105, 106]:
        # 최적화: 핵심 오프셋만 사용 (8개 → 6개)
        offsets = [(0.0005, 0), (-0.0005, 0), (0, 0.0005), (0, -0.0005), (0.001, 0), (0, 0.001)]
        for ddx, ddy in offsets:
            # 출발지 조정
            adj = _try_route(ox+ddx, oy+ddy, dx, dy)
            if adj and adj[2] == 0 and adj[0] > 0:
                return (adj[0], adj[1])
            # 도착지 조정
            adj = _try_route(ox, oy, dx+ddx, dy+ddy)
            if adj and adj[2] == 0 and adj[0] > 0:
                return (adj[0], adj[1])
    return None


def format_duration(s): return f"{s//3600}시간 {(s%3600)//60}분" if s >= 3600 else f"{s//60}분"
def format_distance(m): return f"{round(m/1000, 1)} km"
def meters_to_km(m): return round(m / 1000, 1)
def seconds_to_minutes(s): return round(s / 60)


def create_template_excel():
    """엑셀 양식 생성"""
    data = {
        "배송호차": ["1호차", "1호차", "1호차", "2호차", "2호차"],
        "운행순번": [1, 2, 3, 1, 2],
        "거래처명": ["강남 물류센터", "판교 배송센터", "수원 창고", "인천 물류창고", "부천 배송센터"],
        "거래처주소": ["서울특별시 강남구 테헤란로 152", "경기도 성남시 분당구 판교역로 235",
                   "경기도 수원시 영통구 광교중앙로 170", "인천광역시 연수구 센트럴로 194", "경기도 부천시 원미구 부일로 309"]
    }
    output = BytesIO()
    pd.DataFrame(data).to_excel(output, index=False, engine='openpyxl')
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
st.markdown("""
<div class="main-header">
    <h1>거리 계산기</h1>
    <p>Kakao Mobility API를 활용한 배차 거리/시간 계산 시스템</p>
</div>
""", unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    menu = st.radio("메뉴", ["🚛 거리 계산", "📋 업데이트 내역"], label_visibility="collapsed")
    st.markdown("---")
    
    if menu == "🚛 거리 계산":
        st.markdown("### 📍 상차지 정보")
        origin_address = st.text_input("상차지 주소", value="서울특별시 중구 세종대로 110")
        if st.button("🔍 상차지 주소 확인"):
            with st.spinner("검증 중..."):
                result = validate_address(origin_address)
                if result:
                    st.success(f"✅ {result[2]}")
                else:
                    st.error("❌ 주소를 찾을 수 없습니다.")
    else:
        origin_address = "서울특별시 중구 세종대로 110"


# ============================================================
# 거리 계산 메뉴
# ============================================================
if menu == "🚛 거리 계산":
    tab1, tab2 = st.tabs(["📤 엑셀 업로드", "✏️ 직접 입력"])
    
    # 탭 1: 엑셀 업로드
    with tab1:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📁 엑셀 파일 업로드")
            st.download_button("📥 양식 다운로드", create_template_excel(), "input_template.xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            st.markdown("---")
            
            uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=['xlsx', 'xls'])
            if uploaded_file:
                try:
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                    required = ['배송호차', '운행순번', '거래처명', '거래처주소']
                    missing = [c for c in required if c not in df.columns]
                    if missing:
                        st.error(f"❌ 필수 컬럼이 없습니다: {missing}")
                    else:
                        df['배송호차'] = df['배송호차'].astype(str)
                        st.session_state.customers = df.to_dict('records')
                        st.success(f"✅ {len(df)}건 로드 완료")
                        st.dataframe(df, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"❌ 파일 읽기 오류: {e}")
        
        with col2:
            st.markdown("### 📊 계산 결과")
            if st.button("🚀 경로 계산", key="calc_excel", use_container_width=True, type="primary"):
                if not origin_address:
                    st.error("⚠️ 상차지 주소를 입력해주세요.")
                elif not st.session_state.customers:
                    st.error("⚠️ 엑셀 파일을 업로드해주세요.")
                else:
                    with st.spinner("🔄 경로 계산 중..."):
                        origin_result = validate_address(origin_address)
                        if not origin_result:
                            st.error(f"❌ 상차지 주소를 찾을 수 없습니다: {origin_address}")
                        else:
                            ox, oy, origin_name = origin_result
                            st.success(f"✅ 상차지 확인: {origin_name}")
                            
                            df = pd.DataFrame(st.session_state.customers)
                            df['배송호차'] = df['배송호차'].astype(str)
                            groups = df.groupby('배송호차')
                            
                            all_results, summary_results = [], []
                            progress = st.progress(0)
                            
                            for idx, (name, gdf) in enumerate(groups):
                                progress.progress((idx + 1) / len(groups))
                                gdf = gdf.sort_values('운행순번').reset_index(drop=True)
                                cx, cy, cname = ox, oy, "상차지"
                                gdist, gdur, cdist, cdur = 0, 0, 0, 0
                                
                                for _, row in gdf.iterrows():
                                    seq, cust, addr = int(row['운행순번']), row['거래처명'], row['거래처주소']
                                    dest = validate_address(addr)
                                    
                                    if not dest:
                                        all_results.append({"배송호차": name, "운행순번": seq, "출발지": cname, "도착지": cust,
                                                          "구간거리(km)": "-", "구간소요시간": "-",
                                                          "누적거리(km)": meters_to_km(cdist), "누적시간": format_duration(cdur), "비고": "주소 확인 필요"})
                                        cname = cust
                                        continue
                                    
                                    dx, dy, _ = dest
                                    route = calculate_route(cx, cy, dx, dy)
                                    
                                    if route:
                                        dist, dur = route
                                        gdist += dist; gdur += dur; cdist += dist; cdur += dur
                                        all_results.append({"배송호차": name, "운행순번": seq, "출발지": cname, "도착지": cust,
                                                          "구간거리(km)": meters_to_km(dist), "구간소요시간": format_duration(dur),
                                                          "누적거리(km)": meters_to_km(cdist), "누적시간": format_duration(cdur), "비고": ""})
                                    else:
                                        all_results.append({"배송호차": name, "운행순번": seq, "출발지": cname, "도착지": cust,
                                                          "구간거리(km)": "-", "구간소요시간": "-",
                                                          "누적거리(km)": meters_to_km(cdist), "누적시간": format_duration(cdur), "비고": "경로 계산 실패"})
                                    cx, cy, cname = dx, dy, cust
                                
                                summary_results.append({"배송호차": name, "거래처수": len(gdf), 
                                                       "총 운행거리(km)": meters_to_km(gdist), "총 운행시간": format_duration(gdur)})
                            
                            progress.empty()
                            st.session_state.results = all_results
                            st.session_state.summary = summary_results
            
            # 결과 표시
            if st.session_state.results and st.session_state.summary:
                st.markdown("#### 📈 호차별 요약")
                df_summary = pd.DataFrame(st.session_state.summary)
                st.dataframe(df_summary, use_container_width=True, hide_index=True)
                
                total_dist = sum([r.get('구간거리(km)', 0) for r in st.session_state.results if isinstance(r.get('구간거리(km)'), (int, float))])
                st.markdown(f"""
                <div class="total-card">
                    <h2>📊 전체 합계</h2>
                    <div class="metric-container">
                        <div class="metric-item"><div class="metric-label">🚛 총 운행 거리</div><div class="total-value">{round(total_dist, 1)} km</div></div>
                        <div class="metric-item"><div class="metric-label">📍 총 배송처</div><div class="total-value">{len(st.session_state.results)}곳</div></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown("#### 📋 상세 결과")
                df_results = pd.DataFrame(st.session_state.results)
                
                # 비고 컬럼이 잘리지 않도록 컬럼 설정
                column_config = {
                    "비고": st.column_config.TextColumn(
                        "비고",
                        width="large",
                        help="비고 내용 (스크롤하여 전체 내용 확인)"
                    )
                }
                st.dataframe(df_results, use_container_width=True, hide_index=True, column_config=column_config)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_results.to_excel(writer, sheet_name='배송상세', index=False)
                    df_summary.to_excel(writer, sheet_name='호차별요약', index=False)
                output.seek(0)
                st.download_button("📥 결과 다운로드 (Excel)", output.getvalue(), "dispatch_result.xlsx",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    
    # 탭 2: 직접 입력
    with tab2:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📦 거래처 정보")
            if not st.session_state.customers:
                st.session_state.customers = [
                    {"배송호차": "1호차", "운행순번": 1, "거래처명": "강남 물류센터", "거래처주소": "서울특별시 강남구 테헤란로 152"},
                    {"배송호차": "1호차", "운행순번": 2, "거래처명": "판교 배송센터", "거래처주소": "경기도 성남시 분당구 판교역로 235"},
                ]
            
            edited_df = st.data_editor(pd.DataFrame(st.session_state.customers), num_rows="dynamic", 
                                       use_container_width=True, hide_index=True)
            st.session_state.customers = edited_df.to_dict('records')
        
        with col2:
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
                            st.error(f"❌ 상차지 주소를 찾을 수 없습니다")
                        else:
                            ox, oy, _ = origin_result
                            st.success(f"✅ 상차지 확인")
                            
                            df = pd.DataFrame(st.session_state.customers)
                            df['배송호차'] = df['배송호차'].astype(str)
                            
                            all_results, summary_results = [], []
                            for name, gdf in df.groupby('배송호차'):
                                gdf = gdf.sort_values('운행순번').reset_index(drop=True)
                                cx, cy, cname = ox, oy, "상차지"
                                cdist, cdur = 0, 0
                                
                                for _, row in gdf.iterrows():
                                    cust, addr = row['거래처명'], row['거래처주소']
                                    dest = validate_address(addr)
                                    if dest:
                                        dx, dy, _ = dest
                                        route = calculate_route(cx, cy, dx, dy)
                                        if route:
                                            dist, dur = route
                                            cdist += dist; cdur += dur
                                            all_results.append({"배송호차": name, "구간": f"{cname} → {cust}",
                                                              "거리": format_distance(dist), "시간": format_duration(dur)})
                                        cx, cy = dx, dy
                                    cname = cust
                                
                                summary_results.append({"배송호차": name, "총 거리": format_distance(cdist), "총 시간": format_duration(cdur)})
                            
                            if all_results:
                                st.markdown("#### 📋 계산 결과")
                                st.dataframe(pd.DataFrame(all_results), use_container_width=True, hide_index=True)
                                st.markdown("#### 📈 호차별 요약")
                                st.dataframe(pd.DataFrame(summary_results), use_container_width=True, hide_index=True)


# ============================================================
# 업데이트 내역 메뉴
# ============================================================
else:
    st.markdown("### 📋 버전별 업데이트 내역")
    st.markdown("---")
    
    versions = [
        {"version": "v1.3.0", "date": "2024-12-17", "changes": [
            "🔧 도로 접근 불가(105 에러) 시 주변 좌표 자동 보정 기능 추가",
            "🔧 SSL 인증서 검증 오류 해결 (기업 프록시 환경 지원)",
            "🔧 키워드 검색 API 추가로 주소 검증 성공률 향상"
        ]},
        {"version": "v1.2.0", "date": "2024-12-16", "changes": [
            "✨ 엑셀 업로드 기능 추가", "✨ 호차별 그룹 계산 지원", "✨ 결과 엑셀 다운로드"
        ]},
        {"version": "v1.1.0", "date": "2024-12-15", "changes": [
            "✨ 직접 입력 모드 추가", "✨ 구간별 거리/시간 계산", "✨ 누적 거리/시간 표시"
        ]},
        {"version": "v1.0.0", "date": "2024-12-14", "changes": [
            "🚀 최초 버전 출시", "✨ Kakao Mobility API 연동", "✨ 주소 검증/경로 계산 기능"
        ]}
    ]
    
    for v in versions:
        with st.expander(f"**{v['version']}** - {v['date']}", expanded=(v['version'] == 'v1.3.0')):
            for c in v['changes']:
                st.markdown(f"- {c}")


# 푸터
st.markdown('<div class="footer"><p>거리 계산기 v1.3.0 | Powered by Kakao Mobility API</p></div>', unsafe_allow_html=True)
