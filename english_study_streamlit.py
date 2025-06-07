import streamlit as st
import json
import re
from typing import List, Dict
import openai
import os

# ページ設定
st.set_page_config(
    page_title="英語学習アプリ - 文法・語彙解析",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化関数
def init_session_state():
    if 'sentences' not in st.session_state:
        st.session_state.sentences = []
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0
    if 'show_all' not in st.session_state:
        st.session_state.show_all = False
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False
    if 'grammar_filter' not in st.session_state:
        st.session_state.grammar_filter = []
    if 'file_loaded' not in st.session_state:
        st.session_state.file_loaded = False

# 初期化を実行
init_session_state()

# カスタムCSS
st.markdown("""
<style>
    .sentence-card {
        background-color: white;
        padding: 25px;
        margin-bottom: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .sentence-number {
        background-color: #e74c3c;
        color: white;
        padding: 5px 12px;
        border-radius: 20px;
        display: inline-block;
        margin-bottom: 15px;
        font-weight: bold;
    }
    .english-text {
        font-size: 20px;
        color: #2c3e50;
        margin-bottom: 15px;
        line-height: 1.6;
        font-weight: 500;
    }
    .japanese-text {
        font-size: 16px;
        color: #555;
        margin-bottom: 15px;
        padding: 15px;
        background-color: #f8f9fa;
        border-left: 4px solid #3498db;
        border-radius: 4px;
    }
    .grammar-points {
        background-color: #e8f4f8;
        padding: 15px;
        border-radius: 5px;
        margin-top: 15px;
    }
    .grammar-title {
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 8px;
    }
    .highlight {
        background-color: #fff3cd;
        padding: 2px 4px;
        border-radius: 3px;
    }
</style>
""", unsafe_allow_html=True)

# コールバック関数
def go_prev():
    if st.session_state.current_index > 0:
        st.session_state.current_index -= 1

def go_next():
    if st.session_state.current_index < len(st.session_state.sentences) - 1:
        st.session_state.current_index += 1

def toggle_show_all():
    st.session_state.show_all = not st.session_state.show_all

def toggle_edit_mode():
    st.session_state.edit_mode = not st.session_state.edit_mode

def save_edit(index):
    japanese_key = f"japanese_{index}"
    grammar_key = f"grammar_{index}"
    
    if japanese_key in st.session_state:
        st.session_state.sentences[index]['japanese'] = st.session_state[japanese_key]
    if grammar_key in st.session_state:
        st.session_state.sentences[index]['grammar'] = st.session_state[grammar_key]

# ヘルパー関数
def parse_tsv_content(content: str) -> List[Dict[str, str]]:
    """TSVファイルの内容を解析"""
    sentences = []
    lines = content.strip().split('\n')
    
    # ヘッダー行をスキップ
    start_index = 0
    if lines and lines[0].strip():
        first_line = lines[0].lower()
        # 最初のタブ区切りの要素をチェック
        parts = lines[0].split('\t')
        if len(parts) >= 4:  # インデックス + 3つのカラム
            # 2番目の要素が「英文」というヘッダーかチェック
            if parts[1].strip() == '英文':
                start_index = 1
        elif 'english' in first_line or 'japanese' in first_line or 'grammar' in first_line:
            start_index = 1
    
    for i in range(start_index, len(lines)):
        line = lines[i]
        if line.strip():
            parts = line.split('\t')
            # インデックス番号がある場合は、2番目の要素から取得
            if len(parts) >= 4 and parts[0].strip().isdigit():
                sentence = {
                    'english': parts[1].strip() if parts[1] else '',
                    'japanese': parts[2].strip() if len(parts) > 2 and parts[2] else '',
                    'grammar': parts[3].strip() if len(parts) > 3 and parts[3] else ''
                }
            elif len(parts) >= 3:
                sentence = {
                    'english': parts[0].strip() if parts[0] else '',
                    'japanese': parts[1].strip() if len(parts) > 1 and parts[1] else '',
                    'grammar': parts[2].strip() if len(parts) > 2 and parts[2] else ''
                }
            else:
                continue
            
            # 空の英文はスキップ
            if sentence['english'] and sentence['english'] not in ['英文', 'english']:
                sentences.append(sentence)
    
    return sentences

def parse_json_content(content: str) -> List[Dict[str, str]]:
    """JSONファイルの内容を解析"""
    try:
        data = json.loads(content)
        
        if isinstance(data, list):
            sentences = []
            for item in data:
                if isinstance(item, dict):
                    sentence = {
                        'english': str(item.get('english', item.get('text', item.get('sentence', '')))),
                        'japanese': str(item.get('japanese', item.get('translation', ''))),
                        'grammar': str(item.get('grammar', item.get('grammar_points', '')))
                    }
                    sentences.append(sentence)
            return sentences
        elif isinstance(data, dict) and 'sentences' in data:
            return parse_json_content(json.dumps(data['sentences']))
    except:
        pass
    return []

def parse_pipe_text(content: str) -> List[Dict[str, str]]:
    """パイプ区切りテキストを解析"""
    sentences = []
    lines = content.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if line and '｜' in line:
            line = re.sub(r'^\d+[.、]\s*', '', line)
            parts = line.split('｜')
            if len(parts) >= 1:
                sentence = {
                    'english': parts[0].strip(),
                    'japanese': parts[1].strip() if len(parts) > 1 else '',
                    'grammar': parts[2].strip() if len(parts) > 2 else ''
                }
                sentences.append(sentence)
    
    return sentences

def split_text_with_llm(text: str) -> List[str]:
    """GPT-4o-miniを使用してテキストを適切な文単位に分割"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            # API Keyがない場合は簡易的な分割を行う
            return simple_split_sentences(text)
        
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""以下のテキストを、意味のある文単位に正確に分割してください。
各文は独立して理解できる完全な文になるようにしてください。
略語（Dr., Mr., etc.）や数字（1.5, 3:00）に注意してください。

テキスト:
{text}

以下の形式で、分割された文を1行ずつ出力してください：
1. [最初の文]
2. [2番目の文]
3. [3番目の文]
...以下同様"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは英文を適切に分割する専門家です。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content
        sentences = []
        
        # レスポンスから文を抽出
        lines = content.split('\n')
        for line in lines:
            # 番号付きリストから文を抽出
            match = re.match(r'^\d+\.\s*(.+)$', line.strip())
            if match:
                sentence = match.group(1).strip()
                if sentence:
                    sentences.append(sentence)
        
        return sentences if sentences else simple_split_sentences(text)
        
    except Exception as e:
        st.warning(f"LLMでの文分割に失敗しました。簡易分割を使用します。")
        return simple_split_sentences(text)

def simple_split_sentences(text: str) -> List[str]:
    """簡易的な文分割（フォールバック用）"""
    # 改行で分割
    lines = text.strip().split('\n')
    sentences = []
    
    for line in lines:
        line = line.strip()
        if line:
            # ピリオド、感嘆符、疑問符で分割（ただし略語は除外）
            # 簡易的な実装
            parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', line)
            sentences.extend([p.strip() for p in parts if p.strip()])
    
    return sentences

def parse_plain_text(content: str) -> List[Dict[str, str]]:
    """プレーンテキストを解析"""
    sentences = []
    
    # LLMを使って文を分割
    split_sentences = split_text_with_llm(content)
    
    for sentence_text in split_sentences:
        if sentence_text:
            sentence = {
                'english': sentence_text,
                'japanese': '',
                'grammar': ''
            }
            sentences.append(sentence)
    
    return sentences

def generate_translation_and_grammar(english_text: str) -> Dict[str, str]:
    """GPT-4o-miniを使用して日本語訳と文法・語彙ポイントを生成"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return {'japanese': '', 'grammar': ''}
        
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""以下の英文について、日本語訳と文法・語彙のポイントを提供してください。

英文: {english_text}

以下の形式で回答してください：
日本語訳: [自然な日本語訳]
文法・語彙のポイント: [重要な文法事項、語彙、表現の解説]"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは英語教育の専門家です。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        
        # レスポンスを解析
        japanese = ''
        grammar = ''
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('日本語訳:'):
                japanese = line.replace('日本語訳:', '').strip()
            elif line.startswith('文法・語彙のポイント:'):
                grammar = line.replace('文法・語彙のポイント:', '').strip()
                # 複数行にわたる場合の処理
                for j in range(i+1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith('日本語訳:'):
                        grammar += ' ' + lines[j].strip()
        
        return {'japanese': japanese, 'grammar': grammar}
        
    except Exception as e:
        st.error(f"GPT-4o-miniでの生成エラー: {str(e)}")
        return {'japanese': '', 'grammar': ''}

def highlight_grammar_points(text: str) -> str:
    """文法ポイントをハイライト"""
    # 接続詞
    conjunctions = ['However', 'Therefore', 'Although', 'Because', 'Since', 'While', 'When', 'If', 'Unless', 'As']
    for conj in conjunctions:
        text = text.replace(conj, f'<span class="highlight">{conj}</span>')
    
    # 関係詞
    relatives = ['which', 'who', 'whom', 'whose', 'that', 'where', 'when']
    for rel in relatives:
        pattern = r'\b' + rel + r'\b'
        text = re.sub(pattern, f'<span class="highlight">{rel}</span>', text, flags=re.IGNORECASE)
    
    return text

def extract_grammar_categories(sentences: List[Dict[str, str]]) -> List[str]:
    """文法カテゴリーを抽出"""
    categories = set()
    grammar_patterns = {
        '現在完了形': r'現在完了|have\s+\w+ed|has\s+\w+ed',
        '過去完了形': r'過去完了|had\s+\w+ed',
        '関係詞': r'関係[代名]?詞|which|who|whom|whose|that節',
        '仮定法': r'仮定法|would\s+have|could\s+have|should\s+have',
        '受動態': r'受[動身]態|be\s+\w+ed|was\s+\w+ed|were\s+\w+ed',
        '不定詞': r'不定詞|to\s+\w+',
        '動名詞': r'動名詞|ing形',
        '分詞構文': r'分詞構文|ing\s*句',
        '比較級': r'比較級|more\s+\w+|er\s+than',
        '最上級': r'最上級|most\s+\w+|est'
    }
    
    for sentence in sentences:
        grammar_text = sentence.get('grammar', '')
        for category, pattern in grammar_patterns.items():
            if re.search(pattern, grammar_text, re.IGNORECASE):
                categories.add(category)
    
    return sorted(list(categories))

def display_sentence(index: int, sentence: Dict[str, str]):
    """文を表示"""
    with st.container():
        st.markdown(f'<div class="sentence-card">', unsafe_allow_html=True)
        st.markdown(f'<span class="sentence-number">文 {index + 1}</span>', unsafe_allow_html=True)
        
        # 英文
        english_highlighted = highlight_grammar_points(sentence['english'])
        st.markdown(f'<div class="english-text">{english_highlighted}</div>', unsafe_allow_html=True)
        
        if st.session_state.edit_mode:
            # 編集モード
            col1, col2 = st.columns(2)
            with col1:
                new_japanese = st.text_area(
                    "日本語訳",
                    value=sentence['japanese'],
                    key=f"japanese_{index}",
                    height=100
                )
            with col2:
                new_grammar = st.text_area(
                    "文法・語彙",
                    value=sentence['grammar'],
                    key=f"grammar_{index}",
                    height=100
                )
            
            if st.button("💾 保存", key=f"save_{index}", on_click=save_edit, args=(index,)):
                st.success("保存しました")
        else:
            # 表示モード
            if sentence['japanese']:
                st.markdown(f'<div class="japanese-text">{sentence["japanese"]}</div>', unsafe_allow_html=True)
            
            if sentence['grammar']:
                st.markdown('<div class="grammar-points">', unsafe_allow_html=True)
                st.markdown('<div class="grammar-title">📚 文法・語彙のポイント</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="grammar-content">{sentence["grammar"]}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# メインアプリ
def main():
    st.title("🎓 英語特講2025 - 文法・語彙解析")
    
    # サイドバー
    with st.sidebar:
        st.header("設定")
        
        # ファイルアップロード
        st.subheader("📁 ファイル読み込み")
        uploaded_file = st.file_uploader(
            "ファイルを選択",
            type=['tsv', 'json', 'txt'],
            help="TSV、JSON、またはテキストファイルをアップロード",
            key="file_uploader"
        )
        
        # OpenAI API Key入力
        st.subheader("🔑 OpenAI API設定")
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="英文のみの場合、GPT-4o-miniで日本語訳と文法ポイントを自動生成します"
        )
        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key
        
        if uploaded_file is not None and not st.session_state.file_loaded:
            content = uploaded_file.read().decode('utf-8')
            
            if uploaded_file.name.endswith('.tsv'):
                sentences = parse_tsv_content(content)
            elif uploaded_file.name.endswith('.json'):
                sentences = parse_json_content(content)
            elif '｜' in content:
                sentences = parse_pipe_text(content)
            else:
                sentences = parse_plain_text(content)
            
            if sentences:
                # 英文のみの場合はGPT-4o-miniで翻訳と文法ポイントを生成
                if all(not s['japanese'] and not s['grammar'] for s in sentences):
                    total = len(sentences)
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, sentence in enumerate(sentences):
                        if sentence['english'] and not sentence['japanese']:
                            status_text.text(f"処理中... ({i+1}/{total})")
                            result = generate_translation_and_grammar(sentence['english'])
                            sentences[i]['japanese'] = result['japanese']
                            sentences[i]['grammar'] = result['grammar']
                            progress_bar.progress((i + 1) / total)
                    
                    progress_bar.empty()
                    status_text.empty()
                
                st.session_state.sentences = sentences
                st.session_state.current_index = 0
                st.session_state.file_loaded = True
                st.success(f"{len(sentences)}個の文を読み込みました")
                st.rerun()
        
        # ファイルがアップロードされていない状態に戻った場合の処理
        if uploaded_file is None and st.session_state.file_loaded:
            st.session_state.file_loaded = False
            st.session_state.sentences = []
            st.session_state.current_index = 0
            st.rerun()
        
        st.divider()
        
        # 文法フィルター
        if st.session_state.sentences:
            st.subheader("🔍 文法フィルター")
            categories = extract_grammar_categories(st.session_state.sentences)
            selected_categories = st.multiselect(
                "文法項目を選択",
                categories,
                default=st.session_state.grammar_filter,
                key="grammar_filter_select"
            )
            st.session_state.grammar_filter = selected_categories
    
    # メインコンテンツ
    if not st.session_state.sentences:
        st.info("👈 サイドバーからファイルをアップロードしてください")
        return
    
    # 統計情報
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("総文数", len(st.session_state.sentences))
    with col2:
        current = st.session_state.current_index + 1
        st.metric("現在の文", f"{current}/{len(st.session_state.sentences)}")
    with col3:
        incomplete = sum(1 for s in st.session_state.sentences if not s['japanese'] or not s['grammar'])
        st.metric("未完成", incomplete)
    with col4:
        if st.session_state.grammar_filter:
            filtered = len([s for s in st.session_state.sentences 
                          if any(cat in s.get('grammar', '') for cat in st.session_state.grammar_filter)])
            st.metric("フィルター結果", filtered)
    
    st.divider()
    
    # コントロールボタン
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.button(
            "⬅️ 前へ", 
            disabled=st.session_state.current_index <= 0,
            on_click=go_prev,
            key="prev_button"
        )
    
    with col2:
        st.button(
            "➡️ 次へ", 
            disabled=st.session_state.current_index >= len(st.session_state.sentences) - 1,
            on_click=go_next,
            key="next_button"
        )
    
    with col3:
        toggle_text = "🔄 全文表示" if not st.session_state.show_all else "📄 単文表示"
        st.button(
            toggle_text,
            on_click=toggle_show_all,
            key="toggle_button"
        )
    
    with col4:
        edit_text = "✏️ 編集モード" if not st.session_state.edit_mode else "👁️ 表示モード"
        st.button(
            edit_text,
            on_click=toggle_edit_mode,
            key="edit_button"
        )
    
    st.divider()
    
    # 文の表示
    if st.session_state.show_all:
        # 全文表示モード
        for i, sentence in enumerate(st.session_state.sentences):
            if st.session_state.grammar_filter:
                if not any(cat in sentence.get('grammar', '') for cat in st.session_state.grammar_filter):
                    continue
            
            display_sentence(i, sentence)
    else:
        # 単文表示モード
        if 0 <= st.session_state.current_index < len(st.session_state.sentences):
            sentence = st.session_state.sentences[st.session_state.current_index]
            display_sentence(st.session_state.current_index, sentence)
    
    # デバッグ情報（開発中のみ表示）
    with st.expander("デバッグ情報", expanded=False):
        st.write("現在のインデックス:", st.session_state.current_index)
        st.write("総文数:", len(st.session_state.sentences))
        st.write("ファイル読み込み済み:", st.session_state.file_loaded)

if __name__ == "__main__":
    main()