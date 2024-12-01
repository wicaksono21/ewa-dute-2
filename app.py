import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from openai import OpenAI
from datetime import datetime
import pytz
import requests

# Import configurations
from stageprompts import INITIAL_ASSISTANT_MESSAGE
from reviewinstructions import SYSTEM_INSTRUCTIONS, REVIEW_INSTRUCTIONS, DISCLAIMER

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
        self.conversations_per_page = 10  # Number of conversations per page


    def format_time(self, dt=None):
        """Format datetime with consistent timezone"""
        if isinstance(dt, (datetime, type(firestore.SERVER_TIMESTAMP))):
            return dt.strftime("[%Y-%m-%d %H:%M:%S]")
        dt = dt or datetime.now(self.tz)
        return dt.strftime("[%Y-%m-%d %H:%M:%S]")

    def generate_title(self, message_content, current_time):
        """Generate title from date and first 4 words of message"""
        title = current_time.strftime('%b %d, %Y • ') + ' '.join(message_content.split()[:4])
        return title[:50] if len(title) > 50 else title

    def get_conversations(self, user_id):
        """Retrieve conversation history from Firestore"""
        # Get total conversation count
        count = len(list(db.collection('conversations')
                        .where('user_id', '==', user_id)
                        .stream()))
    
        # Calculate start position based on current page
        page = st.session_state.get('page', 0)
        start = page * 10
    
        return db.collection('conversations')\
                 .where('user_id', '==', user_id)\
                 .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                 .offset(start)\
                 .limit(10)\
                 .stream(), count > (start + 10)

    def render_sidebar(self):
        """Render sidebar with conversation history"""
        with st.sidebar:
            st.title("Essay Writing Assistant")
        
            if st.button("New Session"):
                user = st.session_state.user
                st.session_state.clear()
                st.session_state.user = user
                st.session_state.logged_in = True
                st.session_state.messages = [
                    {**INITIAL_ASSISTANT_MESSAGE, "timestamp": self.format_time()}
                ]
                st.session_state.page = 0
                st.rerun()
            
            if st.button("Latest Chat History"):
                st.session_state.page = 0
                st.rerun()
            
            st.divider()
        
            # Initialize page if not exists
            if 'page' not in st.session_state:
                st.session_state.page = 0
            
            # Get conversations and has_more flag
            convs, has_more = self.get_conversations(st.session_state.user.uid)
        
            # Display conversations
            for conv in convs:
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
            
            # Simple pagination controls
            cols = st.columns(2)
            with cols[0]:
                if st.session_state.page > 0:
                    if st.button("Previous"):
                        st.session_state.page -= 1
                        st.rerun()
            with cols[1]:
                if has_more:
                    if st.button("Next"):
                        st.session_state.page += 1
                        st.rerun()
    
    def handle_chat(self, prompt):
        """Process chat messages and manage conversation flow"""
        if not prompt:
            return

        current_time = datetime.now(self.tz)
        time_str = self.format_time(current_time)

        # Display user message
        st.chat_message("user").write(f"{time_str} {prompt}")

        # Build messages context
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
        
        # Check for review/scoring related keywords
        review_keywords = ["review", "assess", "grade", "evaluate", "score", "feedback"]
        is_review = any(keyword in prompt.lower() for keyword in review_keywords)
    
        if is_review:            
            messages.append({
                "role": "system",
                "content": REVIEW_INSTRUCTIONS            
            })            
            max_tokens = 1000
        else:            
            max_tokens = 200

        # Add conversation history
        if 'messages' in st.session_state:
            messages.extend(st.session_state.messages)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        try:
            # Get AI response
            response = OpenAI(api_key=st.secrets["default"]["OPENAI_API_KEY"]).chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0,
                max_tokens=max_tokens
            )

            assistant_content = response.choices[0].message.content
            
            # Add disclaimer for review responses
            if is_review:
                assistant_content = f"{assistant_content}\n\n{DISCLAIMER}"
                
            st.chat_message("assistant").write(f"{time_str} {assistant_content}")

            # Update session state
            if 'messages' not in st.session_state:
                st.session_state.messages = []

            user_message = {"role": "user", "content": prompt, "timestamp": time_str}
            assistant_msg = {"role": "assistant", "content": assistant_content, "timestamp": time_str}
            
            st.session_state.messages.extend([user_message, assistant_msg])

            # Save to database
            conversation_id = st.session_state.get('current_conversation_id')
            conversation_id = self.save_message(conversation_id, 
                                             {**user_message, "timestamp": current_time})
            self.save_message(conversation_id, 
                            {**assistant_msg, "timestamp": current_time})

        except Exception as e:
            st.error(f"Error processing message: {str(e)}")

    def save_message(self, conversation_id, message):
        """Save message to Firestore database"""
        current_time = datetime.now(self.tz)
        firestore_time = firestore.SERVER_TIMESTAMP

        try:
            if not conversation_id:
                new_conv_ref = db.collection('conversations').document()
                conversation_id = new_conv_ref.id
                
                if message['role'] == 'user':
                    title = self.generate_title(message['content'], current_time)
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
        """Authenticate user with Firebase Auth REST API"""
        try:
            # Firebase Auth REST API endpoint
            auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={st.secrets['default']['apiKey']}"
        
            # Request body
            auth_data = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
        
            # Make authentication request
            response = requests.post(auth_url, json=auth_data)
            if response.status_code != 200:
                raise Exception("Authentication failed")
            
            # Get user details
            user = auth.get_user_by_email(email)
            st.session_state.user = user
            st.session_state.logged_in = True 
            st.session_state.messages = [{
                **INITIAL_ASSISTANT_MESSAGE,
                "timestamp": self.format_time()
            }]
            st.session_state.stage = 'initial'
            return True
        
        except Exception as e:
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
    st.title("DUTE Essay Writing Assistant")
    app.render_sidebar()

    # Display message history
    if 'messages' in st.session_state:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(
                f"{msg.get('timestamp', '')} {msg['content']}"
            )

    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        app.handle_chat(prompt)

if __name__ == "__main__":
    main()
