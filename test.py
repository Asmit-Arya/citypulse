# 1. Storing information about a business using a dictionary
business = {
    "name": "City Care Dental",
    "category": "Healthcare",
    "queue_count": 4,
    "wait_per_person": 15  # in minutes
}

# 2. A function to calculate wait time
def get_estimated_wait(queue, time_each):
    return queue * time_each

# 3. Running the calculation
total_wait = get_estimated_wait(business["queue_count"], business["wait_per_person"])

# 4. Displaying the result
print("Business Name:", business["name"])
print("People currently in line:", business["queue_count"])
print("Estimated waiting time:", total_wait, "minutes")