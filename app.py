import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from openai import OpenAI
from datetime import datetime
import pytz

# Initialize Firebase and Firestore
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Page setup
st.set_page_config(page_title="Essay Writing Assistant", layout="wide")
st.markdown("""
    <style>
        .main { max-width: 800px; margin: 0 auto; }
        .chat-message { padding: 1rem; margin: 0.5rem 0; border-radius: 0.5rem; background-color: #444654; color: white !important; }
        #MainMenu, footer { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# Keep only essential caching
@st.cache_resource
def get_static_messages():
    return {
        "initial": {
    "role": "assistant",
    "content": """Hi there! Ready to start your essay? I'm here to guide and help you improve your argumentative essay writing skills with activities like:

1. **Topic Selection**
2. **Outlining**
3. **Drafting**
4. **Reviewing**
5. **Proofreading**

What topic are you interested in writing about? If you'd like suggestions, just let me know!"""
           },
        "system": """Role: Essay Writing Assistant (300-500 words)
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
    • Once the outline is approved, prompt the student to draft each section of the essay one by one (Introduction, Body Paragraphs, Conclusion). Use up to two guiding questions for each section and pause for the student's draft.
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
    • Every three interactions, ask an emotional check-in question to gauge the student's comfort level and engagement.
    • Check-in Question Examples:
        ○ "How confident do you feel about presenting your argument effectively?"
        ○ "How are you feeling about your progress so far?"

Additional Guidelines:
    • Promote Critical Thinking: Encourage the student to reflect on their arguments, the evidence provided, and the effectiveness of addressing counterarguments.
    • Active Participation: Always pause after questions or feedback, allowing students to revise independently.
    • Clarification: If the student's response is unclear, always ask for more details before proceeding.
    • Student Voice: Help the student preserve their unique style and voice, and avoid imposing your own suggestions on the writing.
    • Strengthening Arguments: Emphasize the importance of logical reasoning, credible evidence, and effectively refuting counterarguments throughout the writing process."""
        
# Single cached object instead of separate functions
STATIC_MESSAGES = get_static_messages()
    }


class EWA:
    def __init__(self):
        self.tz = pytz.timezone("Europe/London")

    def generate_title(self, message_content, current_time):  
        title = current_time.strftime('%b %d, %Y • ') + ' '.join(message_content.split()[:4])
        return title[:50] if len(title) > 50 else title
    
    def format_time(self, dt=None):
        if isinstance(dt, (datetime, type(firestore.SERVER_TIMESTAMP))):
            return dt.strftime("[%Y-%m-%d %H:%M:%S]")
        dt = dt or datetime.now(self.tz)
        return dt.strftime("[%Y-%m-%d %H:%M:%S]")
    
    def get_conversations(self, user_id):
        return db.collection('conversations')\
                 .where('user_id', '==', user_id)\
                 .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                 .limit(10)\
                 .stream()
    
    def save_message(self, conversation_id, message):
        current_time = datetime.now(self.tz)
        firestore_time = firestore.SERVER_TIMESTAMP

        try:
            # Create new conversation if it doesn't exist
            if not conversation_id:
                # Generate new conversation ID and create conversation document
                new_conv_ref = db.collection('conversations').document()
                conversation_id = new_conv_ref.id
                
                if message['role'] == 'user':
                    # Create conversation document first
                    title = self.generate_title(message['content'], current_time)  # Added current_time parameter here
                    new_conv_ref.set({
                        'user_id': st.session_state.user.uid,
                        'created_at': firestore_time,
                        'updated_at': firestore_time,
                        'title': title or f"{current_time.strftime('%b %d, %Y')} • New Essay",
                        'status': 'active'
                    })  
                    st.session_state.current_conversation_id = conversation_id                                                
           
            # Save message to exisiting conversation
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
    
    def handle_chat(self, prompt):
        if not prompt:
            return
        
        current_time = datetime.now(self.tz)
        time_str = self.format_time(current_time)

        # IMMEDIATE USER MESSAGE DISPLAY
        st.chat_message("user").write(f"{time_str} {prompt}")

        # Create messages context including system instructions and conversation history
        messages_context = [
            {"role": "system", "content": STATIC_MESSAGES["system"]},
            *(st.session_state.messages if 'messages' in st.session_state else []),
            {"role": "user", "content": prompt}
        ]
    
        # Add current message to context
        #messages_context.append({"role": "user", "content": prompt})
               
        # Get AI response
        response = OpenAI(api_key=st.secrets["default"]["OPENAI_API_KEY"]).chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_context,
            temperature=0,
            max_tokens=200
        )
        
        # 4. IMMEDIATE ASSISTANT RESPONSE DISPLAY
        assistant_content = response.choices[0].message.content
        st.chat_message("assistant").write(f"{time_str} {assistant_content}")
        
        # 5. Update session state in background
        if 'messages' not in st.session_state:
            st.session_state.messages = []
    
        user_message = {"role": "user", "content": prompt, "timestamp": time_str}
        assistant_msg = {"role": "assistant", "content": assistant_content, "timestamp": time_str}

        # Update session state
        st.session_state.messages.append(user_message)
        st.session_state.messages.append(assistant_msg)
               
        # 5. DATABASE OPERATIONS (after display)
        try:
            # Get conversation ID if exists
            conversation_id = st.session_state.get('current_conversation_id')
        
            # Save user message
            conversation_id = self.save_message(
                conversation_id,
                {**user_message, "timestamp": current_time}  # Use actual timestamp for database
            )

            # Save assistant message
            self.save_message(
                conversation_id,
                {**assistant_msg, "timestamp": current_time}  # Use actual timestamp for database
            )
        except Exception as e:
            st.error(f"Error saving messages: {str(e)}")
        # Continue even if save fails - messages are already displayed
            
    def render_sidebar(self):
        with st.sidebar:
            st.title("Essay Writing Assistant")
            
            if st.button("+ New Session", use_container_width=True):
                user = st.session_state.user  # Store user
                st.session_state.clear()
                st.session_state.user = user  # Restore user
                st.session_state.logged_in = True
                st.session_state.messages = [
                    {**STATIC_MESSAGES["initial"], "timestamp": self.format_time()}
                ]
                st.rerun()
            
            st.divider()
            
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
    
    def render_messages(self):
        """Only render existing messages from session state"""
        if 'messages' in st.session_state:
            for msg in st.session_state.messages:
                if msg["role"] != "system":
                    st.chat_message(msg["role"]).write(
                        f"{msg.get('timestamp', '')} {msg['content']}"
                    )
    
    def login(self, email, password):
        try:
            user = auth.get_user_by_email(email)
            st.session_state.user = user
            st.session_state.logged_in = True
            st.session_state.messages = [{
                **STATIC_MESSAGES["initial"],
                "timestamp": self.format_time()
            }]
            return True
        except:
            st.error("Login failed")
            return False

def main():
    app = EWA()
    
    # Login page
    if not st.session_state.get('logged_in', False):
        st.title("Essay Writing Assistant")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                if app.login(email, password):
                    st.rerun()
        return
    
    # Main chat interface
    app.render_sidebar()
    app.render_messages()
    
    if prompt := st.chat_input("Type your message here..."):
        app.handle_chat(prompt)

if __name__ == "__main__":
    main()
