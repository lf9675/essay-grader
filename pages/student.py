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
                        model="claude-sonnet-4-5",
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
                            model="claude-sonnet-4-5",
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
        st.caption("如识别不准确，可借助其他工具识别后粘贴到这里，再点提交。")
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
                        max_tokens=5000,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_msg}]
                    )

                    raw = response.content[0].text.strip()

                    # 清理markdown标记
                    if "```" in raw:
                        parts = raw.split("```")
                        for part in parts:
                            part = part.strip()
                            if part.startswith("json"):
                                part = part[4:].strip()
                            if part.startswith("{"):
                                raw = part
                                break

                    # 提取 { ... } 内容
                    if not raw.strip().startswith("{"):
                        start = raw.find("{")
                        end = raw.rfind("}") + 1
                        if start != -1 and end > start:
                            raw = raw[start:end]

                    # 修复截断的JSON：补上缺失的结尾
                    raw = raw.strip()
                    if not raw.endswith("}"):
                        # 截断了，尝试补全
                        open_braces = raw.count("{") - raw.count("}")
                        open_brackets = raw.count("[") - raw.count("]")
                        # 关闭未关闭的字符串
                        if raw.count('"') % 2 != 0:
                            raw += '"'
                        # 关闭数组和对象
                        raw += "]" * max(0, open_brackets)
                        raw += "}" * max(0, open_braces)

                    try:
                        feedback = json.loads(raw)
                    except json.JSONDecodeError:
                        # 最后尝试：只提取已完整的字段
                        import re
                        scores_match = re.search(r'"scores"\s*:\s*\{[^}]+\}', raw)
                        grade_match = re.search(r'"grade_estimate"\s*:\s*"([^"]+)"', raw)
                        audio_match = re.search(r'"audio_script"\s*:\s*"([^"]+)"', raw)
                        feedback = {
                            "scores": json.loads("{" + scores_match.group(0) + "}") if scores_match else {},
                            "grade_estimate": grade_match.group(1) if grade_match else "",
                            "audio_script": audio_match.group(1) if audio_match else "",
                            "strengths": [],
                            "issues": {"language": [], "structure": [], "content": []},
                            "upgrade_table": [],
                            "overall_suggestion": "AI返回内容被截断，请重试一次。",
                            "encouragement": "请点击重新上传，再试一次！"
                        }

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
# STAGE 3 — Show feedback (分层展示)
# ═══════════════════════════════════════════════════════════
elif st.session_state['feedback']:

    fb = st.session_state['feedback']
    sub_id = st.session_state.get('sub_id')
    lang = st.session_state.get('tts_lang', '普通话 (Mandarin)')
    name = st.session_state.get('student_name', '同学')

    if sub_id:
        mark_viewed(sub_id)

    scores = fb.get('scores', {})
    grade = fb.get('grade_estimate', '')
    strengths = fb.get('strengths', [])
    issues = fb.get('issues', {})
    lang_issues = issues.get('language', [])
    struct_issues = issues.get('structure', [])
    content_issues = issues.get('content', [])
    upgrades = fb.get('upgrade_table', [])
    overall = fb.get('overall_suggestion', '')
    encourage = fb.get('encouragement', '')
    audio_script = fb.get('audio_script', '')
    if not audio_script:
        audio_script = f"{name}同学，你好！{'。'.join(strengths)}。{overall}。{encourage}"

    total_issues = len(lang_issues) + len(struct_issues) + len(content_issues)

    # ── 顶部摘要卡片 ─────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:20px;
        padding:1.5rem 2rem;margin-bottom:1.5rem;color:white;">
        <div style="font-size:1.1rem;color:#f0c27f;font-family:'Noto Serif SC',serif;
            margin-bottom:1rem;">📋 {name} 的作文批改结果</div>
        <div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center;">
            <div style="text-align:center;">
                <div style="font-size:0.75rem;color:#b8c5d6;">预估等级</div>
                <div style="font-size:2.8rem;font-weight:700;color:#f0c27f;
                    font-family:'Noto Serif SC',serif;line-height:1.1;">{grade}</div>
            </div>
            <div style="flex:1;min-width:200px;">
                <div style="font-size:0.85rem;color:#b8c5d6;margin-bottom:0.4rem;">
                    发现 <strong style="color:#f0c27f">{total_issues}</strong> 个问题
                    · <strong style="color:#7ecb8f">{len(strengths)}</strong> 个优点
                </div>
                <div style="font-size:0.9rem;color:#e0e8f0;line-height:1.6;">{overall}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 雷达图 ───────────────────────────────────────────────
    if scores:
        try:
            import plotly.graph_objects as go
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
                showlegend=False, height=300,
                margin=dict(l=50,r=50,t=30,b=30),
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.caption(f"图表暂时无法显示：{e}")

    # ── 语音总评 ─────────────────────────────────────────────
    tts_lang_code = "zh-TW" if "普通话" in lang else "en"
    st.markdown(f"""
    <div style="background:#1a1a2e;border-radius:12px;padding:0.8rem 1.2rem;
        margin-bottom:0.4rem;display:flex;align-items:center;gap:0.8rem;">
        <span style="color:#f0c27f;font-size:1.3rem;">🔊</span>
        <span style="color:#b8c5d6;font-size:0.9rem;">
            {"老师语音总评" if "普通话" in lang else "Teacher's voice summary"}
        </span>
    </div>
    <div style="background:#fdf8ee;border-radius:8px;padding:0.8rem 1rem;
        font-size:0.9rem;color:#3a3020;font-style:italic;
        margin-bottom:1rem;border-left:3px solid #f0c27f;">
        💬 {audio_script}
    </div>
    """, unsafe_allow_html=True)
    try:
        from gtts import gTTS
        import io as _io
        tts = gTTS(text=audio_script, lang=tts_lang_code, slow=False)
        audio_buf = _io.BytesIO()
        tts.write_to_fp(audio_buf)
        audio_buf.seek(0)
        st.audio(audio_buf, format="audio/mp3")
    except Exception as e:
        st.caption(f"语音暂时不可用：{e}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 四个展开按钮区 ───────────────────────────────────────
    st.markdown("### 👇 点击查看详细批改")

    # 优点
    with st.expander(f"✅ 优点  ({len(strengths)} 项)", expanded=False):
        for i, s in enumerate(strengths):
            st.markdown(f"""
            <div style="background:#e8f5e9;border-radius:10px;padding:0.8rem 1rem;
                margin-bottom:0.6rem;border-left:4px solid #43a047;">
                <span style="color:#1b5e20;font-weight:500;">第{i+1}点：</span>
                <span style="color:#2e7d32;">{s}</span>
            </div>""", unsafe_allow_html=True)

    # 语言问题
    with st.expander(f"🔤 语言问题（错别字、病句）  ({len(lang_issues)} 项)", expanded=False):
        if not lang_issues:
            st.success("这方面没有发现明显问题，继续保持！")
        for i, item in enumerate(lang_issues):
            loc = item.get('location','')
            orig = item.get('original','')
            imp = item.get('improved','')
            exp = item.get('explanation','')
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:1rem;
                margin-bottom:0.8rem;border:1px solid #ffe0b2;
                box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.6rem;">
                    <span style="background:#fb8c00;color:white;border-radius:4px;
                        padding:0.1rem 0.5rem;font-size:0.75rem;">问题 {i+1}</span>
                    <span style="background:#1a1a2e;color:white;border-radius:4px;
                        padding:0.1rem 0.5rem;font-size:0.75rem;">{loc}</span>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.8rem;margin-bottom:0.5rem;">
                    <div style="background:#fce4ec;border-radius:8px;padding:0.6rem 0.8rem;">
                        <div style="font-size:0.72rem;color:#c62828;margin-bottom:0.2rem;">❌ 你的写法</div>
                        <div style="color:#b71c1c;font-size:0.95rem;">{orig}</div>
                    </div>
                    <div style="background:#e8f5e9;border-radius:8px;padding:0.6rem 0.8rem;">
                        <div style="font-size:0.72rem;color:#2e7d32;margin-bottom:0.2rem;">✓ 改成这样</div>
                        <div style="color:#1b5e20;font-size:0.95rem;font-weight:500;">{imp}</div>
                    </div>
                </div>
                <div style="background:#fff8e1;border-radius:6px;padding:0.4rem 0.7rem;
                    font-size:0.82rem;color:#5d4037;margin-bottom:0.5rem;">
                    💡 {exp}
                </div>
            </div>""", unsafe_allow_html=True)
            try:
                from gtts import gTTS as _gTTS; import io as _io
                _t = _gTTS(text=f"{loc}。你写的是：{orig}。改成：{imp}。原因：{exp}", lang=tts_lang_code, slow=False)
                _b = _io.BytesIO(); _t.write_to_fp(_b); _b.seek(0)
                st.audio(_b, format="audio/mp3")
            except: pass

    # 结构与内容问题
    all_other = [('struct', i) for i in struct_issues] + [('content', i) for i in content_issues]
    with st.expander(f"🏗️ 结构与内容问题  ({len(all_other)} 项)", expanded=False):
        if not all_other:
            st.success("这方面没有发现明显问题，继续保持！")
        for i, (kind, item) in enumerate(all_other):
            loc = item.get('location','')
            prob = item.get('problem','')
            sug = item.get('suggestion','')
            color = "#1e88e5" if kind == 'struct' else "#e53935"
            bg = "#e3f2fd" if kind == 'struct' else "#fce4ec"
            label = "结构" if kind == 'struct' else "内容"
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:1rem;
                margin-bottom:0.8rem;border:1px solid #e0e7ef;
                box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.6rem;">
                    <span style="background:{color};color:white;border-radius:4px;
                        padding:0.1rem 0.5rem;font-size:0.75rem;">{label}问题 {i+1}</span>
                    <span style="background:#1a1a2e;color:white;border-radius:4px;
                        padding:0.1rem 0.5rem;font-size:0.75rem;">{loc}</span>
                </div>
                <div style="background:{bg};border-radius:8px;padding:0.6rem 0.8rem;margin-bottom:0.5rem;">
                    <div style="font-size:0.72rem;color:{color};margin-bottom:0.2rem;">⚠️ 发现的问题</div>
                    <div style="color:#333;font-size:0.92rem;">{prob}</div>
                </div>
                <div style="background:#f3e5f5;border-radius:8px;padding:0.6rem 0.8rem;margin-bottom:0.5rem;">
                    <div style="font-size:0.72rem;color:#7b1fa2;margin-bottom:0.2rem;">💡 老师建议</div>
                    <div style="color:#4a148c;font-size:0.92rem;">{sug}</div>
                </div>
            </div>""", unsafe_allow_html=True)
            try:
                from gtts import gTTS as _gTTS; import io as _io
                _t2 = _gTTS(text=f"{loc}。发现的问题：{prob}。老师建议：{sug}", lang=tts_lang_code, slow=False)
                _b2 = _io.BytesIO(); _t2.write_to_fp(_b2); _b2.seek(0)
                st.audio(_b2, format="audio/mp3")
            except: pass

    # 升级打怪
    with st.expander(f"⬆️ 升级打怪：把句子写得更好！  ({len(upgrades)} 句)", expanded=True):
        st.caption("每张卡片展示一句话的三个等级，看看差距在哪里：")
        for i, u in enumerate(upgrades):
            orig = u.get('original','')
            lv2 = u.get('level2','')
            lv3 = u.get('level3','')
            tip = u.get('tip','')
            st.markdown(f"""
            <div style="background:white;border-radius:14px;padding:1.1rem;
                margin-bottom:1rem;border:1px solid #e8e0d5;
                box-shadow:0 2px 10px rgba(0,0,0,0.07);">
                <div style="font-size:0.8rem;color:#888;margin-bottom:0.7rem;">
                    第 {i+1} 句
                    <span style="background:#f3e5f5;color:#6a1b9a;border-radius:20px;
                        padding:0.15rem 0.6rem;margin-left:0.5rem;font-size:0.75rem;">
                        ✨ 升级秘籍：{tip}
                    </span>
                </div>
                <div style="display:grid;grid-template-columns:1fr;gap:0.5rem;">
                    <div style="background:#fce4ec;border-radius:8px;padding:0.6rem 0.9rem;">
                        <span style="font-size:0.72rem;color:#c62828;">😐 你的原句</span><br>
                        <span style="color:#b71c1c;font-size:0.95rem;">{orig}</span>
                    </div>
                    <div style="background:#fff8e1;border-radius:8px;padding:0.6rem 0.9rem;">
                        <span style="font-size:0.72rem;color:#f57f17;">🙂 及格版（通顺）</span><br>
                        <span style="color:#e65100;font-size:0.95rem;">{lv2}</span>
                    </div>
                    <div style="background:#e8f5e9;border-radius:8px;padding:0.6rem 0.9rem;">
                        <span style="font-size:0.72rem;color:#2e7d32;">😎 优秀版（生动有力）</span><br>
                        <span style="color:#1b5e20;font-size:0.95rem;font-weight:500;">{lv3}</span>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#f3e5f5;border-radius:12px;padding:1rem 1.2rem;
        border-left:4px solid #8e24aa;margin-bottom:1rem;">
        <div style="font-size:0.8rem;color:#7b1fa2;margin-bottom:0.3rem;">✨ 鼓励</div>
        <div style="color:#4a148c;font-size:0.95rem;">{encourage}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("📝 提交另一篇作文"):
        for key in ['feedback','sub_id','ocr_done','ocr_text','image_bytes','all_image_bytes',
                    'all_image_names','selected_assignment','student_id','student_name','tts_lang']:
            st.session_state.pop(key, None)
        st.rerun()
