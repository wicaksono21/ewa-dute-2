# stage_prompts.py

INITIAL_ASSISTANT_MESSAGE = {
    "role": "assistant",
    "content": """Hi there! Ready to start your Part B essay writing? I'm here to guide and help you improve essay writing skills with activities like:

1. **Topic Selection**
2. **Outlining**
3. **Drafting**
4. **Reviewing**

For your Part B Essay, you have two options:

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

STAGE_PROMPTS = {
    "topic_selection": {
        "design_case": """Let's explore your design case extension:

1. Original Design Context:
   - What was the original educational challenge?
   - What were the key features of your solution?
   - What were the main theoretical frameworks used?

2. New Problem Space:
   - What new educational challenge do you want to address?
   - How does it relate to the original problem?
   - What new constraints or requirements exist?

3. Analysis Focus:
   - Which aspects of the original design will you analyze?
   - What metrics will you use to evaluate effectiveness?
   - How will you justify your modifications?

Please share your thoughts on these aspects.""",
        
        "critique": """Let's define your technology critique focus:

1. Technology Selection:
   - Which educational technology interests you?
   - What is its primary educational purpose?
   - Who are the main users/stakeholders?

2. Value Framework:
   - How do you define educational value?
   - What metrics will you use for evaluation?
   - Which theoretical frameworks will you apply?

3. Analysis Scope:
   - Which aspects will you focus on?
   - What evidence types will you consider?
   - How will you structure your critique?

Please share your initial thoughts."""
    },
    
    "outline": {
        "design_case": """Let's develop your essay outline (2,500 words):

1. Introduction (250-300 words)
   - Original design context
   - New challenge identification
   - Your approach overview

2. Original Design Analysis (500-600 words)
   - Key features and rationale
   - Strengths and limitations
   - Theoretical framework

3. New Context Requirements (400-500 words)
   - Educational environment
   - User needs analysis
   - Technical considerations

4. Proposed Modifications (600-700 words)
   - Design changes
   - Implementation strategy
   - Expected impacts

5. Evaluation Framework (400-500 words)
   - Success metrics
   - Assessment methods
   - Validation approach

6. Conclusion (250-300 words)
   - Summary of changes
   - Implementation considerations
   - Future directions

Which section would you like to discuss first?""",
        
        "critique": """Let's structure your critique (2,500 words):

1. Introduction (250-300 words)
   - Technology overview
   - Educational context
   - Value framework

2. Technology Analysis (500-600 words)
   - Feature description
   - Pedagogical approach
   - Technical implementation

3. Stakeholder Impact (400-500 words)
   - User experiences
   - Implementation challenges
   - Organizational effects

4. Educational Value (600-700 words)
   - Learning outcomes
   - Engagement metrics
   - Cost-benefit analysis

5. Critical Discussion (400-500 words)
   - Strengths and weaknesses
   - Contextual factors
   - Alternative approaches

6. Conclusion (250-300 words)
   - Overall assessment
   - Recommendations
   - Future considerations

Which section should we focus on first?"""
    },
    
    "drafting": {
        "general_guidance": """As you draft your essay, consider:

1. Writing Style:
   - Use first person voice appropriately
   - Maintain academic tone
   - Balance description with analysis

2. Evidence Integration:
   - Support claims with research
   - Use recent sources (last 5 years)
   - Apply APA citation style

3. Section Development:
   - Start with topic sentences
   - Provide supporting evidence
   - Include critical analysis
   - End with clear transitions

4. Argument Construction:
   - Present clear reasoning
   - Address counterarguments
   - Support with evidence
   - Link to educational theory

Which section would you like help with?""",
        
        "section_prompts": {
            "introduction": """For your introduction, consider:
- How will you hook your reader?
- What context is essential?
- What is your main argument?
- How will you outline your approach?""",
            
            "body": """For this body section, focus on:
- What is your main point?
- What evidence supports it?
- How does it connect to your argument?
- What counterarguments should you address?""",
            
            "conclusion": """For your conclusion, address:
- How do your points support your argument?
- What are the key implications?
- What future directions emerge?
- What's your final message?"""
        }
    }
}
