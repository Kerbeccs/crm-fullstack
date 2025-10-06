import re
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

# --- Configuration ---
# Replace this with your actual MongoDB Atlas connection string
# It's best practice to load this from an environment variable!
# ATLAS_URI = os.getenv("MONGO_ATLAS_URI", "mongodb://localhost:27017/") 
ATLAS_URI = "mongodb+srv://chandramishra71:mani123@cluster0.skcdd1g.mongodb.net/" # <--- REPLACE THIS LINE!

DB_NAME = "crm_db"
COLLECTION_NAME = "customers"

# The header and data provided in your request, separated by tabs or multiple spaces
DATA_TEXT = """
Salon / Parlour\tContact Number\tAddress\tInstagram ID\tDescription\tGoogle Maps Link\tEmail
Diva Divine Hair Extensions\t+91 96503 77003\tShop 3, Nizamuddin East Market, New Delhi 110013\t@divadivinehair\tFull range of premium clip-in, permanent, tape-in, keratin & micro-ring extensions; custom wigs\thttps://www.google.com/maps/search/?api=1&query=Diva+Divine+Hair+Extensions+Nizamuddin+East+Delhicontact@divadivinehair.comThe\t
Planet Of Hair Cloning (PHC)\t+91 83758 45551/52\tT-136/5, ABC Bldg, Shivalik Main Rd, Malviya Nagar 110017\t@phctheplanetofhaircloning\tSpecialized non-surgical hair patch & replacement: micro-rings, bonding, loops, full toppers\thttps://g.page/phc-hair-wigs-shop?share\tplanetofhaircloning@gmail.com
Sunny Hairport\t98188 40719 /9818840734\tMalviya Nagar & Vasant Kunj 110070\t@sunnyhairport\tCelebrity stylist salon; advanced extensions, coloring & styling; runs academy in Malviya Nagar & VK\thttps://www.google.com/maps/search/?api=1&query=Sunny+Hairport+Malviya+Nagar+Delhisunnyhairport@gmail.comAdvance\t
Clinic\t+91 70429 37788\t1st Floor, C 23, opposite Bikaner Sweets, Central Market, Lajpat Nagar II, Lajpat Nagar, New Delhi, Delhi 110024\t@advanceclinicdelhi\tExperts in hair-patches, wigs, human-hair extensions & non-surgical replacement; laser hair removal\thttps://www.google.com/maps/search/?api=1&query=Advance+Clinic+Lajpat+Nagar+Delhiadvanceclinicinfo@gmail.comWelefull\t
Unisex Salon\t+91 83687 67939\t19-20 first floor, central Market, opposite Gurunanak Public school, cooperative Housing society, West Punjabi Bagh, Punjabi Bagh, Delhi, 110026\t@welefullsalonofficial\tUnisex salon specializing in personalized clip-in & tape-in installations\thttps://www.google.com/maps/place/Welefull+Unisex+Salon+%7C+The+Best+Unisex+Hair+Salon+In+Punjabi+Bagh,+Delhi/@28.6704458,77.1327209,17z/data=!3m1!4b1!4m6!3m5!1s0x390d0352e42a9ef5:0x2e5b01f0adf5a97!8m2!3d28.6704458!4d77.1327209!16s%2Fg%2F11kptpz3jr?entry=ttu&g_ep=EgoyMDI1MDcyMy4wIKXMDSoASAFQAw%3D%3Dwelefulsalonpbagh@gmail.comTrendz\t
Salon (Rajouri)\t9315535872/\n+91-8851047255/\n+11-47072172\tJ-13/61, Block J, Rajouri Garden Extension, Rajouri Garden, New Delhi, Delhi, 110027\thttps://www.instagram.com/meghajgoyal/\tClip-in & tape-in extensions with on-site color matching & maintenance advice\thttps://www.google.com/maps/search/?api=1&query=Trendz+Salon+Rajouri+Garden+Delhitrendzsalonweb@gmail.comAlisha's\t
Empire Salon -Permanent Hair Extensions in Rajouri garden |9899130018\t\tBasement, J-13/59 - Below 24x7, 1, Major Sudesh Kumar Marg, opposite Ajay Makan's House, Rajouri Garden, New Delhi, Delhi 110027\thttps://www.instagram.com/alishamehta000/\tMakeup💄Artist 🔹Hair 💇🏻🔹🔹Salon owner 🔹Alisha's Empire Salon 💇‍♀️\t\tcontact@alishaempiresalon.com
Hair Zone\t96543 36671 / 011-40106447\t📍F - 159 G F, Rajouri Garden ,Opp Gurukul Play school , Delhi (only Branch)\t@hairzone09\tUpscale salon: haircuts, color & extension installations\thttps://www.google.com/maps/search/?api=1&query=Hair+Zone+Rajouri+Garden-Visage\t
Salon\t+91 98993 32220\tPlot-133, Block R, New Roshanpura, (Ration card office) Najafgarh, ND-110043\t@visagesalon1\tPremium ladies’ outlet: clip-in, tape-in, keratin & bespoke styling\thttps://www.google.com/maps/search/?api=1&query=Visage+Salon+Tilak+Nagar-JS\t
Unisex Salon\t7982099463\tbasement, H-4A, near by anjali jewellersb, Krishna Market, Block H, Kalkaji, New Delhi, Delhi 110019\t@jsunisexsalon\tSalon & academy: micro-ring, tape-in & weft-ring extensions\thttps://www.google.com/maps/search/?api=1&query=JS+Unisex+Salon+Janakpuri-Impressive\t
Salon\t9718319111\tG89, Block 22, Tilak Nagar, New Delhi, Delhi, 110018\tN/A\tFeatures human-hair toppers, clip-ins, tape-ins & keratin bonds\thttps://www.google.com/maps/search/?api=1&query=Impressive+Salon+Mukhram+Garden-Mr.\t
& Mrs. Unisex Salon\t9518516584/9717868665\tPillar Number 674, G1 66, near, Mandir Marg, Uttam Nagar West, New Delhi, Delhi 110059\t@mr.mrs.unisex.salon\t- \t\t
Jacks N Glory\t99997 55969\t3/204 Subhash Nagar Near Aggarwal sweets Beri wala Bagh, Delhi, India, Delhi\thttps://www.facebook.com/mabyrd204/\tMakeup Studio, Academy, Hair Salon, Beauty Salon\thttps://www.google.com/maps/search/?api=1&query=Jacks+N+Glory+Subhash+Nagar+Delhi-Inspire\t
Hair Lounge\t919871664470\t194, Pkt-8, Sarvodaya Appartments, Sector 12 Dwarka, Dwarka, New Delhi, Delhi 110078, India\thttps://www.facebook.com/inspirehairlounge/ and https://www.instagram.com/inspirehairlounge/\tINSPIRE Hair Lounge is a one stop solution for beauty, skincare & hair\thttps://www.google.com/maps/place/Inspire+Hair+Lounge/@29.468971,76.7483577,9z/data=!4m10!1m2!2m1!1sStrands+Lounge+Sector+4+Dwarka+Delhi!3m6!1s0x390d1ac86f3eb0b1:0xce181e4c27fc696b!8m2!3d28.5966902!4d77.0360785!15sCiRTdHJhbmRzIExvdW5nZSBTZWN0b3IgNCBEd2Fya2EgRGVsaGlaJiIkc3RyYW5kcyBsb3VuZ2Ugc2VjdG9yIDQgZHdhcmthIGRlbGhpkgEMYmVhdXR5X3NhbG9umgEkQ2hkRFNVaE5NRzluUzBWSlEwRm5TVVJsTlZrMmFYUm5SUkFCqgF3CgovbS8wMjV4c2YxCggvbS8wOWYwNxABKhIiDnN0cmFuZHMgbG91bmdlKAAyHxABIhvy01Fj1cFAPHn8NSgfzWsoT2WJwO31KnMEyIAyKBACIiRzdHJhbmRzIGxvdW5nZSBzZWN0b3IgNCBkd2Fya2EgZGVsaGngAQD6AQQIABAY!16s%2Fg%2F11hb2_5w8k?entry=ttu&g_ep=EgoyMDI1MDcyMy4wIKXMDSoASAFQAw%3D%3D-Shivaay\t
Salon & Academy\t+91 78698 88214\t102 Site-1 Janta Flat, near by Shankar Garden, Vikaspuri, New Delhi, Delhi 110018\t@shivaay_the_hair_studio\tAcademy & salon: professional clip-in, tape-in & keratin extension training\thttps://www.google.com/maps/search/?api=1&query=Shivaay+Salon+Academy+Vikaspuri+Delhi-Girl-ish\t
Salon\t+91 85958 09909\tD BLOCK, D-530, opp. GURUDWARA SAHIB, Block D, Tagore Garden, Tagore Garden Extension, New Delhi, Delhi, 110027\t@extensionsbygirlish\tOffers nail, eyelash & personalized hair-extension fittings\thttps://www.google.com/maps/search/?api=1&query=Girlish+Salon+Tagore+Garden+Delhi-Marvelous\t
Unisex Salon & Makeup studio\t9899801388 | 8527284406 / 09899801388\tb-3/12, opposite Deep Market, Ashok Vihar II, Pocket B 3, Phase 2, Ashok Vihar, New Delhi, Delhi, 110052\t@marvelous_unisex_salon_academy\tKnown for bridal makeup & high-quality weft & clip-in extensions\thttps://www.google.com/maps/place/Marvelous+Unisex+Salon+%26+Makeup+Studio/@28.6935996,77.1734669,17z/data=!3m1!4b1!4m6!3m5!1s0x390d0215ef593c0f:0xc2576f1d55114c2b!8m2!3d28.6935996!4d77.1734669!16s%2Fg%2F1pty6hfnh?entry=ttu&g_ep=EgoyMDI1MDcyMy4wIKXMDSoASAFQAw%3D%3D-Hair\t
Extensions Castle\t+91 98993 26534\tGali 1, Indira Niketan, Shahdara 110094\t@hairextensionscastle\tFlagship offering full-set wigs & premium hair-extension services\thttps://www.google.com/maps/search/?api=1&query=Hair+Extensions+Castle+Shahdara+Delhi-Vandana\t
Hair Beauty salon\t7065354541/ 7065354542\tMangolpuri, Delhi\t@vandana.hair.beauty.salon\tKarol Bagh specialist & exporter: smoothing & custom human-hair extensions\thttps://www.google.com/maps/search/?api=1&query=Vandana+Hair+Extension+Karol+Bagh+Delhi-Sheen\t
Wigs salon and studio\t98183 76888 / 011 4003 672 / +918045799454 / +918047790037\t15A/29, W.E.A., Karol Bagh 110005\t@sheenwigs\t35+ years expertise in clip-on wigs, toppers & hair-fall solutions\thttps://www.google.com/maps/search/?api=1&query=Sheen+Wigs+Beauty+Salon+Karol+Bagh+Delhi-Intense\t
Makeovers Studio\t+91 98915 59997\tD-2 Patparganj Rd, Shakarpur 110092\t@intensemakeovers\tSpecializes in 100% human-hair extensions & styling services\thttps://www.google.com/maps/search/?api=1&query=Intense+Makeovers+Studio+Shakarpur+Delhi-Lynx\t
Hair Skin Clinic\t7428475559\t1st Floor at CSC, B-4, Lawrence Road, Keshav Puram, Delhi, India 110035\t@lynxhairskinclinic\tOffers micro-ring, keratin, weft, tape-in & clip-in extensions\thttps://www.google.com/maps/search/?api=1&query=Lynx+Hair+Skin+Clinic+Delhi-Glamzon\t
Hair Extension salon\t+91 87508 27075\tG-19/7a 1st floor Rajouri Garden New Delhi\t@glamzon_hair_salon\tMobile & Kondli studio: hair extensions, nail art & eyelashes\thttps://www.google.com/maps/search/?api=1&query=Glamzon+Hair+Extension+Delhi-Royal\t
Look makeover's\t9999027753 /9911503735\tC-62, G-78 (Block C), Arya Samaj Road\nUttam Nagar, New Delhi – 110059, I\t@makeupymouli\tOffers customized hair-extension installations & styling\thttps://www.google.com/maps/search/?api=1&query=Royal+Looks+Unisex+Salon+Uttam+Nagar+Delhi-Beauty\t
Experts Salon by Ritesh Verma\t9911118129\n8882186835\tArya Samaj Road Market, Uttam Nagar, New Delhi\t@ritesh_verma_5841\tWomen-owned academy run by a professional makeup artist; offers hair-smoothening with extensions and bespoke extension installations\thttps://www.google.com/maps/search/?api=1&query=Beauty+Experts+Salon+Uttam+Nagar-Angel\t
The Luxury Salon (Arya Samaj)\t8920061453\n9212927333\tD174, Bal Udhyan Road, Arya Samaj Rd, opposite Kings Momos’s, near Scoops, Uttam Nagar West, Delhi, 110059\t@angeltheluxurysalon\tWomen-owned luxury salon & academy with London/Dubai-certified staff; offers human-hair extensions by expert technicians\thttps://www.google.com/maps/search/?api=1&query=Angel+The+Luxury+Salon+Arya+Samaj+Uttam+Nagar-\t
"""

def parse_data(data_text: str) -> list[dict]:
    """Parses the raw text data into a list of dictionaries."""
    
    # 1. Split the text into lines and remove empty lines
    lines = [line.strip() for line in data_text.strip().split('\n') if line.strip()]
    
    if not lines:
        return []

  
    header_line = lines[0].replace('/', '').replace('|', '').strip()

    headers = [h.strip().lower().replace(' ', '_').replace('-', '_') for h in re.split(r'\t{1,}', header_line)]

    records = []
    
    # Iterate through the data lines, starting from the second line (index 1)
    for line in lines[1:]:

        values = re.split(r'\t{1,}', line)
        
        # Fill missing trailing fields with an empty string
        values.extend([''] * (len(headers) - len(values)))
        values = values[:len(headers)] # Truncate if there are extra fields

        record = {}
        for i, header in enumerate(headers):
            # Clean up the value by replacing newlines/tabs with a space and stripping whitespace
            cleaned_value = values[i].replace('\n', ' ').strip()
            if header == 'instagram_id':
                record['instagram_id'] = cleaned_value.replace('https://www.instagram.com/', '').replace('/', '')
            elif header == 'name':
                record['name'] = cleaned_value
            elif header == 'google_maps_link':
                record['google_maps_link'] = cleaned_value
            else:
                record[header] = cleaned_value
        
        if 'name' in record:
            record['name'] = record.pop('name')

        records.append(record)

    return records


async def populate_mongodb(data: list[dict]):
    """Connects to MongoDB and inserts the data asynchronously."""
    print("Attempting to connect to MongoDB...")
    
    try:
        # Client initialization as requested by the user
        client = AsyncIOMotorClient(ATLAS_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # 1. Clean the collection (Optional: uncomment if you want to clear old data)
        # await collection.delete_many({})
        # print(f"Cleared existing documents from '{COLLECTION_NAME}' collection.")

        # 2. Insert the new documents
        if data:
            result = await collection.insert_many(data)
            print(f"✅ Successfully inserted {len(result.inserted_ids)} new documents into '{COLLECTION_NAME}'.")
        else:
            print("❌ No data to insert.")
        
    except Exception as e:
        print(f"🚨 An error occurred during database operation: {e}")
        # A common error is network connectivity or incorrect URI/authentication

    finally:
        # Close the connection
        if 'client' in locals() and client:
            client.close()
            print("MongoDB connection closed.")


def main():
    """Main function to run the data parsing and population."""
    print("--- Starting Data Parsing ---")
    
    # 1. Parse the text data
    structured_data = parse_data(DATA_TEXT)
    
    if structured_data:
        print(f"Successfully parsed {len(structured_data)} records.")
        print("\n--- Starting MongoDB Population ---")
        # 2. Run the asynchronous MongoDB insertion
        asyncio.run(populate_mongodb(structured_data))
    else:
        print("Parsing failed or resulted in zero records.")

if __name__ == "__main__":
    main()