import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

def create_assignment():
    doc = Document()

    # --- Page Setup (A4, 0.5-inch margins for uniform fit) ---
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.55)
        section.right_margin = Inches(0.55)

    # Style defaults
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(9.5)
    font.color.rgb = RGBColor(0, 0, 0)

    def add_p(text, bold_prefix="", space_after=2, italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            run_b = p.add_run(bold_prefix)
            run_b.bold = True
            run_b.font.color.rgb = RGBColor(0, 0, 0)
        if text:
            run_t = p.add_run(text)
            run_t.italic = italic
            run_t.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_sec_title(title):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(title)
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def format_cell(cell, bold_label, body_text):
        cell.paragraphs[0].text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.12
        if bold_label:
            rb = p.add_run(bold_label)
            rb.bold = True
            rb.font.size = Pt(8.5)
        if body_text:
            rt = p.add_run(body_text)
            rt.font.size = Pt(8.5)

    # ==========================================================
    # PAGE 1: YOUR IDEAL CUSTOMERS (PART 1)
    # ==========================================================
    # Header Info Table
    header_tbl = doc.add_table(rows=3, cols=2)
    header_tbl.style = 'Table Grid'
    header_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    format_cell(header_tbl.rows[0].cells[0], "Course: ", "IT Workshop — Entrepreneurship Module")
    format_cell(header_tbl.rows[0].cells[1], "Submission Date: ", "15th Oct 2026")
    format_cell(header_tbl.rows[1].cells[0], "Instructor: ", "Dr. Amit Agrawal")
    format_cell(header_tbl.rows[1].cells[1], "Startup Name: ", "CityPulse")
    
    c_merge = header_tbl.rows[2].cells[0]
    c_merge.merge(header_tbl.rows[2].cells[1])
    format_cell(c_merge, "Team Members: ", 
                "1. Asmit Arya (Roll: [Roll No], CSE) | 2. [Name] (Roll: [Roll No], CSE) | "
                "3. [Name] (Roll: [Roll No], CSE) | 4. [Name] (Roll: [Roll No], CSE)")

    add_sec_title("PAGE 1: YOUR IDEAL CUSTOMERS")

    add_p("College students living in hostels bound by lecture hours, mandatory labs, and campus curfews; "
          "hostellers and local residents who rely on neighborhood shops (clinics, barbers, phone repair) for everyday errands; "
          "digital natives who use on-demand apps daily but still face blind offline waiting rooms; "
          "busy individuals with narrow 1-hour free windows to run personal tasks.",
          bold_prefix="1. What groups of people do you, or did you, belong to? ")

    add_p("Small, neighborhood business owners (local doctors, barbers, repair specialists) losing walk-in customers to "
          "lobby chaos, alongside students and working folks who cannot afford to waste 1 to 2 hours sitting in waiting rooms.",
          bold_prefix="2. Who are you passionate about helping? ")

    add_p("• Potential Segment #1: Local Clinic & OPD Doctors (Small 1-to-2 doctor setups where lines pile up)\n"
          "• Potential Segment #2: College Students & Busy Locals (People trying to run errands on tight schedules)\n"
          "• Potential Segment #3: Neighborhood Salons & Repair Shops (Walk-in counters hit by unpredictable evening crowds)",
          bold_prefix="3. Pick the 3 groups you're most excited to help:\n")

    p1_tbl = doc.add_table(rows=3, cols=3)
    p1_tbl.style = 'Table Grid'
    p1_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = [
        "Potential Segment #1:\nLocal Clinic & OPD Doctors",
        "Potential Segment #2:\nCollege Students & Busy Locals",
        "Potential Segment #3:\nSalons & Repair Shops"
    ]
    for i, h in enumerate(headers):
        format_cell(p1_tbl.rows[0].cells[i], h, "")
        p1_tbl.rows[0].cells[i].paragraphs[0].runs[0].bold = True

    p1_problems = [
        "• Severe lobby congestion during evening peak OPD hours.\n• Patients leaving without consultation ('walk-aways') due to crowded lines.\n• Receptionists repeatedly interrupted by 'how much longer?' inquiries.",
        "• Having zero visibility into live line lengths before traveling to the shop.\n• Losing 45 to 90 minutes sitting idle on waiting benches.\n• Missed study blocks or delayed schedules from unpredictable service delays.",
        "• Severe demand imbalance: empty chairs during the day, chaotic rushes in the evening.\n• Direct revenue lost when prospective walk-ins see full couches and walk away.\n• Commercial booking apps are too rigid and expensive for casual walk-ins."
    ]
    for i, prob in enumerate(p1_problems):
        format_cell(p1_tbl.rows[1].cells[i], f"{4+i}. Biggest Problems:\n", prob)

    p1_hardest = [
        "The 6:00 PM – 8:30 PM OPD rush. Over a dozen patients crowd a tiny reception area, disputes emerge over turn sequences, and consultations get rushed.",
        "Attempting to finish a 20-minute errand during an open 1-hour class window, only to arrive and find an unexpected 90-minute queue ahead.",
        "Watching high-paying customers peek inside the front door, see all seats full, turn around, and walk straight to a competitor."
    ]
    for i, hard in enumerate(p1_hardest):
        format_cell(p1_tbl.rows[2].cells[i], "Hardest Part of their Day:\n", hard)

    doc.add_page_break()

    # ==========================================================
    # PAGE 2: CUSTOMER EMOTIONS & VALIDATION
    # ==========================================================
    add_sec_title("PAGE 2: CUSTOMER EMOTIONS & VALIDATION")

    p2_tbl = doc.add_table(rows=5, cols=4)
    p2_tbl.style = 'Table Grid'
    p2_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    cols_p2 = [
        "7. Customer Emotions",
        "Segment #1: Clinic Doctors",
        "Segment #2: Students & Patrons",
        "Segment #3: Salons & Repair"
    ]
    for i, col in enumerate(cols_p2):
        format_cell(p2_tbl.rows[0].cells[i], col, "")
        p2_tbl.rows[0].cells[i].paragraphs[0].runs[0].bold = True

    emotions_data = [
        ("What is this segment afraid of?",
         "Patients getting hostile over long delays, leaving negative reviews, or switching to corporate hospital OPDs.",
         "Missing assignment deadlines, exam study blocks, or scheduled classes due to being stuck in an unexpected queue.",
         "Regular, loyal customers giving up on the wait and permanently switching to salon chains in malls."),
        ("What frustrates this segment?",
         "Being interrupted repeatedly about wait times while trying to focus on diagnosing patients.",
         "Showing up in person only to hear 'just 10 minutes,' and still sitting on the bench 50 minutes later.",
         "Having chairs sit empty for hours, followed by turning paying customers away during the evening rush."),
        ("What overwhelms this segment?",
         "Managing messy paper registers, noisy waiting rooms, and impatient patients all at the same time.",
         "Trying to balance intense coursework when every single chore outside campus turns into an unpredictable time sink.",
         "Complicated enterprise booking tools that charge high monthly fees and require desktop setups."),
        ("What does this segment love?",
         "A calm waiting room where patients arrive right on time for their turn, allowing focus on care quality.",
         "Knowing the line beforehand so they can leave their room at the right time and get served right away.",
         "A predictable flow of customers throughout the day, steady chair utilization, and happy recurring clients.")
    ]

    for row_idx, data in enumerate(emotions_data, start=1):
        format_cell(p2_tbl.rows[row_idx].cells[0], data[0], "")
        p2_tbl.rows[row_idx].cells[0].paragraphs[0].runs[0].bold = True
        for col_idx in range(1, 4):
            format_cell(p2_tbl.rows[row_idx].cells[col_idx], "", data[col_idx])

    add_p("[✓] Segment #1 Fear: The constant fear of losing walk-in patients and revenue simply because the lobby looks too chaotic.\n"
          "[✓] Segment #2 Frustration: The daily frustration of walking in blind and losing 1 to 2 valuable hours to stagnant queues.",
          bold_prefix="8. Circle the 2 that are the most intense for your customers:\n")

    add_p("[☑] Potential Segment #1: Independent Local Clinic & OPD Operators\n"
          "[☑] Potential Segment #2: Time-Constrained Students & Urban Patrons\n"
          "[☐] Potential Segment #3: Neighborhood Salons & Repair Shops",
          bold_prefix="9. Put a check next to the 2 you are most excited about:\n")

    add_p("• \"My ideal customers are independent neighborhood clinic and OPD doctors. I want to help them stop waiting-room chaos and keep their walk-in patients by letting them show live queue updates and issue simple virtual tokens.\"\n"
          "• \"My ideal customers are busy college students and working professionals. I want to help them stop wasting 1 to 2 hours in waiting rooms by letting them check line length and join the queue from their phone before leaving home.\"\n"
          "• \"My ideal customers are local walk-in business owners. I want to help them spread out customer rushes and prevent walk-outs without forcing anyone to use rigid appointment apps or buy expensive hardware.\"",
          bold_prefix="10. Positioning Statements (Pick 3):\n")

    doc.add_page_break()

    # ==========================================================
    # PAGE 3: THE PROBLEM STATEMENT CANVAS
    # ==========================================================
    add_sec_title("PAGE 3: THE PROBLEM STATEMENT CANVAS")

    meta_tbl = doc.add_table(rows=1, cols=3)
    meta_tbl.style = 'Table Grid'
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    format_cell(meta_tbl.rows[0].cells[0], "STARTUP GROUPNAME: ", "CityPulse")
    format_cell(meta_tbl.rows[0].cells[1], "DATE: ", "15th Oct 2026")
    format_cell(meta_tbl.rows[0].cells[2], "VERSION: ", "1.0")

    canvas_tbl = doc.add_table(rows=3, cols=3)
    canvas_tbl.style = 'Table Grid'
    canvas_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Row 1
    format_cell(canvas_tbl.rows[0].cells[0], "CONTEXT (When does it occur?):\n",
                "During daily peak hours—especially weekday evenings (5:30 PM to 8:30 PM) and weekend mornings (10:00 AM to 1:00 PM)—when everyone shows up at the exact same time.")
    format_cell(canvas_tbl.rows[0].cells[1], "PROBLEM (Root Cause):\n",
                "Zero communication between offline service desks and customers. Shops have no easy way to show how busy they are, and customers cannot check the line without walking through the door.")
    format_cell(canvas_tbl.rows[0].cells[2], "ALTERNATIVES (Current Fixes):\n",
                "1. Showing up and waiting on benches.\n2. Calling the shop (rarely answered).\n3. Checking Google Maps 'Popular Times'.\n4. Giving up and walking away.")

    # Row 2
    format_cell(canvas_tbl.rows[1].cells[0], "CUSTOMERS (Who has it most?):\n",
                "Local solo doctors, clinic receptionists, and salon operators (Business Side); college students and working people on tight routines (Consumer Side).")
    format_cell(canvas_tbl.rows[1].cells[1], "EMOTIONAL IMPACT:\n",
                "Customers: Anxious about lost time, annoyed by false 'just 10 minutes' promises.\nOwners: Stressed by noisy lobbies and frustrated watching walk-in customers leave.")
    format_cell(canvas_tbl.rows[1].cells[2], "ALTERNATIVE SHORTCOMINGS:\n",
                "• In-person waiting spreads illness in clinics.\n• Calls interrupt active service.\n• Google Maps shows outdated averages.\n• Booking apps (e.g. Practo) force rigid slots and charge high fees.")

    # Row 3 (Merged across 3 columns)
    r3_cell = canvas_tbl.rows[2].cells[0]
    r3_cell.merge(canvas_tbl.rows[2].cells[1]).merge(canvas_tbl.rows[2].cells[2])
    format_cell(r3_cell, "QUANTIFIABLE IMPACT (Measurable Units):\n",
                "• 45 to 75 minutes of wasted idle waiting time per customer per visit.\n"
                "• 15% to 25% of potential walk-in customers lost by shops during peak hours due to overcrowded rooms.\n"
                "• 15 to 20 interrupted phone calls handled by the owner or receptionist in a single 3-hour evening shift.")

    add_p("Summary: The canvas confirms that offline queues hurt both shop revenue and student productivity. "
          "CityPulse bridges this operational gap using lightweight web tokens without requiring app downloads or expensive merchant hardware.",
          bold_prefix="\nCanvas Key Synthesis: ", space_after=2, italic=True)

    doc.add_page_break()

    # ==========================================================
    # PAGE 4: ACTIVITY — PILOT YOUR PURPOSE
    # ==========================================================
    add_sec_title("PAGE 4: ACTIVITY — PILOT YOUR PURPOSE")

    add_p("To stop people from wasting their day in crowded waiting rooms by creating a dead-simple, "
          "real-time link between local walk-in businesses and neighborhood customers: \"Know before you go.\"",
          bold_prefix="1. Venture Purpose & Ethos:\n")

    add_p("Every single day, people waste hours sitting on plastic chairs waiting for their turn, while independent "
          "business owners lose paying customers because their shops look overcrowded. Corporate chains have their own booking "
          "apps, but local neighborhood businesses are left behind. We believe getting a haircut or seeing a doctor should be "
          "predictable and hassle-free, without forcing anyone into rigid time slots or complex setups.",
          bold_prefix="2. Core Problem Conviction:\n")

    add_p("• We Live This Problem: As hostel students without personal transport, surprise 90-minute waits at local clinics or barbers throw off our academic schedules and hostel timing.\n"
          "• Skills to Build It: As CSE students, we have the web-development background (Python, Flask, SQLite, Bootstrap) to build a fast, lightweight platform that runs in any mobile browser without forcing app downloads or merchant hardware costs.\n"
          "• Proximity to Market: Our campus is right beside busy student and residential hubs with dozens of clinics, salons, and repair counters within 3 km, enabling immediate real-world testing.",
          bold_prefix="3. Founder-Problem Fit (Why Our Team?):\n")

    add_p("• Keep It Dead Simple: A shop owner must update their line in five seconds with one click. A customer must see the wait time without downloading an app or making an account.\n"
          "• Realistic Times, Not Guesses: Wait-time predictions must dynamically adjust using moving averages based on real service times.\n"
          "• Support Local Businesses: Help neighborhood businesses keep their walk-in customers instead of losing them to large chains.",
          bold_prefix="4. Guiding Operational Principles:\n")

    p4_tbl = doc.add_table(rows=4, cols=2)
    p4_tbl.style = 'Table Grid'
    p4_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    pilot_data = [
        ("Target Establishments", "3 local partner businesses: 1 neighborhood clinic/OPD, 1 busy barbershop/salon, and 1 local campus repair counter."),
        ("Wait Time Reduction", "Cut down physical lobby waiting time from 50 minutes to under 15 minutes for users using the virtual queue."),
        ("User Adoption", "Log at least 100 completed virtual queue check-ins over a 2-week trial period."),
        ("Revenue Retention", "Reduce peak-hour customer walk-away rates for pilot shops from ~20% down to under 5%.")
    ]
    for i, (metric, target) in enumerate(pilot_data):
        format_cell(p4_tbl.rows[i].cells[0], metric, "")
        p4_tbl.rows[i].cells[0].paragraphs[0].runs[0].bold = True
        format_cell(p4_tbl.rows[i].cells[1], "", target)

    # Save output
    output_filename = "CityPulse_Entrepreneurship_Assignment.docx"
    doc.save(output_filename)
    print(f"Successfully created: {output_filename}")

if __name__ == '__main__':
    create_assignment()