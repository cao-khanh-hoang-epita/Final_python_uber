from pymongo.mongo_client import MongoClient
client = MongoClient("mongodb://localhost:27017")
db = client['jobs']
collection = db['job_details']

jobs_data = [
    {
        "name": "Waiter",
        "description": "Serve customers in a restaurant, take orders, and ensure a pleasant dining experience.",
        "wage": 10.00  # Wage per hour
    },
    {
        "name": "Barista",
        "description": "Prepare and serve coffee and other beverages to customers at a cafe.",
        "wage": 12.50  # Wage per hour
    },
    {
        "name": "Chef",
        "description": "Create and prepare dishes in a restaurant's kitchen, manage food quality, and lead the kitchen team.",
        "wage": 20.00  # Wage per hour
    },
    {
        "name": "Outdoor Adventure Guide",
        "description": "Lead outdoor activities such as hiking, rafting, and camping for adventure-seeking participants.",
        "wage": 15.00  # Wage per hour
    },
    {
        "name": "Data Analyst",
        "description": "Analyze and interpret data to help organizations make informed decisions.",
        "wage": 25.00  # Wage per hour
    },
    {
        "name": "Lifeguard",
        "description": "Ensure the safety of swimmers at a pool or beach by monitoring water conditions and assisting in emergencies.",
        "wage": 12.00  # Wage per hour
    },
    {
        "name": "Customer Service Representative",
        "description": "Assist customers with inquiries, resolve issues, and provide information about products or services.",
        "wage": 14.00  # Wage per hour
    },
    {
        "name": "Software Developer",
        "description": "Create, maintain, and improve software applications and systems.",
        "wage": 30.00  # Wage per hour
    },
    {
        "name": "Event Planner",
        "description": "Organize and coordinate events, such as weddings, conferences, and parties.",
        "wage": 18.00  # Wage per hour
    },
    {
        "name": "Graphic Designer",
        "description": "Create visual content, such as logos, graphics, and layouts, for various projects.",
        "wage": 20.00  # Wage per hour
    }
]


for job in jobs_data:
            # Check if the product already exists in the collection
            if collection.count_documents({"name": job["name"]}) == 0:
                # If it doesn't exist, insert it
                collection.insert_one(job)

# Close the MongoDB client
client.close()