from langgraph.graph import StateGraph, END
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import google.generativeai as genai
import asyncio
from langchain_core.tools import tool
import os
from dotenv import load_dotenv
import json

load_dotenv()

ATLAS_URI = os.getenv("MONGODB_URI")  # Changed to match your other code
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = AsyncIOMotorClient(ATLAS_URI)
db = client["crm_db"]
customers_collection = db["customers"]  
interactions_collection = db["interactions"] 
convosummary_collection = db["convosummary"]

genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel('gemini-2.5-flash')

# ============= TOOLS =============

@tool
async def add_customer_response(customer_id: str, sender: str, interaction_type: str, interaction_summary: str):
    """Add a customer's response to the interactions collection
    Args:
        customer_id: ObjectId of the customer
        sender: 'me' (sales agent) or 'customer'
        interaction_type: Type of interaction ('call', 'email', 'meeting')
        interaction_summary: Summary of what was discussed
    """
    try:
        object_id = ObjectId(customer_id)
        
        interaction = {
            "sender": sender,  # Now flexible - can be 'me' or 'customer'
            "type": interaction_type,
            "date": datetime.utcnow(),
            "summary": interaction_summary
        }
        
        result = await interactions_collection.update_one(
            {"_id": object_id},
            {"$push": {"interactions": interaction}},
            upsert=True
        )
        
        return json.dumps({
            "success": True, 
            "message": f"Customer response added successfully"
        })
    except Exception as e:
        error_msg = f"Error adding customer response: {e}"
        print(error_msg)
        return json.dumps({"success": False, "error": error_msg})

@tool    
async def update_conversation_summary(customer_id: str, summary: str):
    """Update the conversation summary for a customer
    Args:
        customer_id: ObjectId of the customer
        summary: Updated summary of all interactions
    """
    try:
        object_id = ObjectId(customer_id)
        
        result = await convosummary_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "customer_id": object_id,
                    "summary": summary,
                    "last_updated": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return json.dumps({
            "success": True, 
            "message": "Summary updated successfully"
        })
    except Exception as e:
        error_msg = f"Error updating summary: {e}"
        print(error_msg)
        return json.dumps({"success": False, "error": error_msg})

@tool
async def fetch_summary(customer_id: str):
    """Fetch conversation summary from convosummary collection"""
    try:
        object_id = ObjectId(customer_id)
        document = await convosummary_collection.find_one({"_id": object_id})
        
        if document:
            document["_id"] = str(document["_id"])
            if "customer_id" in document:
                document["customer_id"] = str(document["customer_id"])
            return json.dumps(document, default=str)
        else:
            return json.dumps({
                "summary": "No previous interactions recorded.", 
                "message": "First customer response"
            })
    except Exception as e:
        error_msg = f"Error fetching summary: {e}"
        print(error_msg)
        return json.dumps({"error": error_msg})

@tool
async def fetch_last_agent_message(customer_id: str):
    """Fetch the last message sent by the agent to provide context"""
    try:
        object_id = ObjectId(customer_id)
        document = await interactions_collection.find_one({"_id": object_id})
        
        if document and "interactions" in document:
            # Find last interaction from "me" (the agent)
            agent_messages = [i for i in document["interactions"] if i.get("sender") == "me"]
            if agent_messages:
                last_msg = agent_messages[-1]
                return json.dumps({
                    "found": True,
                    "type": last_msg.get("type"),
                    "summary": last_msg.get("summary"),
                    "date": str(last_msg.get("date"))
                }, default=str)
        
        return json.dumps({
            "found": False, 
            "message": "No previous agent message found"
        })
    except Exception as e:
        error_msg = f"Error fetching last message: {e}"
        print(error_msg)
        return json.dumps({"error": error_msg})

# ============= STATE DEFINITION =============

class CustomerResponseState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    customer_id: str
    interaction_type: str
    customer_response: str
    current_summary: str
    last_agent_message: str
    updated_summary: str

# ============= WORKFLOW NODES =============

async def fetch_context_node(state: CustomerResponseState):
    """Node 1: Fetch current summary and last agent message for context"""
    print("📥 Fetching conversation context...")
    
    try:
        # Fetch summary
        summary_result = await fetch_summary.ainvoke({"customer_id": state["customer_id"]})
        summary_data = json.loads(summary_result)
        
        # Fetch last agent message
        last_msg_result = await fetch_last_agent_message.ainvoke({"customer_id": state["customer_id"]})
        last_msg_data = json.loads(last_msg_result)
        
        last_msg_text = ""
        if last_msg_data.get("found"):
            last_msg_text = f"Last agent message ({last_msg_data['type']}): {last_msg_data['summary']}"
        else:
            last_msg_text = "No previous agent message (this may be inbound inquiry)"
        
        print(f"   ✅ Context fetched")
        
        return {
            **state,
            "current_summary": summary_data.get("summary", "No previous summary"),
            "last_agent_message": last_msg_text
        }
    except Exception as e:
        print(f"   ❌ Error fetching context: {e}")
        return {
            **state,
            "current_summary": "Error fetching summary",
            "last_agent_message": "Error fetching last message"
        }

async def store_customer_response_node(state: CustomerResponseState):
    """Node 2: Store the customer's response in interactions collection"""
    print("💾 Storing customer response...")
    
    try:
        result = await add_customer_response.ainvoke({
            "customer_id": state["customer_id"],
            "sender": "customer",  # This is a customer response
            "interaction_type": state["interaction_type"],
            "interaction_summary": state["customer_response"]
        })
        
        result_data = json.loads(result)
        if result_data.get("success"):
            print(f"   ✅ Customer response stored")
        else:
            print(f"   ⚠️ Storage issue: {result_data.get('error')}")
        
        return state
    except Exception as e:
        print(f"   ❌ Error storing response: {e}")
        return state

async def generate_updated_summary_node(state: CustomerResponseState):
    """Node 3: Generate updated summary using LLM"""
    print("🤖 Generating updated summary with customer response...")
    
    summary_prompt = f"""
PREVIOUS CONVERSATION SUMMARY:
{state["current_summary"]}

LAST AGENT MESSAGE:
{state["last_agent_message"]}

NEW CUSTOMER RESPONSE:
Type: {state["interaction_type"]}
Customer said: {state["customer_response"]}

---

Create a concise updated summary (max 250 words) that:
1. Integrates this new customer response
2. Maintains key points from previous interactions
3. Highlights the customer's needs, concerns, or objections
4. Notes their sentiment (positive, neutral, negative, interested, etc.)
5. Identifies any required follow-up actions
6. Tracks the stage of the conversation (cold, interested, negotiating, ready to buy, etc.)

Focus on:
- What the customer wants
- Their objections or concerns
- Their timeline and urgency
- Decision-making status
- Next steps needed

Write from a neutral, analytical perspective.
"""
    
    try:
        summary_response = await llm.generate_content_async(summary_prompt)
        new_summary = summary_response.text
        
        print(f"   ✅ Summary generated")
        
        return {
            **state,
            "updated_summary": new_summary
        }
    except Exception as e:
        print(f"   ❌ Error generating summary: {e}")
        return {
            **state,
            "updated_summary": state["current_summary"]  # Fallback to old summary
        }

async def update_summary_db_node(state: CustomerResponseState):
    """Node 4: Store the updated summary in database"""
    print("📝 Updating conversation summary in database...")
    
    try:
        result = await update_conversation_summary.ainvoke({
            "customer_id": state["customer_id"],
            "summary": state["updated_summary"]
        })
        
        result_data = json.loads(result)
        if result_data.get("success"):
            print(f"   ✅ Summary updated in database")
        else:
            print(f"   ⚠️ Update issue: {result_data.get('error')}")
        
        return state
    except Exception as e:
        print(f"   ❌ Error updating summary: {e}")
        return state

# ============= BUILD GRAPH =============

def create_customer_response_workflow():
    """Create the LangGraph workflow for handling customer responses"""
    
    workflow = StateGraph(CustomerResponseState)
    
    # Add nodes
    workflow.add_node("fetch_context", fetch_context_node)
    workflow.add_node("store_response", store_customer_response_node)
    workflow.add_node("generate_summary", generate_updated_summary_node)
    workflow.add_node("update_summary", update_summary_db_node)
    
    # Add edges (linear flow)
    workflow.set_entry_point("fetch_context")
    workflow.add_edge("fetch_context", "store_response")
    workflow.add_edge("store_response", "generate_summary")
    workflow.add_edge("generate_summary", "update_summary")
    workflow.add_edge("update_summary", END)
    
    return workflow.compile()

# ============= MAIN EXECUTION =============

async def main():
    """Main function to run the customer response processor"""
    print("="*60)
    print("📨 Customer Response Processor")
    print("="*60)
    
    # Get customer ID
    customer_id = input("\nEnter Customer ObjectId: ").strip()
    
    # Validate customer exists
    try:
        object_id = ObjectId(customer_id)
        
        # Check if customer exists in customers collection
        customer = await customers_collection.find_one({"_id": object_id})
        
        if not customer:
            print("❌ Customer not found in customers collection!")
            print("   Make sure this customer exists before adding responses.")
            return
        
        print(f"✅ Found customer: {customer.get('name', 'Unknown')}")
        
        # Check if they have interaction history
        interaction_doc = await interactions_collection.find_one({"_id": object_id})
        if interaction_doc:
            interaction_count = len(interaction_doc.get("interactions", []))
            print(f"   📊 Existing interactions: {interaction_count}")
        else:
            print(f"   📊 No previous interactions (this will be the first)")
        
    except Exception as e:
        print(f"❌ Invalid Customer ID: {e}")
        return
    
    # Get interaction type
    print("\nHow did the customer respond?")
    print("1. Call")
    print("2. Email") 
    print("3. Meeting")
    interaction_choice = input("Choose interaction type (1-3): ").strip()
    
    interaction_types = {
        "1": "call",
        "2": "email",
        "3": "meeting"
    }
    
    if interaction_choice not in interaction_types:
        print("❌ Invalid interaction type!")
        return
        
    interaction_type = interaction_types[interaction_choice]
    
    # Get customer's response
    print("\nEnter what the customer said/wrote:")
    print("(Be specific - this will be stored and used for AI analysis)")
    customer_response = input("> ").strip()
    
    if not customer_response:
        print("❌ Customer response cannot be empty!")
        return
    
    print("\n" + "="*60)
    print("🔄 Processing customer response...")
    print("="*60)
    
    # Create and run workflow
    workflow = create_customer_response_workflow()
    
    initial_state = CustomerResponseState(
        messages=[],
        customer_id=customer_id,
        interaction_type=interaction_type,
        customer_response=customer_response,
        current_summary="",
        last_agent_message="",
        updated_summary=""
    )
    
    final_state = await workflow.ainvoke(initial_state)
    
    # Show results
    print("\n" + "="*60)
    print("✅ Customer response processed successfully!")
    print("="*60)
    
    if final_state["updated_summary"]:
        print("\n📝 Updated Conversation Summary:")
        print("-"*60)
        print(final_state["updated_summary"])
        print("-"*60)
    
    print("\n💡 Next: Use the conversation assistant to generate your reply!")

if __name__ == "__main__":
    asyncio.run(main())