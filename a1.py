import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageChops
import re
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="건설안전기사 모바일 v5.0", layout="centered")

# --- 스타일 설정 (버튼을 더 작고 세련되게) ---
st.markdown("""
    <style>
    /* 전체 배경 흰색 */
    .stApp { background-color: white; }
    
    /* 버튼 스타일 조정: 글자 크기 축소, 여백 최소화 */
    div.stButton > button {
        font-size: 12px !important;
        padding: 4px 10px !important;
        min-height: 28px !important;
        margin-bottom: -12px !important;
        border-radius: 5px !important;
        background-color: #f8f9fa !important;
        color: #333 !important;
    }
    
    /* 이미지와 버튼 사이 간격 제거 */
    .stImage { margin-top: -30px !important; margin-bottom: -20px !important; }
    
    /* 제목 크기 조정 */
    h1 { font-size: 20px !important; padding-top: 0px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 유틸리티: 이미지 여백 자동 제거 함수 ---
def trim_white_space(img):
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))
    diff = ImageChops.difference(img, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return img.crop(bbox)
    return img

# --- 세션 상태 초기화 ---
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0
if 'pdf_doc' not in st.session_state:
    st.session_state.pdf_doc = None

# --- PDF 분석 함수 ---
def parse_pdf(doc):
    q_list = []
    ans_markers = ['●', '⚫', '⬤', '❶', '❷', '❸', '❹', '❺']
    marker_pattern = re.compile(r'[①②③④' + "".join(ans_markers) + r']')
    
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
                            if any(am in m for am in ans_markers): curr['ans_idx'] = len(curr['options'])
                            curr['options'].append(contents[i] if i < len(contents) else "내용 없음")
                    elif curr['options']:
                        curr['options'][-1] = (curr['options'][-1] + " " + txt).strip()
            if curr: q_list.append(curr)
    return [q for q in q_list if len(q['options']) >= 4]

# --- 메인 로직 ---
st.title("👷‍♂️ 건설안전 v5.0 (지문 확대)")

uploaded_file = st.sidebar.file_uploader("PDF 업로드", type="pdf")

if uploaded_file:
    if st.session_state.pdf_doc is None:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        st.session_state.pdf_doc = doc
        st.session_state.questions = parse_pdf(doc)
        st.rerun()

    if st.session_state.questions:
        q = st.session_state.questions[st.session_state.current_idx]
        page = st.session_state.pdf_doc[q['page']]
        
        # 1. 문제 이미지 추출 (초고화질 Matrix 6.0)
        y_start = max(0, q['y0'] - 15)
        y_end = q['opt_y'] - 5 if q['opt_y'] else y_start + 300
        x0, x1 = (page.rect.width / 2) * q['side'], (page.rect.width / 2) * (q['side'] + 1)
        clip_rect = fitz.Rect(x0, y_start, x1, y_end)
        
        pix = page.get_pixmap(matrix=fitz.Matrix(6.0, 6.0), clip=clip_rect)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # 2. ★ 핵심: 지문 여백 자동 삭제 ★
        img = trim_white_space(img)
        
        # 3. 이미지 표시 (컨테이너 폭에 맞춤)
        st.image(img, use_container_width=True)

        # 4. 보기 선택 (더 콤팩트하게)
        st.write("") 
        for i, option in enumerate(q['options']):
            if st.button(f"{i+1}. {option}", key=f"opt_{i}", use_container_width=True):
                if i == q['ans_idx']:
                    st.success("⭕ 정답!")
                    time.sleep(0.8)
                    if st.session_state.current_idx < len(st.session_state.questions) - 1:
                        st.session_state.current_idx += 1
                        st.rerun()
                else:
                    st.error(f"❌ 오답! 정답은 {q['ans_idx']+1}번")

        # 5. 네비게이션
        st.write("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("⬅ 이전"):
                if st.session_state.current_idx > 0:
                    st.session_state.current_idx -= 1
                    st.rerun()
        with col2:
            st.write(f"**{st.session_state.current_idx + 1}/{len(st.session_state.questions)}**")
        with col3:
            if st.button("다음 ➔"):
                if st.session_state.current_idx < len(st.session_state.questions) - 1:
                    st.session_state.current_idx += 1
                    st.rerun()
else:
    st.info("사이드바에서 PDF를 선택해 주세요.")
