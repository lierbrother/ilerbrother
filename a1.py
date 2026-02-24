import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageChops
import re
import time
import random

# --- 페이지 설정 ---
st.set_page_config(page_title="건설안전 v8.2 Mobile Fix", layout="centered")

# --- 강력한 모바일 한 줄 배치 CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    .stApp { background-color: white; }
    .app-title { font-size: 1.1rem; font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; text-align: center; }
    img { border: 1px solid #f0f0f0; border-radius: 8px; width: 100% !important; }
    
    /* 보기 버튼 스타일 */
    div.stButton > button {
        width: 100% !important;
        font-size: 13px !important;
        text-align: left !important;
        padding: 6px 10px !important;
        margin-bottom: -12px !important;
        background-color: #f8f9fa !important;
        border: 1px solid #ececec !important;
    }

    /* ★ 하단 네비게이션 한 줄 강제 배치 ★ */
    [data-testid="column"] {
        min-width: 0px !important;
        flex: 1 1 0% !important;
        text-align: center;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
    }
    
    /* 네비게이션 버튼 텍스트 크기 */
    div[data-testid="stHorizontalBlock"] button {
        font-size: 12px !important;
        padding: 5px !important;
        min-height: 35px !important;
    }

    .result-card { background-color: #e9ecef; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 유틸리티 함수 ---
def auto_crop(img):
    bg = Image.new(img.mode, img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img

def reset_quiz(mode='normal'):
    if not st.session_state.all_questions: return
    st.session_state.current_solve_ptr = 0
    st.session_state.quiz_finished = False
    indices = list(range(len(st.session_state.all_questions)))
    if mode == 'random': random.shuffle(indices)
    st.session_state.solve_indices = indices
    st.session_state.results = {}
    st.rerun()

def retry_incorrect():
    incorrect_indices = [idx for idx, res in st.session_state.results.items() if not res]
    if not incorrect_indices:
        st.sidebar.warning("틀린 문제가 없습니다!")
        return
    st.session_state.solve_indices = incorrect_indices
    st.session_state.current_solve_ptr = 0
    st.session_state.results = {}
    st.session_state.quiz_finished = False
    st.rerun()

# --- 세션 초기화 ---
if 'all_questions' not in st.session_state:
    st.session_state.update({
        'all_questions': [], 'solve_indices': [], 'current_solve_ptr': 0,
        'pdf_doc': None, 'last_file': None, 'results': {}, 'quiz_finished': False
    })

# --- PDF 분석 ---
def parse_pdf(doc):
    q_list = []
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
                            if m in ['❶','❷','❸','❹','❺','●','⚫','⬤']: curr['ans_idx'] = len(curr['options'])
                            curr['options'].append(contents[i] if i < len(contents) else "")
                    elif curr['options']:
                        curr['options'][-1] = (curr['options'][-1] + " " + txt).strip()
            if curr: q_list.append(curr)
    for q in q_list:
        if q['ans_idx'] == -1: q['ans_idx'] = 0
    return q_list

# --- 메인 실행 ---
st.markdown('<p class="app-title">👷‍♂️ 건설안전 v8.2 (모바일 최적화)</p>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 도구")
    uploaded_file = st.file_uploader("PDF 업로드", type="pdf")
    if st.session_state.all_questions:
        if st.button("🔄 초기화"): reset_quiz('normal')
        if st.button("🎲 랜덤"): reset_quiz('random')
        if st.button("🔥 오답만"): retry_incorrect()

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        st.session_state.pdf_doc = doc
        st.session_state.all_questions = parse_pdf(doc)
        st.session_state.solve_indices = list(range(len(st.session_state.all_questions)))
        st.session_state.last_file = uploaded_file.name
        st.rerun()

    if st.session_state.quiz_finished:
        score = list(st.session_state.results.values()).count(True)
        st.markdown(f'<div class="result-card"><h3>🎉 학습 완료!</h3><h4>{score} / {len(st.session_state.solve_indices)}</h4></div>', unsafe_allow_html=True)
        for idx in st.session_state.solve_indices:
            q = st.session_state.all_questions[idx]
            color = "green" if st.session_state.results.get(idx) else "red"
            st.markdown(f"**{q['num']}번:** <span style='color:{color}'>{'⭕' if color=='green' else '❌'}</span>", unsafe_allow_html=True)
    elif st.session_state.solve_indices:
        ptr = st.session_state.current_solve_ptr
        q = st.session_state.all_questions[st.session_state.solve_indices[ptr]]
        
        # 지문 캡처 및 출력
        page = st.session_state.pdf_doc[q['page']]
        y_start, y_end = max(0, q['y0'] - 12), (q['opt_y'] - 5 if q['opt_y'] else q['y0'] + 280)
        x_start = (page.rect.width / 2) * q['side']
        pix = page.get_pixmap(matrix=fitz.Matrix(3.5, 3.5), clip=fitz.Rect(x_start, y_start, x_start + (page.rect.width / 2), y_end))
        st.image(auto_crop(Image.frombytes("RGB", [pix.width, pix.height], pix.samples)), use_container_width=True)

        # 보기 버튼
        markers = ["①", "②", "③", "④"]
        for i, opt in enumerate(q['options']):
            if st.button(f"{markers[i]} {opt}", key=f"btn_{ptr}_{i}"):
                st.session_state.results[st.session_state.solve_indices[ptr]] = (i == q['ans_idx'])
                if i == q['ans_idx']: st.success("⭕ 정답!")
                else: st.error(f"❌ 오답! 정답은 {markers[q['ans_idx']]}")
                time.sleep(0.5)
                if ptr < len(st.session_state.solve_indices) - 1: st.session_state.current_solve_ptr += 1
                else: st.session_state.quiz_finished = True
                st.rerun()

        # ★ 하단 네비게이션 (한 줄 고정) ★
        st.write("---")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅ 이전"):
                if st.session_state.current_solve_ptr > 0:
                    st.session_state.current_solve_ptr -= 1
                    st.rerun()
        with c2:
            st.markdown(f"<p style='font-size:12px; margin-top:10px;'>{ptr + 1}/{len(st.session_state.solve_indices)}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("다음 ➔"):
                if ptr < len(st.session_state.solve_indices) - 1:
                    st.session_state.current_solve_ptr += 1
                    st.rerun()
                else:
                    st.session_state.quiz_finished = True
                    st.rerun()
else:
    st.info("사이드바에서 PDF 파일을 업로드해 주세요!")
