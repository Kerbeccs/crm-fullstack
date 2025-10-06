# HI THERE READER THIS IS A WALK THROUGHT OF MY AGENTIC AI CRM FOR THE EMAIL PART OF CAPREA CAPITAL
# I SAY YOUR SAAS WEBSITE AND FOUND IT AS MISSING HENCE CREATED A TOOL THAT WILL HELP ONES SALES PERSONAL TO HANDEL LOTS OF DATA

# IF YOU WANT YOU CAN RUN AGENTS SEPERATLY AND SEE THE OUTPUT THEY WERE INITAILLY WRITTEN BY ME TO WORK SOLELY

An intelligent Customer Relationship Management system powered by **Agentic AI** (LangGraph + Gemini(as my LLM)) and **FastAPI**. This system automates customer segmentation, campaign creation, and provides AI-driven next-action suggestions for sales teams.
##  Features

### 1. **Customer Data Management**
- Comprehensive customer data ingestion with multiple fields
- Store customer information including:
  - Business details (name, description, size)
  - Contact information (phone, email, Instagram)
  - Location data (city, address, Google Maps link)
- Real-time statistics dashboard
These feilds will help the LLM to create seperate campaigns 
### 2. **AI-Powered Campaign Creation**
- Automated customer segmentation using Gemini AI
- Pattern recognition based on:
  - Location (city)
  - Business size (Small/Medium/Large)
  - Industry type
  - Contact availability
- Intelligent campaign-to-customer mapping

### 3. **Intelligent Next-Action Suggestions**
- AI agent analyzes customer interaction history
- Generates personalized action recommendations:
  - Email templates
  - Call scripts
  - Meeting agendas
  - Lead qualification decisions
- Context-aware suggestions based on conversation history
THE PROMPT IN THIS PART CAN BE CHANGED ACCORDING TO YOU NEED AND SEE HOW THINGS WORK HERE 
SEE THE LLM WILL WORK ACCORDING TO YOUR REPLIES AND CANRECTIFY ITS SELD FOR OUTREACH
### 4. **Interaction Tracking**
- Complete conversation history for each customer
- Track interactions by type (Call, Email, Meeting)
- Automatic conversation summarization
- Sender identification (Agent vs Customer)
AND DONT WORRY ABOUT YOUR TOKEN CONVOSUMMARY COLLECTION I HAVE MADE IS FOR THAT PURPOSE ONLYYYY


## 📁 Project Structure

```
ml/
├── backend/
│   ├── main.py                 # FastAPI application with all endpoints
│   ├── agents/
│   │   ├── campaign_creator.py # AI agent for campaign creation
│   │   ├── nextmove.py        # AI agent for next action suggestions
│   │   └── adder.py           # AI agent for customer response processing
│   ├─
│   │ 
│   ├── populate.py            # Database population script
│   └── req.txt               # Python dependencies
│
└── frontend/
    ├── index.html            # Home page - Customer data ingestion
    ├── campaigns.html        # Campaign management & customer details
    └── styles.css           # Modern, responsive styles
```

## 🗄️ Database Collections

The system uses **MongoDB Atlas** with the following collections:

### 1. **customers**
Stores customer data:
this will have the data ingestion , we will use rabbitq or kafka for better ingestion rigth now i just used pydantic for verfication
{
  _id: ObjectId,
  name: String,
  contact_number: String,
  address: String,
  instagram_id: String,
  description: String,
  google_maps_link: String,
  email: String,
  city: String,
  size: String,  // Small/Medium/Large
  created_at: DateTime
}
```

### 2. **campaigns**
Stores campaign definitions:
now when you click on create campign the the whole content is parsed and out put is givena dn campaigns are created on that basis only 
{
  _id: ObjectId,
  campaign_id: Integer,
  parameter_description: String,
  created_at: DateTime
}
```

### 3. **mapcamp**
Maps customers to campaigns:
whoever suits which ever campign is placed in that collection 
{
  _id: ObjectId,
  customer_obj_id: String,  // Customer's _id
  campaign_id: Integer,
  mapped_at: DateTime
}
```

### 4. **interactions**
Stores interaction history:
this is the collection to be used by used and the som latest interactions will be used by my ai also
{
  _id: ObjectId,  // Same as customer _id
  interactions: [
    {
      sender: String,        // "me" or "customer"
      type: String,          // "call", "email", "meeting"
      date: DateTime,
      summary: String
    }
  ]
}
```

### 5. **convosummary**
this is the part used by LLM to save token of parsing wholeinteraction history i am only using currrent summary and only one or 2 past interaction forn db
{
  _id: ObjectId,  // Same as customer _id
  customer_id: ObjectId,
  summary: String,
  last_updated: DateTime
}
```

## 🔧 Setup Instructions

### Prerequisites
- Python 3.8+
- MongoDB Atlas account
- Gemini API key

### Backend Setup

1. **Install Dependencies**
```bash
cd backend
pip install -r req.txt
```

2. **Configure Environment Variables**
Create a `.env` file in the `backend` directory:
```env
MONGODB_URI=your_mongodb_atlas_connection_string
GEMINI_API_KEY=your_gemini_api_key
```

3. **Run the FastAPI Server**
```bash
cd backend
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Simply open the frontend files in a web browser or use a local server:
```bash
# Using Python's built-in server
cd frontend
python -m http.server 3000
```

2. Access the application:
   - Home Page: `http://localhost:3000/index.html`
   - Campaigns: `http://localhost:3000/campaigns.html`


## 📝 License

This project is proprietary and confidential.Please do not sahre the current database thate i have used here

## 🤝 Contributing

This is a private project. For any questions or issues, please contact the development team.

---

**Built with ❤️ using FastAPI, LangGraph, Gemini AI, and MongoDB**

