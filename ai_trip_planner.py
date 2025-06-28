import streamlit as st
import google.generativeai as genai
import json
import uuid
import datetime
import requests
from typing import Dict, List, Any
import hashlib
import time
import pandas as pd
import io
import base64
import pickle

st.set_page_config(
    page_title="AI Trip Planner",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

GOOGLE_API_KEY = "AIzaSyB46mW-7p4MIrKSe-oudQLpjxWli6XjVpE"
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-001')

GITHUB_TOKEN = "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"
GITHUB_USERNAME = "Saksham700"
REPO_NAME = "ai_trip_planner"
BRANCH = "main"

GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

if 'user_logged_in' not in st.session_state:
    st.session_state.user_logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'current_room' not in st.session_state:
    st.session_state.current_room = None

def get_github_file_content(file_path):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"
    response = requests.get(url, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        file_data = response.json()
        content = base64.b64decode(file_data['content']).decode('utf-8')
        return content, file_data['sha']
    elif response.status_code == 404:
        return None, None
    else:
        st.error(f"Error fetching file from GitHub: {response.status_code}")
        return None, None

def update_github_file(file_path, content, sha=None, commit_message="Update file"):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"
    content_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    data = {
        "message": commit_message,
        "content": content_encoded,
        "branch": BRANCH
    }   
    if sha:
        data["sha"] = sha   
    response = requests.put(url, json=data, headers=GITHUB_HEADERS)    
    if response.status_code in [200, 201]:
        return True
    else:
        st.error(f"Error updating file on GitHub: {response.status_code} - {response.text}")
        return False

def get_github_pickle_file(file_path):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"
    response = requests.get(url, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        file_data = response.json()
        content = base64.b64decode(file_data['content'])
        return pickle.loads(content), file_data['sha']
    elif response.status_code == 404:
        return None, None
    else:
        st.error(f"Error fetching pickle file from GitHub: {response.status_code}")
        return None, None

def update_github_pickle_file(file_path, data, sha=None, commit_message="Update pickle file"):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"
    pickle_data = pickle.dumps(data)
    content_encoded = base64.b64encode(pickle_data).decode('utf-8')  
    payload = {
        "message": commit_message,
        "content": content_encoded,
        "branch": BRANCH
    }  
    if sha:
        payload["sha"] = sha  
    response = requests.put(url, json=payload, headers=GITHUB_HEADERS)   
    if response.status_code in [200, 201]:
        return True
    else:
        st.error(f"Error updating pickle file on GitHub: {response.status_code} - {response.text}")
        return False

def load_users():
    try:
        content, sha = get_github_file_content("users.csv")
        if content:
            df = pd.read_csv(io.StringIO(content))
            users_db = {}
            for _, row in df.iterrows():
                users_db[row['username']] = {
                    'password': row['password'],
                    'email': row['email'],
                    'created_at': row['created_at']
                }
            return users_db, sha
        else:
            return {}, None
    except Exception as e:
        st.error(f"Error loading users: {e}")
        return {}, None

def save_users(users_db):
    try:
        users_list = []
        for username, data in users_db.items():
            users_list.append({
                'username': username,
                'password': data['password'],
                'email': data['email'],
                'created_at': data['created_at']
            })
        df = pd.DataFrame(users_list)
        csv_content = df.to_csv(index=False)
        _, sha = get_github_file_content("users.csv")
        return update_github_file("users.csv", csv_content, sha, "Update users data")
    except Exception as e:
        st.error(f"Error saving users: {e}")
        return False

def load_rooms():
    try:
        content, sha = get_github_file_content("rooms.csv")
        if content:
            df = pd.read_csv(io.StringIO(content))
            rooms = {}
            for _, row in df.iterrows():
                room_id = row['room_id']
                rooms[room_id] = {
                    'name': row['name'],
                    'description': row['description'],
                    'creator': row['creator'],
                    'participants': eval(row['participants']),
                    'max_participants': row['max_participants'],
                    'is_private': row['is_private'],
                    'created_at': row['created_at']
                }
                room_data, _ = get_github_pickle_file(f"room_data/{room_id}_data.pkl")
                if room_data:
                    rooms[room_id].update(room_data)
                else:
                    rooms[room_id].update({
                        'messages': [],
                        'constraints': {},
                        'trip_plan': None
                    })
            return rooms, sha
        else:
            return {}, None
    except Exception as e:
        st.error(f"Error loading rooms: {e}")
        return {}, None

def save_rooms(rooms):
    try:
        rooms_list = []
        for room_id, room_data in rooms.items():
            rooms_list.append({
                'room_id': room_id,
                'name': room_data['name'],
                'description': room_data['description'],
                'creator': room_data['creator'],
                'participants': str(room_data['participants']),
                'max_participants': room_data['max_participants'],
                'is_private': room_data['is_private'],
                'created_at': room_data['created_at']
            })
            detailed_data = {
                'messages': room_data.get('messages', []),
                'constraints': room_data.get('constraints', {}),
                'trip_plan': room_data.get('trip_plan', None)
            }          
            pickle_file_path = f"room_data/{room_id}_data.pkl"
            _, pickle_sha = get_github_pickle_file(pickle_file_path)
            update_github_pickle_file(pickle_file_path, detailed_data, pickle_sha, f"Update room {room_id} data")      
        df = pd.DataFrame(rooms_list)
        csv_content = df.to_csv(index=False)
        _, sha = get_github_file_content("rooms.csv")
        return update_github_file("rooms.csv", csv_content, sha, "Update rooms data")
    except Exception as e:
        st.error(f"Error saving rooms: {e}")
        return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def search_web_info(query):
    search_results = {
        "places": f"Popular attractions and places to visit for: {query}",
        "weather": f"Weather information for: {query}",
        "cafes": f"Recommended cafes and restaurants for: {query}",
        "safety": f"Safety and travel advisories for: {query}"
    }
    return search_results

def get_booking_links(destination, service_type, service_name):
    base_urls = {
        "hotel": {
            "makemytrip": f"https://www.makemytrip.com/hotels/{destination.lower().replace(' ', '-')}/",
            "booking": f"https://www.booking.com/searchresults.html?ss={destination}",
            "oyo": f"https://www.oyorooms.com/search?location={destination}"
        },
        "flight": {
            "makemytrip": f"https://www.makemytrip.com/flight/search?tripType=O&fromCity=DEL&toCity={destination}",
            "indigo": "https://www.goindigo.in/",
            "spicejet": "https://www.spicejet.com/"
        },
        "train": {
            "irctc": "https://www.irctc.co.in/nget/train-search",
            "trainman": f"https://trainman.in/trains-between-stations/{destination}"
        },
        "restaurant": {
            "zomato": f"https://www.zomato.com/{destination.lower().replace(' ', '-')}/restaurants",
            "swiggy": "https://www.swiggy.com/",
            "dineout": f"https://www.dineout.co.in/{destination.lower().replace(' ', '-')}"
        }
    }   
    if service_type in base_urls:
        return base_urls[service_type]
    return {}

def get_ai_recommendations(prompt, user_constraints=None, room_constraints=None, quick_plan=False):
    try:
        if quick_plan:
            enhanced_prompt = f"""
            You are a professional travel planner for Indian travelers. Create a quick but comprehensive trip plan based on:
            
            {prompt}
            
            Please provide:
            1. A 3-day suggested itinerary with day-wise activities
            2. Transportation recommendations with approximate costs in INR
            3. Budget accommodation suggestions (₹2000-5000 per night)
            4. Popular local food spots and restaurants with price ranges in INR
            5. Essential items to pack
            6. Quick safety tips
            7. Total estimated budget in INR
            8. Best time to visit
            
            Keep it concise but informative. All costs should be in Indian Rupees (₹).
            """
        else:
            enhanced_prompt = f"""
            You are a professional travel planner for Indian travelers. Create a detailed trip plan based on the following:
            
            {prompt}
            
            User Constraints: {user_constraints if user_constraints else "None specified"}
            Group Constraints: {room_constraints if room_constraints else "None specified"}
            
            Please provide:
            1. Day-by-day detailed itinerary
            2. Transportation recommendations with cost estimates in INR
            3. Accommodation suggestions within budget (in INR)
            4. Food recommendations with specific cafes/restaurants and price ranges in INR
            5. What to pack/carry for the weather and activities
            6. Safety alerts and precautions
            7. Budget breakdown in INR
            8. Alternative options for different weather conditions
            9. Local customs and cultural tips
            10. Emergency contacts and important phone numbers
            
            All monetary amounts should be in Indian Rupees (₹). Format the response in a clear, organized manner.
            """    
        response = model.generate_content(enhanced_prompt)
        return response.text
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

def login_page():
    st.title("🌍 AI Trip Planner")
    tab1, tab2 = st.tabs(["Login", "Register"])   
    users_db, users_sha = load_users()  
    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")     
        if st.button("Login"):
            if username in users_db:
                if users_db[username]["password"] == hash_password(password):
                    st.session_state.user_logged_in = True
                    st.session_state.username = username
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid password!")
            else:
                st.error("Username not found!")              
    with tab2:
        st.subheader("Register")
        new_username = st.text_input("Choose Username", key="reg_username")
        new_password = st.text_input("Choose Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
        email = st.text_input("Email", key="reg_email")   
        if st.button("Register"):
            if new_password != confirm_password:
                st.error("Passwords don't match!")
            elif new_username in users_db:
                st.error("Username already exists!")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters!")
            else:
                users_db[new_username] = {
                    "password": hash_password(new_password),
                    "email": email,
                    "created_at": datetime.datetime.now().isoformat()
                }
                if save_users(users_db):
                    st.success("Registration successful! Please login.")
                else:
                    st.error("Registration failed. Please try again.")

def create_room():
    st.subheader("Create New Planning Room")
    room_name = st.text_input("Room Name", placeholder="e.g., Europe Summer Trip 2024")
    room_description = st.text_area("Description", placeholder="Brief description of the trip...") 
    col1, col2 = st.columns(2)
    with col1:
        max_participants = st.number_input("Max Participants", min_value=2, max_value=20, value=5)
    with col2:
        is_private = st.checkbox("Private Room", help="Only invited users can join") 
    if st.button("Create Room"):
        if room_name:
            room_id = str(uuid.uuid4())[:8]
            rooms, rooms_sha = load_rooms()
            rooms[room_id] = {
                "name": room_name,
                "description": room_description,
                "creator": st.session_state.username,
                "participants": [st.session_state.username],
                "max_participants": max_participants,
                "is_private": is_private,
                "created_at": datetime.datetime.now().isoformat(),
                "messages": [],
                "constraints": {},
                "trip_plan": None
            }
            if save_rooms(rooms):
                st.success(f"Room created! Room ID: {room_id}")
                st.info("Share this Room ID with others to invite them.")
            else:
                st.error("Failed to create room. Please try again.")
        else:
            st.error("Please enter a room name!")

def join_room():
    st.subheader("Join Planning Room")
    room_id = st.text_input("Room ID", placeholder="Enter the room ID to join...") 
    if st.button("Join Room"):
        rooms, rooms_sha = load_rooms()
        if room_id in rooms:
            room = rooms[room_id]
            if st.session_state.username not in room["participants"]:
                if len(room["participants"]) < room["max_participants"]:
                    room["participants"].append(st.session_state.username)
                    if save_rooms(rooms):
                        st.success(f"Joined room: {room['name']}")
                        st.session_state.current_room = room_id
                    else:
                        st.error("Failed to join room. Please try again.")
                else:
                    st.error("Room is full!")
            else:
                st.info("You're already in this room!")
                st.session_state.current_room = room_id
        else:
            st.error("Room ID not found!")

def room_chat():
    if not st.session_state.current_room:
        st.warning("Please select or join a room first!")
        return    
    rooms, rooms_sha = load_rooms()
    room_id = st.session_state.current_room  
    if room_id not in rooms:
        st.error("Room not found!")
        return      
    room = rooms[room_id]  
    st.title(f"🏠 {room['name']}")
    st.write(f"Participants: {', '.join(room['participants'])}")   
    with st.sidebar:
        st.subheader("Your Constraints")      
        budget = st.number_input("Your Budget (₹)", min_value=0, value=50000, key=f"budget_{st.session_state.username}")     
        travel_dates = st.date_input(
            "Preferred Travel Dates",
            value=[datetime.date.today(), datetime.date.today() + datetime.timedelta(days=7)],
            key=f"dates_{st.session_state.username}"
        ) 
        destination = st.text_input("Destination Preference", key=f"dest_{st.session_state.username}")     
        activities = st.multiselect(
            "Preferred Activities",
            ["Sightseeing", "Adventure", "Beach", "Mountains", "Culture", "Food", "Shopping", "Nightlife"],
            key=f"activities_{st.session_state.username}"
        )   
        accommodation = st.selectbox(
            "Accommodation Type",
            ["Hotel", "Hostel", "Airbnb", "Resort", "Camping"],
            key=f"accommodation_{st.session_state.username}"
        )      
        transport = st.multiselect(
            "Transport Preferences",
            ["Flight", "Train", "Bus", "Car Rental", "Walking", "Public Transport"],
            key=f"transport_{st.session_state.username}"
        )     
        dietary = st.multiselect(
            "Dietary Requirements",
            ["Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free", "None"],
            key=f"dietary_{st.session_state.username}"
        )    
        if st.button("Save My Constraints"):
            if isinstance(travel_dates, (list, tuple)):
                dates_list = [d.isoformat() for d in travel_dates]
            else:
                dates_list = [travel_dates.isoformat()]         
            room["constraints"][st.session_state.username] = {
                "budget": budget,
                "dates": dates_list,
                "destination": destination,
                "activities": activities,
                "accommodation": accommodation,
                "transport": transport,
                "dietary": dietary
            }
            if save_rooms({room_id: room}):
                st.success("Constraints saved!")
            else:
                st.error("Failed to save constraints. Please try again.")
    col1, col2 = st.columns([2, 1]) 
    with col1:
        st.subheader("💬 Group Chat")
        for msg in room["messages"]:
            if msg["type"] == "user":
                st.write(f"**{msg['sender']}**: {msg['content']}")
            elif msg["type"] == "ai":
                st.info(f"🤖 AI Assistant: {msg['content']}")      
        user_message = st.text_input("Type your message...", key="user_message")       
        col_send, col_plan = st.columns(2)            
        with col_send:
            if st.button("Send Message"):
                if user_message:
                    room["messages"].append({
                        "type": "user",
                        "sender": st.session_state.username,
                        "content": user_message,
                        "timestamp": datetime.datetime.now().isoformat()
                    })
                    rooms[room_id] = room
                    if save_rooms(rooms):
                        st.rerun()
                    else:
                        st.error("Failed to send message. Please try again.")
        with col_plan:
            if st.button("🤖 Get AI Trip Plan"):
                all_constraints = []
                for participant, constraints in room["constraints"].items():
                    all_constraints.append(f"{participant}: {constraints}")            
                prompt = f"""
                Plan a group trip for {len(room['participants'])} people: {', '.join(room['participants'])}.
                
                Recent messages from the group:
                {chr(10).join([f"{msg['sender']}: {msg['content']}" for msg in room["messages"][-5:] if msg["type"] == "user"])}
                
                Individual constraints:
                {chr(10).join(all_constraints)}
                
                Please create a detailed trip plan that accommodates everyone's preferences and constraints.
                Consider budget limitations, date preferences, activity interests, and dietary requirements.
                All costs should be in Indian Rupees (₹).
                """            
                with st.spinner("AI is planning your trip..."):
                    ai_response = get_ai_recommendations(prompt, room_constraints=all_constraints)                
                    room["messages"].append({
                        "type": "ai",
                        "sender": "AI Assistant",
                        "content": ai_response,
                        "timestamp": datetime.datetime.now().isoformat()
                    })                 
                    room["trip_plan"] = ai_response
                    rooms[room_id] = room
                    if save_rooms(rooms):
                        st.rerun()
                    else:
                        st.error("Failed to generate trip plan. Please try again.")
    with col2:
        st.subheader("👥 Group Constraints")   
        if room["constraints"]:
            for participant, constraints in room["constraints"].items():
                with st.expander(f"{participant}'s Preferences"):
                    st.write(f"**Budget**: ₹{constraints.get('budget', 'Not set')}")
                    st.write(f"**Destination**: {constraints.get('destination', 'Not set')}")
                    st.write(f"**Activities**: {', '.join(constraints.get('activities', []))}")
                    st.write(f"**Accommodation**: {constraints.get('accommodation', 'Not set')}")
                    st.write(f"**Transport**: {', '.join(constraints.get('transport', []))}")
                    st.write(f"**Dietary**: {', '.join(constraints.get('dietary', []))}")
        else:
            st.info("No constraints set yet. Add yours in the sidebar!")    
        st.subheader("🚀 Quick Actions")
        if st.button("Check Weather"):
            destinations = [c.get('destination', '') for c in room["constraints"].values() if c.get('destination')]
            if destinations:
                weather_info = search_web_info(f"weather {destinations[0]}")
                st.info(weather_info["weather"])        
        if st.button("Find Cafes & Restaurants"):
            destinations = [c.get('destination', '') for c in room["constraints"].values() if c.get('destination')]
            if destinations:
                cafe_info = search_web_info(f"restaurants cafes {destinations[0]}")
                st.info(cafe_info["cafes"])        
        if st.button("Safety Check"):
            destinations = [c.get('destination', '') for c in room["constraints"].values() if c.get('destination')]
            if destinations:
                safety_info = search_web_info(f"travel safety {destinations[0]}")
                st.warning(safety_info["safety"])

def solo_planner():
    st.title("🎒 Solo Trip Planner")
    tab1, tab2 = st.tabs(["✍️ Quick Plan", "📋 Detailed Form"])   
    with tab1:
        st.subheader("🚀 Quick Trip Planning")
        trip_message = st.text_area(
            "Tell me about your trip plan:",
            placeholder="e.g., I want to visit Goa for 5 days with a budget of ₹30,000. I love beaches, adventure sports, and local food. Planning to go in December.",
            height=150
        )
        if st.button("🔥 Get My Trip Plan!", type="primary", key="quick_plan"):
            if trip_message:
                prompt = f"""
                Create a comprehensive trip plan based on this request: {trip_message}
                
                Focus on:
                - Popular attractions and must-visit places
                - Local experiences and activities
                - Practical travel tips for Indian travelers
                - Budget-friendly options and cost estimates in INR
                - Transportation recommendations
                - Accommodation suggestions
                - Food recommendations
                - Safety tips
                """
                with st.spinner("Creating your personalized trip plan..."):
                    plan = get_ai_recommendations(prompt, quick_plan=True)
                    st.subheader("✈️ Your Trip Plan")
                    st.write(plan)
                    words = trip_message.lower().split()
                    common_destinations = ["goa", "kerala", "rajasthan", "himachal", "kashmir", "mumbai", "delhi", "bangalore", "pune", "hyderabad", "manali", "shimla", "darjeeling", "ooty", "kodaikanal", "rishikesh", "haridwar", "varanasi", "agra", "jaipur", "udaipur", "jodhpur", "pushkar", "bikaner"]              
                    destination = None
                    for word in words:
                        if word in common_destinations:
                            destination = word.title()
                            break                  
                    if destination:
                        display_booking_links(destination)
            else:
                st.error("Please describe your trip plan!")    
    with tab2:
        st.subheader("📋 Detailed Trip Planning")
        col1, col2 = st.columns(2)
        with col1:
            destination_type = st.selectbox(
                "🏞️ Destination Type",
                ["Beach", "Mountains", "City", "Heritage", "Adventure", "Spiritual", "Wildlife", "Hill Station"]
            )      
        with col2:
            destination = st.selectbox(
                "📍 Select Destination",
                ["Goa", "Kerala", "Rajasthan", "Himachal Pradesh", "Kashmir", "Mumbai", "Delhi", "Bangalore", 
                 "Pune", "Hyderabad", "Manali", "Shimla", "Darjeeling", "Ooty", "Kodaikanal", "Rishikesh", 
                 "Haridwar", "Varanasi", "Agra", "Jaipur", "Udaipur", "Jodhpur", "Pushkar", "Bikaner", "Other"]
            )     
        if destination == "Other":
            custom_destination = st.text_input("Enter your destination:")
            destination = custom_destination if custom_destination else "Other"
        col3, col4 = st.columns(2)
        with col3:
            duration = st.number_input("🗓️ Trip Duration (days)", min_value=1, max_value=30, value=5)      
        with col4:
            travel_month = st.selectbox(
                "📅 Preferred Travel Month",
                ["January", "February", "March", "April", "May", "June", 
                 "July", "August", "September", "October", "November", "December"]
            )
        col5, col6 = st.columns(2)
        with col5:
            budget = st.number_input("💰 Budget (₹)", min_value=5000, max_value=500000, value=30000, step=5000)      
        with col6:
            accommodation_type = st.selectbox(
                "🏨 Accommodation Preference",
                ["Budget Hotels", "Mid-range Hotels", "Luxury Hotels", "Hostels", "Homestays", "Resorts", "Any"]
            )
        st.subheader("🎯 Your Interests")
        interests = st.multiselect(
            "Select your interests (choose multiple):",
            ["Adventure Sports", "Beaches", "Mountains", "Historical Sites", "Museums", "Local Food", 
             "Street Food", "Nightlife", "Shopping", "Photography", "Nature", "Wildlife", "Temples", 
             "Festivals", "Art & Culture", "Trekking", "Water Sports", "Yoga & Meditation", "Local Markets"]
        )
        col7, col8 = st.columns(2)
        with col7:
            travel_style = st.selectbox(
                "🎒 Travel Style",
                ["Relaxed", "Moderate", "Packed", "Adventurous", "Cultural", "Luxury"]
            )     
        with col8:
            group_size = st.selectbox(
                "👥 Group Size",
                ["Solo", "Couple", "Small Group (3-5)", "Large Group (6+)"]
            )
        transportation = st.multiselect(
            "🚗 Preferred Transportation",
            ["Flight", "Train", "Bus", "Car Rental", "Taxi/Cab", "Local Transport", "Walking"]
        )
        dietary = st.multiselect(
            "🍽️ Dietary Preferences",
            ["Vegetarian", "Vegan", "Non-Vegetarian", "Jain Food", "Gluten-Free", "Local Cuisine", "International Cuisine"]
        )
        special_requirements = st.text_area(
            "✨ Special Requirements or Notes",
            placeholder="Any specific requirements, accessibility needs, or additional preferences...",
            height=100
        )
        if st.button("🚀 Create Detailed Trip Plan!", type="primary", key="detailed_plan"):
            if destination and interests:
                prompt = f"""
                Create a comprehensive and detailed trip plan based on these specifications:
                
                DESTINATION: {destination} ({destination_type} destination)
                DURATION: {duration} days
                TRAVEL MONTH: {travel_month}
                BUDGET: ₹{budget:,}
                ACCOMMODATION: {accommodation_type}
                TRAVEL STYLE: {travel_style}
                GROUP SIZE: {group_size}
                
                INTERESTS: {', '.join(interests)}
                TRANSPORTATION: {', '.join(transportation) if transportation else 'Any suitable option'}
                DIETARY PREFERENCES: {', '.join(dietary) if dietary else 'No specific preferences'}
                
                SPECIAL REQUIREMENTS: {special_requirements if special_requirements else 'None'}
                
                Please create a detailed itinerary that includes:
                1. Day-wise breakdown of activities
                2. Specific attractions and experiences based on interests
                3. Accommodation recommendations within budget
                4. Transportation options and costs
                5. Food recommendations considering dietary preferences
                6. Budget breakdown with estimated costs
                7. Best time to visit attractions
                8. Local tips and cultural insights
                9. Safety recommendations
                10. Packing suggestions for {travel_month}
                
                Make sure the plan is practical for Indian travelers and includes cost estimates in INR.
                """               
                with st.spinner("Creating your detailed personalized trip plan..."):
                    plan = get_ai_recommendations(prompt, quick_plan=False)
                    st.subheader("✈️ Your Detailed Trip Plan")
                    st.write(plan)
                    if destination and destination != "Other":
                        display_booking_links(destination)
            else:
                st.error("Please select a destination and at least one interest!")

def display_booking_links(destination):
    st.subheader("🔗 Book Your Trip")
    booking_cols = st.columns(3)    
    with booking_cols[0]:
        st.subheader("🏨 Hotels")
        hotel_links = get_booking_links(destination, "hotel", "")
        for platform, link in hotel_links.items():
            st.markdown(f"[Book on {platform.title()}]({link})")    
    with booking_cols[1]:
        st.subheader("✈️ Travel")
        flight_links = get_booking_links(destination, "flight", "")
        for platform, link in flight_links.items():
            st.markdown(f"[Book on {platform.title()}]({link})")
        train_links = get_booking_links(destination, "train", "")
        for platform, link in train_links.items():
            st.markdown(f"[Book on {platform.title()}]({link})")  
    with booking_cols[2]:
        st.subheader("🍽️ Restaurants")
        restaurant_links = get_booking_links(destination, "restaurant", "")
        for platform, link in restaurant_links.items():
            st.markdown(f"[Find on {platform.title()}]({link})")

def main():
    if not st.session_state.user_logged_in:
        login_page()
        return   
    with st.sidebar:
        st.write(f"Welcome, **{st.session_state.username}**!")      
        page = st.selectbox(
            "Choose Mode",
            ["Solo Planner", "Group Planning", "My Rooms"]
        )      
        if st.button("Logout"):
            st.session_state.user_logged_in = False
            st.session_state.username = ""
            st.session_state.current_room = None
            st.rerun()   
    if page == "Solo Planner":
        solo_planner()   
    elif page == "Group Planning":
        st.title("👥 Group Trip Planning")       
        tab1, tab2 = st.tabs(["Create Room", "Join Room"])       
        with tab1:
            create_room()        
        with tab2:
            join_room()
        if st.session_state.current_room:
            st.divider()
            room_chat()   
    elif page == "My Rooms":
        st.title("🏠 My Rooms")       
        rooms, rooms_sha = load_rooms()
        user_rooms = [
            (room_id, room) for room_id, room in rooms.items()
            if st.session_state.username in room["participants"]
        ]       
        if user_rooms:
            for room_id, room in user_rooms:
                with st.expander(f"{room['name']} (ID: {room_id})"):
                    st.write(f"**Description**: {room['description']}")
                    st.write(f"**Creator**: {room['creator']}")
                    st.write(f"**Participants**: {', '.join(room['participants'])}")
                    st.write(f"**Created**: {room['created_at']}")                   
                    if st.button(f"Enter Room", key=f"enter_{room_id}"):
                        st.session_state.current_room = room_id
                        st.rerun()
        else:
            st.info("You haven't joined any rooms yet. Create or join a room to start planning!")

if __name__ == "__main__":
    main()