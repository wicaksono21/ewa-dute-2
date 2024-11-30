import streamlit as st
from firebase_admin import firestore, auth
from datetime import datetime
import pytz
import pandas as pd

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
            auth_users = auth.list_users().iterate_all()
            synced_count = 0
            
            for auth_user in auth_users:
                user_doc = self.db.collection('users').document(auth_user.uid).get()
                
                if not user_doc.exists:
                    self.create_user_document(auth_user)
                    synced_count += 1
            
            return synced_count
        except Exception as e:
            st.error(f"Error syncing users: {e}")
            return 0
            
    def check_admin_access(self, email):
        """Check if user has admin privileges"""
        try:
            user_ref = self.db.collection('users').where('email', '==', email).limit(1).get()
            if not user_ref:
                return False
            user_data = user_ref[0].to_dict()
            return user_data.get('role') == 'admin'
        except Exception as e:
            st.error(f"Error checking admin access: {e}")
            return False
    
    def delete_conversation(self, conversation_id):
        """Delete a single conversation and all its messages"""
        try:
            # Delete all messages in the conversation
            messages_ref = self.db.collection('conversations').document(conversation_id).collection('messages')
            self._batch_delete(messages_ref)
            
            # Delete the conversation document
            self.db.collection('conversations').document(conversation_id).delete()
            return True
        except Exception as e:
            st.error(f"Error deleting conversation: {e}")
            return False

    def delete_user_conversations(self, user_id):
        """Delete all conversations for a specific user"""
        try:
            conversations = self.db.collection('conversations').where('user_id', '==', user_id).stream()
            
            for conv in conversations:
                self.delete_conversation(conv.id)
            return True
        except Exception as e:
            st.error(f"Error deleting user conversations: {e}")
            return False

    def _batch_delete(self, collection_ref, batch_size=100):
        """Helper method to delete collection in batches"""
        docs = collection_ref.limit(batch_size).stream()
        deleted = 0

        for doc in docs:
            doc.reference.delete()
            deleted += 1

        if deleted >= batch_size:
            return self._batch_delete(collection_ref, batch_size)
    
    def render_dashboard(self):
        st.title("Admin Dashboard")
        
        # Sync Users Button
        if st.button("Sync Authentication Users", key="sync_users_btn"):
            synced_count = self.sync_users()
            if synced_count > 0:
                st.success(f"Successfully synced {synced_count} new users to Firestore")
            else:
                st.info("All users are already synced")
        
        # Get counts for metrics
        users_count = len(list(self.db.collection('users').get()))
        convs = list(self.db.collection('conversations').get())
        convs_count = len(convs)
        
        # Display metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Users", users_count)
        with col2:
            st.metric("Total Conversations", convs_count)
               
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
            placeholder="Choose a user...",
            key="user_select"
        )
        
        if selected_email:
            selected_user = next((user for user in users if user.get('email') == selected_email), None)
            
            if selected_user:
                # Add delete all conversations button
                st.button("Delete All User Conversations", 
                         key=f"delete_all_{selected_user['id']}",
                         type="primary",
                         use_container_width=True,
                         on_click=lambda: self._handle_delete_all(selected_user['id']))
                
                if st.session_state.get('confirm_delete_all'):
                    st.warning("Are you sure? Click 'Delete All User Conversations' again to confirm deletion.")
                
                conversations = self.db.collection('conversations')\
                                .where('user_id', '==', selected_user['id'])\
                                .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                                .stream()
                
                # For each conversation
                for conv in conversations:
                    conv_data = conv.to_dict()
                    conv_title = conv_data.get('title', 'Untitled')
                    
                    # Update the conversation display section in render_dashboard method

                    with st.expander(f"View Essay: {conv_title}", expanded=True):
                        messages = self.db.collection('conversations').document(conv.id)\
                                  .collection('messages')\
                                  .order_by('timestamp')\
                                  .stream()
                        
                        detailed_data = []
                        prev_msg_time = None
                        
                        for msg in messages:
                            # ... existing message processing code ...

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
                                hide_index=True,
                                key=f"dataframe_{conv.id}"
                            )
                            
                            # Create columns for buttons at the bottom
                            col1, col2 = st.columns([5,1])
                            with col1:
                                df = pd.DataFrame(detailed_data)
                                csv = df.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    label="Download Chat Log as CSV",
                                    data=csv,
                                    file_name=f"{conv_title}_chat_log.csv",
                                    mime="text/csv",
                                    key=f"download_{conv.id}"
                                )
                            with col2:
                                if st.button("Delete", key=f"delete_{conv.id}", type="secondary"):
                                    if st.session_state.get(f'confirm_delete_{conv.id}'):
                                        if self.delete_conversation(conv.id):
                                            st.success("Conversation deleted successfully")
                                            st.rerun()
                                        st.session_state[f'confirm_delete_{conv.id}'] = False
                                    else:
                                        st.session_state[f'confirm_delete_{conv.id}'] = True
                                        st.warning("Click again to confirm deletion")
                        else:
                            st.info("No messages found for this essay.")

    def _handle_delete_all(self, user_id):
        """Helper method to handle delete all confirmation"""
        if st.session_state.get('confirm_delete_all'):
            if self.delete_user_conversations(user_id):
                st.success("All conversations deleted successfully")
                st.rerun()
            st.session_state.confirm_delete_all = False
        else:
            st.session_state.confirm_delete_all = True

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
