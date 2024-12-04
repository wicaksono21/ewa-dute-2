import streamlit as st
from streamlit.runtime.caching import cache_data, cache_resource
import firebase_admin
from firebase_admin import credentials, auth, firestore
from openai import OpenAI
from datetime import datetime
import pytz
import requests

# Import configurations
from stageprompts import INITIAL_ASSISTANT_MESSAGE
from reviewinstructions import SYSTEM_INSTRUCTIONS, REVIEW_INSTRUCTIONS, DISCLAIMER, SCORING_CRITERIA

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

    def _convert_conversation_to_dict(self, conv):
        """Helper method to convert Firestore conversation to dictionary"""
        data = conv.to_dict()
        data['id'] = conv.id
        return data
    
    @st.cache_data(ttl=60)  # Cache for 1 minute
    def format_time(_self, dt=None):
        """Format datetime with consistent timezone"""
        tz = pytz.timezone("Europe/London")  # Move timezone inside method
        if isinstance(dt, (datetime, type(firestore.SERVER_TIMESTAMP))):
            return dt.strftime("[%Y-%m-%d %H:%M:%S]")
        dt = dt or datetime.now(self.tz)
        return dt.strftime("[%Y-%m-%d %H:%M:%S]")           

    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def get_conversations(_self, user_id):
        """Retrieve conversation history from Firestore"""
        try:
            # Get total conversation count
            query = db.collection('conversations').where('user_id', '==', user_id)
            count = len(list(query.stream()))
    
            # Calculate start position based on current page
            page = st.session_state.get('page', 0)
            start = page * 10
    
            # Get conversations and convert to list of dictionaries
            conversations = list(query
                .order_by('updated_at', direction=firestore.Query.DESCENDING)
                .offset(start)
                .limit(10)
                .stream())
            
            # Convert to serializable format
            conv_list = [_self._convert_conversation_to_dict(conv) for conv in conversations]
            
            return conv_list, count > (start + 10)
            
        except Exception as e:
            st.error(f"Error fetching conversations: {str(e)}")
            return [], False

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
                if st.button(f"{conv.get('title', 'Untitled')}", key=conv['id']):
                    messages = db.collection('conversations').document(conv['id'])\
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
        review_keywords = [
            # Grade variations
            "grade", "grades", "grading", "graded",
            # Score variations
            "score", "scores", "scoring", "scored",
            # Review variations
            "review", "reviews", "reviewing", "reviewed",
            # Assess variations
            "assess", "assesses", "assessing", "assessed", "assessment",
            # Evaluate variations
            "evaluate", "evaluates", "evaluating", "evaluated", "evaluation",
            # Feedback (no common variations)
            "feedback"
            # Feedback (no common variations)
            "rubric"
        ]
        is_review = any(keyword in prompt.lower() for keyword in review_keywords)
    
        if is_review:            
            messages.append({
                "role": "system",
                "content": REVIEW_INSTRUCTIONS            
            })            
            max_tokens = 5000
        else:            
            max_tokens = 400

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

    
    # For save_message, we'll create a separate cached helper function
    @st.cache_data(ttl=60)
    def _get_conversation_summary(_self, messages, current_time):
        """Helper function to get conversation summary"""
        recent_messages = [msg.to_dict()['content'] for msg in messages[-5:]]
        context = " ".join(recent_messages)
        
        summary = OpenAI(api_key=st.secrets["default"]["OPENAI_API_KEY"]).chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Create a 2-3 word title for this conversation."},
                {"role": "user", "content": context}
            ],
            temperature=0.3,
            max_tokens=10
        ).choices[0].message.content.strip()
        
        return f"{current_time.strftime('%b %d, %Y')} • {summary} [{len(messages)}📝]"
    
    def save_message(self, conversation_id, message):
        """Save message and update title with summary"""
        current_time = datetime.now(self.tz)
        
        try:
            # For new conversation
            if not conversation_id:
                new_conv_ref = db.collection('conversations').document()
                conversation_id = new_conv_ref.id
                new_conv_ref.set({
                    'user_id': st.session_state.user.uid,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP,
                    'title': f"{current_time.strftime('%b %d, %Y')} • New Chat [1📝]",
                    'status': 'active'
                })
                st.session_state.current_conversation_id = conversation_id
        
            # Save message
            conv_ref = db.collection('conversations').document(conversation_id)
            conv_ref.collection('messages').add({
                **message,
                "timestamp": firestore.SERVER_TIMESTAMP
            })

            # Get messages and update title using cached function
            messages = list(conv_ref.collection('messages').get())
            title = self._get_conversation_summary(messages, current_time)
            
            # Update conversation with summary title
            conv_ref.set({
                'updated_at': firestore.SERVER_TIMESTAMP,
                'title': title
            }, merge=True)
        
            return conversation_id
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return conversation_id       
            
def main():
    # Initialize the EWA instance at the start
    if 'app' not in st.session_state:
        st.session_state.app = EWA()

    # Login handling
    if not st.session_state.get('logged_in', False):
        st.title("DUTE Essay Writing Assistant")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted and email and password:
                try:
                    # Firebase Auth REST API endpoint
                    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={st.secrets['default']['apiKey']}"
                    response = requests.post(auth_url, json={
                        "email": email,
                        "password": password,
                        "returnSecureToken": True
                    })
                    
                    if response.status_code == 200:
                        user = auth.get_user_by_email(email)
                        st.session_state.user = user
                        st.session_state.logged_in = True
                        st.session_state.messages = [{
                            **INITIAL_ASSISTANT_MESSAGE,
                            "timestamp": st.session_state.app.format_time()
                        }]
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                except Exception as e:
                    st.error("Login failed")
        return

    # Main chat interface
    app = st.session_state.app
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
