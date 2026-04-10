import streamlit as st
import anthropic
import base64
import json
import sys
import os
import PIL.Image
import io
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_active_assignments, save_submission, mark_viewed

st.set_page_config(page_title="学生作文提交", page_icon="✏️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@300;400;500&display=swap');
* { font-family: 'Noto Sans SC', sans-serif; }
h1,h2,h3 { font-family: 'Noto Serif SC', serif; }
.main { background: #faf8f5; }

.page-header {
    background: linear-gradient(135deg, #1a1a2e, #0f3460);
    color: white; border-radius: 16px; padding: 1.5rem 2rem;
    margin-bottom: 1.5rem; display: flex; align-items: center; gap: 1rem;
}
.page-header h2 { color: #f0c27f; margin: 0; font-size: 1.6rem; }
.page-header p { color: #b8c5d6; margin: 0; font-size: 0.95rem; }

.card {
    background: white; border-radius: 16px; padding: 1.5rem;
    border: 1px solid #e8e0d5; margin-bottom: 1rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}
.step-badge {
    background: #0f3460; color: #f0c27f; border-radius: 50%;
    width: 28px; height: 28px; display: inline-flex;
    align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.9rem; margin-right: 0.5rem;
}
.assignment-badge {
    background: #f0c27f22; border: 1px solid #f0c27f;
    border-radius: 8px; padding: 0.8rem 1rem;
    color: #7a5c1e; font-size: 0.95rem; margin-bottom: 0.5rem;
}
.ocr-warning {
    background: #fff8e1; border: 1px solid #ffc107;
    border-radius: 8px; padding: 0.8rem 1rem; color: #7a5000;
    font-size: 0.9rem; margin-bottom: 0.8rem;
}
.feedback-section { border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem; }
.strengths { background: #e8f5e9; border-left: 4px solid #43a047; }
.issues-lang { background: #fff3e0; border-left: 4px solid #fb8c00; }
.issues-struct { background: #e3f2fd; border-left: 4px solid #1e88e5; }
.issues-content { background: #fce4ec; border-left: 4px solid #e53935; }
.suggestions { background: #f3e5f5; border-left: 4px solid #8e24aa; }
.upgrade-section { background: #f9fbe7; border-left: 4px solid #c0ca33; border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem; }
.issue-item {
    background: white; border-radius: 8px; padding: 0.8rem;
    margin-bottom: 0.6rem; font-size: 0.92rem;
}
.location-tag {
    background: #1a1a2e; color: white; border-radius: 4px;
    padding: 0.1rem 0.5rem; font-size: 0.78rem; margin-right: 0.5rem;
}
.original { color: #c62828; text-decoration: line-through; }
.improved { color: #2e7d32; font-weight: 500; }
.level-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; margin-top: 0.5rem; }
.level-table th { background: #1a1a2e; color: #f0c27f; padding: 0.5rem 0.7rem; text-align: left; font-size: 0.82rem; }
.level-table td { padding: 0.5rem 0.7rem; border-bottom: 1px solid #e8e0d5; vertical-align: top; }
.level-table tr:nth-child(even) td { background: #fafaf0; }
.orig-cell { color: #c62828; }
.mid-cell { color: #e65100; }
.best-cell { color: #2e7d32; font-weight: 500; }
.tip-cell { color: #6a1b9a; font-size: 0.78rem; background: #f3e5f5; border-radius: 4px; padding: 0.2rem 0.4rem; }
.stButton > button {
    background: linear-gradient(135deg, #0f3460, #16213e);
    color: white; border: none; border-radius: 10px;
    padding: 0.7rem 2rem; font-family: 'Noto Sans SC', sans-serif;
    font-size: 1rem; font-weight: 500; width: 100%;
}
.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(15,52,96,0.3); }
.stTextInput > div > div > input { border-radius: 10px; border-color: #e8e0d5; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.markdown("""
<div class="page-header">
    <span style="font-size:2rem">✏️</span>
    <div><h2>学生作文提交</h2><p>上传作文照片，获取即时批改反馈</p></div>
</div>""", unsafe_allow_html=True)

if st.button("← 返回主页"):
    st.switch_page("app.py")

assignments = get_active_assignments()
if not assignments:
    st.info("📢 目前没有开放中的作文题目，请联系老师。")
    st.stop()

# ═══════════════════════════════════════════════════════════
# STAGE 1 — Student info + upload
# ═══════════════════════════════════════════════════════════
if 'ocr_done' not in st.session_state:
    st.session_state['ocr_done'] = False
if 'feedback' not in st.session_state:
    st.session_state['feedback'] = None

if not st.session_state['ocr_done']:

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="step-badge">1</span> **填写你的资料**', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        student_id = st.text_input("学号", placeholder="例如：24S101A")
    with col2:
        student_name = st.text_input("姓名", placeholder="例如：陈明辉")

    assignment_options = {f"{a['title']} ({a['genre']})": a for a in assignments}
    selected_label = st.selectbox("选择作文题目", list(assignment_options.keys()))
    selected_assignment = assignment_options[selected_label]

    if selected_assignment:
        st.markdown(f'<div class="assignment-badge">📌 <strong>题目：</strong>{selected_assignment["prompt"]}</div>', unsafe_allow_html=True)
        if selected_assignment.get('requirements'):
            st.markdown(f'<div class="assignment-badge" style="background:#e3f2fd22;border-color:#1e88e5;color:#1a3a5c;">📋 <strong>写作要求：</strong>{selected_assignment["requirements"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="step-badge">2</span> **上传作文照片（可多张）**', unsafe_allow_html=True)
    st.caption("作文有几页就上传几张，按顺序上传第1页、第2页……系统会自动合并识别。")
    uploaded_files = st.file_uploader(
        "请上传作文照片（JPG / PNG，可同时选多张）",
        type=["jpg","jpeg","png"],
        accept_multiple_files=True
    )
    if uploaded_files:
        st.caption(f"已上传 {len(uploaded_files)} 张照片：")
        cols = st.columns(min(len(uploaded_files), 3))
        for i, f in enumerate(uploaded_files):
            with cols[i % 3]:
                st.image(f, caption=f"第{i+1}页", use_column_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="step-badge">3</span> **选择语音反馈语言**', unsafe_allow_html=True)
    tts_lang = st.radio("批改结果将以你选择的语言朗读", ["普通话 (Mandarin)", "英语 (English)"], horizontal=True)
    st.markdown('</div>', unsafe_allow_html=True)

    can_ocr = student_id and student_name and uploaded_files
    if not can_ocr:
        st.warning("请填写学号、姓名，并上传作文照片。")

    if st.button("📷 识别作文文字（核对后才批改）", disabled=not can_ocr):
        with st.spinner(f"正在识别 {len(uploaded_files)} 张照片的文字，请稍候……"):
            try:
                # Read all images
                all_image_bytes = [f.read() for f in uploaded_files]

                client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

                def get_media_type(filename):
                    ext = filename.split(".")[-1].lower()
                    return "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"

                if len(all_image_bytes) == 1:
                    b64 = base64.standard_b64encode(all_image_bytes[0]).decode()
                    mt = get_media_type(uploaded_files[0].name)
                    ocr_resp = client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=3000,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
                            {"type": "text", "text": "请把图片中学生的手写作文，逐字逐句准确转录成文字。保留原本的分段结构，用换行表示分段。只输出转录的文字，不要加任何说明或评语。"}
                        ]}]
                    )
                    ocr_text = ocr_resp.content[0].text.strip()
                else:
                    all_pages = []
                    for i, (img_bytes, img_file) in enumerate(zip(all_image_bytes, uploaded_files)):
                        b64 = base64.standard_b64encode(img_bytes).decode()
                        mt = get_media_type(img_file.name)
                        page_resp = client.messages.create(
                            model="claude-3-5-sonnet-20241022",
                            max_tokens=3000,
                            messages=[{"role": "user", "content": [
                                {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
                                {"type": "text", "text": f"这是学生作文的第{i+1}页（共{len(all_image_bytes)}页）。请把这一页的手写文字逐字逐句准确转录成文字。保留分段结构，用换行表示分段。只输出转录的文字，不要加任何说明或页码标注。"}
                            ]}]
                        )
                        all_pages.append(page_resp.content[0].text.strip())
                    ocr_text = "\n".join(all_pages)

                st.session_state['ocr_text'] = ocr_text
                st.session_state['image_bytes'] = all_image_bytes[0]
                st.session_state['all_image_bytes'] = all_image_bytes
                st.session_state['all_image_names'] = [f.name for f in uploaded_files]
                st.session_state['selected_assignment'] = selected_assignment
                st.session_state['student_id'] = student_id
                st.session_state['student_name'] = student_name
                st.session_state['tts_lang'] = tts_lang
                st.session_state['ocr_done'] = True
                st.rerun()

            except Exception as e:
                st.error(f"识别出错：{e}")

# ═══════════════════════════════════════════════════════════
# STAGE 2 — OCR verification
# ═══════════════════════════════════════════════════════════
elif st.session_state['ocr_done'] and not st.session_state['feedback']:

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="step-badge">4</span> **核对识别文字**', unsafe_allow_html=True)
    st.markdown('<div class="ocr-warning">⚠️ 请仔细核对下面识别出来的文字，如有错误请直接修改，然后再点击"提交批改"。这也是你重新检查自己作文的好机会！</div>', unsafe_allow_html=True)

    col_orig, col_ocr = st.columns(2)
    with col_orig:
        all_imgs = st.session_state.get('all_image_bytes', [st.session_state['image_bytes']])
        st.markdown(f"**📸 原图（共{len(all_imgs)}页）**")
        for i, img_b in enumerate(all_imgs):
            st.image(img_b, caption=f"第{i+1}页", use_column_width=True)
    with col_ocr:
        st.markdown("**📝 识别出的文字（可直接修改）**")
        corrected_text = st.text_area(
            label="识别文字",
            value=st.session_state['ocr_text'],
            height=500,
            label_visibility="collapsed"
        )
    st.markdown('</div>', unsafe_allow_html=True)

    col_back, col_submit = st.columns(2)
    with col_back:
        if st.button("← 重新上传"):
            st.session_state['ocr_done'] = False
            st.rerun()
    with col_submit:
        if st.button("🚀 确认无误，提交批改！"):
            with st.spinner("AI 正在仔细批改你的作文，请稍候约30秒……"):
                try:
                    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                    asgn = st.session_state['selected_assignment']
                    genre = asgn['genre']
                    rubric = asgn.get('rubric', '')
                    prompt_text = asgn['prompt']
                    requirements = asgn.get('requirements', '')

                    try:
                        focus_list = json.loads(asgn.get('focus_areas') or '[]')
                    except:
                        focus_list = []

                    focus_instruction = ""
                    if focus_list:
                        focus_str = "、".join(focus_list)
                        focus_instruction = f"\n\n【本次批改重点】老师要求只重点关注以下方面：{focus_str}。其他方面如没有明显问题可以略过。"

                    if genre == "议论文":
                        dims = ["论点清晰度", "论据充分性", "论证逻辑", "结构组织", "语言表达"]
                    elif genre == "应用文":
                        dims = ["格式正确性", "语气得体性", "内容切题", "结构条理", "语言表达"]
                    else:
                        dims = ["内容主题", "情节结构", "人物描写", "语言表达", "开头结尾"]

                    dims_str = ", ".join([f'"{d}": 0到10的整数' for d in dims])

                    system_prompt = f"""你是一位经验丰富的新加坡中学华文老师，专门批改{genre}。
批改风格：简明清晰、鼓励为主、指出问题直接具体、示范改法实用。
学生是新加坡中学高级华文学生，中文程度中等，请用他们能理解的语言。
{focus_instruction}

评估标准：
{rubric if rubric else f'按照{genre}的一般标准评估：内容、结构、语言表达三个维度。'}

请严格按以下JSON格式返回，不要加任何其他文字或markdown标记：
{{
  "scores": {{{dims_str}}},
  "grade_estimate": "预估等级，如 A2 / B3 / C5",
  "audio_script": "口语化、鼓励性的总评，约100字，像老师面对面说话的语气",
  "strengths": ["优点1（具体）", "优点2（具体）"],
  "issues": {{
    "language": [
      {{"location": "第X段第Y句", "original": "原句", "improved": "改后句", "explanation": "简短说明（10字内）"}}
    ],
    "structure": [
      {{"location": "第X段", "problem": "问题", "suggestion": "建议"}}
    ],
    "content": [
      {{"location": "第X段", "problem": "问题", "suggestion": "建议"}}
    ]
  }},
  "upgrade_table": [
    {{"original": "原句（学生写的弱句）", "level2": "及格版（通顺）", "level3": "优秀版（生动有力）", "tip": "升级秘籍（10字内）"}}
  ],
  "overall_suggestion": "最重要的一句话建议（不超过50字）",
  "encouragement": "一句鼓励的话"
}}

upgrade_table只需提供3至5句最有代表性的弱句。"""

                    user_msg = f"""题目：{prompt_text}
写作要求：{requirements}
文体：{genre}

以下是学生的作文（经过OCR识别，学生已核对）：

{corrected_text}"""

                    response = client.messages.create(
                        model="claude-sonnet-4-5",
                        max_tokens=2500,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_msg}]
                    )

                    raw = response.content[0].text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    feedback = json.loads(raw.strip())

                    sub_id = save_submission(
                        asgn['id'],
                        st.session_state['student_id'],
                        st.session_state['student_name'],
                        st.session_state['image_bytes'],
                        corrected_text,
                        feedback
                    )
                    st.session_state['feedback'] = feedback
                    st.session_state['sub_id'] = sub_id
                    st.rerun()

                except json.JSONDecodeError:
                    st.error("AI返回格式有误，请重试。")
                    st.code(raw[:500])
                except Exception as e:
                    st.error(f"发生错误：{e}")

# ═══════════════════════════════════════════════════════════
# STAGE 3 — Show feedback
# ═══════════════════════════════════════════════════════════
elif st.session_state['feedback']:

    fb = st.session_state['feedback']
    sub_id = st.session_state.get('sub_id')
    lang = st.session_state.get('tts_lang', '普通话 (Mandarin)')
    name = st.session_state.get('student_name', '同学')

    if sub_id:
        mark_viewed(sub_id)

    st.markdown(f"## 📋 {name} 的作文批改结果")

    # ── Radar chart + grade ──────────────────────────────────
    scores = fb.get('scores', {})
    grade = fb.get('grade_estimate', '')
    if scores:
        try:
            import plotly.graph_objects as go
            col_r, col_g = st.columns([3, 1])
            with col_r:
                dims = list(scores.keys())
                vals = list(scores.values())
                fig = go.Figure(go.Scatterpolar(
                    r=vals + [vals[0]], theta=dims + [dims[0]],
                    fill='toself',
                    fillcolor='rgba(15,52,96,0.15)',
                    line=dict(color='#0f3460', width=2.5),
                    marker=dict(size=7, color='#f0c27f', line=dict(color='#0f3460', width=1.5))
                ))
                fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0,10], tickfont=dict(size=10))),
                    showlegend=False, height=320,
                    margin=dict(l=50,r=50,t=40,b=40),
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)
            with col_g:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:16px;
                    padding:2rem 1rem;text-align:center;color:white;margin-top:2rem;">
                    <div style="font-size:0.85rem;color:#b8c5d6;margin-bottom:0.3rem;">预估等级</div>
                    <div style="font-size:3rem;font-weight:700;color:#f0c27f;font-family:'Noto Serif SC',serif;">{grade}</div>
                </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.caption(f"图表暂时无法显示：{e}")

    # ── TTS ──────────────────────────────────────────────────
    audio_script = fb.get('audio_script', '')
    if not audio_script:
        strengths_text = "。".join(fb.get('strengths', []))
        audio_script = f"{name}同学，你好！{strengths_text}。{fb.get('overall_suggestion','')}。{fb.get('encouragement','')}"

    tts_voice_lang = "zh-CN" if "普通话" in lang else "en-US"
    tts_escaped = audio_script.replace('"', '\\"').replace('\n', ' ')

    st.components.v1.html(f"""
    <div style="background:#1a1a2e;border-radius:12px;padding:1rem 1.5rem;margin-bottom:1rem;
        display:flex;align-items:center;gap:1rem;flex-wrap:wrap;">
        <span style="color:#f0c27f;font-size:1.5rem;">🔊</span>
        <span style="color:#b8c5d6;font-family:'Noto Sans SC',sans-serif;font-size:0.95rem;flex:1;">
            {'老师语音总评' if '普通话' in lang else "Teacher's voice summary"}
        </span>
        <button onclick="speakFeedback()" style="background:#f0c27f;color:#1a1a2e;border:none;
            border-radius:8px;padding:0.5rem 1.2rem;font-weight:700;cursor:pointer;font-size:0.95rem;">
            ▶ {'朗读' if '普通话' in lang else 'Play'}
        </button>
        <button onclick="stopSpeaking()" style="background:#e53935;color:white;border:none;
            border-radius:8px;padding:0.5rem 1rem;font-weight:600;cursor:pointer;font-size:0.9rem;">
            ■ {'停止' if '普通话' in lang else 'Stop'}
        </button>
    </div>
    <div style="background:#1a1a2e22;border-radius:8px;padding:0.8rem 1rem;font-size:0.92rem;
        color:#1a1a2e;font-style:italic;margin-bottom:1rem;">
        💬 {audio_script}
    </div>
    <script>
    let utterance=null;
    function speakFeedback(){{
        stopSpeaking();
        utterance=new SpeechSynthesisUtterance("{tts_escaped}");
        utterance.lang="{tts_voice_lang}";
        utterance.rate=0.88;
        window.speechSynthesis.speak(utterance);
    }}
    function stopSpeaking(){{window.speechSynthesis.cancel();}}
    </script>""", height=150)

    # ── Strengths ─────────────────────────────────────────────
    strengths = fb.get('strengths', [])
    if strengths:
        st.markdown('<div class="feedback-section strengths">', unsafe_allow_html=True)
        st.markdown("#### ✅ 优点")
        for s in strengths:
            st.markdown(f"- {s}")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Upgrade table ──────────────────────────────────────────
    upgrades = fb.get('upgrade_table', [])
    if upgrades:
        st.markdown('<div class="upgrade-section">', unsafe_allow_html=True)
        st.markdown("#### ⬆️ 升级打怪：把你的句子变得更好！")
        st.caption("以下是你作文中有代表性的句子，三个等级让你看到差距在哪里：")
        rows_html = ""
        for u in upgrades:
            rows_html += f"""<tr>
                <td class="orig-cell">{u.get('original','')}</td>
                <td class="mid-cell">{u.get('level2','')}</td>
                <td class="best-cell">{u.get('level3','')}</td>
                <td><span class="tip-cell">{u.get('tip','')}</span></td>
            </tr>"""
        st.markdown(f"""
        <table class="level-table">
            <tr>
                <th>😐 你的原句</th>
                <th>🙂 及格版（通顺）</th>
                <th>😎 优秀版（生动有力）</th>
                <th>✨ 升级秘籍</th>
            </tr>
            {rows_html}
        </table>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Detailed issues ───────────────────────────────────────
    issues = fb.get('issues', {})
    lang_issues = issues.get('language', [])
    struct_issues = issues.get('structure', [])
    content_issues = issues.get('content', [])

    if lang_issues:
        st.markdown('<div class="feedback-section issues-lang">', unsafe_allow_html=True)
        st.markdown("#### 🔤 语言问题（词句）")
        for item in lang_issues:
            st.markdown(f"""<div class="issue-item">
                <span class="location-tag">{item.get('location','')}</span>
                <span class="original">❌ {item.get('original','')}</span> →
                <span class="improved">✓ {item.get('improved','')}</span><br>
                <small style="color:#666;margin-top:0.3rem;display:block;">💡 {item.get('explanation','')}</small>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if struct_issues:
        st.markdown('<div class="feedback-section issues-struct">', unsafe_allow_html=True)
        st.markdown("#### 🏗️ 结构问题")
        for item in struct_issues:
            st.markdown(f"""<div class="issue-item">
                <span class="location-tag">{item.get('location','')}</span>
                <strong>问题：</strong>{item.get('problem','')}<br>
                <small style="color:#1565c0;margin-top:0.3rem;display:block;">💡 建议：{item.get('suggestion','')}</small>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if content_issues:
        st.markdown('<div class="feedback-section issues-content">', unsafe_allow_html=True)
        st.markdown("#### 💡 内容问题")
        for item in content_issues:
            st.markdown(f"""<div class="issue-item">
                <span class="location-tag">{item.get('location','')}</span>
                <strong>问题：</strong>{item.get('problem','')}<br>
                <small style="color:#c62828;margin-top:0.3rem;display:block;">💡 建议：{item.get('suggestion','')}</small>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Overall suggestion ────────────────────────────────────
    st.markdown('<div class="feedback-section suggestions">', unsafe_allow_html=True)
    st.markdown("#### 🎯 老师最重要的建议")
    st.markdown(f"**{fb.get('overall_suggestion','')}**")
    st.markdown(f"\n✨ {fb.get('encouragement','')}")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("📝 提交另一篇作文"):
        for key in ['feedback','sub_id','ocr_done','ocr_text','image_bytes','all_image_bytes',
                    'all_image_names','selected_assignment','student_id','student_name','tts_lang']:
            st.session_state.pop(key, None)
        st.rerun()
