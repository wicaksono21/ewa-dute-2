import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from openai import OpenAI
from datetime import datetime
import pytz

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

# Constants and Prompts
INITIAL_ASSISTANT_MESSAGE = {
    "role": "assistant",
    "content": """Hi there! Let's work on your DUTE Part B Essay. You have two options:

1. **Extending the group design case to a new problem**
   • Redefine the educational challenge
   • Analyze original design strengths/weaknesses
   • Propose and justify modifications

2. **Critiquing a data-driven technology's educational value**
   • Analyze an existing educational technology
   • Evaluate its impact and effectiveness
   • Suggest improvements

Which option would you like to explore? I'll guide you through the process."""
}

SYSTEM_INSTRUCTIONS = """Role: DUTE Essay Writing Assistant
Primary Task: Guide students through their 2,500-word Part B essay development
Focus: Keep responses brief and targeted. Ask guiding questions rather than providing direct content.

Instructions:
1. Topic Selection:
    • Help student choose and refine their essay focus
    • For Design Case: Guide analysis of original design and new context
    • For Critique: Help select appropriate technology and value framework
    
2. Initial Outline Development:
    • Confirm understanding of essay requirements
    • Guide structure development
    • Help identify key arguments and evidence needs

3. Drafting Support (by section):
    • Introduction guidance
    • Body paragraph development
    • Conclusion strengthening
    • Support source integration

4. Review and Feedback:
    Assessment based on:
        - Understanding & Analysis (40%)
            • Topic understanding (15%)
            • Literature review (15%)
            • Creative thinking (10%)
        - Research Approach (40%)
            • Method & planning (10%)
            • Analysis & insight (15%)
            • Evidence support (15%)
        - Structure (20%)
            • Logical flow
            • Strong conclusions
            • Professional presentation

Additional Guidelines:
    • Encourage first-person writing with evidence support
    • Guide use of APA referencing
    • Help balance personal insights with research
    • Maintain focus on educational technology context
"""

GRADING_CRITERIA = """
Essay Scoring Criteria (Total 100 points):

Understanding & Analysis (40 points):
- Topic Understanding (15 points)
  • Shows deep understanding of main issues
  • Breaks down complex ideas clearly
  • Goes beyond basic descriptions
- Literature Review (15 points)
  • Uses relevant sources effectively
  • Shows critical evaluation of sources
  • Connects source material to own arguments
- Creative Thinking (10 points)
  • Combines ideas in original ways
  • Develops new perspectives
  • Shows independent thinking

Research Approach (40 points):
- Method & Planning (10 points)
  • Uses appropriate research methods
  • Shows clear connection to course themes
  • Justifies chosen approach
- Analysis & Insight (15 points)
  • Shows clear understanding of arguments
  • Develops own interpretations
  • Creates meaningful insights
- Evidence & Support (15 points)
  • Backs up claims with evidence
  • Explains research methods clearly
  • Discusses limitations and validity

Structure & Presentation (20 points):
- Clear logical flow (5 points)
- Strong conclusions (5 points)
- Well-organized content (5 points)
- Professional presentation (5 points)
"""

STYLE_GUIDES = {
    "general": [
        "Use first person ('I think/believe/argue') when presenting your views",
        "Support personal insights with academic evidence",
        "Maintain consistent APA referencing",
        "Balance personal voice with academic rigor"
    ],
    "design_case": [
        "Clearly explain your reasoning for modifications",
        "Compare and contrast with original design",
        "Justify methodological choices"
    ],
    "critique": [
        "Define educational value clearly",
        "Consider multiple stakeholder perspectives",
        "Support critiques with evidence"
    ]
}

STAGE_PROMPTS = {
    "topic_selection": {
        "design_case": """Let's explore your design case extension:
1. What aspects of the original design would you like to modify?
2. What new educational context are you considering?
3. How might the theoretical framework need to change?
4. What additional data requirements do you envision?""",
        
        "critique": """Let's choose your technology for critique:
1. Which educational technology interests you?
2. What is its claimed educational value?
3. Which stakeholder perspectives will you consider?
4. What evidence will you examine?"""
    },
    "outline": {
        "design_case": """Suggested outline structure:
1. Introduction
   - Original design context
   - New challenge identification
   - Your approach
2. Original Design Analysis
   - Key features and rationale
   - Strengths and limitations
3. New Context Requirements
   - Educational environment
   - User needs
   - Data considerations
4. Theoretical Framework
   - Modifications needed
   - Justification
5. Methodological Approach
   - Design methods
   - Data collection and analysis
6. Proposed Changes
   - Specific modifications
   - Implementation considerations
7. Conclusion
   - Implications
   - Future work""",
        
        "critique": """Suggested outline structure:
1. Introduction
   - Technology overview
   - Educational value framework
2. Technology Analysis
   - Features and functionality
   - Pedagogical approach
3. Stakeholder Perspectives
   - Users (learners/teachers)
   - Implementation context
4. Evidence Evaluation
   - Research support
   - Implementation results
5. Critical Analysis
   - Strengths and limitations
   - Educational impact
6. Recommendations
   - Improvements
   - Future directions"""
    },
    "review": {
        "prompts": [
            "How effectively have you demonstrated understanding of the core issues?",
            "How well have you integrated and evaluated sources?",
            "What unique insights have you contributed?",
            "How strong is your evidence and methodology?",
            "How clear and logical is your essay structure?"
        ],
        "feedback_structure": {
            "strengths": "Key strengths in your essay:",
            "improvements": "Areas for improvement:",
            "next_steps": "Suggested revisions:"
        }
    }
}

def get_stage_guidance(stage, essay_type=None):
    """Returns appropriate guidance for the current stage and essay type"""
    if stage == "initial":
        return INITIAL_ASSISTANT_MESSAGE["content"]
    elif stage == "review":
        return STAGE_PROMPTS["review"]
    elif essay_type and stage in STAGE_PROMPTS:
        return STAGE_PROMPTS[stage][essay_type]
    return ""

def get_style_reminders(essay_type=None):
    """Returns style reminders based on essay type"""
    reminders = STYLE_GUIDES["general"]
    if essay_type in STYLE_GUIDES:
        reminders.extend(STYLE_GUIDES[essay_type])
    return reminders

class EWA:
    def __init__(self):
        self.tz = pytz.timezone("Europe/London")

    def format_time(self, dt=None):
        if isinstance(dt, (datetime, type(firestore.SERVER_TIMESTAMP))):
            return dt.strftime("[%Y-%m-%d %H:%M:%S]")
        dt = dt or datetime.now(self.tz)
        return dt.strftime("[%Y-%m-%d %H:%M:%S]")

    def handle_chat(self, prompt):
        """Main chat handler with integrated guidance"""
        if not prompt:
            return

        current_time = datetime.now(self.tz)
        time_str = self.format_time(current_time)

        # Display user message
        st.chat_message("user").write(f"{time_str} {prompt}")

        # Get current stage and essay type from session state
        current_stage = st.session_state.get('stage', 'initial')
        essay_type = st.session_state.get('essay_type', None)

        # Build conversation context
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]

        # Add stage-specific guidance
        stage_guidance = get_stage_guidance(current_stage, essay_type)
        if stage_guidance:
            messages.append({"role": "assistant", "content": stage_guidance})

        # Add style reminders if past initial stage
        if current_stage not in ['initial', 'option']:
            style_reminders = get_style_reminders(essay_type)
            messages.append({"role": "assistant", "content": "\n".join(style_reminders)})

        # Add grading criteria if in review stage
        if current_stage == 'review':
            messages.append({"role": "assistant", "content": GRADING_CRITERIA})

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
        """Save message to database"""
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
        """Handle user login"""
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
    st.title("DUTE Essay Writing Assistant")

    # Display current stage info
    if st.session_state.get('stage') == 'initial':
        st.write(INITIAL_ASSISTANT_MESSAGE["content"])

    # Display message history
    if 'messages' in st.session_state:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(
                f"{msg.get('timestamp', '')} {msg['content']}"
            )

    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        app.handle_chat(prompt)
        
        # Basic stage progression
        if st.session_state.get('stage') == 'initial':
            if "1" in prompt:
                st.session_state.stage = 'topic'
                st.session_state.essay_type = 'design_case'
            elif "2" in prompt:
                st.session_state.stage = 'topic'
                st.session_state.essay_type = 'critique'
        elif 'review' in prompt.lower():
            st.session_state.stage = 'review'

if __name__ == "__main__":
    main()
