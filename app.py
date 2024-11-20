import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from google.cloud.firestore import FieldFilter
from openai import OpenAI
from datetime import datetime, timedelta
import pytz

# Page configuration
st.set_page_config(
    page_title="Essay Writing Assistant",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clean interface
st.markdown("""
    <style>
        /* Global text colors */
        .main * {
            color: white !important;
        }
        
        /* Sidebar styling */
        .css-1d391kg {
            background-color: #202123;
        }
        
        .css-1d391kg * {
            color: white !important;
        }
        
        /* Sidebar buttons */
        .stButton > button {
            width: 100%;
            text-align: left;
            background-color: transparent !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            color: white !important;
            padding: 0.5rem;
        }
        
        /* Chat message styling */
        .chat-message {
            padding: 1.5rem;
            margin: 1rem 0;
            border-radius: 0.5rem;
            color: white !important;
        }
        
        .user-message {
            background-color: #343541;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .assistant-message {
            background-color: #444654;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Input field styling */
        .stTextInput input, .stTextArea textarea {
            color: white !important;
            background-color: #40414f !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }
        
        /* Main chat input */
        .stChatInput input {
            color: white !important;
            background-color: #40414f !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }
        
        /* Message content */
        .message-content {
            color: white !important;
        }
        
        /* Timestamp */
        .message-timestamp {
            color: rgba(255, 255, 255, 0.5) !important;
            font-size: 0.8rem;
        }
        
        /* Headers and titles */
        h1, h2, h3, h4, h5, h6 {
            color: white !important;
        }
        
        /* All text elements */
        p, span, div {
            color: white !important;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

	/* Message content styling */
        .message-content {
            color: white !important;
            white-space: pre-wrap;
            line-height: 1.5;
        }
        
        /* Make markdown bold text more visible */
        .message-content strong {
            color: white !important;
            font-weight: 600;
        }
        
        /* Numbered list styling */
        .message-content ol {
            margin: 1rem 0;
            padding-left: 1.5rem;
        }
        
        .message-content ol li {
            margin: 0.5rem 0;
        }
        
        /* Message container */
        .chat-message {
            padding: 1rem;  /* Reduced padding */
            margin: 0.5rem 0;  /* Reduced margin */
            border-radius: 0.5rem;
            background-color: #444654;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Message content */
        .message-content {
            color: white !important;
            line-height: 1.4;  /* Reduced line height */
            margin: 0;  /* Remove margins */
        }
        
        /* Bold text */
        .message-content strong {
            color: white !important;
            font-weight: 600;
        }
        
        /* List styling */
        .message-content ol {
            margin: 0.3rem 0 0.3rem 1.2rem;  /* Compact margins */
            padding-left: 0;
        }
        
        .message-content ol li {
            margin: 0.2rem 0;  /* Reduced spacing between list items */
            padding-left: 0.3rem;
        }
        
        /* Timestamp */
        .message-timestamp {
            color: rgba(255, 255, 255, 0.5) !important;
            font-size: 0.8rem;
            margin-top: 0.5rem;  /* Reduced top margin */
        }
    </style>
""", unsafe_allow_html=True)

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Define initial assistant message with proper formatting
INITIAL_ASSISTANT_MESSAGE = {
    "role": "assistant",
    "content": """Hi there! Ready to start your essay? I'm here to guide and help you improve your argumentative essay writing skills with activities like:

1. **Topic Selection**
2. **Outlining**
3. **Drafting**
4. **Reviewing**
5. **Proofreading**

What topic are you interested in writing about? If you'd like suggestions, just let me know!"""
}

class ChatInterface:
    def __init__(self):
        self.london_tz = pytz.timezone("Europe/London")
        
    def initialize_session_state(self):
        """Initialize or get session state variables"""
        if "user" not in st.session_state:
            st.session_state.user = None
        if "current_conversation_id" not in st.session_state:
            st.session_state.current_conversation_id = None
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "last_activity" not in st.session_state:
            st.session_state.last_activity = datetime.now()

    def create_new_conversation(self, user_id: str) -> str:
        try:
            conversation_ref = db.collection('conversations').document()
            current_time = datetime.now(self.london_tz)
            conversation_data = {
                'user_id': user_id,
                'created_at': current_time,
                'updated_at': current_time,
                'title': f"Essay {current_time.strftime('%Y-%m-%d %H:%M')}",
                'status': 'active'
            }
            conversation_ref.set(conversation_data)

            # Add initial assistant message
            initial_message = {
                **INITIAL_ASSISTANT_MESSAGE,
                "timestamp": current_time
            }
            db.collection('conversations').document(conversation_ref.id)\
                .collection('messages').add(initial_message)

            return conversation_ref.id
        except Exception as e:
            st.error(f"Error creating conversation: {str(e)}")
            return None

    def load_conversation(self, conversation_id: str):
        """Load a specific conversation from Firestore"""
        try:
            messages = (db.collection('conversations')
                       .document(conversation_id)
                       .collection('messages')
                       .order_by('timestamp')
                       .stream())
            
            # Convert Firestore timestamps to strings
            formatted_messages = []
            for msg in messages:
                msg_dict = msg.to_dict()
                if 'timestamp' in msg_dict and hasattr(msg_dict['timestamp'], 'strftime'):
                    msg_dict['timestamp'] = msg_dict['timestamp'].strftime("%Y-%m-%d %H:%M")
                formatted_messages.append(msg_dict)
            
            st.session_state.messages = formatted_messages
            st.session_state.current_conversation_id = conversation_id
        except Exception as e:
            st.error(f"Error loading conversation: {str(e)}")

    def save_message(self, message: dict):
        """Save message to Firestore"""
        try:
            if not st.session_state.current_conversation_id:
                st.session_state.current_conversation_id = self.create_new_conversation(
                    st.session_state.user.uid
                )

            # Save to Firestore (message already contains datetime timestamp)
            db.collection('conversations').document(st.session_state.current_conversation_id)\
                .collection('messages').add(message)
            
            # Update conversation metadata
            db.collection('conversations').document(st.session_state.current_conversation_id)\
                .update({
                    'updated_at': message['timestamp'],
                    'last_message': message['content'][:100]
                })
        except Exception as e:
            st.error(f"Error saving message: {str(e)}")

    def get_user_conversations(self, user_id: str, limit: int = 10):
        """Get recent conversations for the user"""
        try:
            conversations = (db.collection('conversations')
                            .where(filter=FieldFilter("user_id", "==", user_id))
                            .order_by('updated_at', direction=firestore.Query.DESCENDING)
                            .limit(limit)
                            .stream())
            
            # Convert Firestore timestamps when returning
            formatted_conversations = []
            for conv in conversations:
                conv_dict = conv.to_dict()
                # Handle timestamps
                if 'created_at' in conv_dict and hasattr(conv_dict['created_at'], 'strftime'):
                    conv_dict['created_at'] = conv_dict['created_at'].strftime("%Y-%m-%d %H:%M")
                if 'updated_at' in conv_dict and hasattr(conv_dict['updated_at'], 'strftime'):
                    conv_dict['updated_at'] = conv_dict['updated_at'].strftime("%Y-%m-%d %H:%M")
                formatted_conversations.append({'id': conv.id, **conv_dict})
            
            return formatted_conversations
        except Exception as e:
            st.error(f"Error getting conversations: {str(e)}")
            return []

    def render_sidebar(self):
        with st.sidebar:
            st.markdown('<h2 style="color: white;">Essay Writing Assistant</h2>', unsafe_allow_html=True)
            
            if st.button("+ New Essay", key="new_chat", use_container_width=True):
                # Initialize new conversation with welcome message
                current_time = datetime.now(self.london_tz)
                st.session_state.messages = [{
                    **INITIAL_ASSISTANT_MESSAGE,
                    "timestamp": current_time.strftime("%H:%M")
                }]
                st.session_state.current_conversation_id = None
                st.rerun()
            
            st.markdown("<hr style='margin: 1rem 0; opacity: 0.2;'>", unsafe_allow_html=True)
            
            conversations = self.get_user_conversations(st.session_state.user.uid)
            for conv in conversations:
                if st.button(
                    conv.get('title', 'Untitled Essay'),
                    key=f"conv_{conv['id']}",
                    use_container_width=True
                ):
                    self.load_conversation(conv['id'])
                    st.rerun()

    def render_messages(self):
    	"""Render chat messages"""
    	for msg in st.session_state.messages:
            if msg["role"] != "system":
            	style_class = "assistant-message" if msg["role"] == "assistant" else "user-message"
            	timestamp = msg.get("timestamp", "")
            
            	# Clean up the content - remove extra newlines
            	content = msg["content"].strip()
            	content = content.replace("\n\n\n", "\n")  # Remove triple newlines
            	content = content.replace("\n\n", "\n")    # Convert double to single newlines
            
            	# Convert markdown
            	content = content.replace("**", "<strong>", 1)
            	content = content.replace("**", "</strong>", 1)
            	while "**" in content:
                	content = content.replace("**", "<strong>", 1)
                	content = content.replace("**", "</strong>", 1)
            
          	st.markdown(f"""
               	    <div class="chat-message {style_class}">
                    	<div class="message-content">{content}</div>
                    	<div class="message-timestamp">{timestamp}</div>
                     </div>
             	""", unsafe_allow_html=True)

    def handle_chat_input(self):
        """Handle chat input and responses"""
        if prompt := st.chat_input("Type your message here..."):
            try:
                # Create user message with string timestamp
                current_time = datetime.now(self.london_tz)
                user_message = {
                    "role": "user",
                    "content": prompt,
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M")
                }
                
                # Add to session state
                st.session_state.messages.append(user_message)
                
                # For Firestore, use datetime
                firestore_user_message = {
                    "role": "user",
                    "content": prompt,
                    "timestamp": current_time
                }
                self.save_message(firestore_user_message)
                
                # Get AI response with loading spinner
                with st.spinner('Getting response...'):
                    response = OpenAI(api_key=st.secrets["default"]["OPENAI_API_KEY"]).chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": """Role: Essay Writing Assistant (300-500 words)
Response Length: Keep answers brief and to the point. Max. 75 words per response.
Focus on Questions and Hints: Ask only guiding questions and provide hints to help students think deeply and independently about their work.
Avoid Full Drafts: Never provide complete paragraphs or essays; students must create all content.

Instructions:
1. Topic Selection:
	• Prompt: Begin by asking the student for their preferred argumentative essay topic. If they are unsure, suggest 2-3 debatable topics. Only proceed once a topic is chosen.
	• Hint: "What controversial issue are you passionate about, and what position do you want to argue? Why is this issue important to you?"
2. Initial Outline Development:
Request the student's outline ideas. Confirm the outline before proceeding.
	• Key Questions:
		○ Introduction: "What is your main argument or thesis statement that clearly states your position? (Estimated word limit: 50-100 words)"
		○ Body Paragraphs: "What key points will you present to support your thesis, and how will you address potential counterarguments? (Estimated word limit: 150-300 words)"
		○ Conclusion: "How will you summarize your argument and reinforce your thesis to persuade your readers? (Estimated word limit: 50-100 words)"
Provide all guiding questions at once, then confirm the outline before proceeding.
3. Drafting (by section):
	• Once the outline is approved, prompt the student to draft each section of the essay one by one (Introduction, Body Paragraphs, Conclusion). Use up to two guiding questions for each section and pause for the student’s draft.
		○ Guiding Questions for Introduction:
			§ "How will you hook your readers' attention on this issue?"
			§ "How will you present your thesis statement to clearly state your position?"
		○ Body Paragraphs:
			§ "What evidence and examples will you use to support each of your key points?"
			§ "How will you acknowledge and refute counterarguments to strengthen your position?"
		○ Conclusion:
			§ "How will you restate your thesis and main points to reinforce your argument?"
			§ "What call to action or final thought will you leave with your readers?"
4. Review and Feedback (by section):
	• Assessment: Evaluate the draft based on the rubric criteria, focusing on Content, Analysis, Organization & Structure, Quality of Writing, and Word Limit.
	• Scoring: Provide an approximate score (1-4) for each of the following areas:
		1. Content (30%) - Assess how well the student presents a clear, debatable position and addresses opposing views.
		2. Analysis (30%) - Evaluate the strength and relevance of arguments and evidence, including the consideration of counterarguments.
		3. Organization & Structure (15%) - Check the logical flow, clarity of structure, and effective use of transitions.
		4. Quality of Writing (15%) - Review sentence construction, grammar, and overall writing clarity.
		5. Word Limit (10%) - Determine if the essay adheres to the specified word count of 300-500 words.
	• Feedback Format:
		○ Strengths: Highlight what the student has done well in each assessed area, aligning with rubric descriptors.
		○ Suggestions for Improvement: Offer specific advice on how to enhance their score in each area. For example:
			§ For Content: "Consider further exploring opposing views to deepen your argument."
			§ For Analysis: "Include more credible evidence to support your claims and strengthen your analysis."
			§ For Organization & Structure: "Improve the transitions between paragraphs for a more cohesive flow."
			§ For Quality of Writing: "Work on refining sentence structures to enhance clarity."
			§ For Word Limit: "Trim any unnecessary information to stay within the word limit."
	• Feedback Guidelines:
		○ Provide up to two targeted feedback points per section, keeping suggestions constructive and actionable.
		○ Encourage the student to reflect on and revise their work based on this feedback before moving on to the next section.
  		○ Avoid proofreading for grammar, punctuation, or spelling at this stage.
	• Scoring Disclaimer: Mention that the score is an approximate evaluation to guide improvement and may differ from final grading.
5. Proofreading (by section):
	• After revisions, check for adherence to the rubric, proper citation, and argument strength.
	• Focus on one section at a time, providing up to two feedback points related to grammar, punctuation, and clarity.
6. Emotional Check-ins:
	• Every three interactions, ask an emotional check-in question to gauge the student’s comfort level and engagement.
	• Check-in Question Examples:
		○ "How confident do you feel about presenting your argument effectively?"
		○ "How are you feeling about your progress so far?"

Additional Guidelines:
	• Promote Critical Thinking: Encourage the student to reflect on their arguments, the evidence provided, and the effectiveness of addressing counterarguments.
	• Active Participation: Always pause after questions or feedback, allowing students to revise independently.
	• Clarification: If the student’s response is unclear, always ask for more details before proceeding.
	• Student Voice: Help the student preserve their unique style and voice, and avoid imposing your own suggestions on the writing.
	• Strengthening Arguments: Emphasize the importance of logical reasoning, credible evidence, and effectively refuting counterarguments throughout the writing process."""},
                            *[{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.messages]
                        ],
                        temperature=0,
                        presence_penalty=0.5,
                        frequency_penalty=0.5
                    )
                    
                    # Create assistant message with string timestamp
                    assistant_message = {
                        "role": "assistant",
                        "content": response.choices[0].message.content,
                        "timestamp": datetime.now(self.london_tz).strftime("%Y-%m-%d %H:%M")
                    }
                    
                    # Add to session state
                    st.session_state.messages.append(assistant_message)
                    
                    # For Firestore, use datetime
                    firestore_assistant_message = {
                        "role": "assistant",
                        "content": response.choices[0].message.content,
                        "timestamp": datetime.now(self.london_tz)
                    }
                    self.save_message(firestore_assistant_message)
                    
                st.rerun()
            except Exception as e:
                st.error(f"Error in chat handling: {str(e)}")

def login_page():
    st.markdown("""
        <div style="color: white; text-align: center; margin-bottom: 2rem;">
            <h1>Essay Writing Assistant</h1>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown('<p style="color: white;">Email</p>', unsafe_allow_html=True)
        email = st.text_input("", key="email")
        
        st.markdown('<p style="color: white;">Password</p>', unsafe_allow_html=True)
        password = st.text_input("", type="password", key="password")
        
        if st.button("Login", use_container_width=True):
            try:
                user = auth.get_user_by_email(email)
                st.session_state.user = user
                st.session_state.logged_in = True
                st.session_state.last_activity = datetime.now()
                
                # Initialize first conversation with welcome message
                current_time = datetime.now(pytz.timezone("Europe/London"))
                st.session_state.messages = [{
                    **INITIAL_ASSISTANT_MESSAGE,
                    "timestamp": current_time.strftime("%H:%M")
                }]
                
                st.rerun()
            except Exception as e:
                st.error("Login failed. Please check your credentials.")

def check_session_timeout():
    if 'last_activity' in st.session_state:
        if (datetime.now() - st.session_state.last_activity).seconds > 3600:
            st.session_state.clear()
            return True
    return False

def main():
    chat = ChatInterface()
    chat.initialize_session_state()
    
    if check_session_timeout():
        st.warning("Session expired. Please login again.")
        st.rerun()
    
    st.session_state.last_activity = datetime.now()
    
    if not st.session_state.get('logged_in', False):
        login_page()
        return
    
    chat.render_sidebar()
    
    if st.session_state.current_conversation_id:
        try:
            conversation = db.collection('conversations').document(
                st.session_state.current_conversation_id
            ).get().to_dict()
            if conversation:
                st.markdown(
                    f"<div class='conversation-title'>{conversation['title']}</div>",
                    unsafe_allow_html=True
                )
        except Exception as e:
            st.error(f"Error loading conversation title: {str(e)}")
    
    chat.render_messages()
    chat.handle_chat_input()

if __name__ == "__main__":
    main()
