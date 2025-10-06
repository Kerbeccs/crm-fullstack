from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from dotenv import load_dotenv
from bson import ObjectId
from bson.errors import InvalidId
import os

app = FastAPI()
"""PLEASE IGNR THE CLUTTERED CODE THIS MAIN.PY THINGS ARE PILED ONE AFTER THE ANOTHER WITHOUT ANY STRUCTURE"""
load_dotenv()
ATLAS_URI = os.getenv("MONGODB_URI")
if not ATLAS_URI:
    raise ValueError("ATLAS_URI not found in .env file")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncIOMotorClient(ATLAS_URI)
db = client["crm_db"]
customers_collection = db["customers"]
campaigns_collection = db["campaigns"]
mapcamp_collection = db["mapcamp"]
interactions_collection = db["interactions"]
convosummary_collection = db["convosummary"]

def serialize_doc(doc):
    """Convert a single MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

def serialize_docs(docs):
    """Convert multiple MongoDB documents to JSON-serializable format"""
    return [serialize_doc(doc) for doc in docs]

def serialize_customer(customer):
    """Convert customer document to JSON-serializable format"""
    return serialize_doc(customer)

class CustomerIdsRequest(BaseModel):
    ids: List[str]

class Customer(BaseModel):
    name: str
    contact_number: Optional[str] = None
    address: Optional[str] = None
    instagram_id: Optional[str] = None
    description: Optional[str] = None
    google_maps_link: Optional[str] = None
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    size: Optional[str] = None
    created_at: Optional[str] = None

@app.post("/customers")
async def create_customer(customer: Customer):
    try:
        # Set created_at if not provided
        customer_data = customer.dict(exclude_unset=True)
        if not customer_data.get("created_at"):
            customer_data["created_at"] = datetime.utcnow().isoformat()

        print("customer_data:", customer_data)

        # Save to MongoDB Atlas
        result = await customers_collection.insert_one(customer_data)
        print("inserted_id:", result.inserted_id, "type:", type(result.inserted_id))

        # Convert ObjectId to string for JSON response
        customer_data["_id"] = str(result.inserted_id)
        
        response = {"status": "Customer created", "customer": customer_data}
        print("response:", response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create customer: {str(e)}")

@app.get("/customers")
async def get_customers():
    customers = await customers_collection.find().to_list(100)
    return serialize_docs(customers)

@app.get("/api/customers/{customer_id}")
async def get_customer_by_id(customer_id: str):
    """Fetch a single customer by ID"""
    try:
        object_id = ObjectId(customer_id)
        customer = await customers_collection.find_one({"_id": object_id})
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return serialize_doc(customer)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid customer ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching customer: {str(e)}")

# Campaign Dashboard API Routes
@app.get("/api/campaigns")
async def get_campaigns():
    """Fetch all campaigns from MongoDB"""
    try:
        campaigns = await campaigns_collection.find().sort("campaign_id", 1).to_list(1000)
        print(f"Found {len(campaigns)} campaigns")
        return serialize_docs(campaigns)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching campaigns: {str(e)}")

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int):
    """Fetch specific campaign by ID"""
    try:
        campaign = await campaigns_collection.find_one({"campaign_id": campaign_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return serialize_doc(campaign)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching campaign: {str(e)}")

@app.get("/api/mapcamp")
async def get_campaign_mapping(campaign_id: Optional[int] = None):
    """Fetch campaign-customer mapping"""
    try:
        query = {}
        if campaign_id:
            query["campaign_id"] = campaign_id
        mappings = await mapcamp_collection.find(query).to_list(1000)
        return serialize_docs(mappings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching campaign mapping: {str(e)}")

@app.post("/api/customers")
async def get_customers_by_ids(request: CustomerIdsRequest):
    """Fetch customers by list of IDs"""
    try:
        object_ids = [ObjectId(id_str) for id_str in request.ids]
        customers = await customers_collection.find({"_id": {"$in": object_ids}}).to_list(1000)
        return serialize_docs(customers)
    except InvalidId as e:
        raise HTTPException(status_code=400, detail=f"Invalid ObjectId: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching customers: {str(e)}")

@app.get("/api/campaigns/{campaign_id}/customers")
async def get_campaign_customers(campaign_id: int):
    """Fetch all customers for a specific campaign"""
    try:
        mappings = await mapcamp_collection.find({"campaign_id": campaign_id}).to_list(1000)
        if not mappings:
            return []
        customer_ids = [ObjectId(mapping["customer_obj_id"]) for mapping in mappings]
        customers = await customers_collection.find({"_id": {"$in": customer_ids}}).to_list(1000)
        return serialize_docs(customers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching campaign customers: {str(e)}")

@app.get("/api/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        total_campaigns = await campaigns_collection.count_documents({})
        total_customers = await customers_collection.count_documents({})
        total_mappings = await mapcamp_collection.count_documents({})
        
        city_pipeline = [
            {"$group": {"_id": "$city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        cities = await customers_collection.aggregate(city_pipeline).to_list(100)
        
        size_pipeline = [
            {"$group": {"_id": "$size", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        sizes = await customers_collection.aggregate(size_pipeline).to_list(100)
        
        return {
            "total_campaigns": total_campaigns,
            "total_customers": total_customers,
            "total_mappings": total_mappings,
            "customers_by_city": cities,
            "customers_by_size": sizes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        await db.command("ping")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")

@app.get("/api/debug")
async def debug():
    """Debug endpoint for troubleshooting"""
    try:
        await db.command("ping")
        campaign_count = await campaigns_collection.count_documents({})
        first_campaign = await campaigns_collection.find_one()
        return {
            "database_connected": True,
            "campaign_count": campaign_count,
            "first_campaign": serialize_doc(first_campaign) if first_campaign else None,
            "atlas_uri_set": bool(ATLAS_URI)
        }
    except Exception as e:
        return {
            "error": str(e),
            "atlas_uri_set": bool(ATLAS_URI)
        }

@app.get("/api/customers/{customer_id}/interactions")
async def get_customer_interactions(customer_id: str):
    """Get all interactions for a specific customer"""
    try:
        # Convert customer_id string to ObjectId
        object_id = ObjectId(customer_id)
        
        # Fetch interactions document (stored with _id as customer ObjectId)
        interaction_doc = await interactions_collection.find_one({"_id": object_id})
        
        # Extract interactions array from the document
        interactions_list = []
        if interaction_doc and "interactions" in interaction_doc:
            interactions_list = interaction_doc["interactions"]
            # Add timestamp field if it doesn't exist (use 'date' field)
            for interaction in interactions_list:
                if "timestamp" not in interaction and "date" in interaction:
                    interaction["timestamp"] = interaction["date"]
        
        # Fetch conversation summary (also stored with _id as customer ObjectId)
        summary_doc = await convosummary_collection.find_one({"_id": object_id})
        summary_text = summary_doc.get("summary") if summary_doc else None
        
        return {
            "interactions": interactions_list,
            "summary": summary_text
        }
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid customer ID format")
    except Exception as e:
        print(f"Error fetching interactions for customer {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching interactions: {str(e)}")

class NextActionRequest(BaseModel):
    customer_id: str
    approval: Optional[str] = None
    suggestion: Optional[str] = None
    interaction_type: Optional[str] = None
    customer_response: Optional[str] = None

@app.post("/api/customers/{customer_id}/next-action")
async def generate_next_action(customer_id: str, request: NextActionRequest):
    """Run the nextmove agent for a customer - API version without terminal interaction"""
    try:
        # Import the necessary functions from nextmove
        from agents.nextmove import (
            check_customer_node, 
            fetch_context_node, 
            generate_suggestion_node,
            store_interaction_node,
            AgentState
        )
        
        # Create initial state
        state = AgentState(
            messages=[],
            customer_id=customer_id,
            has_history=False,
            interaction_data={},
            conversation_summary="",
            next_action="",
            user_approved=False
        )
        
        # Check if this is an approval request
        if request.approval:
            if request.approval.lower() == "ok":
                # User approved - store the suggestion
                state["next_action"] = request.suggestion or ""
                state["user_approved"] = True
                await store_interaction_node(state)
                
                return {
                    "status": "success",
                    "message": "Action stored successfully",
                    "suggestion": state["next_action"]
                }
            else:
                # User requested changes - regenerate with feedback
                print(f"✏️ Regenerating with feedback: {request.approval}")
                
                # Add user feedback as a message
                from langchain_core.messages import HumanMessage
                state["messages"] = [HumanMessage(content=f"Please modify the suggestion: {request.approval}")]
                
                # Re-run the workflow with feedback
                state = await check_customer_node(state)
                state = await fetch_context_node(state)
                state = await generate_suggestion_node(state)
                
                return {
                    "status": "success",
                    "suggestion": state.get("next_action", ""),
                    "needs_approval": True
                }
        
        # Otherwise, generate new suggestion (run workflow nodes manually without present_to_user)
        # Step 1: Check customer history
        state = await check_customer_node(state)
        
        # Step 2: Fetch context
        state = await fetch_context_node(state)
        
        # Step 3: Generate suggestion
        state = await generate_suggestion_node(state)
        
        # Return suggestion to frontend for approval
        return {
            "status": "success",
            "suggestion": state.get("next_action", ""),
            "needs_approval": True
        }
        
    except Exception as e:
        print(f"Error in next-action endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running next action agent: {str(e)}")

@app.post("/api/customers/{customer_id}/add-response")
async def add_customer_response(customer_id: str, request: NextActionRequest):
    """Add a customer response using the adder agent"""
    try:
        from agents.adder import create_customer_response_workflow, CustomerResponseState
        import asyncio
        
        if not request.interaction_type or not request.customer_response:
            raise HTTPException(status_code=400, detail="interaction_type and customer_response are required")
        
        # Create and run workflow
        workflow = create_customer_response_workflow()
        
        initial_state = CustomerResponseState(
            messages=[],
            customer_id=customer_id,
            interaction_type=request.interaction_type,
            customer_response=request.customer_response,
            current_summary="",
            last_agent_message="",
            updated_summary=""
        )
        
        final_state = await workflow.ainvoke(initial_state)
        
        return {
            "status": "success",
            "updated_summary": final_state.get("updated_summary", "")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding customer response: {str(e)}")

@app.post("/api/campaigns/create")
async def create_campaigns():
    """Trigger campaign creation using the campaign_creator agent"""
    try:
        from agents.campaign_creator import run_campaign_creation
        
        # Run the campaign creation workflow
        result = await run_campaign_creation()
        
        return {
            "status": "success",
            "message": "Campaigns created successfully",
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating campaigns: {str(e)}")

# Mount the frontend static files
frontend_path = pathlib.Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

@app.get("/")
async def read_root():
    return FileResponse(str(frontend_path / "index.html"))