import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageChops
import re
import time
import random

# --- 페이지 설정 ---
st.set_page_config(page_title="건설안전 v8.0 Master", layout="centered")

# --- 모바일 최적화 스타일 ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    .stApp { background-color: white; }
    .app-title { font-size: 1.2rem; font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; text-align: center; }
    img { border: 1px solid #f0f0f0; border-radius: 8px; width: 100% !important; }
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
    .result-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 여백 제거 함수 ---
def auto_crop(img):
    bg = Image.new(img.mode, img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img

# --- 세션 상태 초기화 ---
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
                    curr = {'num': q_match.group(1), 'page': p_idx, 'y0': b[1], 'options': [], 'ans_idx': -1, 'side': side, 'opt_y': None, 'original_idx': len(q_list)}
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

# --- 앱 기능 로직 ---
def reset_quiz(mode='normal'):
    if not st.session_state.all_questions: return
    st.session_state.current_solve_ptr = 0
    st.session_state.results = {}
    st.session_state.quiz_finished = False
    
    indices = list(range(len(st.session_state.all_questions)))
    if mode == 'random':
        random.shuffle(indices)
    st.session_state.solve_indices = indices
    st.rerun()

def retry_incorrect():
    incorrect_indices = [idx for idx, res in st.session_state.results.items() if not res]
    if not incorrect_indices:
        st.warning("틀린 문제가 없습니다!")
        return
    st.session_state.solve_indices = incorrect_indices
    st.session_state.current_solve_ptr = 0
    st.session_state.results = {}
    st.session_state.quiz_finished = False
    st.rerun()

# --- 메인 UI ---
st.markdown('<p class="app-title">👷‍♂️ 건설안전기사 Master v8.0</p>', unsafe_allow_html=True)
uploaded_file = st.sidebar.file_uploader("PDF 업로드", type="pdf")

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        st.session_state.pdf_doc = doc
        st.session_state.all_questions = parse_pdf(doc)
        st.session_state.solve_indices = list(range(len(st.session_state.all_questions)))
        st.session_state.last_file = uploaded_file.name
        st.rerun()

    # 결과 화면 출력
    if st.session_state.quiz_finished:
        st.markdown(f"""<div class="result-card"><h2>🎉 학습 완료!</h2>
                    <h3>점수: {list(st.session_state.results.values()).count(True)} / {len(st.session_state.solve_indices)}</h3></div>""", unsafe_allow_html=True)
        
        # 맞춤/틀림 리스트 보여주기
        for idx in st.session_state.solve_indices:
            q_num = st.session_state.all_questions[idx]['num']
            status = "⭕ 정답" if st.session_state.results.get(idx) else "❌ 오답"
            color = "green" if st.session_state.results.get(idx) else "red"
            st.markdown(f"**{q_num}번 문제:** <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)
        
        st.write("---")
        if st.button("🔄 처음부터 다시 풀기"): reset_quiz('normal')
        if st.button("🔥 틀린 문제만 다시 풀기"): retry_incorrect()
        if st.button("🎲 랜덤 순서로 다시 풀기"): reset_quiz('random')

    # 문제 풀기 화면
    elif st.session_state.solve_indices:
        ptr = st.session_state.current_solve_ptr
        q_idx = st.session_state.solve_indices[ptr]
        q = st.session_state.all_questions[q_idx]
        page = st.session_state.pdf_doc[q['page']]
        
        # 지문 캡처
        y_start, y_end = max(0, q['y0'] - 12), (q['opt_y'] - 5 if q['opt_y'] else q['y0'] + 280)
        x_start = (page.rect.width / 2) * q['side']
        clip_rect = fitz.Rect(x_start, y_start, x_start + (page.rect.width / 2), y_end)
        pix = page.get_pixmap(matrix=fitz.Matrix(3.5, 3.5), clip=clip_rect)
        img = auto_crop(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        st.image(img, use_container_width=True)

        # 보기 선택
        markers = ["①", "②", "③", "④"]
        for i, option in enumerate(q['options']):
            if st.button(f"{markers[i]} {option}", key=f"btn_{q_idx}_{i}", use_container_width=True):
                is_correct = (i == q['ans_idx'])
                st.session_state.results[q_idx] = is_correct
                
                if is_correct: st.success("⭕ 정답입니다!")
                else: st.error(f"❌ 오답! 정답은 {markers[q['ans_idx']]} 입니다.")
                
                time.sleep(0.6)
                if ptr < len(st.session_state.solve_indices) - 1:
                    st.session_state.current_idx = ptr + 1
                    st.session_state.current_solve_ptr += 1
                else:
                    st.session_state.quiz_finished = True
                st.rerun()

        # 하단 제어
        st.write("---")
        c1, c2 = st.columns(2)
        with c1: st.write(f"진행: {ptr + 1} / {len(st.session_state.solve_indices)}")
        with c2: 
            if st.button("🏠 초기화"): reset_quiz()
