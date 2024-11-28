import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from openai import OpenAI
from datetime import datetime
import pytz

# Import configurations
from stage_prompts import STAGE_PROMPTS, INITIAL_ASSISTANT_MESSAGE
from review_instructions import REVIEW_INSTRUCTIONS, GRADING_CRITERIA, STYLE_GUIDES

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Page setup
st.set_page_config(page_title="DUTE Essay Writing Assistant", layout="wide")
st.markdown("""
    <style>
        .main { max-width: 800px; margin: 0 auto; }
        .chat-message { padding: 1rem; margin: 0.5rem 0; border-radius: 0.5rem; }
        #MainMenu, footer { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

class EWA:
    def __init__(self):
        self.tz = pytz.timezone("Europe/London")

    def get_conversations(self, user_id):
       """Retrieve conversation history from Firestore"""
       return db.collection('conversations')\
                .where('user_id', '==', user_id)\
                .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                .limit(10)\
                .stream()

    def render_sidebar(self):
        """Render sidebar with conversation history and controls"""
        with st.sidebar:
            st.title("Essay Writing Assistant")
            
            # New Session button
            if st.button("+ New Session", use_container_width=True):
                user = st.session_state.user  # Store user
                st.session_state.clear()
                st.session_state.user = user  # Restore user
                st.session_state.logged_in = True
                st.session_state.messages = [
                    {**INITIAL_ASSISTANT_MESSAGE, "timestamp": self.format_time()}
                ]
                st.rerun()
            
            st.divider()
            
            # Display conversation history
            for conv in self.get_conversations(st.session_state.user.uid):
                conv_data = conv.to_dict()
                if st.button(f"{conv_data.get('title', 'Untitled')}", key=conv.id):
                    messages = db.collection('conversations').document(conv.id)\
                              .collection('messages').order_by('timestamp').stream()
                    st.session_state.messages = []
                    for msg in messages:
                        msg_dict = msg.to_dict()
                        if 'timestamp' in msg_dict:
                            msg_dict['timestamp'] = self.format_time(msg_dict['timestamp'])
                        st.session_state.messages.append(msg_dict)
                    st.session_state.current_conversation_id = conv.id
                    st.rerun()

    def format_time(self, dt=None):
        if isinstance(dt, (datetime, type(firestore.SERVER_TIMESTAMP))):
            return dt.strftime("[%Y-%m-%d %H:%M:%S]")
        dt = dt or datetime.now(self.tz)
        return dt.strftime("[%Y-%m-%d %H:%M:%S]")

    def handle_chat(self, prompt):
        if not prompt:
            return

        current_time = datetime.now(self.tz)
        time_str = self.format_time(current_time)

        # Display user message
        st.chat_message("user").write(f"{time_str} {prompt}")

        # Get current stage and essay type
        current_stage = st.session_state.get('stage', 'initial')
        essay_type = st.session_state.get('essay_type', None)

        # Build conversation context
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]

        # Add stage-specific guidance
        if current_stage in STAGE_PROMPTS and essay_type in STAGE_PROMPTS.get(current_stage, {}):
            messages.append({
                "role": "assistant",
                "content": STAGE_PROMPTS[current_stage][essay_type]
            })

        # Add conversation history
        if 'messages' in st.session_state:
            messages.extend(st.session_state.messages)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        # Get AI response
        response = OpenAI(api_key=st.secrets["default"]["OPENAI_API_KEY"]).chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        assistant_content = response.choices[0].message.content
        st.chat_message("assistant").write(f"{time_str} {assistant_content}")

        # Update session state
        if 'messages' not in st.session_state:
            st.session_state.messages = []

        user_message = {"role": "user", "content": prompt, "timestamp": time_str}
        assistant_msg = {"role": "assistant", "content": assistant_content, "timestamp": time_str}
        
        st.session_state.messages.extend([user_message, assistant_msg])

        # Save to database
        try:
            conversation_id = st.session_state.get('current_conversation_id')
            conversation_id = self.save_message(conversation_id, 
                                             {**user_message, "timestamp": current_time})
            self.save_message(conversation_id, 
                            {**assistant_msg, "timestamp": current_time})
        except Exception as e:
            st.error(f"Error saving messages: {str(e)}")

    def save_message(self, conversation_id, message):
        current_time = datetime.now(self.tz)
        firestore_time = firestore.SERVER_TIMESTAMP

        try:
            if not conversation_id:
                new_conv_ref = db.collection('conversations').document()
                conversation_id = new_conv_ref.id
                
                if message['role'] == 'user':
                    title = f"{current_time.strftime('%b %d, %Y')} • DUTE Essay"
                    new_conv_ref.set({
                        'user_id': st.session_state.user.uid,
                        'created_at': firestore_time,
                        'updated_at': firestore_time,
                        'title': title,
                        'status': 'active'
                    })
                    st.session_state.current_conversation_id = conversation_id

            if conversation_id:
                conv_ref = db.collection('conversations').document(conversation_id)
                conv_ref.collection('messages').add({
                    **message,
                    "timestamp": firestore_time
                })
                
                conv_ref.set({
                    'updated_at': firestore_time,
                    'last_message': message['content'][:100]
                }, merge=True)
            
            return conversation_id
            
        except Exception as e:
            st.error(f"Error saving message: {str(e)}")
            return conversation_id

    def login(self, email, password):
        try:
            user = auth.get_user_by_email(email)
            st.session_state.user = user
            st.session_state.logged_in = True
            st.session_state.messages = []
            st.session_state.stage = 'initial'
            return True
        except:
            st.error("Login failed")
            return False

def main():
    app = EWA()

    # Login page
    if not st.session_state.get('logged_in', False):
        st.title("DUTE Essay Writing Assistant")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                if app.login(email, password):
                    st.rerun()
        return

    # Main chat interface
    app.render_sidebar()  # Add sidebar with conversation history

    # Add stage selector
    stages = ['topic', 'outline', 'drafting', 'review']
    if 'stage' not in st.session_state:
        st.session_state.stage = 'initial'

    # Display stage selection if past initial stage
    if st.session_state.stage != 'initial':
        selected_stage = st.sidebar.selectbox(
            "Current Stage",
            stages,
            index=stages.index(st.session_state.stage) if st.session_state.stage in stages else 0
        )
        if selected_stage != st.session_state.stage:
            st.session_state.stage = selected_stage
            st.rerun()

    # Display current stage guidance
    if st.session_state.stage in STAGE_PROMPTS:
        stage_prompt = app.get_stage_prompt(
            st.session_state.stage,
            st.session_state.get('essay_type'),
            st.session_state.get('current_section')
        )
        if stage_prompt:
            st.info(stage_prompt)

    # Display message history
    if 'messages' in st.session_state:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(
                f"{msg.get('timestamp', '')} {msg['content']}"
            )

    # Section selector for drafting stage
    if st.session_state.stage == 'drafting':
        sections = ['introduction', 'body', 'conclusion']
        current_section = st.sidebar.selectbox(
            "Current Section",
            sections,
            index=sections.index(st.session_state.get('current_section', 'introduction')) 
                if st.session_state.get('current_section') in sections else 0
        )
        if current_section != st.session_state.get('current_section'):
            st.session_state.current_section = current_section
            st.rerun()

    # Progress tracking
    if st.session_state.stage != 'initial':
        progress = {
            'topic': 0,
            'outline': 1,
            'drafting': 2,
            'review': 3
        }
        current_progress = progress.get(st.session_state.stage, 0)
        st.sidebar.progress(current_progress / 3)
        st.sidebar.write(f"Stage {current_progress + 1}/4: {st.session_state.stage.title()}")

    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Stage progression logic
        if st.session_state.stage == 'initial':
            if "1" in prompt:
                st.session_state.stage = 'topic'
                st.session_state.essay_type = 'design_case'
            elif "2" in prompt:
                st.session_state.stage = 'topic'
                st.session_state.essay_type = 'critique'
        elif 'outline' in prompt.lower() and st.session_state.stage == 'topic':
            st.session_state.stage = 'outline'
        elif 'draft' in prompt.lower() and st.session_state.stage == 'outline':
            st.session_state.stage = 'drafting'
            st.session_state.current_section = 'introduction'
        elif 'review' in prompt.lower() and st.session_state.stage == 'drafting':
            st.session_state.stage = 'review'

        app.handle_chat(prompt)

if __name__ == "__main__":
    main()
