import streamlit as st
from firebase_admin import firestore, auth
from datetime import datetime
import pytz

class AdminDashboard:
    def __init__(self):
        self.db = firestore.client()
        self.tz = pytz.timezone("Europe/London")
    
    def create_user_document(self, user):
        """Create or update user document in Firestore"""
        try:
            user_data = {
                'email': user.email,
                'role': 'user',
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_login': firestore.SERVER_TIMESTAMP
            }
            
            self.db.collection('users').document(user.uid).set(user_data)
            return True
        except Exception as e:
            st.error(f"Error creating user document: {e}")
            return False
            
    def sync_users(self):
        """Sync Authentication users with Firestore users collection"""
        try:
            # Get all users from Authentication
            auth_users = auth.list_users().iterate_all()
            synced_count = 0
            
            for auth_user in auth_users:
                # Check if user document exists in Firestore
                user_doc = self.db.collection('users').document(auth_user.uid).get()
                
                if not user_doc.exists:
                    # Create user document if it doesn't exist
                    self.create_user_document(auth_user)
                    synced_count += 1
            
            return synced_count
        except Exception as e:
            st.error(f"Error syncing users: {e}")
            return 0
            
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
        
        # Sync Users Button
        if st.button("Sync Authentication Users"):
            synced_count = self.sync_users()
            if synced_count > 0:
                st.success(f"Successfully synced {synced_count} new users to Firestore")
            else:
                st.info("All users are already synced")
        
        # Get counts for metrics
        users_count = len(list(self.db.collection('users').get()))
        convs = list(self.db.collection('conversations').get())
        convs_count = len(convs)
        active_convs = len(list(self.db.collection('conversations').where('status', '==', 'active').get()))
        
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
        users_ref = self.db.collection('users').stream()
        users = [{"id": doc.id, **doc.to_dict()} for doc in users_ref]
        
        # Create user table
        st.table({
            'Email': [user.get('email', 'N/A') for user in users],
            'Role': [user.get('role', 'N/A') for user in users],
            'Last Login': [
                user.get('last_login').astimezone(self.tz).strftime("%Y-%m-%d %H:%M:%S") 
                if user.get('last_login') else 'N/A' 
                for user in users
            ]
        })
        
        # Essay History
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
                
                # For each conversation
                for conv in conversations:
                    conv_data = conv.to_dict()
                    conv_title = conv_data.get('title', 'Untitled')
                    
                    # Add expandable section for each conversation
                    with st.expander(f"View Essay: {conv_title}", expanded=True):
                        messages = self.db.collection('conversations').document(conv.id)\
                                  .collection('messages')\
                                  .order_by('timestamp')\
                                  .stream()
                        
                        detailed_data = []
                        prev_msg_time = None
                        
                        for msg in messages:
                            msg_data = msg.to_dict()
                            timestamp = msg_data.get('timestamp')
                            
                            if timestamp:
                                date = timestamp.astimezone(self.tz).strftime('%Y-%m-%d')
                                time = timestamp.astimezone(self.tz).strftime('%H:%M:%S')
                                
                                # Calculate response time for all messages
                                if prev_msg_time:
                                    curr_seconds = int(time.split(':')[0]) * 3600 + \
                                                 int(time.split(':')[1]) * 60 + \
                                                 int(time.split(':')[2])
                                    prev_seconds = int(prev_msg_time.split(':')[0]) * 3600 + \
                                                 int(prev_msg_time.split(':')[1]) * 60 + \
                                                 int(prev_msg_time.split(':')[2])
                                    response_time = curr_seconds - prev_seconds
                                else:
                                    response_time = 'N/A'
                                    
                                prev_msg_time = time
                            else:
                                date = 'N/A'
                                time = 'N/A'
                                response_time = 'N/A'
                                
                            content = msg_data.get('content', '')
                            word_count = len(content.split()) if content else 0
                            
                            detailed_data.append({
                                'date': date,
                                'time': time,
                                'role': msg_data.get('role', 'N/A'),
                                'content': content,
                                'length': word_count,
                                'response_time': response_time
                            })
                        
                        if detailed_data:
                            st.dataframe(
                                detailed_data,
                                column_config={
                                    "date": "Date",
                                    "time": "Time",
                                    "role": "Role",
                                    "content": "Content",
                                    "length": st.column_config.NumberColumn(
                                        "Length",
                                        help="Number of words"
                                    ),
                                    "response_time": st.column_config.NumberColumn(
                                        "Response Time (s)",
                                        help="Time since previous message in seconds"
                                    )
                                },
                                hide_index=True
                            )
                            
                            # Add download button for CSV
                            import pandas as pd
                            df = pd.DataFrame(detailed_data)
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="Download Chat Log as CSV",
                                data=csv,
                                file_name=f"{conv_title}_chat_log.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("No messages found for this essay.")

def main():
    st.set_page_config(
        page_title="Essay Writing Assistant - Admin", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
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
