import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import re
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="건설안전기사 모바일 v3.0", layout="centered")

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

# --- 메인 화면 ---
st.title("👷‍♂️ 건설안전기사 모바일")

# 1. 파일 업로드 (다시 복구!)
uploaded_file = st.sidebar.file_uploader("PDF 파일을 선택하세요", type="pdf")

if uploaded_file:
    # 새로운 파일이 업로드되면 초기화
    if st.session_state.pdf_doc is None:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        st.session_state.pdf_doc = doc
        st.session_state.questions = parse_pdf(doc)
        st.rerun()

    if st.session_state.questions:
        q = st.session_state.questions[st.session_state.current_idx]
        page = st.session_state.pdf_doc[q['page']]
        
        # 2. 문제 이미지 추출 (3.0배 확대로 크게!)
        y_start = max(0, q['y0'] - 10)
        y_end = q['opt_y'] - 5 if q['opt_y'] else y_start + 250
        x0, x1 = (page.rect.width / 2) * q['side'], (page.rect.width / 2) * (q['side'] + 1)
        clip_rect = fitz.Rect(x0 + 5, y_start, x1 - 5, y_end)
        
        # Matrix(3, 3)으로 1.5배 더 선명하고 크게 캡처
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip_rect)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        
        st.image(img, use_container_width=True)

        st.write("---")
        # 3. 보기 선택 버튼 (번호 1. 2. 3. 4. 추가)
        for i, option in enumerate(q['options']):
            # 버튼 텍스트에 확실하게 번호 삽입
            if st.button(f" {i+1}번. {option}", key=f"opt_{i}", use_container_width=True):
                if i == q['ans_idx']:
                    st.success(f"⭕ 정답입니다! ({i+1}번)")
                    time.sleep(1)
                    if st.session_state.current_idx < len(st.session_state.questions) - 1:
                        st.session_state.current_idx += 1
                        st.rerun()
                else:
                    st.error(f"❌ 오답! 정답은 {q['ans_idx']+1}번입니다.")

        # 4. 네비게이션
        st.write("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("⬅ 이전"):
                if st.session_state.current_idx > 0:
                    st.session_state.current_idx -= 1
                    st.rerun()
        with col2:
            st.write(f"**{st.session_state.current_idx + 1} / {len(st.session_state.questions)}**")
        with col3:
            if st.button("다음 ➔"):
                if st.session_state.current_idx < len(st.session_state.questions) - 1:
                    st.session_state.current_idx += 1
                    st.rerun()
else:
    st.info("왼쪽 사이드바에서 PDF 파일을 업로드해 주세요!")
