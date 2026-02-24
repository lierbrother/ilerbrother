import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageChops
import re
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="건설안전 v7.0 Stable", layout="centered")

# --- 모바일 최적화 스타일 ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    .stApp { background-color: white; }
    
    /* 제목 */
    .app-title { font-size: 1.2rem; font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; text-align: center; }

    /* 지문 이미지: 여백 없이 꽉 차게 */
    img { border: 1px solid #f0f0f0; border-radius: 8px; width: 100% !important; }

    /* 사지선다 버튼: 번호 잘 보이고 슬림하게 */
    div.stButton > button {
        width: 100% !important;
        font-size: 14px !important;
        text-align: left !important;
        padding: 8px 12px !important;
        margin-bottom: -10px !important;
        background-color: #f8f9fa !important;
        border: 1px solid #ececec !important;
        border-radius: 6px !important;
    }
    
    /* 버튼 내부 텍스트 정렬 */
    div.stButton > button p { line-height: 1.3 !important; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 여백 제거 함수 (이미지에서 글자만 남기기) ---
def auto_crop(img):
    bg = Image.new(img.mode, img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        return img.crop(bbox)
    return img

# --- 세션 상태 초기화 ---
if 'questions' not in st.session_state:
    st.session_state.update({'questions': [], 'current_idx': 0, 'pdf_doc': None, 'last_file': None})

# --- PDF 분석 ---
def parse_pdf(doc):
    q_list = []
    # 교사용 정답 마커 및 일반 번호 마커 포함
    marker_pattern = re.compile(r'[①②③④❶❷❸❹❺●⚫⬤]')
    
    for p_idx in range(len(doc)):
        page = doc[p_idx]
        blocks = page.get_text("blocks")
        width = page.rect.width
        for side in [0, 1]:
            side_x0, side_x1 = (0, width/2) if side == 0 else (width/2, width)
            side_blocks = sorted([b for b in blocks if b[0] < side_x1 and b[2] > side_x0], key=lambda x: x[1])
            curr = None
            for b in side_blocks:
                txt = b[4].strip()
                if not txt or "comcbt" in txt.lower(): continue
                q_match = re.match(r'^(\d+)\.', txt)
                if q_match:
                    if curr: q_list.append(curr)
                    curr = {'num': q_match.group(1), 'page': p_idx, 'y0': b[1], 'options': [], 'ans_idx': -1, 'side': side, 'opt_y': None}
                elif curr:
                    m_found = marker_pattern.findall(txt)
                    if m_found:
                        if curr['opt_y'] is None: curr['opt_y'] = b[1]
                        parts = marker_pattern.split(txt)
                        contents = [p.strip() for p in parts if p.strip()]
                        for i, m in enumerate(m_found):
                            if len(curr['options']) >= 4: break
                            # 특수 마커가 정답임
                            if m in ['❶','❷','❸','❹','❺','●','⚫','⬤']:
                                curr['ans_idx'] = len(curr['options'])
                            curr['options'].append(contents[i] if i < len(contents) else "")
                    elif curr['options']:
                        curr['options'][-1] = (curr['options'][-1] + " " + txt).strip()
            if curr: q_list.append(curr)
    
    # 정답 보정
    for q in q_list:
        if q['ans_idx'] == -1: q['ans_idx'] = 0
    return [q for q in q_list if len(q['options']) >= 4]

# --- 메인 실행 ---
st.markdown('<p class="app-title">👷‍♂️ 건설안전기사 v7.0</p>', unsafe_allow_html=True)

uploaded_file = st.sidebar.file_uploader("PDF 파일을 선택하세요", type="pdf")

if uploaded_file:
    # 파일이 새로 업로드된 경우 초기화
    if st.session_state.last_file != uploaded_file.name:
        with st.spinner('문제를 분석 중입니다...'):
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            st.session_state.pdf_doc = doc
            st.session_state.questions = parse_pdf(doc)
            st.session_state.current_idx = 0
            st.session_state.last_file = uploaded_file.name
        st.rerun()

    if st.session_state.questions:
        q = st.session_state.questions[st.session_state.current_idx]
        page = st.session_state.pdf_doc[q['page']]
        
        # 1. 지문 캡처 (안정적인 Matrix 3.5)
        y_start = max(0, q['y0'] - 12)
        y_end = q['opt_y'] - 5 if q['opt_y'] else y_start + 280
        x_start = (page.rect.width / 2) * q['side']
        x_end = x_start + (page.rect.width / 2)
        
        clip_rect = fitz.Rect(x_start, y_start, x_end, y_end)
        pix = page.get_pixmap(matrix=fitz.Matrix(3.5, 3.5), clip=clip_rect)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # 2. 여백 자르기 및 출력
        img = auto_crop(img)
        st.image(img, use_container_width=True)

        # 3. 사지선다 버튼 (번호 기호 추가)
        markers = ["①", "②", "③", "④"]
        st.write("") 
        for i, option in enumerate(q['options']):
            if st.button(f"{markers[i]} {option}", key=f"btn_{i}", use_container_width=True):
                if i == q['ans_idx']:
                    st.success("⭕ 정답입니다!")
                    time.sleep(0.6)
                    if st.session_state.current_idx < len(st.session_state.questions) - 1:
                        st.session_state.current_idx += 1
                        st.rerun()
                else:
                    st.error(f"❌ 오답! 정답은 {markers[q['ans_idx']]} 입니다.")

        # 4. 하단 네비게이션
        st.write("---")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅ 이전"):
                if st.session_state.current_idx > 0:
                    st.session_state.current_idx -= 1
                    st.rerun()
        with c2:
            st.write(f"**{st.session_state.current_idx + 1} / {len(st.session_state.questions)}**")
        with c3:
            if st.button("다음 ➔"):
                if st.session_state.current_idx < len(st.session_state.questions) - 1:
                    st.session_state.current_idx += 1
                    st.rerun()
else:
    st.info("사이드바(왼쪽 위 '>' 버튼)에서 PDF를 올려주세요.")
