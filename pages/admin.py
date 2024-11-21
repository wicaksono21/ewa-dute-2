# admin.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from datetime import datetime
import pytz

class AdminDashboard:
    def __init__(self):
        self.db = firestore.client()
        self.tz = pytz.timezone("Europe/London")
        
    def check_admin_access(self, email):
        try:
            user_ref = self.db.collection('users').where('email', '==', email).limit(1).get()
            if not user_ref:
                return False
            user_data = user_ref[0].to_dict()
            return user_data.get('role') == 'admin'
        except Exception as e:
            st.error(f"Error checking admin access: {e}")
            return False
            
    def render_dashboard(self):
        st.title("Admin Dashboard")
        
        # Admin metrics overview
        col1, col2, col3 = st.columns(3)
        with col1:
            total_users = len(list(self.db.collection('users').get()))
            st.metric("Total Users", total_users)
        with col2:
            total_convs = len(list(self.db.collection('conversations').get()))
            st.metric("Total Conversations", total_convs)
        with col3:
            active_convs = len(list(self.db.collection('conversations').where('status', '==', 'active').get()))
            st.metric("Active Essays", active_convs)
        
        # User management
        st.subheader("User Management")
        users_ref = self.db.collection('users').stream()
        users = [{"id": doc.id, **doc.to_dict()} for doc in users_ref]
        
        user_data = []
        for user in users:
            last_login = user.get('last_login')
            if last_login:
                last_login = last_login.astimezone(self.tz).strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_login = 'N/A'
                
            user_data.append([
                user.get('email', 'N/A'),
                user.get('role', 'N/A'),
                last_login,
            ])
        
        st.dataframe({
            'Email': [u[0] for u in user_data],
            'Role': [u[1] for u in user_data],
            'Last Login': [u[2] for u in user_data]
        })
        
        # Chat history viewer
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
                conversations = self.db.collection('conversations')\
                                .where('user_id', '==', selected_user['id'])\
                                .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                                .stream()
                
                conv_data = []
                for conv in conversations:
                    data = conv.to_dict()
                    created_at = data.get('created_at')
                    if created_at:
                        created_at = created_at.astimezone(self.tz).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # View conversation button
                    if st.button(f"View Essay: {data.get('title', 'Untitled')}", key=conv.id):
                        messages = self.db.collection('conversations').document(conv.id)\
                                  .collection('messages').order_by('timestamp').stream()
                        
                        st.write("---")
                        st.write(f"Essay Content - {data.get('title', 'Untitled')}")
                        for msg in messages:
                            msg_data = msg.to_dict()
                            st.text(f"{msg_data.get('role')}: {msg_data.get('content')}")
                    
                    conv_data.append({
                        'Date': created_at,
                        'Title': data.get('title', 'Untitled'),
                        'Status': data.get('status', 'N/A'),
                        'Last Message': data.get('last_message', 'N/A')[:100] + '...' if data.get('last_message') else 'N/A'
                    })
                
                if conv_data:
                    st.dataframe(conv_data)
                else:
                    st.info("No essays found for this user.")

def main():
    st.set_page_config(page_title="Essay Writing Assistant - Admin", layout="wide")
    
    # Check if user is logged in and is admin
    if 'user' not in st.session_state:
        st.error("Please log in first")
        return
        
    admin = AdminDashboard()
    if not admin.check_admin_access(st.session_state.user.email):
        st.error("Access denied. Admin privileges required.")
        return
        
    admin.render_dashboard()

if __name__ == "__main__":
    main()
