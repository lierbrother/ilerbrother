import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageChops
import re
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="건설안전기사 v6.0", layout="centered")

# --- 강력한 모바일 최적화 CSS ---
st.markdown("""
    <style>
    /* 여백 및 배경 설정 */
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    .stApp { background-color: white; }
    
    /* 제목 스타일 */
    .main-title { font-size: 18px !important; font-weight: bold; color: #333; margin-bottom: 10px; }

    /* 이미지 스타일 (지문) */
    .stImage > img { border: 1px solid #eee; border-radius: 5px; }

    /* 버튼 스타일 (사지선다) - 슬림하게 */
    div.stButton > button {
        width: 100% !important;
        font-size: 13px !important;
        padding: 5px 10px !important;
        min-height: 32px !important;
        height: auto !important;
        margin-bottom: -15px !important;
        background-color: #f1f3f5 !important;
        border: 1px solid #dee2e6 !important;
        text-align: left !important;
        display: block !important;
    }
    
    /* 버튼 텍스트 정렬 */
    div.stButton > button div p {
        margin-bottom: 0px !important;
        line-height: 1.2 !important;
    }

    /* 네비게이션 버튼 간격 */
    .nav-col { margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 여백 자동 제거 함수 (지문 크게 만들기) ---
def crop_to_content(img):
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        # 좌우 여백을 조금 더 타이트하게 잡음
        return img.crop(bbox)
    return img

# --- 세션 초기화 ---
if 'questions' not in st.session_state: st.session_state.questions = []
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'pdf_doc' not in st.session_state: st.session_state.pdf_doc = None

# --- PDF 분석 함수 ---
def parse_pdf(doc):
    q_list = []
    marker_pattern = re.compile(r'[①②③④]')
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
                            if m in ['❶','❷','❸','❹','❺','●','⚫']: curr['ans_idx'] = len(curr['options']) # 정답 마커 처리
                            curr['options'].append(contents[i] if i < len(contents) else "")
                    elif curr['options']:
                        curr['options'][-1] = (curr['options'][-1] + " " + txt).strip()
            if curr: q_list.append(curr)
    # 정답 인덱스 자동 보정 (안 잡힌 경우 대비)
    for q in q_list:
        if q['ans_idx'] == -1: q['ans_idx'] = 0 
    return [q for q in q_list if len(q['options']) >= 4]

# --- 화면 구성 ---
st.markdown('<p class="main-title">👷‍♂️ 건설안전기사 v6.0</p>', unsafe_allow_html=True)

uploaded_file = st.sidebar.file_uploader("PDF 업로드", type="pdf")

if uploaded_file:
    if st.session_state.pdf_doc is None:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        st.session_state.pdf_doc = doc
        st.session_state.questions = parse_pdf(doc)
        st.rerun()

    if st.session_state.questions:
        q = st.session_state.questions[st.session_state.current_idx]
        page = st.session_state.pdf_doc[q['page']]
        
        # 1. 지문 캡처 (초고해상도 7.0배)
        y_start = max(0, q['y0'] - 10)
        y_end = q['opt_y'] - 5 if q['opt_y'] else y_start + 250
        x_start = (page.rect.width / 2) * q['side']
        x_end = x_start + (page.rect.width / 2)
        
        clip_rect = fitz.Rect(x_start, y_start, x_end, y_end)
        pix = page.get_pixmap(matrix=fitz.Matrix(7.0, 7.0), clip=clip_rect)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # 2. 여백 잘라내기 (글자를 화면 끝까지 채움)
        img = crop_to_content(img)
        st.image(img, use_container_width=True)

        # 3. 사지선다 버튼 (번호 명시)
        st.write("")
        for i, option in enumerate(q['options']):
            btn_label = f"[{i+1}] {option}"
            if st.button(btn_label, key=f"btn_{i}", use_container_width=True):
                if i == q['ans_idx']:
                    st.success("⭕ 정답!")
                    time.sleep(0.7)
                    if st.session_state.current_idx < len(st.session_state.questions) - 1:
                        st.session_state.current_idx += 1
                        st.rerun()
                else:
                    st.error(f"❌ 오답! 정답은 {q['ans_idx']+1}번")

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
