import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from openai import OpenAI
from datetime import datetime
import pytz

# Cache initialization constants
@st.cache_data
def get_init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()

# Cache page config and styles
@st.cache_data
def get_page_config():
    return {
        "page_title": "DUTE Essay Writing Assistant",
        "layout": "wide"
    }

@st.cache_data
def get_page_style():
    return """
        <style>
            .main { max-width: 800px; margin: 0 auto; }
            .chat-message { padding: 1rem; margin: 0.5rem 0; border-radius: 0.5rem; }
            #MainMenu, footer { visibility: hidden; }
        </style>
    """

# Cache system messages and prompts
@st.cache_data
def get_initial_message():
    return {
        "role": "assistant",
        "content": """Welcome! I'm your DUTE Essay Writing Assistant. Here are my capabilities:

1. **Topic Selection**
   • Guide you in choosing and refining your essay focus
   • Help analyze context and requirements
   • Ensure alignment with course objectives

2. **Outline Development**
   • Support structure development
   • Help identify key arguments
   • Guide evidence planning

3. **Drafting Support**
   • Section-by-section guidance
   • Source integration help
   • Style and tone advice

4. **Review and Feedback**
   • Detailed scoring
   • Specific strengths analysis
   • Improvement suggestions

Hi there! Let's work on your DUTE Part B Essay. You have two options:

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

@st.cache_data
def get_system_instructions():
    return """Role: DUTE Essay Writing Assistant..."""  # Your full system instructions here

@st.cache_data
def get_stage_prompts():
    return {
        "topic_selection": {
            "design_case": """Let's develop your design case extension...""",  # Your full prompt here
            "critique": """Let's define your technology critique focus..."""    # Your full prompt here
        },
        "outline": {
            "design_case": """Let's develop your essay outline...""",          # Your full prompt here
            "critique": """Let's structure your critique..."""                 # Your full prompt here
        },
        "drafting": {
            "general_guidance": """As you draft your essay, remember...""",    # Your full prompt here
            "section_prompts": {
                "introduction": """For your introduction, consider...""",
                "body": """For this body section, focus on...""",
                "conclusion": """For your conclusion, address..."""
            }
        }
    }

1. Original Design Context:
   • What was the original educational challenge?
   • What were the key features of your solution?
   • What were the main theoretical frameworks used?

2. New Problem Space:
   • What new educational challenge do you want to address?
   • How does it relate to the original problem?
   • What new constraints or requirements exist?

3. Analysis Focus:
   • Which aspects of the original design will you analyze?
   • What metrics will you use to evaluate effectiveness?
   • How will you justify your modifications?

Please share your thoughts on these aspects, and I'll help you refine your focus.""",
        
        "critique": """Let's define your technology critique focus:

1. Technology Selection:
   • Which educational technology interests you?
   • What is its primary educational purpose?
   • Who are the main users/stakeholders?

2. Value Framework:
   • How do you define educational value?
   • What metrics will you use for evaluation?
   • Which theoretical frameworks will you apply?

3. Analysis Scope:
   • Which aspects will you focus on?
   • What evidence types will you consider?
   • How will you structure your critique?

Share your initial thoughts, and I'll help you develop a strong foundation for your critique."""
    },
    
    "outline": {
        "design_case": """Let's develop your essay outline. Consider this structure:

1. Introduction (250-300 words)
   • Original design context
   • New challenge identification
   • Your approach overview

2. Original Design Analysis (500-600 words)
   • Key features and rationale
   • Strengths and limitations
   • Theoretical framework

3. New Context Requirements (400-500 words)
   • Educational environment
   • User needs analysis
   • Technical considerations

4. Proposed Modifications (600-700 words)
   • Design changes
   • Implementation strategy
   • Expected impacts

5. Evaluation Framework (400-500 words)
   • Success metrics
   • Assessment methods
   • Validation approach

6. Conclusion (250-300 words)
   • Summary of changes
   • Implementation considerations
   • Future directions

Would you like to discuss any specific section?""",
        
        "critique": """Let's structure your critique. Consider this outline:

1. Introduction (250-300 words)
   • Technology overview
   • Educational context
   • Value framework

2. Technology Analysis (500-600 words)
   • Feature description
   • Pedagogical approach
   • Technical implementation

3. Stakeholder Impact (400-500 words)
   • User experiences
   • Implementation challenges
   • Organizational effects

4. Educational Value (600-700 words)
   • Learning outcomes
   • Engagement metrics
   • Cost-benefit analysis

5. Critical Discussion (400-500 words)
   • Strengths and weaknesses
   • Contextual factors
   • Alternative approaches

6. Conclusion (250-300 words)
   • Overall assessment
   • Recommendations
   • Future considerations

Which section would you like to explore first?"""
    },
    
    "drafting": {
        "general_guidance": """As you draft your essay, remember:

1. Writing Style:
   • Use first person voice appropriately
   • Maintain academic tone
   • Balance description with analysis

2. Evidence Integration:
   • Support claims with research
   • Use recent sources (last 5 years)
   • Apply APA citation style

3. Section Development:
   • Start with topic sentences
   • Provide supporting evidence
   • Include critical analysis
   • End with clear transitions

4. Argument Construction:
   • Present clear reasoning
   • Address counterarguments
   • Support with evidence
   • Link to educational theory

Would you like specific guidance for any section?""",
        
        "section_prompts": {
            "introduction": """For your introduction, consider:
• How will you hook your reader?
• What context is essential?
• What is your main argument?
• How will you outline your approach?""",
            
            "body": """For this body section, focus on:
• What is your main point?
• What evidence supports it?
• How does it connect to your argument?
• What counterarguments should you address?""",
            
            "conclusion": """For your conclusion, address:
• How do your points support your argument?
• What are the key implications?
• What future directions emerge?
• What's your final message?"""
        }
    }
}

INITIAL_ASSISTANT_MESSAGE = {
    "role": "assistant",
    "content": """Welcome! I'm your DUTE Essay Writing Assistant. Here are my capabilities:

1. **Topic Selection**
   • Guide you in choosing and refining your essay focus
   • Help analyze context and requirements
   • Ensure alignment with course objectives

2. **Outline Development**
   • Support structure development
   • Help identify key arguments
   • Guide evidence planning

3. **Drafting Support**
   • Section-by-section guidance
   • Source integration help
   • Style and tone advice

4. **Review and Feedback**
   • Detailed scoring
   • Specific strengths analysis
   • Improvement suggestions

Hi there! Let's work on your DUTE Part B Essay. You have two options:

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
Primary Task: Evaluate 2,500-word Part B essays and provide comprehensive scoring and feedback
Approach: Analyze essay content, assign numeric scores, and provide structured feedback

SCORING CRITERIA (Total 100 points):

1. Understanding & Analysis (40 points)
   a. Topic Understanding (15 points)
      • Deep understanding of main issues
      • Clear breakdown of complex ideas
      • Beyond basic descriptions
   
   b. Literature Review (15 points)
      • Effective use of relevant sources
      • Critical evaluation of sources
      • Connection to arguments
   
   c. Creative Thinking (10 points)
      • Original combination of ideas
      • New perspectives
      • Independent thinking

2. Research Approach (40 points)
   a. Method & Planning (10 points)
      • Appropriate research methods
      • Clear connection to course themes
      • Justified approach
   
   b. Analysis & Insight (15 points)
      • Clear understanding of arguments
      • Original interpretations
      • Meaningful insights
   
   c. Evidence Support (15 points)
      • Evidence-backed claims
      • Clear research methods
      • Discussion of limitations

3. Structure & Presentation (20 points)
   a. Logical Flow (5 points)
      • Clear progression of ideas
      • Effective transitions
      • Coherent structure
   
   b. Strong Conclusions (5 points)
      • Synthesizes main points
      • Clear recommendations
      • Compelling closing
   
   c. Professional Presentation (10 points)
      • Academic writing style
      • Proper formatting
      • Correct citations

OUTPUT REQUIREMENTS:

1. NUMERIC SCORING:
   • Provide specific scores for each criterion
   • Include subtotals for main categories
   • Show total score out of 100
   • Use format: "Category: X/Y points"

2. DETAILED FEEDBACK:
   A. Strengths
      • Identify specific strong elements
      • Reference concrete examples from essay
      • Align with scoring criteria
      • At least one strength per main category
   
   B. Suggestions for Improvement
      • Provide actionable recommendations
      • Explain how to implement changes
      • Link to scoring criteria
      • At least one suggestion per main category

3. FORMAT:
SCORING:
[Category]
- [Subcategory]: [X/Y points]
[Additional subcategories...]
[Subtotal: X/Y]
[Repeat for each category]
TOTAL SCORE: [X/100]

FEEDBACK:
Strengths:
• [Category]: [Specific strength with example]
[Additional strengths...]

Suggestions for Improvement:
• [Category]: [Specific, actionable suggestion]
[Additional suggestions...]"""

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

        # Determine current stage and essay type
        current_stage = st.session_state.get('stage', 'initial')
        essay_type = st.session_state.get('essay_type', None)

        # Build conversation context
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
        
        # Add stage-specific guidance
        if current_stage in STAGE_PROMPTS:
            if current_stage == 'drafting':
                messages.append({"role": "assistant", "content": STAGE_PROMPTS[current_stage]['general_guidance']})
            elif essay_type and essay_type in STAGE_PROMPTS[current_stage]:
                messages.append({"role": "assistant", "content": STAGE_PROMPTS[current_stage][essay_type]})
        
        # Add review instructions if in review stage
        if current_stage == 'review':
            messages.append({"role": "user", "content": """Please provide:
1. Numeric scores for each criterion
2. Detailed feedback including:
   - Specific strengths in each area
   - Concrete suggestions for improvement"""})
        

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
            max_tokens=1000
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
            st.session_state.stage = 'initial'
            st.session_state.messages = [{
                **INITIAL_ASSISTANT_MESSAGE,
                "timestamp": self.format_time()
            }]
            return True
        except:
            st.error("Login failed")
            return False

    def get_conversations(self, user_id):
        """Get user's conversations from database"""
        return db.collection('conversations')\
                 .where('user_id', '==', user_id)\
                 .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                 .limit(10)\
                 .stream()

    def render_sidebar(self):
        """Render the sidebar with conversation history"""
        with st.sidebar:
            st.title("DUTE Essay Writing Assistant")
            
            if st.button("+ New Session", use_container_width=True):
                user = st.session_state.user  # Store user
                st.session_state.clear()
                st.session_state.user = user  # Restore user
                st.session_state.logged_in = True
                st.session_state.stage = 'initial'  # Reset stage
                st.session_state.messages = [{
                    **INITIAL_ASSISTANT_MESSAGE,
                    "timestamp": self.format_time()
                }]
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


def main():
    # Apply cached configurations
    st.set_page_config(**get_page_config())
    st.markdown(get_page_style(), unsafe_allow_html=True)
    
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
    app.render_sidebar()
    app.render_messages()
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Basic stage progression
        if st.session_state.get('stage') == 'initial':
            if "1" in prompt:
                st.session_state.stage = 'topic_selection'
                st.session_state.essay_type = 'design_case'
            elif "2" in prompt:
                st.session_state.stage = 'topic_selection'
                st.session_state.essay_type = 'critique'
        elif 'outline' in prompt.lower():
            st.session_state.stage = 'outline'
        elif 'draft' in prompt.lower():
            st.session_state.stage = 'drafting'
        elif 'review' in prompt.lower():
            st.session_state.stage = 'review'
            
        app.handle_chat(prompt)

if __name__ == "__main__":
    main()
