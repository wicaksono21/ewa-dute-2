import streamlit as st
from firebase_admin import firestore
from datetime import datetime
import pytz

def admin_dashboard():
    st.title("Admin Dashboard")
    
    # Initialize Firestore
    db = firestore.client()
    
    # Get counts for metrics
    users_count = len(list(db.collection('users').get()))
    convs = list(db.collection('conversations').get())
    convs_count = len(convs)
    active_convs = len(list(db.collection('conversations').where('status', '==', 'active').get()))
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Users", users_count)
    with col2:
        st.metric("Total Conversations", convs_count)
    with col3:
        st.metric("Active Essays", active_convs)
    
    # User Management
    st.subheader("User Management")
    users_ref = db.collection('users').stream()
    users = [{"id": doc.id, **doc.to_dict()} for doc in users_ref]
    
    # Create user table
    st.table({
        'Email': [user.get('email', 'N/A') for user in users],
        'Role': [user.get('role', 'N/A') for user in users],
        'Last Login': [user.get('last_login', 'N/A') for user in users]
    })
    
    # Chat History with Detailed Format
    st.subheader("Essay History")
    selected_email = st.selectbox(
        "Select user to view essay history",
        options=[user.get('email') for user in users],
        index=None,
        placeholder="Choose a user..."
    )
    
    if selected_email:
        selected_user = next((user for user in users if user.get('email') == selected_email), None)
        
        if selected_user:
            conversations = db.collection('conversations')\
                            .where('user_id', '==', selected_user['id'])\
                            .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                            .stream()
            
            # For each conversation
            for conv in conversations:
                conv_data = conv.to_dict()
                conv_title = conv_data.get('title', 'Untitled')
                
                # Add expandable section for each conversation
                with st.expander(f"View Essay: {conv_title}"):
                    # Get messages for this conversation
                    messages = db.collection('conversations').document(conv.id)\
                              .collection('messages').order_by('timestamp').stream()
                    
                    # Convert messages to detailed format
                    detailed_data = []
                    for msg in messages:
                        msg_data = msg.to_dict()
                        timestamp = msg_data.get('timestamp')
                        if timestamp:
                            date = timestamp.astimezone(pytz.UTC).strftime('%Y-%m-%d')
                            time = timestamp.astimezone(pytz.UTC).strftime('%H:%M:%S')
                        else:
                            date = 'N/A'
                            time = 'N/A'
                            
                        detailed_data.append({
                            'date': date,
                            'time': time,
                            'role': msg_data.get('role', 'N/A'),
                            'content': msg_data.get('content', 'N/A'),
                            'length': len(msg_data.get('content', '')) if msg_data.get('content') else 0,
                            'response_time': msg_data.get('response_time', 'N/A')
                        })
                    
                    # Display detailed chat log
                    if detailed_data:
                        st.dataframe(detailed_data)
                    else:
                        st.info("No messages found for this essay.")

def init_admin_page():
    st.set_page_config(page_title="Essay Writing Assistant - Admin", layout="wide")
    
    if 'user' not in st.session_state:
        st.error("Please log in first")
        return
        
    admin = AdminDashboard()
    admin.render_dashboard()

if __name__ == "__main__":
    init_admin_page()
