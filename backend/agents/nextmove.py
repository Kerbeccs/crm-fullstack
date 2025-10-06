from langgraph.graph import StateGraph, END, START
from typing import Annotated, Sequence, TypedDict, List
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
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

ATLAS_URI = os.getenv("MONGODB_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# MongoDB connection
client = AsyncIOMotorClient(ATLAS_URI)
db = client["crm_db"]
customers_collection = db["customers"]  
interactions_collection = db["interactions"] 
convosummary_collection = db["convosummary"]

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel('gemini-2.5-flash')

# ============= STATE DEFINITION =============
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    customer_id: str
    has_history: bool
    interaction_data: dict
    conversation_summary: str
    next_action: str
    user_approved: bool

# ============= TOOLS =============

@tool
async def checkid(customer_id: str):
    """Check if customer has any interactions in the interactions collection.
    Returns True if interactions exist, False if this is first contact."""
    try:
        object_id = ObjectId(customer_id)
        
        # Check if customer exists in customers collection first
        customer = await customers_collection.find_one({"_id": object_id})
        if not customer:
            return json.dumps({"exists": False, "error": "Customer not found in customers collection"})
        
        # Check if interactions document exists
        interaction_doc = await interactions_collection.find_one({"_id": object_id})
        
        if interaction_doc and "interactions" in interaction_doc:
            return json.dumps({
                "exists": True, 
                "has_history": True,
                "interaction_count": len(interaction_doc["interactions"])
            })
        else:
            return json.dumps({
                "exists": True,
                "has_history": False,
                "interaction_count": 0
            })
    except Exception as e:
        return json.dumps({"exists": False, "error": str(e)})

@tool
async def fetch_interactions(customer_id: str):
    """Fetch all past interactions for a customer from interactions collection"""
    try:
        object_id = ObjectId(customer_id)
        document = await interactions_collection.find_one({"_id": object_id})
        
        if document:
            # Convert ObjectId to string for JSON serialization
            document["_id"] = str(document["_id"])
            return json.dumps(document, default=str)
        else:
            return json.dumps({"interactions": [], "message": "No interactions found"})
    except Exception as e:
        error_msg = f"Error fetching interactions: {e}"
        print(error_msg)
        return json.dumps({"error": error_msg})

@tool
async def fetch_summary(customer_id: str):
    """Fetch conversation summary from convosummary collection"""
    try:
        object_id = ObjectId(customer_id)
        document = await convosummary_collection.find_one({"_id": object_id})
        
        if document:
            document["_id"] = str(document["_id"])
            return json.dumps(document, default=str)
        else:
            return json.dumps({"summary": "", "message": "No summary found - first interaction"})
    except Exception as e:
        error_msg = f"Error fetching summary: {e}"
        print(error_msg)
        return json.dumps({"error": error_msg})

@tool
async def add_interaction(customer_id: str, sender: str, interaction_type: str, interaction_summary: str):
    """Add a new interaction to the interactions collection.
    Args:
        customer_id: ObjectId of the customer
        sender: 'me' or 'customer'
        interaction_type: 'call' or 'email' or 'meeting'
        interaction_summary: Summary of what was discussed
    """
    try:
        object_id = ObjectId(customer_id)
        
        interaction = {
            "sender": sender,
            "type": interaction_type,
            "date": datetime.now(),
            "summary": interaction_summary
        }
        
        result = await interactions_collection.update_one(
            {"_id": object_id},
            {"$push": {"interactions": interaction}},
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            return f"✅ Interaction added successfully for customer {customer_id}"
        return f"No changes made for customer {customer_id}"
    except Exception as e:
        error_msg = f"❌ Error adding interaction: {e}"    
        print(error_msg)
        return error_msg

@tool 
async def update_summary(customer_id: str, summary: str):
    """Update or create conversation summary in convosummary collection"""
    try: 
        object_id = ObjectId(customer_id)
        
        result = await convosummary_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "summary": summary,
                    "last_updated": datetime.now()
                }
            },
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            return f"✅ Summary updated for customer {customer_id}"
        return f"No changes made to summary"
    except Exception as e:
        error_msg = f"❌ Error updating summary: {e}"
        print(error_msg)
        return error_msg

# Initialize tools
tools = [checkid, fetch_interactions, fetch_summary, add_interaction, update_summary]

# ============= WORKFLOW NODES =============

async def check_customer_node(state: AgentState):
    """Node 1: Check if customer has interaction history"""
    print("🔍 Checking customer history...")
    
    customer_id = state["customer_id"]
    
    # Call checkid tool
    check_result = await checkid.ainvoke({"customer_id": customer_id})
    result_data = json.loads(check_result)
    
    has_history = result_data.get("has_history", False)
    
    print(f"   Customer has history: {has_history}")
    
    return {
        **state,
        "has_history": has_history
    }

async def fetch_context_node(state: AgentState):
    """Node 2: Fetch interaction history and summary if exists"""
    print("📥 Fetching customer context...")
    
    customer_id = state["customer_id"]
    
    if state["has_history"]:
        # Fetch interactions
        interactions_result = await fetch_interactions.ainvoke({"customer_id": customer_id})
        interactions_data = json.loads(interactions_result)
        
        # Fetch summary
        summary_result = await fetch_summary.ainvoke({"customer_id": customer_id})
        summary_data = json.loads(summary_result)
        
        print(f"   Found {len(interactions_data.get('interactions', []))} past interactions")
        
        return {
            **state,
            "interaction_data": interactions_data,
            "conversation_summary": summary_data.get("summary", "")
        }
    else:
        print("   No previous interactions - new lead")
        return {
            **state,
            "interaction_data": {"interactions": []},
            "conversation_summary": "First contact with this lead"
        }

async def generate_suggestion_node(state: AgentState):
    """Node 3: Generate next action suggestion using LLM"""
    print("🤖 Generating next action suggestion...")
    
    customer_id = state["customer_id"]
    has_history = state["has_history"]
    conversation_summary = state.get("conversation_summary", "")
    interactions = state.get("interaction_data", {}).get("interactions", [])
    
    # Build context for LLM
    if has_history:
        context = f"""
CONVERSATION SUMMARY:
{conversation_summary}

RECENT INTERACTIONS (Last 5):
"""
        for interaction in interactions[-5:]:
            context += f"- {interaction['date']}: [{interaction['type']}] {interaction['sender']}: {interaction['summary']}\n"
    else:
        context = "This is the FIRST contact with this lead. No previous interaction history."
    
    system_prompt = f"""You are an expert sales assistant helping with lead conversion.

CUSTOMER ID: {customer_id}

{context}

YOUR TASK:
1. Analyze the customer's situation and interaction history
2. Suggest the NEXT BEST ACTION to move this lead forward
3. Options: Call, Email, Meeting, or Drop Lead
if the person hints for call or other things plan those things do go in too detials of having ohone number or not 
If suggesting EMAIL: Write a complete, professional yet friendly email
If suggesting CALL: Provide talking points and key questions to ask
If suggesting MEETING: Suggest agenda and objectives
If DROP LEAD: Explain why and suggest alternatives

Format your response clearly with:
- Recommended Action: [Call/Email/Meeting/Drop]
- Reasoning: [Why this action]
- Content: [Email text / Call script / Meeting agenda]
"""

    # Generate suggestion
    response = await llm.generate_content_async(system_prompt)
    suggestion = response.text
    
    print(f"   ✅ Suggestion generated")
    
    return {
        **state,
        "next_action": suggestion,
        "messages": state.get("messages", []) + [AIMessage(content=suggestion)]
    }

async def present_to_user_node(state: AgentState):
    """Node 4: Present suggestion to user and get approval"""
    print("\n" + "="*60)
    print("📋 SUGGESTED NEXT ACTION:")
    print("="*60)
    print(state["next_action"])
    print("="*60)
    
    user_input = input("\n👤 Your response (type 'ok' to approve, or describe changes needed): ").strip().lower()
    
    if user_input == "ok":
        print("✅ Approved! Storing in database...")
        return {
            **state,
            "user_approved": True,
            "messages": state.get("messages", []) + [HumanMessage(content="ok")]
        }
    else:
        print("✏️ Regenerating based on your feedback...")
        return {
            **state,
            "user_approved": False,
            "messages": state.get("messages", []) + [HumanMessage(content=f"Please modify: {user_input}")]
        }

async def store_interaction_node(state: AgentState):
    """Node 5: Store approved interaction and update summary"""
    print("💾 Storing interaction in database...")
    
    customer_id = state["customer_id"]
    next_action = state["next_action"]
    
    # Determine interaction type from the suggestion
    interaction_type = "email"  # Default
    if "call" in next_action.lower():
        interaction_type = "call"
    elif "meeting" in next_action.lower():
        interaction_type = "meeting"
    
    # Add interaction
    await add_interaction.ainvoke({
        "customer_id": customer_id,
        "sender": "me",
        "interaction_type": interaction_type,
        "interaction_summary": next_action
    })
    
    # Update summary with LLM
    print(" Updating conversation summary...")
    
    summary_prompt = f"""
Previous Summary:
{state.get('conversation_summary', 'No previous summary')}

New Interaction:
{next_action}

Create a concise updated summary (max 200 words) that captures:
1. Key points from previous interactions
2. This new action taken
3. Current status of the lead
4. Next expected steps

Keep it brief and focused on actionable insights.
"""
    
    summary_response = await llm.generate_content_async(summary_prompt)
    new_summary = summary_response.text
    
    await update_summary.ainvoke({
        "customer_id": customer_id,
        "summary": new_summary
    })
    
    print("✅ Database updated successfully!")
    
    return state

# ============= CONDITIONAL EDGES =============

def should_continue_after_check(state: AgentState):
    """Decide next step after checking customer"""
    return "fetch_context"

def should_continue_after_presentation(state: AgentState):
    """Decide if we should store or regenerate"""
    if state.get("user_approved", False):
        return "store_interaction"
    else:
        return "generate_suggestion"

# ============= BUILD GRAPH =============

def create_conversation_workflow():
    """Create the LangGraph workflow"""
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("check_customer", check_customer_node)
    workflow.add_node("fetch_context", fetch_context_node)
    workflow.add_node("generate_suggestion", generate_suggestion_node)
    workflow.add_node("present_to_user", present_to_user_node)
    workflow.add_node("store_interaction", store_interaction_node)
    
    # Add edges
    workflow.set_entry_point("check_customer")
    workflow.add_edge("check_customer", "fetch_context")
    workflow.add_edge("fetch_context", "generate_suggestion")
    workflow.add_edge("generate_suggestion", "present_to_user")
    
    # Conditional edge after user approval
    workflow.add_conditional_edges(
        "present_to_user",
        should_continue_after_presentation,
        {
            "store_interaction": "store_interaction",
            "generate_suggestion": "generate_suggestion"
        }
    )
    
    workflow.add_edge("store_interaction", END)
    
    return workflow.compile()

# ============= MAIN EXECUTION =============

async def main():
    """Main function to run the conversation assistant"""
    print("="*60)
    print("🎯 AI Sales Conversation Assistant")
    print("="*60)
    
    # Get customer ID from user
    customer_id = input("\nEnter Customer ObjectId: ").strip()
    
    # Validate customer exists
    try:
        object_id = ObjectId(customer_id)
        customer = await customers_collection.find_one({"_id": object_id})
        
        if not customer:
            print("❌ Customer not found in database!")
            return
        
        print(f"✅ Found customer: {customer.get('name', 'Unknown')}")
        print()
        
    except Exception as e:
        print(f"❌ Invalid Customer ID: {e}")
        return
    
    # Create and run workflow
    workflow = create_conversation_workflow()
    
    initial_state = AgentState(
        messages=[],
        customer_id=customer_id,
        has_history=False,
        interaction_data={},
        conversation_summary="",
        next_action="",
        user_approved=False
    )
    
    print("🔄 Running workflow...\n")
    final_state = await workflow.ainvoke(initial_state)
    
    print("\n" + "="*60)
    print("🎉 Workflow completed successfully!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())