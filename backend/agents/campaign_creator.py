
from langgraph.graph import StateGraph, END
import os
from langchain_core.messages import SystemMessage, AIMessage
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import json
import google.generativeai as genai
from bson.objectid import ObjectId
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from typing import Annotated, Sequence, TypedDict, List
from datetime import datetime
import asyncio

# Load environment variables
load_dotenv()

ATLAS_URI = os.getenv("MONGODB_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not ATLAS_URI:
    raise ValueError("ATLAS_URI not found in .env file")

if not GEMINI_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

# MongoDB connection
client = AsyncIOMotorClient(ATLAS_URI)
db = client["crm_db"]
customers_collection = db["customers"]
campaigns_collection = db["campaigns"]
mapcamp_collection = db["mapcamp"]

# Define state for LangGraph
class CampaignState(TypedDict):
    messages: Annotated[Sequence[AIMessage], "The messages in the conversation"]
    customer_data: List[dict]
    campaigns_created: List[dict]
    mappings_created: List[dict]

# Tools for the LangGraph workflow
@tool
async def fetch_crm_data():
    """Fetch all customer data from the database for analysis"""
    try:
        customer_data = await customers_collection.find().to_list(None)
        # Convert ObjectId to string for JSON serialization
        for customer in customer_data:
            customer["_id"] = str(customer["_id"])
        
        print(f"Fetched {len(customer_data)} customers from database")
        return json.dumps(customer_data, default=str)
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return f"Error fetching data: {str(e)}"

@tool
async def campaign_creation(campaign_custom_id: int, campaign_parameter: str):
    """Create a new campaign in the database with given ID and parameters"""
    try:
        document = {
            "campaign_id": campaign_custom_id,
            "parameter_description": campaign_parameter,
            "created_at": datetime.now()
        }
        
        result = await campaigns_collection.insert_one(document)
        success_msg = f"Campaign {campaign_custom_id} created: {campaign_parameter}"
        print(f"✅ {success_msg}")
        return success_msg
    except Exception as e:
        error_msg = f"Error creating campaign: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@tool
async def campaign_mapping(customer_obj_id: str, suitable_campaign_id: int):
    """Map customer to appropriate campaign based on analysis"""
    try:
        document = {
            "customer_obj_id": customer_obj_id,
            "campaign_id": suitable_campaign_id,
            "mapped_at": datetime.now()
        }
        
        result = await mapcamp_collection.insert_one(document)
        success_msg = f"Customer {customer_obj_id[:8]}... mapped to campaign {suitable_campaign_id}"
        print(f"📍 {success_msg}")
        return success_msg
    except Exception as e:
        error_msg = f"Error mapping customer: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

# Initialize tools
tools = [fetch_crm_data, campaign_creation, campaign_mapping]

# Initialize LLM with tools
genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel('gemini-2.5-flash')

# Define workflow nodes
async def call_model(state: CampaignState):
    """Call the LLM to analyze data and create campaigns """
    system_prompt = SystemMessage(
        content="""You are a professional CRM analyst and campaign strategist. Your task is to:

1. First, use fetch_crm_data tool to get all customer data
2. Analyze the customer data to identify patterns (location, business type, size, etc.)
3. Create  campaigns using campaign_creation tool with:
   - campaign_custom_id: Use integers 1, 2, 3, etc.
   - campaign_parameter: Describe the campaign focus (e.g., "Mumbai-based retail businesses", "Small tech companies")
4. Finally, use campaign_mapping tool to assign each customer to appropriate campaigns
5. Use the campaign to group people in the database with common parameters that you think should be the best
Be systematic and thorough in your analysis. Create campaigns that make business sense based on the actual customer data patterns you observe."""
    )
    
    messages = [system_prompt] + state.get("messages", [])
    print("🤖 Calling AI model for analysis...")

    # Convert messages to a format compatible with Gemini
    prompt = "\n".join([msg.content for msg in messages])
    
    try:
        # Use generate_content_async for the Gemini model
        response = await llm.generate_content_async(prompt)
        # Wrap the response content in an AIMessage for compatibility with LangGraph
        ai_message = AIMessage(content=response.text)
        return {"messages": [ai_message]}
    except Exception as e:
        print(f"Error calling Gemini model: {str(e)}")
        return {"messages": [AIMessage(content=f"Error: {str(e)}")]}
async def execute_tools(state: CampaignState):
    """Execute any tool calls from the LLM response"""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        print(f"🔧 Executing {len(last_message.tool_calls)} tool calls...")
        tool_node = ToolNode(tools)
        result = await tool_node.ainvoke(state)
        return result
    
    return state

def should_continue(state: CampaignState):
    """Determine if workflow should continue or end"""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "execute_tools"
    else:
        return END

# Create the workflow graph
def create_campaign_workflow():
    workflow = StateGraph(CampaignState)
    
    # Add nodes
    workflow.add_node("call_model", call_model)
    workflow.add_node("execute_tools", ToolNode(tools))
    
    # Add edges
    workflow.set_entry_point("call_model")
    workflow.add_conditional_edges("call_model", should_continue)
    workflow.add_edge("execute_tools", "call_model")
    
    return workflow.compile()

# Main execution function
async def run_campaign_creation():
    """Main function to run the campaign creation workflow"""
    try:
        print("=" * 60)
        print("🚀 Starting AI Campaign Creation Workflow")
        print("=" * 60)
        
        # Clear existing campaigns and mappings (optional - for testing)
        campaigns_deleted = await campaigns_collection.delete_many({})
        mappings_deleted = await mapcamp_collection.delete_many({})
        print(f"🗑️  Cleared {campaigns_deleted.deleted_count} existing campaigns")
        print(f"🗑️  Cleared {mappings_deleted.deleted_count} existing mappings")
        print()
        
        # Create and run workflow
        workflow = create_campaign_workflow()
        
        initial_state = CampaignState(
            messages=[],
            customer_data=[],
            campaigns_created=[],
            mappings_created=[]
        )
        
        print("🔄 Running LangGraph workflow...")
        final_state = await workflow.ainvoke(initial_state)
        
        # Get final results
        campaigns_count = await campaigns_collection.count_documents({})
        mappings_count = await mapcamp_collection.count_documents({})
        
        print()
        print("=" * 60)
        print("📊 CAMPAIGN CREATION SUMMARY")
        print("=" * 60)
        print(f"✅ Campaigns Created: {campaigns_count}")
        print(f"✅ Customer Mappings: {mappings_count}")
        print(f"✅ Workflow Messages: {len(final_state.get('messages', []))}")
        
        if campaigns_count > 0:
            print("\n📋 Campaign Details:")
            campaigns = await campaigns_collection.find().to_list(100)
            for campaign in campaigns:
                customer_count = await mapcamp_collection.count_documents({
                    "campaign_id": campaign["campaign_id"]
                })
                print(f"   Campaign {campaign['campaign_id']}: {campaign['parameter_description']}")
                print(f"   └── {customer_count} customers assigned")
        
        result = {
            "status": "success",
            "campaigns_created": campaigns_count,
            "customer_mappings": mappings_count,
            "workflow_messages": len(final_state.get("messages", []))
        }
        
        print("\n🎉 Campaign creation workflow completed successfully!")
        return result
        
    except Exception as e:
        error_msg = f"Campaign creation failed: {str(e)}"
        print(f"❌ {error_msg}")
        return {"status": "error", "message": error_msg}

# Terminal execution
async def main():
    """Main function for terminal execution"""
    print("🤖 AI CRM Campaign Creator")
    print("This will analyze your customer data and create AI-powered campaigns")
 
    customer_count = await customers_collection.count_documents({})
    if customer_count == 0:
        print("❌ No customers found in database. Please add some customers first.")
        return
    
    print(f"📊 Found {customer_count} customers in database")
    

    proceed = input("\nProceed with campaign creation? (y/n): ").lower().strip()
    if proceed != 'y':
        print("Campaign creation cancelled.")
        return
    
    result = await run_campaign_creation()
    
    if result["status"] == "success":
        print(f"\n✅ Success! Check your database for the new campaigns and mappings.")
    else:
        print(f"\n❌ Failed: {result.get('message', 'Unknown error')}")

if __name__ == "__main__":

    asyncio.run(main())